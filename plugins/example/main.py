"""
示例插件 — 展示 OneBot 插件开发方式
"""

__handlers__ = [
    {
        'pattern': r'^ping$',
        'handler': None,  # will be set below
    },
]

__event_handlers__ = []


def handle_ping(event):
    """响应 ping 命令"""
    event.reply('pong')


# 注册
__handlers__[0]['handler'] = handle_ping
