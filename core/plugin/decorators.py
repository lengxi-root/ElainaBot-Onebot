"""插件装饰器"""

import re
from typing import Callable, Optional


def on_command(command: str, aliases: list = None):
    """命令匹配装饰器"""
    patterns = [re.escape(command)]
    if aliases:
        patterns.extend(re.escape(a) for a in aliases)
    pattern = f'^({"|".join(patterns)})(\\s+.*)?$'

    def decorator(func: Callable):
        if not hasattr(func, '__plugin_handlers__'):
            func.__plugin_handlers__ = []
        func.__plugin_handlers__.append({
            'type': 'command',
            'pattern': pattern,
            'handler': func,
        })
        return func
    return decorator


def on_regex(pattern: str):
    """正则匹配装饰器"""
    def decorator(func: Callable):
        if not hasattr(func, '__plugin_handlers__'):
            func.__plugin_handlers__ = []
        func.__plugin_handlers__.append({
            'type': 'regex',
            'pattern': pattern,
            'handler': func,
        })
        return func
    return decorator


def on_event(event_type: str = '*'):
    """事件监听装饰器"""
    def decorator(func: Callable):
        if not hasattr(func, '__event_handlers__'):
            func.__event_handlers__ = []
        func.__event_handlers__.append({
            'type': 'event',
            'event_type': event_type,
            'handler': func,
        })
        return func
    return decorator
