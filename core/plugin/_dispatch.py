"""事件分发 — PluginManager 的 Mixin (OneBot v11 适配)"""

import asyncio
import time

from core.base.logger import PLUGIN, get_logger, report_error

log = get_logger(PLUGIN, '管理器')


class _DispatchMixin:
    """异步事件分发"""

    def _build_dispatch_index(self):
        """按 priority 排序并预分桶

        - _msg_handlers: 可处理 message 事件的处理器
        - _generic_handlers: 未声明 event_types 的处理器 (对所有非消息事件均候选)
        - _typed_handlers: {event_type: [handler...]} 声明了具体事件类型的处理器
        分桶后, 每条事件只需遍历相关子集而非全部处理器。
        """
        self._all_handlers = sorted(self._all_handlers, key=lambda h: -h['priority'])
        self._all_interceptors = sorted(self._all_interceptors, key=lambda i: -i['priority'])

        msg, generic, typed = [], [], {}
        for h in self._all_handlers:
            event_types = h['event_types']
            if not event_types:
                msg.append(h)
                generic.append(h)
                continue
            if 'message' in event_types:
                msg.append(h)
            for et in event_types:
                if et != 'message':
                    typed.setdefault(et, []).append(h)
        self._msg_handlers = msg
        self._generic_handlers = generic
        self._typed_handlers = typed

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

        # 消息事件 — 仅遍历消息桶
        if post_type == 'message':
            for h in self._msg_handlers:
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

        # 通知/请求/元事件 — 候选 = 通用桶 + 该事件类型桶, 按优先级合并
        else:
            event_type = post_type
            if hasattr(event, 'notice_type'):
                event_type = f'notice.{event.notice_type}'
            elif hasattr(event, 'request_type'):
                event_type = f'request.{event.request_type}'

            typed = self._typed_handlers.get(event_type)
            if typed and self._generic_handlers:
                candidates = sorted((*self._generic_handlers, *typed), key=lambda h: -h['priority'])
            else:
                candidates = typed or self._generic_handlers

            for h in candidates:
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
