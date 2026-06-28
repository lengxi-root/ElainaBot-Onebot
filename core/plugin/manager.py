"""插件管理器"""

import importlib
import importlib.util
import json
import os
import sys

from core.base.logger import PLUGIN, get_logger, report_error

log = get_logger(PLUGIN, '管理器')


class PluginManager:
    """插件管理器 — 发现/加载/分发"""

    def __init__(self, plugins_dir: str):
        self._dir = os.path.abspath(plugins_dir)
        self._plugins = {}  # {name: module}
        self._handlers = []  # [(pattern, handler, plugin_name)]
        self._event_handlers = []  # [(event_type, handler, plugin_name)]
        self._disabled_file = os.path.join(self._dir, 'plugins_disabled.json')
        self._disabled = self._load_disabled()

    @property
    def plugins(self) -> dict:
        return self._plugins

    @property
    def handler_count(self) -> int:
        return len(self._handlers) + len(self._event_handlers)

    # ── 禁用状态持久化 ──

    def _load_disabled(self) -> set:
        try:
            if os.path.isfile(self._disabled_file):
                with open(self._disabled_file, encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return set(data)
        except Exception:
            pass
        return set()

    def _save_disabled(self):
        try:
            with open(self._disabled_file, 'w', encoding='utf-8') as f:
                json.dump(sorted(self._disabled), f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.warning(f'保存插件禁用状态失败: {e}')

    def get_disabled_plugins(self) -> set:
        return set(self._disabled)

    def is_disabled(self, name: str) -> bool:
        return name in self._disabled

    def enable_plugin(self, key: str):
        name = key.split('/')[0]
        self._disabled.discard(name)
        self._disabled.discard(key)
        self._save_disabled()

    def disable_plugin(self, key: str):
        name = key.split('/')[0]
        self._disabled.add(name)
        self._save_disabled()

    def get_web_plugin_info(self) -> dict:
        """构建 {目录名: {commands, description, meta}}"""
        info = {}
        for name, module in self._plugins.items():
            commands = []
            for pattern, _h, n in self._handlers:
                if n == name and pattern:
                    # Web 面板期望命令为对象 {pattern, name, desc, owner_only, group_only}
                    commands.append({
                        'pattern': pattern,
                        'name': '',
                        'desc': '',
                        'owner_only': False,
                        'group_only': False,
                    })
            meta = getattr(module, '__plugin_meta__', {}) or {}
            info[name] = {
                'commands': commands,
                'description': meta.get('description', '') if isinstance(meta, dict) else '',
                'meta': meta if isinstance(meta, dict) else {},
            }
        return info

    async def load_all(self):
        """加载所有插件"""
        if not os.path.isdir(self._dir):
            os.makedirs(self._dir, exist_ok=True)
            return

        for name in sorted(os.listdir(self._dir)):
            plugin_dir = os.path.join(self._dir, name)
            if not os.path.isdir(plugin_dir) or name.startswith('_'):
                continue
            if name in self._disabled:
                continue
            await self._load_plugin(name, plugin_dir)

        log.info(f'加载插件: {len(self._plugins)} 个, {self.handler_count} 个处理器')

    async def _load_plugin(self, name: str, plugin_dir: str):
        """加载单个插件"""
        # 查找入口文件
        entry = None
        for fname in (f'{name}.py', 'main.py', '__init__.py'):
            path = os.path.join(plugin_dir, fname)
            if os.path.isfile(path):
                entry = path
                break

        if not entry:
            return

        try:
            mod_name = f'plugins.{name}'
            spec = importlib.util.spec_from_file_location(
                mod_name, entry, submodule_search_locations=[plugin_dir]
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            self._plugins[name] = module

            # 注册处理器
            handlers = getattr(module, '__handlers__', [])
            for h in handlers:
                self._handlers.append((h.get('pattern'), h.get('handler'), name))

            event_handlers = getattr(module, '__event_handlers__', [])
            for h in event_handlers:
                self._event_handlers.append((h.get('event_type'), h.get('handler'), name))

        except Exception as e:
            report_error(PLUGIN, name, e)

    async def reload_plugin(self, name: str) -> bool:
        """重载插件"""
        plugin_dir = os.path.join(self._dir, name)
        if not os.path.isdir(plugin_dir):
            return False

        # 移除旧处理器
        self._handlers = [(p, h, n) for p, h, n in self._handlers if n != name]
        self._event_handlers = [(e, h, n) for e, h, n in self._event_handlers if n != name]
        self._plugins.pop(name, None)
        sys.modules.pop(f'plugins.{name}', None)

        await self._load_plugin(name, plugin_dir)
        return name in self._plugins

    def dispatch(self, event):
        """分发事件到插件"""
        # 消息事件 — 匹配 pattern
        if event.post_type == 'message':
            content = event.content
            for pattern, handler, plugin_name in self._handlers:
                try:
                    import re
                    if pattern and re.match(pattern, content):
                        handler(event)
                except Exception as e:
                    report_error(PLUGIN, plugin_name, e)

        # 通用事件处理
        event_type = f'{event.post_type}'
        if hasattr(event, 'notice_type'):
            event_type = f'notice.{event.notice_type}'
        elif hasattr(event, 'request_type'):
            event_type = f'request.{event.request_type}'

        for etype, handler, plugin_name in self._event_handlers:
            if etype == event_type or etype == '*':
                try:
                    handler(event)
                except Exception as e:
                    report_error(PLUGIN, plugin_name, e)

    def list_plugins(self) -> list:
        """列出所有插件"""
        result = []
        if not os.path.isdir(self._dir):
            return result
        for name in sorted(os.listdir(self._dir)):
            plugin_dir = os.path.join(self._dir, name)
            if not os.path.isdir(plugin_dir) or name.startswith('_'):
                continue
            result.append({
                'name': name,
                'loaded': name in self._plugins,
                'handlers': len([h for _, h, n in self._handlers if n == name]),
            })
        return result

    async def reload(self, name: str) -> bool:
        """重载插件 (web 面板别名)"""
        return await self.reload_plugin(name)

    async def unload(self, name: str) -> bool:
        """卸载插件 (移除处理器 + 模块)"""
        self._handlers = [(p, h, n) for p, h, n in self._handlers if n != name]
        self._event_handlers = [(e, h, n) for e, h, n in self._event_handlers if n != name]
        self._plugins.pop(name, None)
        sys.modules.pop(f'plugins.{name}', None)
        return True

    def get_plugin_bots(self) -> dict:
        return {}

    def set_plugin_bots(self, data: dict):
        pass

    def start_watcher(self):
        """启动文件监视（简化版，不实现热重载）"""
        pass

    def stop_watcher(self):
        pass
