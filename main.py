#!/usr/bin/env python
"""ElainaBot OneBot 入口"""

import asyncio
import contextlib
import os
import sys

if sys.version_info < (3, 11):  # noqa: UP036  运行时版本守卫, 面向使用旧版 Python 的用户
    raise SystemExit(
        f'ElainaBot 需要 Python 3.11+，当前为 {sys.version_info.major}.{sys.version_info.minor}，请升级后再运行。')

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.dont_write_bytecode = True


def main():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    from core.application import Application

    with contextlib.suppress(KeyboardInterrupt):
        restart = asyncio.run(Application().start())
    if restart:
        os.execv(sys.executable, [sys.executable] + sys.argv)


if __name__ == '__main__':
    main()
