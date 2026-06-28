"""会话管理与鉴权 — 基于 v2 架构"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from functools import wraps

from aiohttp import web

from core.base.config import cfg

# Constants
_BAN_DURATION = 43200
_SESSION_CLEANUP_INTERVAL = 300
_IP_CLEANUP_INTERVAL = 3600
_FAIL_WINDOW = 86400
_MAX_SESSIONS = 10
_MAX_FAIL_COUNT = 5
_SESSION_DAYS = 7
_TOKEN_EXPIRY = 86400 * 7
_MAX_IP_RECORDS = 10000

# State
valid_sessions: dict = {}  # token -> info  (also used by ws.py)
_sessions = valid_sessions  # alias
ip_access_data: dict = {}
_last_session_cleanup = 0
_last_ip_cleanup = 0
_data_dir = ''
_ip_file = ''
_session_file = ''
_io_lock = threading.Lock()

SESSION_EXPIRE = _TOKEN_EXPIRY


# ==================== Init ====================

def init(base_dir: str):
    global _data_dir, _ip_file, _session_file
    _data_dir = os.path.join(base_dir, 'data', 'web')
    os.makedirs(_data_dir, exist_ok=True)
    _ip_file = os.path.join(_data_dir, 'ip.json')
    _session_file = os.path.join(_data_dir, 'sessions.json')
    _load_ip_data()
    _load_session_data()


# ==================== JSON IO ====================

def _read_json(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default or {}


def _write_text_sync(path, text):
    with _io_lock:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception:
            pass


def _write_json(path, data):
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return
    _write_text_sync(path, text)


# ==================== Password ====================

_PWD_HASH_PREFIX = 'sha256:'


def hash_password(plain: str) -> str:
    salt = os.urandom(16)
    h = hashlib.sha256(salt + plain.encode('utf-8')).hexdigest()
    return _PWD_HASH_PREFIX + base64.b64encode(salt).decode() + ':' + h


def _is_legacy_hex_hash(s: str) -> bool:
    """Check if stored value is old-style bare SHA-256 hex (64 hex chars)."""
    return len(s) == 64 and all(c in '0123456789abcdef' for c in s)


def verify_password(plain: str, stored: str) -> bool:
    if stored.startswith(_PWD_HASH_PREFIX):
        try:
            rest = stored[len(_PWD_HASH_PREFIX):]
            salt_b64, expected_hex = rest.split(':', 1)
            salt = base64.b64decode(salt_b64)
            actual_hex = hashlib.sha256(salt + plain.encode('utf-8')).hexdigest()
            return hmac.compare_digest(actual_hex, expected_hex)
        except Exception:
            return False
    # legacy bare SHA-256 hex (old framework format)
    if _is_legacy_hex_hash(stored):
        actual_hex = hashlib.sha256(plain.encode('utf-8')).hexdigest()
        return hmac.compare_digest(actual_hex, stored)
    # plain text fallback
    return hmac.compare_digest(plain, stored)


def is_hashed(stored: str) -> bool:
    return stored.startswith(_PWD_HASH_PREFIX) or _is_legacy_hex_hash(stored)


# ==================== IP ====================

def _load_ip_data():
    global ip_access_data
    ip_access_data = _read_json(_ip_file, {})


def _save_ip_data():
    _write_json(_ip_file, ip_access_data)


def get_real_ip(request) -> str:
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        return forwarded.split(',')[0].strip()
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()
    return request.remote or '127.0.0.1'


def record_ip_access(ip, access_type='success'):
    now_iso = datetime.now().isoformat()
    if ip not in ip_access_data:
        ip_access_data[ip] = {
            'first_access': now_iso,
            'last_access': now_iso,
            'fail_count': 0,
            'fail_times': [],
            'is_banned': False,
            'ban_time': None,
        }
    d = ip_access_data[ip]
    d['last_access'] = now_iso
    if access_type == 'fail':
        d['fail_count'] = d.get('fail_count', 0) + 1
        d.setdefault('fail_times', []).append(now_iso)
        now = datetime.now()
        d['fail_times'] = [
            t for t in d['fail_times']
            if (now - datetime.fromisoformat(t)).total_seconds() < _FAIL_WINDOW
        ]
        if len(d['fail_times']) >= _MAX_FAIL_COUNT:
            d['is_banned'] = True
            d['ban_time'] = now_iso
    _save_ip_data()


def is_ip_banned(ip) -> bool:
    d = ip_access_data.get(ip)
    if not d or not d.get('is_banned'):
        return False
    ban_time = d.get('ban_time')
    if not ban_time:
        return True
    try:
        if (datetime.now() - datetime.fromisoformat(ban_time)).total_seconds() >= _BAN_DURATION:
            d['is_banned'] = False
            d['ban_time'] = None
            d['fail_times'] = []
            _save_ip_data()
            return False
        return True
    except Exception:
        return True


def get_remaining_attempts(ip) -> int:
    d = ip_access_data.get(ip)
    if not d:
        return _MAX_FAIL_COUNT
    now = datetime.now()
    recent = [
        t for t in d.get('fail_times', [])
        if (now - datetime.fromisoformat(t)).total_seconds() < _FAIL_WINDOW
    ]
    return max(0, _MAX_FAIL_COUNT - len(recent))


def get_login_logs() -> list:
    raw = _read_json(_ip_file, {})
    logs = []
    for ip, d in raw.items():
        logs.append({
            'ip': ip,
            'first_access': d.get('first_access', ''),
            'last_access': d.get('last_access', ''),
            'fail_count': d.get('fail_count', 0),
            'is_banned': d.get('is_banned', False),
            'ban_time': d.get('ban_time', ''),
        })
    logs.sort(key=lambda x: x['last_access'] or '', reverse=True)
    return logs


def unban_ip(ip) -> bool:
    raw = _read_json(_ip_file, {})
    if ip in raw:
        raw[ip].update({'is_banned': False, 'ban_time': None, 'fail_times': [], 'fail_count': 0})
        _write_json(_ip_file, raw)
        if ip in ip_access_data:
            ip_access_data[ip].update(raw[ip])
        return True
    return False


# ==================== Session ====================

def _load_session_data():
    global valid_sessions, _sessions
    raw = _read_json(_session_file, {})
    now = time.time()
    for token, info in raw.items():
        try:
            created = info.get('created', 0)
            if isinstance(created, str):
                created = datetime.fromisoformat(created).timestamp()
            if now - created < _TOKEN_EXPIRY:
                valid_sessions[token] = {
                    'created': created,
                    'ip': info.get('ip', ''),
                }
        except Exception:
            pass
    _sessions = valid_sessions


def _save_session_data():
    data = {}
    for t, info in valid_sessions.items():
        data[t] = {
            'created': info.get('created', 0),
            'ip': info.get('ip', ''),
        }
    _write_json(_session_file, data)


def _cleanup_sessions():
    global _last_session_cleanup
    now = time.time()
    if now - _last_session_cleanup < _SESSION_CLEANUP_INTERVAL:
        return
    _last_session_cleanup = now
    expired = [t for t, info in valid_sessions.items() if now - info.get('created', 0) >= _TOKEN_EXPIRY]
    for t in expired:
        del valid_sessions[t]
    if expired:
        _save_session_data()


def create_session(request) -> str:
    _cleanup_sessions()
    if len(valid_sessions) > _MAX_SESSIONS:
        oldest = sorted(valid_sessions, key=lambda t: valid_sessions[t].get('created', 0))
        for t in oldest[:len(valid_sessions) - _MAX_SESSIONS]:
            valid_sessions.pop(t)

    ip = get_real_ip(request)
    token = secrets.token_hex(32)
    valid_sessions[token] = {
        'created': time.time(),
        'ip': ip,
    }
    _save_session_data()
    return token


def verify_session(request) -> bool:
    _cleanup_sessions()

    # URL token: check against access_token from config
    url_token = request.query.get('token', '')
    access_token = cfg.get('settings', 'web.access_token', '')
    if url_token and access_token and url_token == access_token:
        return True

    # URL token: check against session store (for WebSocket)
    if url_token and url_token in valid_sessions:
        session = valid_sessions[url_token]
        if (time.time() - session.get('created', 0)) < _TOKEN_EXPIRY:
            return True

    # Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        if token in valid_sessions:
            session = valid_sessions[token]
            if (time.time() - session.get('created', 0)) < _TOKEN_EXPIRY:
                return True
    return False


# ==================== Middleware ====================

def require_auth(handler):
    """鉴权装饰器"""
    @wraps(handler)
    async def wrapper(request: web.Request):
        if not verify_session(request):
            return web.json_response({'success': False, 'error': '未登录或会话已过期'}, status=401)
        return await handler(request)
    wrapper.__name__ = handler.__name__
    wrapper.__qualname__ = handler.__qualname__
    return wrapper
