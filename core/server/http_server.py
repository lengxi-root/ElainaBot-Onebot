"""HTTP 服务器 — 基于 aiohttp"""

import asyncio
import json

from aiohttp import web

from core.base.config import cfg
from core.base.logger import SYSTEM, get_logger

log = get_logger(SYSTEM, 'HTTP')


def _local_port(request: web.Request):
    """获取该请求实际进入的本地监听端口 (用于按连接区分鉴权)"""
    try:
        sock = request.transport.get_extra_info('sockname') if request.transport else None
        if sock and len(sock) >= 2:
            return int(sock[1])
    except Exception:
        pass
    return request.url.port


class HttpServer:
    """aiohttp HTTP 服务器"""

    def __init__(self, app_instance, base_dir: str):
        self._app_instance = app_instance
        self._base_dir = base_dir
        self._app: web.Application = None
        self._runner: web.AppRunner = None
        self._site: web.TCPSite = None

    @property
    def app(self) -> web.Application:
        return self._app

    def init_app(self):
        """初始化 aiohttp 应用"""
        self._app = web.Application()

        # OneBot HTTP 回调
        self._app.router.add_post('/', self._handle_onebot_http)
        self._app.router.add_post('/onebot/v11/', self._handle_onebot_http)
        self._app.router.add_post('/onebot/v11/http', self._handle_onebot_http)
        self._app.router.add_post('/OneBotv11', self._handle_onebot_http)

        # OneBot WebSocket
        self._app.router.add_get('/onebot/v11/', self._handle_onebot_ws)
        self._app.router.add_get('/onebot/v11/ws', self._handle_onebot_ws)
        self._app.router.add_get('/OneBotv11', self._handle_onebot_ws)

        # Health check
        self._app.router.add_get('/health', self._handle_health)

    def mount_web_panel(self):
        """挂载 Web 面板"""
        try:
            from web.setup import setup_web
            setup_web(self._app, self._app_instance, self._base_dir)
        except Exception as e:
            log.error(f'Web 面板挂载失败: {e}')

    async def start(self):
        """启动 HTTP 服务器"""
        host = cfg.get('settings', 'server.host', '0.0.0.0')
        port = cfg.get('settings', 'server.port', 5201)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()

        log.info(f'HTTP 服务器启动: {host}:{port}')
        log.info(f'OneBot: ws://{host}:{port}/OneBotv11')
        log.info(f'Web: http://{host}:{port}/web/')

    async def stop(self, timeout: float = 5):
        """停止服务器"""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()

    async def _handle_onebot_http(self, request: web.Request):
        """处理 OneBot HTTP 回调"""
        adapter = self._app_instance.adapter
        if not adapter:
            return web.Response(status=503)

        body = await request.read()
        if not body:
            return web.Response(status=400)

        port, path = _local_port(request), request.path
        success, event = adapter.handle_http_callback(body, dict(request.headers), port=port, path=path)
        if event:
            asyncio.create_task(self._app_instance.process_event(event))

        return web.Response(status=204)

    async def _handle_onebot_ws(self, request: web.Request):
        """处理 OneBot WebSocket 连接"""
        from core.onebot.api import set_main_loop
        set_main_loop(asyncio.get_running_loop())

        adapter = self._app_instance.adapter
        if not adapter:
            return web.Response(status=503)

        headers = dict(request.headers)
        valid, self_id, error = adapter.validate_websocket_headers(
            headers, port=_local_port(request), path=request.path)
        if not valid:
            return web.Response(status=401, text=error or 'Unauthorized')

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        adapter.register_bot(self_id, ws)
        log.info(f'OneBot 连接: {request.remote} | Bot {self_id}')

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        event = adapter.parse_event(data)
                        if event:
                            asyncio.create_task(self._app_instance.process_event(event))
                        elif "echo" in data and data["echo"] in adapter.api_responses:
                            future = adapter.api_responses.pop(data["echo"])
                            if not future.done():
                                future.set_result(data)
                    except json.JSONDecodeError:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    break
        finally:
            adapter.unregister_bot(self_id)
            log.info(f'OneBot 断开: Bot {self_id}')

        return ws

    async def _handle_health(self, request: web.Request):
        return web.json_response({'status': 'ok'})
