"""ai_dev 配置读取

配置来源 (优先级): 框架 config/settings.yaml 的 `ai` 段 > 环境变量。
api_key 出于安全考虑, 优先从环境变量 AI_DEV_API_KEY / OPENAI_API_KEY 读取,
也允许写在 settings.yaml (该文件已被 .gitignore 忽略, 不会提交)。
"""

import os

from core.base.config import cfg

DEFAULTS = {
    'enabled': True,
    'base_url': 'https://api.ytea.top/v1',
    'model': 'gpt-4.1-nano',
    'temperature': 0.3,
    'max_iterations': 12,
    'request_timeout': 120,
    'system_prompt': '',
}


def _ai(key: str, default=None):
    return cfg.get('settings', f'ai.{key}', default)


def get(key: str):
    val = _ai(key, None)
    if val is None or val == '':
        return DEFAULTS.get(key)
    return val


def base_url() -> str:
    url = str(get('base_url') or DEFAULTS['base_url']).rstrip('/')
    return url


def api_key() -> str:
    key = _ai('api_key', '') or ''
    if not key:
        key = os.environ.get('AI_DEV_API_KEY') or os.environ.get('OPENAI_API_KEY') or ''
    return str(key)


def model() -> str:
    return str(get('model') or DEFAULTS['model'])


def temperature() -> float:
    try:
        return float(get('temperature'))
    except (TypeError, ValueError):
        return DEFAULTS['temperature']


def max_iterations() -> int:
    try:
        return int(get('max_iterations'))
    except (TypeError, ValueError):
        return DEFAULTS['max_iterations']


def request_timeout() -> int:
    try:
        return int(get('request_timeout'))
    except (TypeError, ValueError):
        return DEFAULTS['request_timeout']


def system_prompt() -> str:
    return str(get('system_prompt') or '')


def is_configured() -> bool:
    return bool(api_key())


def public_config() -> dict:
    """返回可暴露给前端的配置 (不含 api_key 明文)"""
    return {
        'enabled': bool(get('enabled')),
        'base_url': base_url(),
        'model': model(),
        'temperature': temperature(),
        'max_iterations': max_iterations(),
        'request_timeout': request_timeout(),
        'system_prompt': system_prompt(),
        'api_key_set': is_configured(),
    }
