"""WebSocket 实时推送"""

import asyncio
import json
import logging
import time

from aiohttp import web

import web.auth as auth

log = logging.getLogger('ElainaBot.web.ws')

_clients = set()


async def handle_ws(request: web.Request):
    """WebSocket 面板连接"""
    if not auth.verify_session(request):
        return web.Response(status=401)

    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _clients.add(ws)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # 心跳
                if msg.data == 'ping':
                    await ws.send_str('pong')
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        _clients.discard(ws)

    return ws


def push_log(log_type: str, entry: dict):
    """推送日志到所有 WebSocket 客户端"""
    if not _clients:
        return
    payload = json.dumps({
        'type': log_type,
        'data': entry,
        'timestamp': time.time(),
    }, ensure_ascii=False)

    closed = set()
    for ws in _clients:
        try:
            asyncio.ensure_future(ws.send_str(payload))
        except Exception:
            closed.add(ws)
    _clients.difference_update(closed)
