"""Web 面板 API 路由"""

import asyncio
import datetime
import json
import logging

from aiohttp import web

import web.auth as auth
import web.ws as panel_ws

log = logging.getLogger('ElainaBot.web.api')

_bot_manager = None
_base_dir = ''


def get_routes() -> list:
    """返回所有 API 路由"""
    _ = auth.require_auth
    return [
        # 鉴权
        web.post('/api/auth/login', handle_login),
        web.get('/api/auth/check', _(handle_auth_check)),
        # 系统信息
        web.get('/api/system/info', _(handle_system_info)),
        # 日志
        web.get('/api/logs/recent', _(handle_recent_logs)),
        web.get('/api/logs/{log_type}', _(handle_get_logs)),
        # 插件
        web.get('/api/plugins/list', _(handle_list_plugins)),
        web.post('/api/plugins/reload', _(handle_reload_plugin)),
        # 模块
        web.get('/api/modules/list', _(handle_list_modules)),
        web.post('/api/modules/toggle', _(handle_toggle_module)),
        # 配置
        web.get('/api/config', _(handle_get_config)),
        web.post('/api/config/save', _(handle_save_config)),
        # 消息
        web.get('/api/messages/recent', _(handle_recent_messages)),
        # Bot 状态
        web.get('/api/bot/status', _(handle_bot_status)),
        # WebSocket
        web.get('/ws/panel', panel_ws.handle_ws),
    ]


def set_context(bot_manager, base_dir: str):
    global _bot_manager, _base_dir
    _bot_manager = bot_manager
    _base_dir = base_dir


# ======================== 鉴权 ========================

async def handle_login(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': '请求格式错误'}, status=400)

    password = body.get('password', '')
    from core.base.config import cfg
    admin_pwd = cfg.get('settings', 'web.admin_password', '')

    if not admin_pwd:
        return web.json_response({'success': False, 'error': '未配置密码'}, status=500)

    if not auth.verify_password(password, admin_pwd):
        return web.json_response({'success': False, 'error': '密码错误'}, status=401)

    # 首次登录自动 hash
    if not auth.is_hashed(admin_pwd):
        cfg.set_value('settings', 'web.admin_password', auth.hash_password(password))

    token = auth.create_session(request)
    return web.json_response({'success': True, 'token': token})


async def handle_auth_check(request: web.Request):
    return web.json_response({'success': True})


# ======================== 系统信息 ========================

async def handle_system_info(request: web.Request):
    import platform
    import psutil

    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()

    from core.base.config import cfg
    fw_name = cfg.get('settings', 'web.framework_name', 'ElainaBot')

    bots = {}
    if _bot_manager and _bot_manager.adapter:
        bots = {k: v.get('type', 'unknown') for k, v in _bot_manager.adapter.bots.items()}

    return web.json_response({
        'success': True,
        'data': {
            'framework_name': fw_name,
            'platform': platform.system(),
            'python_version': platform.python_version(),
            'cpu_percent': cpu_percent,
            'memory_percent': mem.percent,
            'memory_used': mem.used,
            'memory_total': mem.total,
            'bots': bots,
            'bot_count': len(bots),
            'plugin_count': len(_bot_manager.plugin_manager._plugins) if _bot_manager and _bot_manager.plugin_manager else 0,
            'module_count': len(_bot_manager.module_manager._modules) if _bot_manager and _bot_manager.module_manager else 0,
        }
    })


# ======================== 日志 ========================

async def handle_recent_logs(request: web.Request):
    if not _bot_manager or not _bot_manager.log_service:
        return web.json_response({'message': [], 'framework': [], 'error': []})

    ls = _bot_manager.log_service
    messages = ls.query('message', 'SELECT * FROM log ORDER BY id DESC LIMIT 50')
    framework = ls.query('framework', 'SELECT * FROM log ORDER BY id DESC LIMIT 50')

    return web.json_response({
        'message': messages,
        'framework': framework,
    })


async def handle_get_logs(request: web.Request):
    log_type = request.match_info.get('log_type', 'message')
    if not _bot_manager or not _bot_manager.log_service:
        return web.json_response({'success': True, 'data': []})

    ls = _bot_manager.log_service
    data = ls.query(log_type, 'SELECT * FROM log ORDER BY id DESC LIMIT 100')
    return web.json_response({'success': True, 'data': data})


# ======================== 插件 ========================

async def handle_list_plugins(request: web.Request):
    if not _bot_manager or not _bot_manager.plugin_manager:
        return web.json_response({'success': True, 'data': []})
    plugins = _bot_manager.plugin_manager.list_plugins()
    return web.json_response({'success': True, 'data': plugins})


async def handle_reload_plugin(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': '请求格式错误'}, status=400)

    name = body.get('name', '')
    if not name:
        return web.json_response({'success': False, 'error': '缺少插件名'}, status=400)

    if not _bot_manager or not _bot_manager.plugin_manager:
        return web.json_response({'success': False, 'error': '插件管理器未就绪'})

    result = await _bot_manager.plugin_manager.reload_plugin(name)
    return web.json_response({'success': result})


# ======================== 模块 ========================

async def handle_list_modules(request: web.Request):
    if not _bot_manager or not _bot_manager.module_manager:
        return web.json_response({'success': True, 'data': []})
    modules = _bot_manager.module_manager.list_modules()
    return web.json_response({'success': True, 'data': modules})


async def handle_toggle_module(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': '请求格式错误'}, status=400)

    name = body.get('name', '')
    enabled = body.get('enabled', True)

    if not name:
        return web.json_response({'success': False, 'error': '缺少模块名'}, status=400)

    if not _bot_manager or not _bot_manager.module_manager:
        return web.json_response({'success': False, 'error': '模块管理器未就绪'})

    mm = _bot_manager.module_manager
    if enabled:
        result = await mm.enable(name)
    else:
        result = await mm.disable(name)

    return web.json_response({'success': result})


# ======================== 配置 ========================

async def handle_get_config(request: web.Request):
    from core.base.config import cfg
    data = cfg.get_raw('settings')
    return web.json_response({'success': True, 'data': data})


async def handle_save_config(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': '请求格式错误'}, status=400)

    from core.base.config import cfg
    cfg.set_raw('settings', body.get('data', {}))
    return web.json_response({'success': True})


# ======================== 消息 ========================

async def handle_recent_messages(request: web.Request):
    if not _bot_manager or not _bot_manager.log_service:
        return web.json_response({'success': True, 'data': []})

    ls = _bot_manager.log_service
    data = ls.query('message', 'SELECT * FROM log ORDER BY id DESC LIMIT 50')
    return web.json_response({'success': True, 'data': data})


# ======================== Bot 状态 ========================

async def handle_bot_status(request: web.Request):
    if not _bot_manager or not _bot_manager.adapter:
        return web.json_response({'success': True, 'data': {'connected': False, 'bots': {}}})

    adapter = _bot_manager.adapter
    return web.json_response({
        'success': True,
        'data': {
            'connected': len(adapter.bots) > 0,
            'bots': {k: v.get('type', 'unknown') for k, v in adapter.bots.items()},
        }
    })
