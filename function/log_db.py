#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import json
import queue
import sqlite3
import threading
import logging
import datetime
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger('ElainaBot.function.log_db')

LOG_TYPES = ['received', 'plugin', 'framework', 'error']
SAVE_INTERVAL = 3  # 3秒写入一次
BATCH_SIZE = 1000  # 单次最大写入数量

class LogDatabaseManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LogDatabaseManager, cls).__new__(cls)
            return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        
        # 初始化目录
        project_root = Path(__file__).parent.parent
        self.log_dir = project_root / 'data' / 'log'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ 日志目录: {self.log_dir}")
        
        # 初始化队列
        self.log_queues = {log_type: queue.Queue() for log_type in LOG_TYPES}
        
        # 初始化连接缓存
        self._connections = {}
        self._conn_lock = threading.Lock()
        
        # 初始化SQL模板
        self._init_sql_templates()
        
        # 创建今天的表
        self._ensure_today_tables()
        
        # 启动保存线程
        self._stop_event = threading.Event()
        self._save_thread = threading.Thread(target=self._periodic_save, daemon=True, name="LogDBSaveThread")
        self._save_thread.start()
        
        # 启动清理线程
        from config import LOG_DB_CONFIG
        if LOG_DB_CONFIG.get('auto_cleanup', False):
            self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True, name="LogDBCleanupThread")
            self._cleanup_thread.start()
        
        logger.info("✅ 日志系统启动")
    
    def _init_sql_templates(self):
        self._table_schemas = {
            'received': """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    group_id TEXT DEFAULT 'c2c',
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'unknown',
                    message_id TEXT DEFAULT '',
                    real_seq TEXT DEFAULT '',
                    reply_id TEXT DEFAULT NULL,
                    message_segments TEXT,
                    raw_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'plugin': """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    group_id TEXT DEFAULT 'c2c',
                    plugin_name TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'framework': """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """,
            'error': """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    content TEXT NOT NULL,
                    traceback TEXT,
                    resp_obj TEXT,
                    send_payload TEXT,
                    raw_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
        }
        
        self._insert_templates = {
            'received': "INSERT INTO {table_name} (timestamp, user_id, group_id, content, message_type, message_id, real_seq, reply_id, message_segments, raw_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            'plugin': "INSERT INTO {table_name} (timestamp, user_id, group_id, plugin_name, content) VALUES (?, ?, ?, ?, ?)",
            'framework': "INSERT INTO {table_name} (timestamp, content) VALUES (?, ?)",
            'error': "INSERT INTO {table_name} (timestamp, content, traceback, resp_obj, send_payload, raw_message) VALUES (?, ?, ?, ?, ?, ?)"
        }
        
        self._field_extractors = {
            'received': lambda log: (
                log.get('timestamp'),
                log.get('user_id', ''),
                log.get('group_id', 'c2c'),
                log.get('content', ''),
                log.get('message_type', 'unknown'),
                log.get('message_id', ''),
                log.get('real_seq', ''),
                log.get('reply_id', ''),
                log.get('message_segments', ''),
                log.get('raw_message', '')
            ),
            'plugin': lambda log: (
                log.get('timestamp'),
                log.get('user_id', ''),
                log.get('group_id', 'c2c'),
                log.get('plugin_name', ''),
                log.get('content', '')
            ),
            'framework': lambda log: (
                log.get('timestamp'),
                log.get('content', '')
            ),
            'error': lambda log: (
                log.get('timestamp'),
                log.get('content', ''),
                log.get('traceback', ''),
                log.get('resp_obj', ''),
                log.get('send_payload', ''),
                log.get('raw_message', '')
            )
        }
    
    def _get_db_path(self, log_type, date_str=None):
        if date_str is None:
            date_str = datetime.datetime.now().strftime('%Y%m%d')
        return self.log_dir / f"log_{log_type}_{date_str}.db"
    
    def _get_table_name(self, log_type):
        return f"log_{log_type}"
    
    @contextmanager
    def _get_connection(self, log_type, date_str=None):
        db_path = self._get_db_path(log_type, date_str)
        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _ensure_today_tables(self):
        try:
            for log_type in LOG_TYPES:
                with self._get_connection(log_type) as conn:
                    cursor = conn.cursor()
                    table_name = self._get_table_name(log_type)
                    schema_sql = self._table_schemas[log_type].format(table_name=table_name)
                    cursor.execute(schema_sql)
                    
                    # 创建索引
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_time ON {table_name} (timestamp)")
                    
                    if log_type == 'received':
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user ON {table_name} (user_id)")
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_group ON {table_name} (group_id)")
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_msg_id ON {table_name} (message_id)")
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_real_seq ON {table_name} (real_seq)")
                    elif log_type == 'plugin':
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_plugin ON {table_name} (plugin_name)")
                    
                    conn.commit()
        except Exception as e:
            logger.error(f"❌ 创建表失败: {e}")
    
    def add_log(self, log_type, log_data):
        if log_type not in LOG_TYPES:
            return False
        self.log_queues[log_type].put(log_data)
        return True
    
    def _periodic_save(self):
        while not self._stop_event.is_set():
            try:
                self._stop_event.wait(SAVE_INTERVAL)
                if self._stop_event.is_set():
                    break
                self._save_logs_to_db()
            except Exception as e:
                logger.error(f"❌ 保存日志异常: {e}")
                time.sleep(1)
    
    def _periodic_cleanup(self):
        while not self._stop_event.is_set():
            try:
                now = datetime.datetime.now()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    next_run += datetime.timedelta(days=1)
                wait_seconds = (next_run - now).total_seconds()
                if self._stop_event.wait(wait_seconds):
                    break
                from config import LOG_DB_CONFIG
                retention_days = LOG_DB_CONFIG.get('retention_days', 30)
                cleanup_old_logs(retention_days)
            except Exception as e:
                logger.error(f"❌ 清理日志异常: {e}")
                time.sleep(3600)
    
    def _save_logs_to_db(self):
        for log_type in LOG_TYPES:
            self._save_log_type(log_type)
    
    def _save_log_type(self, log_type):
        queue_size = self.log_queues[log_type].qsize()
        if queue_size == 0:
            return
        
        batch_size = min(queue_size, BATCH_SIZE)
        logs_to_insert = []
        
        for _ in range(batch_size):
            try:
                log_data = self.log_queues[log_type].get_nowait()
                logs_to_insert.append(log_data)
            except queue.Empty:
                break
        
        if not logs_to_insert:
            return
        
        try:
            table_name = self._get_table_name(log_type)
            insert_sql = self._insert_templates[log_type].format(table_name=table_name)
            extractor = self._field_extractors[log_type]
            values = [extractor(log) for log in logs_to_insert]
            
            with self._get_connection(log_type) as conn:
                cursor = conn.cursor()
                cursor.executemany(insert_sql, values)
                conn.commit()
        except Exception as e:
            logger.error(f"❌ 写入 {log_type} 日志失败: {e}")
        finally:
            for _ in range(len(logs_to_insert)):
                try:
                    self.log_queues[log_type].task_done()
                except:
                    pass
    
    def shutdown(self):
        self._stop_event.set()
        if hasattr(self, '_save_thread'):
            self._save_thread.join(timeout=5)
        if hasattr(self, '_cleanup_thread'):
            self._cleanup_thread.join(timeout=2)
        self._save_logs_to_db()

log_db_manager = LogDatabaseManager()

def add_log_to_db(log_type, log_data):
    if not isinstance(log_data, dict):
        return False
    log_data.setdefault('timestamp', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    if 'content' not in log_data:
        return False
    return log_db_manager.add_log(log_type, log_data)

def get_log_from_db(log_type, message_id=None, user_id=None, group_id=None, limit=1):
    if log_type not in LOG_TYPES:
        return None
    
    try:
        table_name = log_db_manager._get_table_name(log_type)
        
        where_clauses = []
        params = []
        
        if message_id:
            where_clauses.append("message_id = ?")
            params.append(str(message_id))
        
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(str(user_id))
        
        if group_id:
            where_clauses.append("group_id = ?")
            params.append(str(group_id))
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        # 先取最新的 N 条（DESC），然后反转顺序（ASC）显示
        sql = f"""
            SELECT * FROM (
                SELECT * FROM {table_name} WHERE {where_sql} ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
        """
        params.append(limit)
        
        with log_db_manager._get_connection(log_type) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = cursor.fetchall()
            
            if not results:
                return None
            
            # 转换为字典
            results = [dict(row) for row in results]
            
            if limit == 1:
                return results[0] if results else None
            
            return results
    except Exception as e:
        logger.error(f"❌ 查询日志失败: {e}")
        return None

def add_sent_message_to_db(chat_type, chat_id, content, raw_message=None, timestamp=None):
    if not content:
        return False
    user_id = 'BOT' if chat_type == 'group' else chat_id
    group_id = chat_id if chat_type == 'group' else 'c2c'
    return add_log_to_db('received', {
        'timestamp': timestamp or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': user_id,
        'group_id': group_id,
        'content': content,
        'raw_message': raw_message or ''
    })

def cleanup_old_logs(days=30):
    try:
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        log_dir = log_db_manager.log_dir
        deleted_count = 0
        
        # 清理4种类型的日志文件
        for log_type in LOG_TYPES:
            for db_file in log_dir.glob(f"log_{log_type}_*.db"):
                try:
                    # 提取日期部分 log_received_20251107.db -> 20251107
                    parts = db_file.stem.split('_')
                    if len(parts) < 3:
                        continue
                    date_str = parts[2]
                    if len(date_str) != 8:
                        continue
                    file_date = datetime.datetime.strptime(date_str, '%Y%m%d')
                    if file_date < cutoff_date:
                        db_file.unlink()
                        deleted_count += 1
                except:
                    continue
        
        if deleted_count > 0:
            logger.info(f"✅ 清理了 {deleted_count} 个过期日志文件")
        return True
    except Exception as e:
        logger.error(f"❌ 清理日志失败: {e}")
        return False
