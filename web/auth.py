"""Web 面板鉴权"""

import hashlib
import os
import secrets
import time
from functools import wraps

from aiohttp import web

from core.base.config import cfg

_sessions = {}  # {token: {'created': timestamp, 'ip': str}}
_base_dir = ''

SESSION_EXPIRE = 86400 * 7  # 7天


def init(base_dir: str):
    global _base_dir
    _base_dir = base_dir


def get_real_ip(request) -> str:
    return request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
           request.headers.get('X-Real-IP', '') or \
           (request.remote or '127.0.0.1')


def verify_password(input_pwd: str, stored_pwd: str) -> bool:
    if is_hashed(stored_pwd):
        return hash_password(input_pwd) == stored_pwd
    return input_pwd == stored_pwd


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def is_hashed(pwd: str) -> bool:
    return len(pwd) == 64 and all(c in '0123456789abcdef' for c in pwd)


def create_session(request) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = {
        'created': time.time(),
        'ip': get_real_ip(request),
    }
    return token


def verify_session(request) -> bool:
    # URL token 验证
    url_token = request.query.get('token', '')
    access_token = cfg.get('settings', 'web.access_token', '')
    if url_token and access_token and url_token == access_token:
        return True

    # Session token
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        session = _sessions.get(token)
        if session and (time.time() - session['created']) < SESSION_EXPIRE:
            return True
    return False


def require_auth(handler):
    """鉴权装饰器"""
    @wraps(handler)
    async def wrapper(request: web.Request):
        if not verify_session(request):
            return web.json_response({'success': False, 'error': '未授权'}, status=401)
        return await handler(request)
    return wrapper
