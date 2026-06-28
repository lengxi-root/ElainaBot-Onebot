"""机器人列表 / 详情 (OneBot 适配)"""

import time

from aiohttp import web

from web.tools import _common

_app = None
_login_cache: dict[str, tuple[float, dict]] = {}
_LOGIN_TTL = 60


def set_context(app_instance):
    global _app
    _app = app_instance
    _common.set_app(app_instance)


async def _login_info(self_id: str) -> dict:
    now = time.time()
    c = _login_cache.get(self_id)
    if c and now - c[0] < _LOGIN_TTL:
        return c[1]
    info = {}
    try:
        from core.onebot.api import OneBotAPI

        resp = await OneBotAPI(_common.adapter()).call_api('get_login_info', self_id=self_id)
        if resp and resp.get('retcode') == 0:
            info = resp.get('data') or {}
    except Exception:
        info = {}
    _login_cache[self_id] = (now, info)
    return info


def _avatar(qq: str) -> str:
    return f'http://q1.qlogo.cn/g?b=qq&nk={qq}&s=100' if qq else ''


def _conn_type(ad, self_id: str) -> str:
    """依据适配器记录判断连接方式 (WebSocket 优先于 HTTP)"""
    if self_id in ad.websockets:
        return 'WebSocket'
    rec = ad.bots.get(self_id) or {}
    return 'WebSocket' if rec.get('type') == 'websocket' else 'HTTP'


async def handle_get_bots(request: web.Request):
    ad = _common.adapter()
    bots = []
    if ad:
        for self_id in _common.connected_ids():
            conn_type = _conn_type(ad, self_id)
            connected = self_id in ad.websockets or conn_type == 'WebSocket'
            info = await _login_info(self_id) if connected else {}
            name = info.get('nickname', '') or self_id
            bots.append({
                'bot_qq': self_id,
                'name': name,
                'qq': self_id,
                'avatar': _avatar(self_id),
                'connected': connected,
                'connection_type': conn_type,
                'enabled': True,
            })
    return web.json_response({'success': True, 'bots': bots})


async def handle_toggle_bot(request: web.Request):
    return web.json_response({
        'success': False,
        'error': 'OneBot 连接由客户端主动发起，无法在面板侧开关，请在客户端侧操作。',
    })
