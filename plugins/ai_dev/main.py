"""AI 开发助手插件 (ai_dev)

接入 OpenAI 兼容接口, 让 AI 通过工具调用直接编写/修改框架插件、热重载自测、
读写框架配置、检查系统状态, 并提供一个亮色 Web 面板 (/ai/) 与 AI 对话、
实时查看完整工具调用与日志。

QQ 内使用 (仅主人): 发送  ai <你的需求>   即可触发 AI 开发助手。
Web 面板:        http://<host>:<port>/ai/  (用框架管理员密码登录)
"""

import logging
import os

from core.plugin.decorators import handler, on_load, on_unload
from plugins.ai_dev import agent as agentmod
from plugins.ai_dev import aiconfig
from plugins.ai_dev import webpanel
from plugins.ai_dev.store import AIStore

__plugin_meta__ = {
    'name': 'AI 开发助手',
    'author': 'Devin',
    'description': '接入 OpenAI 让 AI 自主编写/修改框架插件并提供亮色 Web 面板',
    'version': '1.0.0',
}

log = logging.getLogger('ElainaBot.plugins.ai_dev')

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


@on_load
async def init():
    """挂载 Web 面板路由 + 初始化存储 (路由只挂一次, 热重载安全)"""
    from core.application import get_app
    app = get_app()
    if not app:
        log.warning('ai_dev: 无法获取 Application 实例, Web 面板未挂载')
        return

    # AIStore 单例挂在 Application 上, 跨热重载保持同一实例
    if getattr(app, '_ai_dev_store', None) is None:
        app._ai_dev_store = AIStore(os.path.join(_PLUGIN_DIR, 'data'))
    app._ai_dev_plugin_dir = _PLUGIN_DIR

    if getattr(app, '_ai_dev_mounted', False):
        return
    http = getattr(app, '_http_server', None)
    aio = getattr(http, 'app', None) if http else None
    if aio is None:
        log.warning('ai_dev: HTTP 服务尚未就绪, Web 面板未挂载')
        return
    try:
        webpanel.register_routes(aio)
        app._ai_dev_mounted = True
    except RuntimeError as e:
        # 服务已启动 (路由冻结) — 多见于运行时热重载, 路由此前已挂载
        log.debug(f'ai_dev: 路由挂载跳过 ({e})')


@on_unload
async def cleanup():
    pass


@handler(r'^ai\s+([\s\S]+)$', name='ai', desc='AI 开发助手: ai <需求> (仅主人)', owner_only=True)
async def handle_ai(event, match):
    """主人在 QQ 中直接驱动 AI 开发助手"""
    if not aiconfig.is_configured():
        await event.reply('AI 未配置: 请在 config/settings.yaml 的 ai.api_key 填入密钥, 或设置环境变量 AI_DEV_API_KEY')
        return
    prompt = match.group(1).strip()
    from core.application import get_app
    store = getattr(get_app(), '_ai_dev_store', None)
    if store is None:
        await event.reply('AI 存储未初始化')
        return
    sid = f'qq_{event.user_id}'
    if store.get_session(sid) is None:
        store._sessions[sid] = {'id': sid, 'title': f'QQ {event.user_id}', 'created': 0, 'updated': 0, 'messages': []}
    await event.reply('已收到, AI 正在处理...')
    try:
        result = await agentmod.run_agent(store, sid, prompt)
    except Exception as e:  # noqa: BLE001
        await event.reply(f'AI 执行出错: {e}')
        return
    text = result.get('message') or '(无返回)'
    await event.reply(text[:2000])
