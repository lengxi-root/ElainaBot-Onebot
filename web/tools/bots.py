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


async def handle_get_bots(request: web.Request):
    ad = _common.adapter()
    bots = []
    if ad:
        for self_id in _common.connected_ids():
            connected = self_id in ad.websockets
            info = await _login_info(self_id) if connected else {}
            name = info.get('nickname', '') or self_id
            conn_type = 'WebSocket' if self_id in ad.websockets else 'HTTP'
            bots.append({
                'appid': self_id,
                'name': name,
                'robot_qq': self_id,
                'bot_id': self_id,
                'avatar': _avatar(self_id),
                'connected': connected,
                'connection_type': conn_type,
                'enabled': True,
            })
    return web.json_response({'success': True, 'bots': bots})


async def handle_toggle_bot(request: web.Request):
    return web.json_response({
        'success': False,
        'error': 'OneBot 连接由客户端 (如 NapCat/Lagrange) 主动发起，无法在面板侧开关，请在客户端侧操作。',
    })


async def handle_robot_info(request: web.Request):
    ad = _common.adapter()
    appid = request.query.get('appid', '')
    ids = _common.connected_ids()
    if not appid:
        appid = ids[0] if ids else ''

    connected = bool(ad and appid in ad.websockets)
    conn_type = 'WebSocket' if connected else 'HTTP'
    conn_status = '已连接' if connected else '未连接'

    base = {
        'appid': appid,
        'qq': appid,
        'connection_type': conn_type,
        'connection_status': conn_status,
        'avatar': _avatar(appid),
    }

    if not appid:
        return web.json_response({**base, 'success': False, 'name': '无连接的机器人',
                                  'data_source': 'fallback', 'error': '当前没有 OneBot 客户端连接'})

    info = await _login_info(appid)
    name = info.get('nickname', '') or '未知'
    return web.json_response({
        **base,
        'success': True,
        'qq': str(info.get('user_id', appid) or appid),
        'name': name,
        'description': 'OneBot v11 协议机器人',
        'status': '正常' if connected else '离线',
        'data_source': 'onebot',
        'commands_count': 0,
    })
