"""插件系统 — v2 异步架构"""

from core.plugin.decorators import handler, interceptor, on_load, on_unload
from core.plugin.manager import PluginManager

__all__ = ['handler', 'interceptor', 'on_load', 'on_unload', 'PluginManager']
