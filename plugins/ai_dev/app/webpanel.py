"""ai_dev Web 面板路由 (插件侧边栏页面 + /api/ext/aidev/* 接口)

通过框架的 register_route 机制注册, 统一挂在 /api/ext/aidev/ 前缀下,
热重载/卸载即时生效。面板 HTML 由 register_page 提供, 在侧边栏以
iframe 渲染。鉴权复用框架 web.auth (Bearer token / ?token=)。

接口:
- GET  /api/ext/aidev/config         面板配置 (不含 key 明文)
- GET  /api/ext/aidev/models         代理上游模型列表
- GET  /api/ext/aidev/sessions       会话列表
- POST /api/ext/aidev/sessions       新建会话
- POST /api/ext/aidev/sessions/delete  删除会话
- GET  /api/ext/aidev/history        某会话历史
- POST /api/ext/aidev/chat           发送消息 (执行 Agent)
- GET  /api/ext/aidev/calls          最近事件 (完整调用 + 日志)
- GET  /api/ext/aidev/stream         SSE 实时事件流
- POST /api/ext/aidev/clear          清空会话
"""

import asyncio
import contextlib
import json
import logging

import aiohttp
from aiohttp import web

import web.auth as auth
from core.plugin.web_pages import register_route
from plugins.ai_dev.app import aiconfig
from plugins.ai_dev.app import agent as agentmod

log = logging.getLogger('ElainaBot.plugins.ai_dev')

_PREFIX = '/api/ext/aidev'


def _store():
    """从 Application 实例获取 AIStore 单例 (热重载安全)"""
    from core.application import get_app
    app = get_app()
    return getattr(app, '_ai_dev_store', None) if app else None


def register_routes():
    """通过框架 register_route 注册全部 /api/ext/aidev/* 路由 (热重载安全)。"""
    register_route('GET', _PREFIX + '/config', _get_config)
    register_route('POST', _PREFIX + '/config', _set_config)
    register_route('GET', _PREFIX + '/models', _get_models)
    register_route('GET', _PREFIX + '/sessions', _get_sessions)
    register_route('POST', _PREFIX + '/sessions', _create_session)
    register_route('POST', _PREFIX + '/sessions/delete', _delete_session)
    register_route('GET', _PREFIX + '/history', _get_history)
    register_route('POST', _PREFIX + '/chat', _post_chat)
    register_route('GET', _PREFIX + '/calls', _get_calls)
    register_route('POST', _PREFIX + '/clear', _clear)
    register_route('GET', _PREFIX + '/stream', _stream)
    log.info('AI 开发面板路由已注册: /api/ext/aidev/*')


async def _get_config(request: web.Request):
    return web.json_response({'success': True, 'config': aiconfig.public_config()})


async def _set_config(request: web.Request):
    """保存面板自定义配置 (base_url / api_key / model 等), 立即生效。

    api_key 为空字符串表示「不修改」(避免前端因不回显密钥而误清空); 传 null
    表示清除该覆盖, 回退到 settings.yaml / 环境变量。
    """
    body = await _json(request)
    updates = {}
    for k in ('base_url', 'model', 'temperature', 'max_iterations', 'history_limit', 'system_prompt', 'reasoning_effort'):
        if k in body:
            updates[k] = body[k]
    # api_key: 仅当显式提供且非空白时才更新; null 清除
    if 'api_key' in body:
        ak = body['api_key']
        if ak is None:
            updates['api_key'] = None
        elif isinstance(ak, str) and ak.strip() != '':
            updates['api_key'] = ak.strip()
    aiconfig.set_runtime(updates)
    return web.json_response({'success': True, 'config': aiconfig.public_config()})


async def _get_models(request: web.Request):
    # 允许用 query 里临时传入的 base_url/api_key 试连 (面板「获取模型」按钮),
    # 未传则回退到已保存配置。
    base = (request.query.get('base_url') or '').strip().rstrip('/') or aiconfig.base_url()
    key = (request.query.get('api_key') or '').strip() or aiconfig.api_key()
    if not key:
        return web.json_response({'success': False, 'error': '未配置 api_key', 'models': []})
    url = base + '/models'
    headers = {'Authorization': f'Bearer {key}'}
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession() as s, s.get(url, headers=headers, timeout=timeout) as r:
            data = await r.json()
        if not isinstance(data, dict) or 'data' not in data:
            return web.json_response({'success': False, 'error': f'上游返回异常: {str(data)[:200]}', 'models': []})
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
    return web.json_response({'success': True, 'messages': view, 'events': _store().session_events(sid)})


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
        'reasoning': result.get('reasoning', ''),
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
