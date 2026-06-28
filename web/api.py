"""Web 面板 API 路由"""

import logging

from aiohttp import web

import web.auth as auth
import web.ws as panel_ws
from web.tools import (
    bots,
    config_handler,
    database,
    logs,
    market,
    messages,
    onebot_conn,
    plugin_mgr,
    statistics,
    system,
    update,
)

log = logging.getLogger('ElainaBot.web.api')

_app = None
_base_dir = ''


def get_routes() -> list:
    """返回所有 API 路由"""
    _ = auth.require_auth
    return [
        # ── 鉴权 ──
        web.post('/api/auth/login', handle_login),
        web.get('/api/auth/check', _(handle_auth_check)),
        web.get('/api/auth/password-status', _(handle_password_status)),
        # ── 机器人 ──
        web.get('/api/bots', _(bots.handle_get_bots)),
        web.post('/api/bots/toggle', _(bots.handle_toggle_bot)),
        web.get('/api/robot/info', _(bots.handle_robot_info)),
        # ── 系统信息 ──
        web.get('/api/system/info', _(system.handle_system_info)),
        # ── 日志 (具体路径必须在 {log_type} 之前) ──
        web.get('/api/logs/recent', _(logs.handle_recent_logs)),
        web.get('/api/logs/login', _(logs.handle_get_login_logs)),
        web.post('/api/logs/unban', _(logs.handle_unban_ip)),
        web.post('/api/logs/delete-ip', _(logs.handle_delete_ip)),
        web.get('/api/logs/{log_type}', _(logs.handle_get_logs)),
        # ── 插件文件管理 ──
        web.get('/api/plugins/scan', _(plugin_mgr.handle_scan_plugins)),
        web.get('/api/plugins/scan-dirs', _(plugin_mgr.handle_scan_plugin_dirs)),
        web.post('/api/plugins/toggle', _(plugin_mgr.handle_toggle_plugin)),
        web.post('/api/plugins/read', _(plugin_mgr.handle_read_plugin)),
        web.post('/api/plugins/save', _(plugin_mgr.handle_save_plugin)),
        web.post('/api/plugins/create', _(plugin_mgr.handle_create_plugin)),
        web.post('/api/plugins/create-folder', _(plugin_mgr.handle_create_folder)),
        web.get('/api/plugins/folders', _(plugin_mgr.handle_get_folders)),
        web.post('/api/plugins/upload', _(plugin_mgr.handle_upload_plugin)),
        web.post('/api/plugins/reload', _(plugin_mgr.handle_reload_plugin)),
        web.post('/api/plugins/config-files', _(plugin_mgr.handle_plugin_config_files)),
        web.get('/api/plugins/bots', _(plugin_mgr.handle_get_plugin_bots)),
        web.post('/api/plugins/bots', _(plugin_mgr.handle_set_plugin_bots)),
        # ── 模块管理 ──
        web.get('/api/modules/scan', _(plugin_mgr.handle_scan_modules)),
        web.post('/api/modules/toggle', _(plugin_mgr.handle_module_toggle)),
        web.post('/api/modules/upload', _(plugin_mgr.handle_module_upload)),
        # ── 通用配置读写 (模块 + 插件) ──
        web.post('/api/config-file/read', _(plugin_mgr.handle_read_config)),
        web.post('/api/config-file/save', _(plugin_mgr.handle_save_config)),
        # ── 配置 ──
        web.get('/api/config', _(config_handler.handle_get_config)),
        web.post('/api/config/save', _(config_handler.handle_save_config)),
        # ── OneBot 网络连接 ──
        web.get('/api/onebot/connections', _(onebot_conn.handle_get_connections)),
        web.post('/api/onebot/connections', _(onebot_conn.handle_save_connections)),
        # ── 消息 ──
        web.post('/api/message/chats', _(messages.handle_get_chats)),
        web.post('/api/message/history', _(messages.handle_get_chat_history)),
        web.post('/api/message/send', _(messages.handle_send_message)),
        web.post('/api/message/nickname', _(messages.handle_get_nickname)),
        web.post('/api/message/nicknames', _(messages.handle_get_nicknames_batch)),
        web.post('/api/message/recall', _(messages.handle_recall_message)),
        web.get('/api/message/remarks', _(messages.handle_get_remarks)),
        web.post('/api/message/remarks', _(messages.handle_set_remark)),
        web.post('/api/message/remarks/delete', _(messages.handle_delete_remark)),
        web.post('/api/message/group-roles', _(messages.handle_get_group_roles)),
        # ── 统计 ──
        web.get('/api/statistics', _(statistics.handle_get_statistics)),
        web.get('/api/statistics/summary', _(statistics.handle_get_summary)),
        web.get('/api/statistics/active', _(statistics.handle_get_active)),
        web.get('/api/statistics/top', _(statistics.handle_get_top)),
        web.get('/api/statistics/events', _(statistics.handle_get_events)),
        web.get('/api/statistics/totals', _(statistics.handle_get_totals)),
        web.get('/api/statistics/hourly', _(statistics.handle_get_hourly_statistics)),
        web.get('/api/statistics/chart', _(statistics.handle_get_chart_data)),
        web.get('/api/statistics/dates', _(statistics.handle_get_available_dates)),
        # ── 更新 ──
        web.get('/api/update/changelog', _(update.handle_get_changelog)),
        web.get('/api/update/version', _(update.handle_get_current_version)),
        web.get('/api/update/check', _(update.handle_check_update)),
        web.post('/api/update/start', _(update.handle_start_update)),
        web.get('/api/update/progress', _(update.handle_get_update_progress)),
        web.get('/api/update/mirrors', _(update.handle_get_mirrors)),
        web.get('/api/update/test-mirrors', _(update.handle_test_mirrors)),
        web.post('/api/update/mirror', _(update.handle_set_custom_mirror)),
        web.get('/api/update/environment', _(update.handle_detect_environment)),
        # ── 重启 ──
        web.post('/api/bot/restart', _(system.handle_restart)),
        # ── 插件市场 ──
        web.get('/api/market/list', _(market.handle_market_list)),
        web.get('/api/market/categories', _(market.handle_market_categories)),
        web.post('/api/market/detail', _(market.handle_market_detail)),
        web.post('/api/market/refresh', _(market.handle_market_refresh)),
        web.post('/api/market/preview', _(market.handle_market_preview)),
        web.post('/api/market/install', _(market.handle_market_install)),
        web.post('/api/market/uninstall', _(market.handle_market_uninstall)),
        web.get('/api/market/local', _(market.handle_local_plugins)),
        web.post('/api/market/local/read', _(market.handle_local_plugin_read)),
        web.post('/api/market/local/save', _(market.handle_local_plugin_save)),
        web.get('/api/market/mirror', _(market.handle_market_get_mirror)),
        web.post('/api/market/mirror', _(market.handle_market_set_mirror)),
        web.post('/api/market/mirror/test', _(market.handle_market_test_mirror)),
        # ── 自定义页面 ──
        web.get('/api/web-pages', _(handle_get_web_pages)),
        web.get('/api/web-pages/{key}', _(handle_get_web_page_html)),
        # ── 数据库浏览 ──
        web.get('/api/database/list', _(database.handle_list_databases)),
        web.post('/api/database/tables', _(database.handle_list_tables)),
        web.post('/api/database/query', _(database.handle_query_table)),
        web.post('/api/database/sql', _(database.handle_execute_sql)),
        web.post('/api/database/delete', _(database.handle_delete_rows)),
        # ── WebSocket / SSE ──
        web.get('/ws/panel', panel_ws.handle_ws),
        web.get('/api/sse/panel', panel_ws.handle_sse),
    ]


