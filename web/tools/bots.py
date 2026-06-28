"""Bot 管理 — 列出所有连接的机器人"""

import logging
from aiohttp import web

log = logging.getLogger('ElainaBot.web.bots')

_bot_manager = None


def set_context(bot_manager):
    global _bot_manager
    _bot_manager = bot_manager


async def handle_list_bots(request: web.Request):
    bots = []
    if _bot_manager and _bot_manager.adapter:
        for self_id, info in _bot_manager.adapter.bots.items():
            bots.append({
                'self_id': str(self_id),
                'appid': str(self_id),
                'name': info.get('name', f'Bot {self_id}'),
                'status': 'online',
                'connection_type': info.get('type', 'unknown'),
            })
    return web.json_response({'success': True, 'bots': bots})


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
