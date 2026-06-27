#!/usr/bin/env python
"""ElainaBot OneBot 入口"""

import asyncio
import contextlib
import os
import sys

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
