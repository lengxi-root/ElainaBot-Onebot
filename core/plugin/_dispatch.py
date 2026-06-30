"""事件分发 — PluginManager 的 Mixin (OneBot v11 适配)"""

import asyncio
import re
import time

from core.base.logger import PLUGIN, get_logger, report_error

log = get_logger(PLUGIN, '管理器')


class _DispatchMixin:
    """异步事件分发"""

    def _build_dispatch_index(self):
        """按 priority 排序 handler 列表"""
        self._all_handlers = sorted(self._all_handlers, key=lambda h: -h['priority'])
        self._all_interceptors = sorted(self._all_interceptors, key=lambda i: -i['priority'])

    async def dispatch(self, event) -> bool:
        """异步分发事件到匹配的处理器

        Args:
            event: OneBotEvent (MessageEvent / NoticeEvent / ...)

        Returns:
            是否有处理器匹配并执行
        """
        content = event.content if hasattr(event, 'content') else ''
        post_type = event.post_type

        # 拦截器
        for ic in self._all_interceptors:
            try:
                r = await ic['func'](event) if ic['is_coro'] else await asyncio.to_thread(ic['func'], event)
                if r is True:
                    return True
            except Exception as e:
                report_error(PLUGIN, ic.get('_plugin', '?'), e)

        # 消息事件 — 匹配 pattern
        if post_type == 'message':
            for h in self._all_handlers:
                # 事件类型过滤
                if h['event_types'] and post_type not in h['event_types']:
                    continue
                # 场景过滤
                if h['group_only'] and not getattr(event, 'is_group', False):
                    continue
                if h['private_only'] and not getattr(event, 'is_private', False):
                    continue
                # 权限检查
                if h['owner_only'] and not self._is_owner(event):
                    continue
                # 正则匹配
                m = h['compiled'].search(content)
                if not m:
                    continue
                # 冷却检查
                if h['cooldown'] > 0:
                    key = f"{h['name']}:{getattr(event, 'user_id', '')}"
                    now = time.time()
                    if now - self._cooldowns.get(key, 0) < h['cooldown']:
                        continue
                    self._cooldowns[key] = now
                # 异步执行
                asyncio.create_task(self._run_handler(h, event, m))
                return True

        # 通知/请求事件 — 匹配 event_type
        else:
            event_type = post_type
            if hasattr(event, 'notice_type'):
                event_type = f'notice.{event.notice_type}'
            elif hasattr(event, 'request_type'):
                event_type = f'request.{event.request_type}'

            for h in self._all_handlers:
                if h['event_types'] and event_type not in h['event_types']:
                    continue
                # 对非消息事件也尝试正则匹配 (pattern='.*' 可匹配所有)
                m = h['compiled'].search(content or event_type)
                if not m:
                    continue
                asyncio.create_task(self._run_handler(h, event, m))
                return True

        return False

    async def _run_handler(self, h, event, match):
        """执行单个处理器 (带超时和异常捕获)"""
        plugin_name = h['name'] or h.get('_plugin', '')
        try:
            fn = h['func']
            async with asyncio.timeout(300):
                if h['is_coro']:
                    await fn(event, match)
                else:
                    await asyncio.to_thread(fn, event, match)
        except TimeoutError:
            report_error(PLUGIN, plugin_name, f'处理器 [{h["name"]}] 超时(300s)')
        except Exception as e:
            report_error(
                PLUGIN, plugin_name, e,
                context={
                    'handler': h['name'],
                    'user_id': str(getattr(event, 'user_id', '')),
                    'group_id': str(getattr(event, 'group_id', '')),
                    'content': (event.content if hasattr(event, 'content') else '')[:200],
                },
            )
