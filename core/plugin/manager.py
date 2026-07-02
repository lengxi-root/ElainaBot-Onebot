"""插件管理器 — 加载/卸载/分发/热重载 (v2 异步架构)"""

import asyncio
import json
import os
from collections import OrderedDict

from core.base.logger import PLUGIN, get_logger
from core.plugin._dispatch import _DispatchMixin
from core.plugin._loader import _LoaderMixin
from core.plugin._watcher import _WatcherMixin

log = get_logger(PLUGIN, '管理器')


class PluginManager(_LoaderMixin, _WatcherMixin, _DispatchMixin):
    """插件管理器 — 通过 Mixin 组合加载/分发/监视能力"""

    def __init__(self, plugins_dir: str):
        self._dir = os.path.abspath(plugins_dir)
        self._plugins = OrderedDict()
        self._all_handlers = []
        self._all_interceptors = []
        # 分发索引桶 (按事件类型预分组, 避免每条事件遍历全部处理器)
        self._msg_handlers = []
        self._generic_handlers = []
        self._typed_handlers = {}
        self._disabled_plugins = set()
        self._cooldowns = {}  # {handler_key: last_trigger_time}
        self._lock = asyncio.Lock()
        self._file_mtimes = {}
        self._watcher_task = None
        self._watcher_running = False
        self._owner_ids = []
        self._load_disabled_plugins()

    @property
    def plugins(self) -> dict:
        return dict(self._plugins)

    @property
    def handler_count(self) -> int:
        return len(self._all_handlers)

    # ==================== 索引构建 ====================

    def _rebuild_handler_list(self):
        handlers, intercepts = [], []
        for plugin in self._plugins.values():
            if not plugin.enabled:
                continue
            for h in plugin.handlers:
                h['_plugin'] = plugin.name
                handlers.append(h)
            for ic in plugin.interceptors:
                ic['_plugin'] = plugin.name
                intercepts.append(ic)
        self._all_handlers = handlers
        self._all_interceptors = intercepts
        self._build_dispatch_index()

    # ==================== 权限 ====================

    def set_owner_ids(self, owner_ids: list):
        self._owner_ids = [str(uid) for uid in owner_ids]

    def _is_owner(self, event) -> bool:
        uid = str(getattr(event, 'user_id', '') or '')
        return uid in self._owner_ids if self._owner_ids else False

    # ==================== 管理接口 ====================

    def enable_plugin(self, name):
        changed = name in self._disabled_plugins
        self._disabled_plugins.discard(name)
        if changed:
            self._save_disabled_plugins()
        if name in self._plugins:
            self._plugins[name].enabled = True
            self._rebuild_handler_list()
            return True
        return changed

    def disable_plugin(self, name):
        changed = name not in self._disabled_plugins
        self._disabled_plugins.add(name)
        if changed:
            self._save_disabled_plugins()
        if name in self._plugins:
            self._plugins[name].enabled = False
            self._rebuild_handler_list()
            return True
        return changed

    def is_disabled(self, name: str) -> bool:
        return name in self._disabled_plugins

    def get_disabled_plugins(self) -> set:
        return set(self._disabled_plugins)

    def get_plugin_list(self):
        return [
            {
                'name': p.name,
                'enabled': p.enabled,
                'disabled_persist': p.name in self._disabled_plugins,
                'handlers': [h['name'] for h in p.handlers],
                'handler_count': len(p.handlers),
                'load_time': round(p.load_time, 3),
                'error': p.error,
                'is_large': p.is_large,
            }
            for p in self._plugins.values()
        ]

    def get_command_list(self):
        return [
            {
                'name': h['name'],
                'pattern': h['pattern'],
                'desc': h['desc'],
                'plugin': h.get('_plugin', ''),
                'owner_only': h['owner_only'],
                'priority': h['priority'],
            }
            for h in self._all_handlers
        ]

    def get_web_plugin_info(self) -> dict:
        """构建 {目录名: {commands, description, meta}}"""
        result = {}
        for p in self._plugins.values():
            cmds = [
                {
                    'name': h.get('name', ''),
                    'pattern': h.get('pattern', ''),
                    'desc': h.get('desc', ''),
                    'owner_only': h.get('owner_only', False),
                    'group_only': h.get('group_only', False),
                }
                for h in p.handlers
            ]
            desc = ''
            if p.module and getattr(p.module, '__doc__', None):
                desc = p.module.__doc__.strip().split('\n')[0]
            result[p.name] = {'commands': cmds, 'description': desc, 'meta': p.meta}
        return result

    def list_plugins(self) -> list:
        """列出所有可发现的插件 (含未加载的)"""
        result = []
        if not os.path.isdir(self._dir):
            return result
        for name in sorted(os.listdir(self._dir)):
            plugin_dir = os.path.join(self._dir, name)
            if not os.path.isdir(plugin_dir) or name.startswith(('_', '.')):
                continue
            info = self._plugins.get(name)
            result.append({
                'name': name,
                'loaded': name in self._plugins,
                'enabled': info.enabled if info else name not in self._disabled_plugins,
                'handlers': len(info.handlers) if info else 0,
            })
        return result

    def get_plugin_bots(self) -> dict:
        return {}

    def set_plugin_bots(self, data: dict):
        pass

    # ==================== 禁用持久化 ====================

    def _load_disabled_plugins(self):
        path = os.path.join(self._dir, 'plugins_disabled.json')
        if not os.path.isfile(path):
            return
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._disabled_plugins = set(data)
        except Exception as e:
            log.warning(f'加载禁用插件列表失败: {e}')

    def _save_disabled_plugins(self):
        path = os.path.join(self._dir, 'plugins_disabled.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(sorted(self._disabled_plugins), f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f'保存禁用插件列表失败: {e}')