def set_context(app_instance, base_dir: str):
    """注入运行时上下文到所有工具模块 (app_instance 即 Application)"""
    global _app, _base_dir
    _app = app_instance
    _base_dir = base_dir

    system.set_context(app_instance)
    bots.set_context(app_instance)
    logs.set_context(app_instance)
    plugin_mgr.set_context(app_instance, base_dir)
    config_handler.set_context(base_dir)
    database.set_context(app_instance, base_dir)
    statistics.set_context(app_instance, base_dir)
    messages.set_context(app_instance, base_dir)
    onebot_conn.set_context(app_instance)
    market.set_context(base_dir)
    update.set_context(base_dir)


# ======================== 内联路由处理 ========================


async def handle_login(request: web.Request):
    ip = auth.get_real_ip(request)
    auth.cleanup_expired_ip_bans()
    if auth.is_ip_banned(ip):
        return web.json_response({'success': False, 'error': 'IP 已被封禁'}, status=403)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({'success': False, 'error': '请求格式错误'}, status=400)

    password = str(body.get('password', ''))
    from core.base.config import cfg

    admin_pwd = str(cfg.get('settings', 'web.admin_password', '') or '')
    if not admin_pwd:
        return web.json_response({'success': False, 'error': '未配置管理员密码'}, status=500)

    if not auth.verify_password(password, admin_pwd):
        auth.record_ip_access(ip, 'fail')
        remaining = auth.get_remaining_attempts(ip)
        if remaining <= 0:
            return web.json_response({'success': False, 'error': 'IP 已被封禁，12小时后解除'}, status=403)
        return web.json_response(
            {'success': False, 'error': f'密码错误，还剩 {remaining} 次机会', 'remaining': remaining},
            status=401,
        )

    if not auth.is_hashed(admin_pwd):
        cfg.set_value('settings', 'web.admin_password', auth.hash_password(password))

    auth.record_ip_access(ip, 'success')
    token = auth.create_session(request)
    is_weak = password in _WEAK_PASSWORDS
    return web.json_response({'success': True, 'token': token, 'is_weak': is_weak})


async def handle_auth_check(request: web.Request):
    return web.json_response({'success': True})


_WEAK_PASSWORDS = frozenset({'admin', '123456', 'password', 'admin123', '12345678'})


async def handle_password_status(request: web.Request):
    from core.base.config import cfg

    pwd = str(cfg.get('settings', 'web.admin_password', '') or '')
    is_default = not pwd or (not auth.is_hashed(pwd) and pwd in _WEAK_PASSWORDS)
    is_weak = False
    if pwd and auth.is_hashed(pwd):
        is_weak = any(auth.verify_password(w, pwd) for w in _WEAK_PASSWORDS)
    return web.json_response({'success': True, 'is_default': is_default, 'is_weak': is_weak})


# ======================== 自定义页面 (OneBot 暂无插件 web 页面机制) ========================


async def handle_get_web_pages(request: web.Request):
    return web.json_response({'success': True, 'pages': []})


async def handle_get_web_page_html(request: web.Request):
    return web.json_response({'success': False, 'error': '页面不存在'}, status=404)
