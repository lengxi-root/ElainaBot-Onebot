"""WebSocket/SSE 实时推送 — 面板日志广播"""

import asyncio
import contextlib
import json
import logging
import time
from datetime import datetime

from aiohttp import WSMsgType, web

import web.auth as auth

log = logging.getLogger('ElainaBot.web.ws')


class WSBroadcast:
    """WebSocket/SSE 广播管理"""

    def __init__(self):
        self._clients: set = set()
        self._sse_queues: set = set()

    @property
    def clients(self):
        return self._clients

    @property
    def sse_queues(self):
        return self._sse_queues

    def has_clients(self) -> bool:
        return bool(self._clients or self._sse_queues)

    async def broadcast(self, msg_type: str, data: dict):
        if not self.has_clients():
            return
        payload = json.dumps({'type': msg_type, 'data': data}, ensure_ascii=False, default=str)
        dead = set()
        for ws in list(self._clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead.add(ws)
        self._clients.difference_update(dead)
        for q in list(self._sse_queues):
            with contextlib.suppress(Exception):
                q.put_nowait(payload)

    def schedule_broadcast(self, msg_type: str, data: dict):
        if not self.has_clients():
            return
        with contextlib.suppress(RuntimeError):
            asyncio.get_running_loop().create_task(self.broadcast(msg_type, data))

    def push_log(self, log_type: str, entry: dict):
        if 'timestamp' not in entry:
            entry['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.schedule_broadcast('new_log', {'log_type': log_type, **entry})

    def push_system_info(self, data: dict):
        self.schedule_broadcast('system_info', data)

    def shutdown(self):
        for ws in list(self._clients):
            with contextlib.suppress(Exception, RuntimeError):
                asyncio.get_running_loop().create_task(
                    ws.close(code=1001, message=b'Server shutdown')
                )
        self._clients.clear()
        self._sse_queues.clear()


_broadcast = WSBroadcast()


def get_broadcast() -> WSBroadcast:
    return _broadcast


# Module-level compat
async def broadcast(msg_type: str, data: dict):
    await _broadcast.broadcast(msg_type, data)


def push_log(log_type: str, entry: dict):
    _broadcast.push_log(log_type, entry)


def push_system_info(data: dict):
    _broadcast.push_system_info(data)


# ==================== WebSocket ====================

async def handle_ws(request: web.Request) -> web.WebSocketResponse:
    """WebSocket 端点: /ws/panel?token=xxx"""
    if not auth.verify_session(request):
        return web.Response(status=401, text='Unauthorized')

    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    _broadcast.clients.add(ws)
    log.debug(f'WebSocket connected ({len(_broadcast.clients)} clients)')

    try:
        await ws.send_json({'type': 'init', 'data': {}})

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == 'ping':
                    await ws.send_str('pong')
                else:
                    try:
                        data = json.loads(msg.data)
                        await _handle_client_msg(ws, data)
                    except json.JSONDecodeError:
                        pass
            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break
    finally:
        _broadcast.clients.discard(ws)
        log.debug(f'WebSocket disconnected ({len(_broadcast.clients)} clients)')

    return ws


async def _handle_client_msg(ws: web.WebSocketResponse, data: dict):
    pass


# ==================== SSE ====================

async def handle_sse(request: web.Request) -> web.StreamResponse:
    """SSE 端点: /api/sse/panel?token=xxx — WebSocket 不可用时的降级方案"""
    if not auth.verify_session(request):
        return web.Response(status=401, text='Unauthorized')

    resp = web.StreamResponse()
    resp.headers['Content-Type'] = 'text/event-stream'
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    await resp.prepare(request)

    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=256)
    _broadcast.sse_queues.add(queue)
    log.debug(f'SSE connected (WS:{len(_broadcast.clients)} SSE:{len(_broadcast.sse_queues)})')

    try:
        await resp.write(b'data: {"type":"init","data":{}}\n\n')
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=25)
                await resp.write(f'data: {payload}\n\n'.encode())
            except TimeoutError:
                await resp.write(b': keepalive\n\n')
    except (asyncio.CancelledError, ConnectionResetError, Exception):
        pass
    finally:
        _broadcast.sse_queues.discard(queue)
        log.debug(f'SSE disconnected (WS:{len(_broadcast.clients)} SSE:{len(_broadcast.sse_queues)})')

    return resp
