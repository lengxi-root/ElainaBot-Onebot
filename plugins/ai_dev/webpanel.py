"""ai_dev Web 面板路由

挂载到框架共享的 aiohttp 服务上, 提供:
- GET  /ai/                 亮色聊天面板 (静态 HTML)
- GET  /ai/api/config       面板配置 (模型/base_url 等, 不含 key 明文)
- GET  /ai/api/models       代理上游模型列表
- GET  /ai/api/sessions     会话列表
- POST /ai/api/sessions     新建会话
- POST /ai/api/sessions/delete  删除会话
- GET  /ai/api/history      某会话历史
- POST /ai/api/chat         发送消息 (执行 Agent, 返回最终结果)
- GET  /ai/api/calls        最近事件 (完整调用 + 日志)
- GET  /ai/api/stream       SSE 实时事件流
- POST /ai/api/clear        清空会话

鉴权复用框架 web.auth (Bearer token / ?token=)。HTML 页面本身不鉴权,
登录在前端通过框架现有 /api/auth/login 完成。
"""

import asyncio
import contextlib
import json
import logging
import os

import aiohttp
from aiohttp import web

import web.auth as auth
from plugins.ai_dev import aiconfig
from plugins.ai_dev import agent as agentmod

log = logging.getLogger('ElainaBot.plugins.ai_dev')

_PREFIX = '/ai'


def _store():
    """从 Application 实例获取 AIStore 单例 (热重载安全)"""
    from core.application import get_app
    app = get_app()
    return getattr(app, '_ai_dev_store', None) if app else None


def _plugin_dir() -> str:
    from core.application import get_app
    app = get_app()
    return getattr(app, '_ai_dev_plugin_dir', '') if app else ''


def _require(handler):
    async def wrapped(request):
        if not auth.validate_token(request):
            return web.json_response({'success': False, 'error': '未登录或会话已过期'}, status=401)
        return await handler(request)
    wrapped.__name__ = getattr(handler, '__name__', 'wrapped')
    return wrapped


def register_routes(aio_app: web.Application):
    aio_app.router.add_get(_PREFIX, _redirect)
    aio_app.router.add_get(_PREFIX + '/', _serve_panel)
    aio_app.router.add_get(_PREFIX + '/api/config', _require(_get_config))
    aio_app.router.add_get(_PREFIX + '/api/models', _require(_get_models))
    aio_app.router.add_get(_PREFIX + '/api/sessions', _require(_get_sessions))
    aio_app.router.add_post(_PREFIX + '/api/sessions', _require(_create_session))
    aio_app.router.add_post(_PREFIX + '/api/sessions/delete', _require(_delete_session))
    aio_app.router.add_get(_PREFIX + '/api/history', _require(_get_history))
    aio_app.router.add_post(_PREFIX + '/api/chat', _require(_post_chat))
    aio_app.router.add_get(_PREFIX + '/api/calls', _require(_get_calls))
    aio_app.router.add_post(_PREFIX + '/api/clear', _require(_clear))
    aio_app.router.add_get(_PREFIX + '/api/stream', _stream)  # SSE: token via query
    log.info('AI 开发面板路由已挂载: /ai/')


async def _redirect(request: web.Request):
    raise web.HTTPFound(_PREFIX + '/')


async def _serve_panel(request: web.Request):
    path = os.path.join(_plugin_dir(), 'panel.html')
    if not os.path.isfile(path):
        return web.Response(text='panel.html 缺失', status=500)
    with open(path, encoding='utf-8') as f:
        html = f.read()
    return web.Response(text=html, content_type='text/html', charset='utf-8')


async def _get_config(request: web.Request):
    return web.json_response({'success': True, 'config': aiconfig.public_config()})


async def _get_models(request: web.Request):
    if not aiconfig.is_configured():
        return web.json_response({'success': False, 'error': '未配置 api_key', 'models': []})
    url = aiconfig.base_url() + '/models'
    headers = {'Authorization': f'Bearer {aiconfig.api_key()}'}
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as s, s.get(url, headers=headers, timeout=timeout) as r:
            data = await r.json()
        models = sorted(m.get('id', '') for m in data.get('data', []) if m.get('id'))
        return web.json_response({'success': True, 'models': models})
    except Exception as e:  # noqa: BLE001
        return web.json_response({'success': False, 'error': str(e), 'models': []})


async def _get_sessions(request: web.Request):
    return web.json_response({'success': True, 'sessions': _store().list_sessions()})


async def _create_session(request: web.Request):
    sess = _store().create_session()
    return web.json_response({'success': True, 'session': {'id': sess['id'], 'title': sess.get('title', '')}})


async def _delete_session(request: web.Request):
    body = await _json(request)
    ok = _store().delete_session(str(body.get('session_id', '')))
    return web.json_response({'success': ok})


async def _get_history(request: web.Request):
    sid = request.query.get('session_id', '')
    msgs = _store().get_messages(sid)
    # 仅返回对前端有意义的字段
    view = []
    for m in msgs:
        role = m.get('role')
        if role == 'user':
            view.append({'role': 'user', 'content': m.get('content', '')})
        elif role == 'assistant' and m.get('content'):
            view.append({'role': 'assistant', 'content': m.get('content', '')})
    return web.json_response({'success': True, 'messages': view})


async def _post_chat(request: web.Request):
    body = await _json(request)
    message = str(body.get('message', '')).strip()
    model = str(body.get('model', '') or '')
    sid = str(body.get('session_id', '') or '')
    if not message:
        return web.json_response({'success': False, 'error': '消息为空'}, status=400)
    sess = _store().ensure_session(sid)
    result = await agentmod.run_agent(_store(), sess['id'], message, model)
    return web.json_response({
        'success': result.get('ok', False),
        'session_id': sess['id'],
        'message': result.get('message', ''),
        'iterations': result.get('iterations', 0),
    })


async def _get_calls(request: web.Request):
    try:
        limit = min(int(request.query.get('limit', 300)), 1000)
    except ValueError:
        limit = 300
    return web.json_response({'success': True, 'events': _store().recent_events(limit)})


async def _clear(request: web.Request):
    body = await _json(request)
    ok = _store().clear_session(str(body.get('session_id', '')))
    return web.json_response({'success': ok})


async def _stream(request: web.Request):
    if not auth.validate_token(request):
        return web.Response(status=401, text='Unauthorized')
    resp = web.StreamResponse()
    resp.headers['Content-Type'] = 'text/event-stream'
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['X-Accel-Buffering'] = 'no'
    await resp.prepare(request)
    store = _store()
    q = store.subscribe()
    with contextlib.suppress(Exception):
        await resp.write(b'data: {"type":"init"}\n\n')
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=25)
                payload = json.dumps(event, ensure_ascii=False, default=str)
                await resp.write(f'data: {payload}\n\n'.encode())
            except asyncio.TimeoutError:
                await resp.write(b': keepalive\n\n')
    except (asyncio.CancelledError, ConnectionResetError, Exception):
        pass
    finally:
        store.unsubscribe(q)
    return resp


async def _json(request: web.Request) -> dict:
    try:
        return await request.json()
    except Exception:  # noqa: BLE001
        return {}
