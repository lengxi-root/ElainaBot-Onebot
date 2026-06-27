"""配置文件监视服务"""

import asyncio
import os
import threading
import time

from core.base.config import cfg
from core.base.logger import SYSTEM, get_logger

log = get_logger(SYSTEM, '配置监视')


class ConfigWatcherService:
    """定期检查配置文件变更并热加载"""

    def __init__(self, interval: float = 5.0):
        self._interval = interval
        self._running = False
        self._thread = None
        self._mtimes = {}

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _watch_loop(self):
        config_dir = cfg._config_dir
        if not config_dir:
            return
        while self._running:
            time.sleep(self._interval)
            try:
                for fname in os.listdir(config_dir):
                    if not fname.endswith('.yaml') or fname.endswith('.example.yaml'):
                        continue
                    path = os.path.join(config_dir, fname)
                    mtime = os.path.getmtime(path)
                    if path in self._mtimes and mtime != self._mtimes[path]:
                        name = fname[:-5]
                        cfg.reload(name)
                        log.info(f'配置热加载: {fname}')
                    self._mtimes[path] = mtime
            except Exception:
                pass
