"""ai_dev 配置读取

配置来源 (优先级): 面板运行时覆盖 (data/runtime_config.json) > 框架
config/settings.yaml 的 `ai` 段 > 环境变量 > 内置默认值。

面板可在「设置」里自定义 OpenAI 地址(base_url)与密钥(api_key), 保存后写入
data/runtime_config.json (该目录已被 .gitignore, 不会随插件提交), 立即生效。
api_key 也可继续用环境变量 AI_DEV_API_KEY / OPENAI_API_KEY。
"""

import json
import os
import threading

from core.base.config import cfg

DEFAULTS = {
    'enabled': True,
    'base_url': 'https://api.ytea.top/v1',
    'model': 'gpt-4.1-nano',
    'temperature': 0.3,
    'max_iterations': 50,
    'request_timeout': 120,
    'system_prompt': '',
    'reasoning_effort': '',
    'history_limit': 50,
}

# 允许面板写入并持久化的字段
_WRITABLE = ('base_url', 'api_key', 'model', 'temperature', 'max_iterations',
             'request_timeout', 'system_prompt', 'enabled', 'reasoning_effort', 'history_limit')

# 子模块位于 ai_dev/app/, data 目录在插件根 ai_dev/data/
_OVERRIDE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'runtime_config.json')
_lock = threading.Lock()
_override_cache = None


def _load_override() -> dict:
    global _override_cache
    if _override_cache is not None:
        return _override_cache
    data = {}
    try:
        if os.path.exists(_OVERRIDE_FILE):
            with open(_OVERRIDE_FILE, encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = {k: v for k, v in loaded.items() if k in _WRITABLE}
    except Exception:  # noqa: BLE001
        data = {}
    _override_cache = data
    return data


def set_runtime(updates: dict) -> dict:
    """合并并持久化面板可写字段 (base_url / api_key / model 等), 返回最新覆盖值。"""
    global _override_cache
    with _lock:
        cur = dict(_load_override())
        for k, v in (updates or {}).items():
            if k not in _WRITABLE:
                continue
            if v is None:
                cur.pop(k, None)
            elif isinstance(v, str):
                sv = v.strip()
                # 空字符串表示清除该覆盖, 回退到 settings.yaml / 环境变量 / 默认
                if sv == '':
                    cur.pop(k, None)
                else:
                    cur[k] = sv
            else:
                cur[k] = v
        os.makedirs(os.path.dirname(_OVERRIDE_FILE), exist_ok=True)
        tmp = _OVERRIDE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _OVERRIDE_FILE)
        _override_cache = cur
        return dict(cur)


def _ai(key: str, default=None):
    return cfg.get('settings', f'ai.{key}', default)


def get(key: str):
    ov = _load_override().get(key)
    if ov is not None and ov != '':
        return ov
    val = _ai(key, None)
    if val is None or val == '':
        return DEFAULTS.get(key)
    return val


def base_url() -> str:
    url = str(get('base_url') or DEFAULTS['base_url']).rstrip('/')
    return url


def api_key() -> str:
    key = _load_override().get('api_key') or ''
    if not key:
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


def history_limit() -> int:
    """单会话保留的最大对话轮数 (1 轮 = 用户提问 + AI 回复); <=0 表示不限制。"""
    try:
        return int(get('history_limit'))
    except (TypeError, ValueError):
        return DEFAULTS['history_limit']


def request_timeout() -> int:
    try:
        return int(get('request_timeout'))
    except (TypeError, ValueError):
        return DEFAULTS['request_timeout']


def system_prompt() -> str:
    return str(get('system_prompt') or '')


def reasoning_effort() -> str:
    """思考强度: '' 表示不指定 (跟随模型默认), 否则 minimal/low/medium/high。"""
    v = str(get('reasoning_effort') or '').strip().lower()
    return v if v in ('minimal', 'low', 'medium', 'high') else ''


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
        'history_limit': history_limit(),
        'request_timeout': request_timeout(),
        'system_prompt': system_prompt(),
        'reasoning_effort': reasoning_effort(),
        'api_key_set': is_configured(),
    }
