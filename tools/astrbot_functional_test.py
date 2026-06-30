"""逐插件功能测试: 加载基座后, 给每个 app 发代表性指令(含多步流程), 检查出站消息。

用法: python tools/astrbot_functional_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import tools.astrbot_harness as h  # noqa: E402


def _segs(sent):
    kinds = []
    for s in sent:
        msg = s["params"].get("message", [])
        if isinstance(msg, list):
            kinds += [seg.get("type") for seg in msg if isinstance(seg, dict)]
        elif isinstance(msg, str):
            kinds.append("text")
    return kinds


# 让 pairit 关闭白名单, 证明被白名单门控的子命令也能正常工作
APPS_OVERRIDE = {
    "astrbot_plugin_pairit": {"extend_astrbot_whitelist": False,
                              "whitelist_enabled": False},
}

# (用例名, 指令, 期望(None=出站非空 / 子串 / ("seg",类型)), max_wait, want_kind)
CASES = [
    ("actions 列表", "actions", None, 2.0, None),
    ("apis 查看api", "查看api", "APIs", 2.0, None),
    ("arxiv help", "arxiv help", "arxiv", 2.0, None),
    ("arxiv categories", "arxiv categories", None, 2.0, None),
    ("dnd r 1d20", "r 1d20", "d20", 2.0, None),
    ("dnd roll 2d6+3", "roll 2d6+3", "2d6+3", 2.0, None),
    ("dnd 默认骰设置", "dset 1d100", None, 2.0, None),
    ("gomoku 无局提示", "gomoku", None, 2.0, None),
    ("gomoku 开人机", "gomoku_pvp", None, 2.0, None),
    ("idiom 用法", "idiom", "idiom", 2.0, None),
    ("idiom 接龙", "idiom 一帆风顺", None, 2.0, None),
    ("pairit about", "pairit about", "Pairit", 2.0, None),
    ("pairit status", "pairit status", "状态", 2.0, None),
    ("pairit enable", "pairit enable", "启用", 2.0, None),
    ("poetry 帮助", "飞花令帮助", "诗词", 2.0, None),
    ("status 图片", "status", ("seg", "image"), 12.0, "image"),
    ("what_to_eat 触发", "今天中午吃什么", None, 2.0, None),
]


async def main():
    mgr = await h.load_base(APPS_OVERRIDE)
    from plugins.astrbot.runtime import state
    print(f"handlers={mgr.handler_count} plugins={len(state.PLUGIN_SPECS)}")
    print("instances ok:", sum(1 for s in state.PLUGIN_SPECS if s.instance), "/", len(state.PLUGIN_SPECS))
    print("-" * 72)

    ok = 0
    for name, text, expect, mw, wk in CASES:
        try:
            sent = await h.feed(mgr, text, max_wait=mw, want_kind=wk)
        except Exception as e:
            print(f"[ERR ] {name:18} 指令异常: {e}")
            continue
        got = h.texts(sent)
        kinds = _segs(sent)
        if expect is None:
            passed = bool(sent)
        elif isinstance(expect, tuple) and expect[0] == "seg":
            passed = expect[1] in kinds
        else:
            passed = expect in got
        ok += passed
        flag = "PASS" if passed else "FAIL"
        preview = got[:54].replace("\n", " ")
        print(f"[{flag}] {name:18} segs={kinds} {preview!r}")
    print("-" * 72)
    print(f"{ok}/{len(CASES)} cases passed")
    return ok, len(CASES)


if __name__ == "__main__":
    asyncio.run(main())
