"""Web 面板集成入口"""

import logging
import os

from aiohttp import web

import web.api as _panel_api
import web.auth as _auth
import web.ws as _ws

log = logging.getLogger('ElainaBot.web')

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


def setup_web(app: web.Application, bot_manager, base_dir: str):
    """将 Web 面板挂载到 aiohttp 应用"""
    _auth.init(base_dir)
    _panel_api.set_context(bot_manager, base_dir)

    # 注入日志推送
    bot_manager._web_log_cb = _ws.push_log

    # API 路由
    app.router.add_routes(_panel_api.get_routes())

    # dist 目录
    _web_dir = os.path.dirname(__file__)
    dist_dir = os.path.join(_web_dir, 'dist')

    # /web → 重定向到 /web/
    app.router.add_get('/web', _redirect_to_web)

    if os.path.isdir(dist_dir):
        app.router.add_get('/web/{path:.*}', _make_spa_handler(dist_dir))
        log.info(f'Web 面板已挂载 (dist: {dist_dir})')
    else:
        app.router.add_get('/web/{path:.*}', _dev_placeholder)
        log.warning(f'Web 面板未找到编译产物 (期望: {dist_dir})')


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
<body style="background:#fff;color:#333;font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
<h1 style="color:#5865f2">Elaina 管理面板</h1>
<p style="color:#666">未找到 <code>web/dist/</code> 目录，请先编译前端。</p>
<pre style="background:#f5f5f5;padding:16px;border-radius:8px;color:#333">cd web/vue && npm install && npm run build</pre>
</div></body></html>"""
    return web.Response(text=html, content_type='text/html')
