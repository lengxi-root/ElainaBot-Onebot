"""
示例插件 — 展示 v2 异步插件开发方式

插件使用 @handler 装饰器注册处理器, 所有处理函数均为 async def(event, match) 签名。
"""

from core.plugin.decorators import handler, on_load, on_unload


@on_load
async def init():
    """插件加载时执行"""
    pass


@on_unload
async def cleanup():
    """插件卸载时执行"""
    pass


@handler(r'^ping$', name='ping', desc='响应 ping 命令')
async def handle_ping(event, match):
    """响应 ping 命令"""
    await event.reply('pong')


@handler(r'^echo\s+(.+)$', name='echo', desc='回显用户输入')
async def handle_echo(event, match):
    """回显用户输入的内容"""
    text = match.group(1)
    await event.reply(text)
