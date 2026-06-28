"""日志系统"""

import logging
import sys

SYSTEM = 'system'
FRAMEWORK = 'framework'
EXTENSION = 'extension'
PLUGIN = 'plugin'

_FW_NAME = 'ElainaBot'


def setup(framework_name: str = 'ElainaBot', level: int = logging.INFO):
    """初始化日志系统"""
    global _FW_NAME
    _FW_NAME = framework_name

    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    formatter = logging.Formatter(
        f'[{framework_name}] %(asctime)s - %(levelname)s - %(message)s',
        datefmt='%m-%d %H:%M:%S'
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.setLevel(level)
    root.addHandler(handler)

    for name in ('werkzeug', 'socketio', 'engineio', 'urllib3', 'uvicorn.access', 'aiohttp.access'):
        logging.getLogger(name).setLevel(logging.ERROR)


def get_logger(module_type: str = '', name: str = '') -> logging.Logger:
    """获取命名日志器"""
    parts = [_FW_NAME]
    if module_type:
        parts.append(module_type)
    if name:
        parts.append(name)
    return logging.getLogger('.'.join(parts))


# 错误回调
_error_callbacks = []


def on_error(callback):
    """注册全局错误回调"""
    _error_callbacks.append(callback)


def report_error(module_type: str, name: str, error: Exception):
    """报告错误"""
    import traceback
    import datetime
    log = get_logger(module_type, name)
    log.error(f'{error}')
    data = {
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'module_type': module_type,
        'module_name': name,
        'content': str(error),
        'traceback': traceback.format_exc(),
    }
    for cb in _error_callbacks:
        try:
            cb(data)
        except Exception:
            pass
