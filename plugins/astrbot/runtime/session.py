"""session_waiter 兼容层: 用框架 @interceptor 按「会话+用户」拦截下一条消息实现多步等待。"""

from __future__ import annotations

import asyncio
import inspect

from . import state

log = state.log

# 会话key -> asyncio.Queue
_WAITERS: dict[str, asyncio.Queue] = {}


def _session_key(elaina_event) -> str:
    self_id = str(getattr(elaina_event, "self_id", "") or "")
    uid = str(getattr(elaina_event, "user_id", "") or "")
    gid = getattr(elaina_event, "group_id", None) or ""
    scene = f"group:{gid}" if gid else "c2c"
    return f"{self_id}|{scene}|{uid}"


class SessionController:
    def __init__(self, default_timeout: float):
        self._stopped = False
        self._timeout = default_timeout
        self._default_timeout = default_timeout

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def timeout(self) -> float:
        return self._timeout

    def stop(self, *_a, **_k):
        self._stopped = True

    def keep(self, timeout: float = None, reset_timeout: bool = False, *_a, **_k):
        if timeout is not None:
            self._timeout = timeout

    @staticmethod
    def get_session(*_a, **_k):
        return None


def session_waiter(timeout: float = 60, record_history: bool = False, *_a, **_k):
    """装饰 waiter(controller, event); 返回可 `await waiter(first_event)` 的协程。"""
    def deco(func):
        async def _runner(first_event):
            from .events import AstrMessageEvent
            elaina = getattr(first_event, "message_obj", None)
            elaina = getattr(elaina, "raw_message", None) or getattr(first_event, "_e", first_event)
            key = _session_key(getattr(first_event, "_e", first_event))
            queue: asyncio.Queue = asyncio.Queue()
            _WAITERS[key] = queue
            controller = SessionController(timeout)
            try:
                while not controller.stopped:
                    try:
                        next_event = await asyncio.wait_for(queue.get(), timeout=controller.timeout)
                    except TimeoutError:
                        raise TimeoutError("session_waiter timeout") from None
                    try:
                        res = func(controller, AstrMessageEvent(next_event))
                        if inspect.isawaitable(res):
                            await res
                    except TimeoutError:
                        raise
                    except Exception as e:
                        log.error(f"[astrbot基座] session_waiter 处理消息异常: {e}", exc_info=True)
                        controller.stop()
            finally:
                if _WAITERS.get(key) is queue:
                    _WAITERS.pop(key, None)
        return _runner
    return deco


async def _session_interceptor(event):
    """命中等待中的会话则把消息投给 waiter 并消费, 否则放行。"""
    if not _WAITERS:
        return False
    if getattr(event, "post_type", "") != "message":
        return False
    queue = _WAITERS.get(_session_key(event))
    if queue is None:
        return False
    await queue.put(event)
    return True


def register_interceptor():
    try:
        from core.plugin.decorators import interceptor
    except Exception as e:
        log.warning(f"[astrbot基座] 框架无 interceptor, session_waiter 不可用: {e}")
        return
    interceptor(priority=150)(_session_interceptor)
    log.info("[astrbot基座] 已注册 session_waiter 拦截器")
