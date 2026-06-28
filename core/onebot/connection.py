"""OneBot 连接管理器 — 按配置维护正向/反向 WebSocket 与 HTTP 连接

连接类型 (框架视角):
- ws_reverse  : 反向 WS, 框架作为服务器, OneBot 端连入 (复用 HTTP 服务器端口)
- ws_forward  : 正向 WS, 框架作为客户端, 主动连接 OneBot 端的 WS 服务器
- http_server : HTTP 服务器, 框架接收 OneBot 事件上报 (复用 HTTP 服务器端口)
- http_client : HTTP 客户端, 框架通过 HTTP 调用 OneBot API
"""

import asyncio
import json
import logging

import aiohttp

from core.base.config import cfg

logger = logging.getLogger('ElainaBot.onebot.connection')

CONN_TYPES = ('ws_reverse', 'ws_forward', 'http_server', 'http_client')


def default_connections():
    """配置缺省时, 依据旧版 onebot.access_token/secret 生成默认反向连接"""
    token = cfg.get('settings', 'onebot.access_token', '') or ''
    secret = cfg.get('settings', 'onebot.secret', '') or ''
    host = cfg.get('settings', 'server.host', '0.0.0.0')
    port = cfg.get('settings', 'server.port', 5201)
    return [
        {
            'type': 'ws_reverse', 'name': '反向 WS', 'enable': True,
            'host': host, 'port': port, 'path': '/OneBotv11', 'token': token,
        },
        {
            'type': 'http_server', 'name': 'HTTP 上报', 'enable': False,
            'host': host, 'port': port, 'path': '/', 'secret': secret,
        },
        {
            'type': 'ws_forward', 'name': '正向 WS', 'enable': False,
            'url': 'ws://127.0.0.1:3001', 'token': token, 'reconnect_interval': 5000,
        },
        {
            'type': 'http_client', 'name': 'HTTP API', 'enable': False,
            'url': 'http://127.0.0.1:3000', 'token': token,
        },
    ]


def normalize(conn: dict) -> dict:
    """补全连接配置的缺省字段"""
    c = dict(conn or {})
    c.setdefault('type', 'ws_reverse')
    c.setdefault('name', c['type'])
    c['enable'] = bool(c.get('enable', False))
    c.setdefault('host', cfg.get('settings', 'server.host', '0.0.0.0'))
    c.setdefault('port', cfg.get('settings', 'server.port', 5201))
    c.setdefault('path', '/OneBotv11')
    c.setdefault('url', '')
    c.setdefault('token', '')
    c.setdefault('secret', '')
    c.setdefault('reconnect_interval', 5000)
    return c


