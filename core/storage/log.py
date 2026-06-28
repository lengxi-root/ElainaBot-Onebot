"""SQLite 日志存储服务"""

import asyncio
import datetime
import os
import sqlite3
import threading
from collections import deque

from core.base.logger import get_logger, SYSTEM

log = get_logger(SYSTEM, '日志存储')


class LogService:
    """SQLite 日志服务 — 支持批量写入与定期清理"""

    _instance = None

    def __init__(self, base_dir: str, wal_mode: bool = True,
                 insert_interval: float = 2.0, retention_days: int = 30):
        self._base_dir = base_dir
        self._wal_mode = wal_mode
        self._insert_interval = insert_interval
        self._retention_days = retention_days
        self._queues = {}  # {log_type: deque}
        self._connections = {}  # {log_type: sqlite3.Connection}
        self._lock = threading.Lock()
        self._running = False
        self._flush_task = None
        LogService._instance = self

    async def start(self):
        os.makedirs(self._base_dir, exist_ok=True)
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        log.info(f'日志服务启动: {self._base_dir}')

    async def shutdown(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
        self._flush_all()
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()

    def _get_conn(self, log_type: str) -> sqlite3.Connection:
        if log_type in self._connections:
            return self._connections[log_type]
        db_path = os.path.join(self._base_dir, f'{log_type}.db')
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        if self._wal_mode:
            conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                content TEXT,
                source TEXT DEFAULT '',
                level TEXT DEFAULT 'INFO',
                user_id TEXT DEFAULT '',
                group_id TEXT DEFAULT '',
                message_id TEXT DEFAULT '',
                message_type TEXT DEFAULT '',
                raw_data TEXT DEFAULT '',
                extra TEXT DEFAULT ''
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_log_timestamp ON log(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_log_group ON log(group_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_log_user ON log(user_id, group_id)')
        conn.commit()
        self._connections[log_type] = conn
        return conn

    def add(self, log_type: str, entry: dict):
        """添加日志条目到队列"""
        if log_type not in self._queues:
            self._queues[log_type] = deque()
        self._queues[log_type].append(entry)

    def add_sync(self, log_type: str, entry: dict):
        """同步添加（等同于 add）"""
        self.add(log_type, entry)

    def execute(self, log_type: str, sql: str, params=None) -> int:
        """执行写操作（UPDATE/DELETE），返回受影响行数"""
        try:
            conn = self._get_conn(log_type)
            with self._lock:
                cursor = conn.execute(sql, params or [])
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            log.warning(f'执行写操作失败 [{log_type}]: {e}')
            return 0

    def query(self, log_type: str, sql: str, params=None) -> list:
        """查询日志"""
        try:
            conn = self._get_conn(log_type)
            with self._lock:
                cursor = conn.execute(sql, params or [])
                rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            log.warning(f'查询日志失败 [{log_type}]: {e}')
            return []

    async def _flush_loop(self):
        while self._running:
            await asyncio.sleep(self._insert_interval)
            self._flush_all()

    def _flush_all(self):
        for log_type in list(self._queues.keys()):
            queue = self._queues.get(log_type)
            if not queue:
                continue
            entries = []
            while queue:
                entries.append(queue.popleft())
            if not entries:
                continue
            try:
                conn = self._get_conn(log_type)
                with self._lock:
                    for entry in entries:
                        conn.execute(
                            '''INSERT INTO log (timestamp, content, source, level, user_id, group_id, message_id, message_type, raw_data, extra)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                entry.get('timestamp', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                                entry.get('content', ''),
                                entry.get('source', ''),
                                entry.get('level', 'INFO'),
                                entry.get('user_id', ''),
                                entry.get('group_id', ''),
                                entry.get('message_id', ''),
                                entry.get('message_type', ''),
                                entry.get('raw_data', ''),
                                entry.get('extra', ''),
                            )
                        )
                    conn.commit()
            except Exception as e:
                log.warning(f'写入日志失败 [{log_type}]: {e}')

    def cleanup(self):
        """清理过期日志"""
        if self._retention_days <= 0:
            return
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=self._retention_days)).strftime('%Y-%m-%d %H:%M:%S')
        for log_type, conn in self._connections.items():
            try:
                with self._lock:
                    conn.execute('DELETE FROM log WHERE timestamp < ?', (cutoff,))
                    conn.commit()
            except Exception:
                pass
