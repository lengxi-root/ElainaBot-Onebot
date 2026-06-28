"""Web 面板集成入口"""

import logging
import os

from aiohttp import web

import web.api as _panel_api
import web.auth as _auth
import web.ws as _ws

log = logging.getLogger('ElainaBot.web')


class _WebPanelLogHandler(logging.Handler):
    """将 Python logging 记录推送到 web 面板 + 持久化到 SQLite"""

    def __init__(self, app_instance):
        super().__init__()
        self._app = app_instance

    def emit(self, record):
        try:
            from datetime import datetime

            # 标记 web_skip 的记录(如消息内容)不进入框架日志面板, 它们另存于消息记录
            if getattr(record, 'web_skip', False):
                return

            msg = record.getMessage()
            entry = {
                'timestamp': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
                'content': msg,
                'source': record.name,
                'level': record.levelname,
            }
            _ws.push_log('framework', entry)
            svc = getattr(self._app, '_log_service', None)
            if svc:
                svc.add('framework', entry)
        except Exception:
            pass


def setup_web(app: web.Application, bot_manager, base_dir: str):
    """将 Web 面板挂载到 aiohttp 应用 (bot_manager 即 Application 实例)"""
    _auth.init(base_dir)
    _panel_api.set_context(bot_manager, base_dir)

    # 注入日志/错误实时推送
    try:
        from core.base.logger import on_error

        bot_manager._web_log_cb = _ws.push_log

        def _push_error(error_data):
            _ws.push_log('error', {
                'timestamp': error_data.get('timestamp', ''),
                'module_type': error_data.get('module_type', ''),
                'module_name': error_data.get('module_name', ''),
                'content': error_data.get('content', ''),
                'traceback': error_data.get('traceback', ''),
            })
            svc = getattr(bot_manager, '_log_service', None)
            if svc:
                svc.add('error', {
                    'timestamp': error_data.get('timestamp', ''),
                    'source': f"{error_data.get('module_type', '')}.{error_data.get('module_name', '')}",
                    'level': 'ERROR',
                    'content': error_data.get('content', ''),
                    'extra': error_data.get('traceback', ''),
                })

        on_error(_push_error)

        _handler = _WebPanelLogHandler(bot_manager)
        _handler.setLevel(logging.INFO)
        logging.getLogger('ElainaBot').addHandler(_handler)
    except Exception as e:
        log.warning(f'日志推送注入失败: {e}')

    # API 路由
    app.router.add_routes(_panel_api.get_routes())

    # 媒体静态目录
    media_dir = os.path.join(base_dir, 'data', 'media')
    os.makedirs(media_dir, exist_ok=True)
    app.router.add_static('/api/media/', media_dir)

    # dist 目录
    _web_dir = os.path.dirname(__file__)
    dist_dir = os.path.join(_web_dir, 'dist')

    app.router.add_get('/web', _redirect_to_web)

    if os.path.isdir(dist_dir):
        app.router.add_get('/web/{path:.*}', _make_spa_handler(dist_dir))
        log.info(f'Web 面板已挂载 (dist: {dist_dir})')
    else:
        app.router.add_get('/web/{path:.*}', _dev_placeholder)
        log.warning(f'Web 面板未找到编译产物 (期望: {dist_dir})')


_MIME = {
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.html': 'text/html',
    '.json': 'application/json',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
}


def _make_spa_handler(dist_dir: str):
    async def handler(request: web.Request):
        path = request.match_info.get('path', '')
        if not path or path == '/':
            path = 'index.html'

        file_path = os.path.join(dist_dir, path.replace('/', os.sep))

        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            ct = _MIME.get(ext)
            return web.FileResponse(file_path, headers={'Content-Type': ct} if ct else {})

        index = os.path.join(dist_dir, 'index.html')
        if os.path.isfile(index):
            return web.FileResponse(index, headers={'Content-Type': 'text/html'})

        return web.Response(text='Not Found', status=404)

    return handler


async def _redirect_to_web(request: web.Request):
    raise web.HTTPFound('/web/')


async def _dev_placeholder(request: web.Request):
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Elaina Panel</title></head>
<body style="background:#fff;color:#333;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
<h1 style="color:#5865f2">Elaina 管理面板</h1>
<p style="color:#666">未找到 <code>web/dist/</code> 目录。</p>
</div></body></html>"""
    return web.Response(text=html, content_type='text/html')
