"""Web 面板 API 路由"""

import logging

from aiohttp import web

import web.auth as auth
import web.ws as panel_ws
from web.tools import bots, config_handler, database, logs, messages, module_mgr, plugin_mgr, statistics, system

log = logging.getLogger('ElainaBot.web.api')

_bot_manager = None
_base_dir = ''


def get_routes() -> list:
    """返回所有 API 路由"""
    _ = auth.require_auth
    return [
        # Auth
        web.post('/api/auth/login', handle_login),
        web.get('/api/auth/check', _(handle_auth_check)),
        # System
        web.get('/api/system/info', _(system.handle_system_info)),
        # Bots
        web.get('/api/bots', _(bots.handle_list_bots)),
        web.get('/api/bot/status', _(bots.handle_bot_status)),
        # Logs
        web.get('/api/logs/recent', _(logs.handle_recent_logs)),
        web.get('/api/logs/login', _(logs.handle_login_logs)),
        web.get('/api/logs/{log_type}', _(logs.handle_get_logs)),
        # Plugins
        web.get('/api/plugins/list', _(plugin_mgr.handle_list_plugins)),
        web.get('/api/plugins/scan', _(plugin_mgr.handle_scan_plugins)),
        web.post('/api/plugins/read', _(plugin_mgr.handle_read_plugin)),
        web.post('/api/plugins/save', _(plugin_mgr.handle_save_plugin)),
        web.post('/api/plugins/create', _(plugin_mgr.handle_create_plugin)),
        web.post('/api/plugins/create-folder', _(plugin_mgr.handle_create_folder)),
        web.get('/api/plugins/folders', _(plugin_mgr.handle_get_folders)),
        web.post('/api/plugins/reload', _(plugin_mgr.handle_reload_plugin)),
        web.post('/api/plugins/upload', _(plugin_mgr.handle_upload_plugin)),
        # Modules
        web.get('/api/modules/list', _(module_mgr.handle_list_modules)),
        web.get('/api/modules/scan', _(module_mgr.handle_scan_modules)),
        web.post('/api/modules/toggle', _(module_mgr.handle_module_toggle)),
        web.post('/api/modules/upload', _(module_mgr.handle_module_upload)),
        # Config
        web.get('/api/config', _(config_handler.handle_get_config)),
        web.post('/api/config/save', _(config_handler.handle_save_config)),
        # Messages
        web.get('/api/messages/recent', _(messages.handle_recent_messages)),
        web.get('/api/messages/chats', _(messages.handle_chat_list)),
        web.post('/api/messages/history', _(messages.handle_chat_history)),
        # Statistics
        web.get('/api/statistics', _(statistics.handle_statistics)),
        # Database
        web.get('/api/database/list', _(database.handle_list_databases)),
        web.get('/api/database/tables', _(database.handle_list_tables)),
        web.post('/api/database/query', _(database.handle_query_table)),
        web.post('/api/database/execute', _(database.handle_execute_sql)),
        web.post('/api/database/delete', _(database.handle_delete_row)),
        # SSE
        web.get('/api/sse/panel', panel_ws.handle_sse),
        # WebSocket
        web.get('/ws/panel', panel_ws.handle_ws),
    ]


def set_context(bot_manager, base_dir: str):
    global _bot_manager, _base_dir
    _bot_manager = bot_manager
    _base_dir = base_dir
    # Initialize tool modules
    system.set_context(bot_manager)
    bots.set_context(bot_manager)
    logs.set_context(bot_manager)
    plugin_mgr.set_context(bot_manager, base_dir)
    module_mgr.set_context(bot_manager, base_dir)
    config_handler.set_context(base_dir)
    database.set_context(base_dir)
    statistics.set_context(bot_manager, base_dir)
    messages.set_context(bot_manager)


# ======================== Auth ========================

async def handle_login(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': '请求格式错误'}, status=400)

    ip = auth.get_real_ip(request)
    if auth.is_ip_banned(ip):
        return web.json_response({'success': False, 'error': 'IP 已被封禁'}, status=403)

    password = str(body.get('password', ''))
    from core.base.config import cfg
    admin_pwd = cfg.get('settings', 'web.admin_password', '')

    if not admin_pwd:
        return web.json_response({'success': False, 'error': '未配置密码'}, status=500)

    admin_pwd = str(admin_pwd)

    if not auth.verify_password(password, admin_pwd):
        auth.record_ip_access(ip, 'fail')
        remaining = auth.get_remaining_attempts(ip)
        return web.json_response({
            'success': False,
            'error': f'密码错误 (剩余 {remaining} 次)',
        }, status=401)

    # First login: hash password
    if not auth.is_hashed(admin_pwd):
        cfg.set_value('settings', 'web.admin_password', auth.hash_password(password))

    auth.record_ip_access(ip, 'success')
    token = auth.create_session(request)
    return web.json_response({'success': True, 'token': token})


async def handle_auth_check(request: web.Request):
    return web.json_response({'success': True})
