"""消息浏览"""

import logging
from datetime import datetime

from aiohttp import web

log = logging.getLogger('ElainaBot.web.messages')

_bot_manager = None


def set_context(bot_manager):
    global _bot_manager
    _bot_manager = bot_manager


def _ls():
    if _bot_manager and _bot_manager.log_service:
        return _bot_manager.log_service
    return None


async def handle_recent_messages(request: web.Request):
    ls = _ls()
    if not ls:
        return web.json_response({'success': True, 'data': []})

    data = ls.query('message', 'SELECT * FROM log ORDER BY id DESC LIMIT 50')
    return web.json_response({'success': True, 'data': data})


async def handle_chat_list(request: web.Request):
    ls = _ls()
    if not ls:
        return web.json_response({'success': True, 'chats': []})

    search = request.query.get('search', '')
    msg_type = request.query.get('type', '')

    try:
        if msg_type == 'private':
            rows = ls.query(
                'message',
                "SELECT user_id, message_type, COUNT(*) as msg_count, MAX(timestamp) as last_time "
                "FROM log WHERE message_type='private' GROUP BY user_id ORDER BY last_time DESC LIMIT 200"
            )
        elif msg_type == 'group':
            rows = ls.query(
                'message',
                "SELECT group_id, message_type, COUNT(*) as msg_count, MAX(timestamp) as last_time "
                "FROM log WHERE message_type='group' AND group_id != '' GROUP BY group_id ORDER BY last_time DESC LIMIT 200"
            )
        else:
            sql = (
                "SELECT "
                "CASE WHEN message_type='group' THEN group_id ELSE user_id END as chat_id, "
                "message_type, "
                "COUNT(*) as msg_count, "
                "MAX(timestamp) as last_time "
                "FROM log GROUP BY chat_id, message_type ORDER BY last_time DESC LIMIT 200"
            )
            rows = ls.query('message', sql)

        chats = []
        for r in (rows or []):
            chat = {
                'chat_id': r.get('chat_id') or r.get('group_id') or r.get('user_id', ''),
                'type': r.get('message_type', 'unknown'),
                'msg_count': r.get('msg_count', 0),
                'last_time': r.get('last_time', ''),
                'nickname': '',
            }
            if search and search.lower() not in str(chat['chat_id']).lower():
                continue
            chats.append(chat)

        return web.json_response({'success': True, 'chats': chats})
    except Exception as e:
        return web.json_response({'success': True, 'chats': [], 'error': str(e)})


async def handle_chat_history(request: web.Request):
    ls = _ls()
    if not ls:
        return web.json_response({'success': True, 'messages': []})

    body = await request.json()
    chat_id = body.get('chat_id', '')
    chat_type = body.get('type', '')
    page = int(body.get('page', 1))
    limit = min(int(body.get('limit', 50)), 200)
    offset = (page - 1) * limit

    if not chat_id:
        return web.json_response({'success': False, 'error': 'missing chat_id'}, status=400)

    try:
        if chat_type == 'group':
            where = f"WHERE group_id='{chat_id}'"
        else:
            where = f"WHERE user_id='{chat_id}' AND (message_type='private' OR group_id='')"

        count_rows = ls.query('message', f"SELECT COUNT(*) as cnt FROM log {where}")
        total = count_rows[0]['cnt'] if count_rows else 0

        messages = ls.query(
            'message',
            f"SELECT * FROM log {where} ORDER BY id DESC LIMIT {limit} OFFSET {offset}"
        )

        return web.json_response({
            'success': True,
            'messages': messages or [],
            'total': total,
            'page': page,
        })
    except Exception as e:
        return web.json_response({'success': True, 'messages': [], 'error': str(e)})
