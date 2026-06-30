"""离线测试 AstrBot 基座: 加载 plugins/astrbot, 喂合成事件, 捕获出站 API 调用。

用法: python tools/astrbot_harness.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import core.onebot.api as onebot_api  # noqa: E402
from core.base.config import cfg  # noqa: E402
from core.onebot.event import MessageEvent  # noqa: E402
from core.plugin.manager import PluginManager  # noqa: E402

OWNER_ID = "10001"
SENT: list[dict] = []


class FakeAPI:
    """记录所有出站调用, 返回合理的假数据。"""

    async def call_api(self, action, params=None, self_id=None):
        SENT.append({"action": action, "params": params or {}})
        if action == "get_group_info":
            return {"data": {"group_id": params.get("group_id"), "group_name": "测试群"}}
        if action == "get_login_info":
            return {"data": {"user_id": 99999, "nickname": "Bot"}}
        return {"status": "ok", "retcode": 0, "data": {"message_id": int(time.time())}}

    async def send_group_msg(self, group_id, message, **kw):
        return await self.call_api("send_group_msg", {"group_id": group_id, "message": message, **kw})

    async def send_private_msg(self, user_id, message, **kw):
        return await self.call_api("send_private_msg", {"user_id": user_id, "message": message, **kw})

    async def send_group_forward_msg(self, group_id, messages, **kw):
        return await self.call_api("send_group_forward_msg", {"group_id": group_id, "messages": messages, **kw})

    async def send_private_forward_msg(self, user_id, messages, **kw):
        return await self.call_api("send_private_forward_msg", {"user_id": user_id, "messages": messages, **kw})

    def __getattr__(self, name):
        async def _f(*a, **k):
            return await self.call_api(name, dict(enumerate(a)) | k)
        return _f


_FAKE = FakeAPI()
onebot_api.get_api = lambda: _FAKE  # type: ignore


def make_event(text, *, group_id="200", user_id="300", self_id="99999", segments=None):
    msg = segments or [{"type": "text", "data": {"text": text}}]
    data = {
        "post_type": "message",
        "message_type": "group" if group_id else "private",
        "message": msg,
        "raw_message": text,
        "user_id": int(user_id),
        "self_id": int(self_id),
        "message_id": int(time.time() * 1000) % 1_000_000,
        "sender": {"user_id": int(user_id), "nickname": "测试用户"},
        "time": int(time.time()),
    }
    if group_id:
        data["group_id"] = int(group_id)
    ev = MessageEvent(data)
    ev._api = _FAKE
    return ev


async def feed(mgr, text, *, settle=0.05, max_wait=2.0, want_kind=None, **kw):
    """喂一条消息并收集出站调用。

    want_kind: 指定要等到的消息段类型 (如 'image'); 否则出现任意出站即返回。
    截图类插件会先发别的 API(如 get_login_info), 故需按 want_kind 等待图片。
    """
    SENT.clear()
    ev = make_event(text, **kw)
    await mgr.dispatch(ev)
    steps = max(1, int(max_wait / 0.02))

    def _has_kind():
        for s in SENT:
            msg = s["params"].get("message", [])
            if isinstance(msg, list) and any(
                isinstance(x, dict) and x.get("type") == want_kind for x in msg):
                return True
        return False

    for _ in range(steps):
        await asyncio.sleep(0.02)
        if (want_kind and _has_kind()) or (not want_kind and SENT):
            break
    await asyncio.sleep(settle)
    return list(SENT)


def texts(sent):
    """从出站消息段里提取所有文本, 便于断言。"""
    out = []
    for s in sent:
        msg = s["params"].get("message", [])
        if isinstance(msg, list):
            for seg in msg:
                if isinstance(seg, dict) and seg.get("type") == "text":
                    out.append(seg["data"].get("text", ""))
        elif isinstance(msg, str):
            out.append(msg)
    return " | ".join(out)


def _write_base_config(apps_override: dict | None):
    """把 apps 配置覆盖写进基座 data/config.json (在加载前生效)。"""
    import json
    data_dir = os.path.join(_ROOT, "plugins", "astrbot", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "config.json")
    base = {"command_prefixes": {}, "disabled_apps": [], "apps": {}}
    base["apps"] = apps_override or {}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=2)


async def load_base(apps_override: dict | None = None) -> PluginManager:
    cfg._data["settings"] = {
        "owner": {"ids": [OWNER_ID]},
        "pip": {"auto_install": False, "mirror": ""},
    }
    _write_base_config(apps_override)
    mgr = PluginManager(os.path.join(_ROOT, "plugins"))
    mgr.set_owner_ids([OWNER_ID])
    await mgr._load_large("astrbot")
    mgr._rebuild_handler_list()
    return mgr


async def main():
    mgr = await load_base()
    print(f"handlers: {mgr.handler_count}")
    from plugins.astrbot.runtime import state
    print("plugins:", [s.name for s in state.PLUGIN_SPECS])

    cases = [
        ("hello", "你好"),
        ("add 3 5", "3+5=8"),
        ("echo 测试文本", "测试文本"),
        ("喵喵喵", "喵喵喵"),
    ]
    ok = 0
    for text, expect in cases:
        sent = await feed(mgr, text)
        got = texts(sent)
        passed = expect in got
        ok += passed
        print(f"[{'PASS' if passed else 'FAIL'}] {text!r:20} -> {got!r}")
    print(f"\n{ok}/{len(cases)} passed")


if __name__ == "__main__":
    asyncio.run(main())
