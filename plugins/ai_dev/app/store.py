"""ai_dev 会话与调用日志存储

维护:
- 多个对话会话 (session) 的消息历史 (OpenAI messages 格式)
- 全局事件流 (用户消息 / 助手回复 / 工具调用 / 工具结果 / 错误), 用于 Web 面板的
  「完整日志 + 完整调用」展示, 并实时广播给所有连接的 SSE 客户端。

数据持久化到插件 data/ 目录 (sessions.json + events.jsonl), 进程重启后可恢复。
"""

import asyncio
import contextlib
import json
import os
import time
import uuid
from collections import deque

_MAX_EVENTS = 2000              # 内存中保留的事件数
_DEFAULT_HISTORY_ROUNDS = 50    # 单会话默认保留的对话轮数 (面板「设置」可改, 配置不可用时回退)


class AIStore:
    """对话历史 + 事件流 + SSE 广播 (单例)"""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._sessions_file = os.path.join(data_dir, 'sessions.json')
        self._events_file = os.path.join(data_dir, 'events.jsonl')
        self._sessions: dict = {}          # sid -> {id, title, created, updated, messages:[...]}
        self._events: deque = deque(maxlen=_MAX_EVENTS)
        self._subscribers: set = set()     # asyncio.Queue 集合 (SSE)
        self._seq = 0
        self._load()

    # ==================== 会话 ====================

    def list_sessions(self) -> list:
        return sorted(
            (
                {
                    'id': s['id'],
                    'title': s.get('title') or '新对话',
                    'created': s.get('created', 0),
                    'updated': s.get('updated', 0),
                    'message_count': sum(1 for m in s['messages'] if m.get('role') in ('user', 'assistant')),
                }
                for s in self._sessions.values()
            ),
            key=lambda x: x['updated'],
            reverse=True,
        )

    def get_session(self, sid: str) -> dict:
        return self._sessions.get(sid)

    def create_session(self, title: str = '') -> dict:
        sid = uuid.uuid4().hex[:12]
        now = time.time()
        sess = {'id': sid, 'title': title, 'created': now, 'updated': now, 'messages': []}
        self._sessions[sid] = sess
        self._save_sessions()
        return sess

    def ensure_session(self, sid: str) -> dict:
        if sid and sid in self._sessions:
            return self._sessions[sid]
        return self.create_session()

    def delete_session(self, sid: str) -> bool:
        if sid in self._sessions:
            del self._sessions[sid]
            self._save_sessions()
            return True
        return False

    def clear_session(self, sid: str) -> bool:
        sess = self._sessions.get(sid)
        if not sess:
            return False
        sess['messages'] = [m for m in sess['messages'] if m.get('role') == 'system']
        sess['updated'] = time.time()
        self._save_sessions()
        return True

    def _history_limit(self) -> int:
        """单会话保留的最大对话轮数 (面板「设置」可改, 默认 50); <=0 不限制。"""
        try:
            from . import aiconfig
            return int(aiconfig.history_limit())
        except Exception:
            return _DEFAULT_HISTORY_ROUNDS

    def get_messages(self, sid: str) -> list:
        sess = self._sessions.get(sid)
        return list(sess['messages']) if sess else []

    def set_messages(self, sid: str, messages: list):
        sess = self._sessions.get(sid)
        if not sess:
            return
        # 滚动裁剪: 保留 system + 最近的若干「轮」对话 (1 轮 = 1 个 user 回合)
        system = [m for m in messages if m.get('role') == 'system']
        rest = [m for m in messages if m.get('role') != 'system']
        limit_rounds = self._history_limit()
        if limit_rounds > 0:
            # 以 user 消息为「轮」边界, 仅保留最近 limit_rounds 轮。从 user 边界
            # 对齐裁剪, 既避免上下文无限增长, 又不会在工具调用序列中间截断 (OpenAI
            # 要求 role=tool 必须紧跟含 tool_calls 的 assistant), 防止下次请求 400。
            user_idx = [i for i, m in enumerate(rest) if m.get('role') == 'user']
            if len(user_idx) > limit_rounds:
                rest = rest[user_idx[len(user_idx) - limit_rounds]:]
        sess['messages'] = system + rest
        sess['updated'] = time.time()
        if not sess.get('title'):
            for m in rest:
                if m.get('role') == 'user' and isinstance(m.get('content'), str):
                    sess['title'] = m['content'][:24]
                    break
        self._save_sessions()

    def _save_sessions(self):
        try:
            with open(self._sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self._sessions, f, ensure_ascii=False)
        except Exception:
            pass

    def _load(self):
        with contextlib.suppress(Exception):
            if os.path.isfile(self._sessions_file):
                with open(self._sessions_file, encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._sessions = data
        with contextlib.suppress(Exception):
            if os.path.isfile(self._events_file):
                with open(self._events_file, encoding='utf-8') as f:
                    lines = f.readlines()[-_MAX_EVENTS:]
                for line in lines:
                    line = line.strip()
                    if line:
                        with contextlib.suppress(Exception):
                            self._events.append(json.loads(line))
        if self._events:
            self._seq = self._events[-1].get('seq', 0)
            self._compact_event_file()  # 启动时压实事件文件, 防止 jsonl 无限增长

    def _compact_event_file(self):
        """把磁盘事件文件压实为内存中保留的最近事件 (启动时调用一次)"""
        with contextlib.suppress(Exception):
            tmp = self._events_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                for e in self._events:
                    if e.get('type') != 'delta':
                        f.write(json.dumps(e, ensure_ascii=False) + '\n')
            os.replace(tmp, self._events_file)

    # ==================== 事件 ====================

    def add_event(self, etype: str, data: dict, session_id: str = '') -> dict:
        """记录一个事件并广播给所有 SSE 订阅者

        etype: user | assistant | tool_call | tool_result | error | info | delta
        """
        self._seq += 1
        event = {
            'seq': self._seq,
            'type': etype,
            'session_id': session_id,
            'time': time.time(),
            'data': data,
        }
        self._events.append(event)
        # delta (流式增量) 不落盘, 避免事件文件膨胀
        if etype != 'delta':
            self._append_event_file(event)
        self._broadcast(event)
        return event

    def recent_events(self, limit: int = 300, exclude_delta: bool = True) -> list:
        items = [e for e in self._events if not (exclude_delta and e['type'] == 'delta')]
        return items[-limit:]

    def session_events(self, sid: str, limit: int = 1000) -> list:
        """返回某会话的非 delta 事件 (按时间顺序), 用于刷新后重建对话内联调用时间线。"""
        if not sid:
            return []
        items = [e for e in self._events if e.get('session_id') == sid and e['type'] != 'delta']
        return items[-limit:]

    def _append_event_file(self, event: dict):
        try:
            with open(self._events_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception:
            pass

    # ==================== SSE 广播 ====================

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    def _broadcast(self, event: dict):
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
