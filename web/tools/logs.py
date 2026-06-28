"""日志查询"""

import logging
from aiohttp import web
import web.auth as auth

log = logging.getLogger('ElainaBot.web.logs')

_bot_manager = None


def set_context(bot_manager):
    global _bot_manager
    _bot_manager = bot_manager


def _ls():
    if _bot_manager and _bot_manager.log_service:
        return _bot_manager.log_service
    return None


async def handle_recent_logs(request: web.Request):
    ls = _ls()
    if not ls:
        return web.json_response({'message': [], 'framework': [], 'error': []})

    messages = ls.query('message', 'SELECT * FROM log ORDER BY id DESC LIMIT 100')
    framework = ls.query('framework', 'SELECT * FROM log ORDER BY id DESC LIMIT 100')
    return web.json_response({'message': messages, 'framework': framework})


async def handle_get_logs(request: web.Request):
    log_type = request.match_info.get('log_type', 'message')
    page = int(request.query.get('page', '1'))
    limit = min(int(request.query.get('limit', '100')), 500)
    offset = (page - 1) * limit

    ls = _ls()
    if not ls:
        return web.json_response({'success': True, 'data': [], 'total': 0})

    data = ls.query(log_type, f'SELECT * FROM log ORDER BY id DESC LIMIT {limit} OFFSET {offset}')

    count_row = ls.query(log_type, 'SELECT COUNT(*) as cnt FROM log')
    total = count_row[0].get('cnt', 0) if count_row else 0

    return web.json_response({'success': True, 'data': data, 'total': total})


async def handle_login_logs(request: web.Request):
    logs = auth.get_login_logs()
    return web.json_response({'success': True, 'logs': logs})