class ConnectionManager:
    """维护 OneBot 连接 (正向 WS 客户端 + HTTP 客户端 + 反向服务器鉴权)"""

    def __init__(self, app):
        self._app = app
        self._adapter = app.adapter
        self._loop = None
        self._tasks = {}      # name -> asyncio.Task (正向 WS)
        self._status = {}     # name -> {connected, self_id, error}
        self._forward_ids = set()  # 正向连接占用的 self_id (含临时 id)
        self._configs = []
        self._stopping = False

    # ── 配置 ──
    def load_configs(self):
        conns = cfg.get('settings', 'onebot.connections', None)
        if not conns or not isinstance(conns, list):
            conns = default_connections()
        self._configs = [normalize(c) for c in conns if isinstance(c, dict)]
        return self._configs

    @property
    def configs(self):
        return self._configs

    # ── 启动 / 停止 ──
    async def start(self):
        self._loop = asyncio.get_running_loop()
        self._stopping = False
        self.load_configs()
        self._apply_server_auth()
        self._register_http_clients()
        await self._start_forward_clients()

    async def stop(self):
        self._stopping = True
        await self._cancel_forward_clients()

    async def reload(self):
        """配置变更后重新应用 (重启正向客户端 + 刷新鉴权/HTTP 客户端)"""
        await self._cancel_forward_clients()
        self.load_configs()
        self._apply_server_auth()
        self._register_http_clients()
        self._stopping = False
        await self._start_forward_clients()

    # ── 反向服务器鉴权 ──
    def _apply_server_auth(self):
        token, secret = '', ''
        for c in self._configs:
            if not c.get('enable'):
                continue
            if c['type'] == 'ws_reverse' and c.get('token'):
                token = c['token']
            if c['type'] == 'http_server' and c.get('secret'):
                secret = c['secret']
        # 回退到旧版全局配置
        self._adapter.access_token = token or (cfg.get('settings', 'onebot.access_token', '') or '')
        self._adapter.secret = secret or (cfg.get('settings', 'onebot.secret', '') or '')

    # ── HTTP 客户端 ──
    def _register_http_clients(self):
        self._adapter.clear_http_clients()
        for c in self._configs:
            if c.get('enable') and c['type'] == 'http_client' and c.get('url'):
                self._adapter.register_http_client(c['name'], c['url'], c.get('token', ''))

    # ── 正向 WS 客户端 ──
    async def _start_forward_clients(self):
        for c in self._configs:
            if c.get('enable') and c['type'] == 'ws_forward' and c.get('url'):
                name = c['name']
                self._tasks[name] = asyncio.create_task(self._forward_loop(c))

    async def _cancel_forward_clients(self):
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()

    async def _forward_loop(self, conn: dict):
        name = conn['name']
        url = conn['url']
        token = conn.get('token', '')
        interval = max(1.0, float(conn.get('reconnect_interval') or 5000) / 1000.0)
        headers = {}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        temp_id = f'forward:{name}'

        while not self._stopping:
            conn['_self_id'] = None
            try:
                self._set_status(name, connected=False, error='连接中…')
                timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.ws_connect(url, headers=headers, heartbeat=30) as ws:
                        self._adapter.register_bot(temp_id, ws)
                        conn['_self_id'] = temp_id
                        self._forward_ids.add(temp_id)
                        self._set_status(name, connected=True, error='', self_id=temp_id)
                        logger.info(f'正向 WS 已连接: {name} -> {url}')
                        await self._consume(ws, conn)
            except asyncio.CancelledError:
                self._cleanup_forward(conn)
                self._set_status(name, connected=False, error='已停止')
                raise
            except Exception as e:
                logger.warning(f'正向 WS 连接异常 [{name}]: {e}')
                self._set_status(name, connected=False, error=str(e))
            self._cleanup_forward(conn)
            if self._stopping:
                break
            await asyncio.sleep(interval)

    async def _consume(self, ws, conn):
        adapter = self._adapter
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except Exception:
                    continue
                echo = data.get('echo')
                if echo and echo in adapter.api_responses:
                    fut = adapter.api_responses.pop(echo)
                    if not fut.done():
                        fut.set_result(data)
                    continue
                event = adapter.parse_event(data)
                if not event:
                    continue
                sid = str(getattr(event, 'self_id', '') or '')
                if sid and conn.get('_self_id') != sid:
                    self._rekey_forward(conn, sid, ws)
                    self._set_status(conn['name'], connected=True, error='', self_id=sid)
                asyncio.create_task(self._app.process_event(event))
            elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                break

    def _rekey_forward(self, conn, real_id, ws):
        old = conn.get('_self_id')
        if old and old != real_id:
            self._adapter.unregister_bot(old)
            self._forward_ids.discard(old)
        self._adapter.register_bot(real_id, ws)
        self._forward_ids.add(real_id)
        conn['_self_id'] = real_id

    def _cleanup_forward(self, conn):
        sid = conn.get('_self_id')
        if sid:
            self._adapter.unregister_bot(sid)
            self._forward_ids.discard(sid)
        conn['_self_id'] = None

    # ── 状态 ──
    def _set_status(self, name, connected, error='', self_id=None):
        self._status[name] = {'connected': bool(connected), 'error': error or '', 'self_id': self_id}

    def status(self):
        """返回各连接的运行状态"""
        result = []
        server_connected = bool(self._adapter.websockets)
        for c in self._configs:
            name = c['name']
            ctype = c['type']
            entry = {'name': name, 'type': ctype, 'enable': c.get('enable', False), 'connected': False, 'self_id': None, 'error': ''}
            if ctype == 'ws_forward':
                st = self._status.get(name, {})
                entry['connected'] = st.get('connected', False)
                entry['self_id'] = st.get('self_id')
                entry['error'] = st.get('error', '')
            elif ctype == 'ws_reverse':
                # 排除正向连接占用的 self_id, 仅统计真正连入的反向连接
                reverse_ids = [k for k in self._adapter.websockets
                               if not str(k).startswith('forward:') and k not in self._forward_ids]
                entry['connected'] = c.get('enable', False) and bool(reverse_ids)
                entry['self_id'] = reverse_ids[0] if reverse_ids else None
            elif ctype == 'http_client':
                entry['connected'] = c.get('enable', False) and (c['name'] in self._adapter.http_clients)
            elif ctype == 'http_server':
                entry['connected'] = c.get('enable', False)
            result.append(entry)
        return result
