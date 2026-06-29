"""ai_dev Agent 工具集

为 AI 提供操作框架的能力: 文件读写、目录浏览、插件热重载与自检、
配置读写、运行 Python 自测、系统/框架状态检查、通过 OneBot 发消息。

所有文件操作均沙箱限定在仓库根目录内, 并禁止访问 .git 目录。
"""

import asyncio
import json
import os
import platform
import sys
import time

from core.base.config import cfg

# 仓库根目录: plugins/ai_dev/tools.py -> 上溯三层
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MAX_READ_BYTES = 200_000
_MAX_WRITE_BYTES = 1_000_000
_PYTHON_TIMEOUT = 30


def _safe_path(rel: str) -> str:
    """将相对路径解析为仓库内的绝对路径, 越界或访问 .git 则抛错"""
    rel = (rel or '').strip().lstrip('/').lstrip('\\')
    target = os.path.abspath(os.path.join(ROOT, rel))
    if target != ROOT and not target.startswith(ROOT + os.sep):
        raise ValueError(f'路径越界 (仅允许仓库内): {rel}')
    parts = os.path.relpath(target, ROOT).split(os.sep)
    if parts and parts[0] == '.git':
        raise ValueError('禁止访问 .git 目录')
    return target


def _rel(abs_path: str) -> str:
    return os.path.relpath(abs_path, ROOT).replace(os.sep, '/')


# ==================== 工具实现 ====================


async def _t_list_dir(path: str = '.') -> dict:
    base = _safe_path(path or '.')
    if not os.path.isdir(base):
        raise ValueError(f'不是目录: {path}')
    entries = []
    for name in sorted(os.listdir(base)):
        if name == '.git':
            continue
        full = os.path.join(base, name)
        entries.append({
            'name': name,
            'type': 'dir' if os.path.isdir(full) else 'file',
            'size': os.path.getsize(full) if os.path.isfile(full) else None,
        })
    return {'path': _rel(base), 'entries': entries}


async def _t_read_file(path: str) -> dict:
    target = _safe_path(path)
    if not os.path.isfile(target):
        raise ValueError(f'文件不存在: {path}')
    size = os.path.getsize(target)
    with open(target, encoding='utf-8', errors='replace') as f:
        content = f.read(_MAX_READ_BYTES)
    truncated = size > _MAX_READ_BYTES
    return {'path': _rel(target), 'size': size, 'truncated': truncated, 'content': content}


async def _t_write_file(path: str, content: str) -> dict:
    target = _safe_path(path)
    data = content if isinstance(content, str) else str(content)
    if len(data.encode('utf-8')) > _MAX_WRITE_BYTES:
        raise ValueError('内容过大')
    os.makedirs(os.path.dirname(target) or ROOT, exist_ok=True)
    existed = os.path.isfile(target)
    with open(target, 'w', encoding='utf-8') as f:
        f.write(data)
    return {'path': _rel(target), 'bytes': len(data.encode('utf-8')), 'created': not existed}


async def _t_delete_file(path: str) -> dict:
    target = _safe_path(path)
    if os.path.isfile(target):
        os.remove(target)
        return {'path': _rel(target), 'deleted': True, 'type': 'file'}
    if os.path.isdir(target):
        import shutil
        shutil.rmtree(target)
        return {'path': _rel(target), 'deleted': True, 'type': 'dir'}
    raise ValueError(f'路径不存在: {path}')


async def _t_make_dir(path: str) -> dict:
    target = _safe_path(path)
    os.makedirs(target, exist_ok=True)
    return {'path': _rel(target), 'created': True}


def _plugin_manager():
    from core.application import get_app
    app = get_app()
    return app.plugin_manager if app else None


async def _t_list_plugins() -> dict:
    pm = _plugin_manager()
    if not pm:
        raise ValueError('插件管理器不可用')
    return {'plugins': pm.list_plugins(), 'loaded': pm.get_plugin_list()}


async def _t_list_handlers() -> dict:
    pm = _plugin_manager()
    if not pm:
        raise ValueError('插件管理器不可用')
    return {'handlers': pm.get_command_list()}


async def _t_reload_plugin(name: str) -> dict:
    """热重载插件并返回自检结果 (handler 数 / 报错信息)"""
    pm = _plugin_manager()
    if not pm:
        raise ValueError('插件管理器不可用')
    if not name:
        raise ValueError('缺少插件名 name')
    await pm.reload(name)
    info = pm.plugins.get(name)
    if not info:
        return {'name': name, 'loaded': False, 'error': '插件未加载 (可能目录不存在或被禁用)'}
    return {
        'name': name,
        'loaded': True,
        'enabled': info.enabled,
        'error': info.error or '',
        'handler_count': len(info.handlers),
        'handlers': [
            {'name': h.get('name'), 'pattern': h.get('pattern'), 'desc': h.get('desc')}
            for h in info.handlers
        ],
    }


async def _t_run_python(code: str, timeout: int = _PYTHON_TIMEOUT) -> dict:
    """在仓库根目录下以子进程运行 Python 代码 (用于自测), 带超时"""
    if not code or not code.strip():
        raise ValueError('缺少 code')
    try:
        to = min(int(timeout), 120)
    except (TypeError, ValueError):
        to = _PYTHON_TIMEOUT
    start = time.time()
    proc = await asyncio.create_subprocess_exec(
        sys.executable, '-I', '-c', code,
        cwd=ROOT,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, 'PYTHONPATH': ROOT, 'PYTHONDONTWRITEBYTECODE': '1'},
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=to)
        timed_out = False
    except asyncio.TimeoutError:
        proc.kill()
        out, err = await proc.communicate()
        timed_out = True
    return {
        'exit_code': proc.returncode,
        'timed_out': timed_out,
        'duration_ms': int((time.time() - start) * 1000),
        'stdout': out.decode('utf-8', 'replace')[-8000:],
        'stderr': err.decode('utf-8', 'replace')[-8000:],
    }


async def _t_get_config(file: str = 'settings') -> dict:
    if file not in ('settings', 'connections'):
        raise ValueError('file 仅支持 settings 或 connections')
    data = cfg.get_raw(file)
    # 隐去敏感字段
    safe = json.loads(json.dumps(data, ensure_ascii=False, default=str))
    if isinstance(safe, dict):
        ai = safe.get('ai')
        if isinstance(ai, dict) and ai.get('api_key'):
            ai['api_key'] = '***'
    return {'file': file, 'config': safe}


async def _t_set_config(file: str, key: str, value) -> dict:
    if file not in ('settings', 'connections'):
        raise ValueError('file 仅支持 settings 或 connections')
    if not key:
        raise ValueError('缺少 key (点号路径, 如 web.framework_name)')
    cfg.set_value(file, key, value)
    return {'file': file, 'key': key, 'value': value, 'saved': True}


async def _t_system_info() -> dict:
    info = {
        'os': platform.platform(),
        'system': platform.system(),
        'python': platform.python_version(),
        'cwd': ROOT,
    }
    try:
        import psutil
        vm = psutil.virtual_memory()
        info['cpu_percent'] = psutil.cpu_percent(interval=0.1)
        info['cpu_count'] = psutil.cpu_count()
        info['memory'] = {
            'total_mb': round(vm.total / 1024 / 1024),
            'used_mb': round(vm.used / 1024 / 1024),
            'percent': vm.percent,
        }
        p = psutil.Process()
        info['process'] = {
            'pid': p.pid,
            'memory_mb': round(p.memory_info().rss / 1024 / 1024, 1),
            'threads': p.num_threads(),
        }
    except Exception as e:
        info['psutil_error'] = str(e)
    pm = _plugin_manager()
    if pm:
        info['framework'] = {
            'plugins': len(pm.plugins),
            'handlers': pm.handler_count,
        }
    return info


async def _t_send_qq_message(target_type: str, target_id, text: str) -> dict:
    """通过 OneBot 主动发送一条消息 (group 或 private)"""
    from core.onebot.api import get_api
    api = get_api()
    if not api:
        raise ValueError('OneBot API 不可用')
    message = [{'type': 'text', 'data': {'text': str(text)}}]
    if target_type == 'group':
        res = await api.send_group_msg(int(target_id), message)
    elif target_type == 'private':
        res = await api.send_private_msg(int(target_id), message)
    else:
        raise ValueError("target_type 仅支持 'group' 或 'private'")
    if res is None:
        return {'sent': False, 'error': '无可用 OneBot 连接 (机器人未连接)'}
    return {'sent': True, 'result': res.get('data') if isinstance(res, dict) else res}


# ==================== 调度表 ====================

_DISPATCH = {
    'list_dir': _t_list_dir,
    'read_file': _t_read_file,
    'write_file': _t_write_file,
    'delete_file': _t_delete_file,
    'make_dir': _t_make_dir,
    'list_plugins': _t_list_plugins,
    'list_handlers': _t_list_handlers,
    'reload_plugin': _t_reload_plugin,
    'run_python': _t_run_python,
    'get_config': _t_get_config,
    'set_config': _t_set_config,
    'system_info': _t_system_info,
    'send_qq_message': _t_send_qq_message,
}


async def run_tool(name: str, args: dict) -> dict:
    """执行工具, 返回结果 dict; 异常由调用方捕获"""
    func = _DISPATCH.get(name)
    if not func:
        raise ValueError(f'未知工具: {name}')
    args = args or {}
    return await func(**args)


# ==================== OpenAI tools schema ====================

TOOLS_SCHEMA = [
    {
        'type': 'function',
        'function': {
            'name': 'list_dir',
            'description': '列出仓库内某个目录下的文件与子目录。',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string', 'description': "相对仓库根的路径, 默认 '.'"}},
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': '读取仓库内某个文本文件的内容。',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string', 'description': '相对仓库根的文件路径'}},
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'write_file',
            'description': '写入/创建仓库内的文件 (会覆盖原内容并自动创建父目录)。用于编写或修改插件。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': '相对仓库根的文件路径, 如 plugins/demo/main.py'},
                    'content': {'type': 'string', 'description': '完整文件内容'},
                },
                'required': ['path', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'delete_file',
            'description': '删除仓库内的文件或目录。',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'make_dir',
            'description': '在仓库内创建目录。',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_plugins',
            'description': '列出所有插件 (含未加载的) 及其加载状态、handler 数。',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'list_handlers',
            'description': '列出当前所有已注册的命令处理器 (名称/正则/描述/所属插件)。',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'reload_plugin',
            'description': '热重载指定插件目录并返回自检结果 (handler 数与报错)。编写或修改插件后用它测试是否能正常加载。',
            'parameters': {
                'type': 'object',
                'properties': {'name': {'type': 'string', 'description': '插件目录名, 如 example'}},
                'required': ['name'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'run_python',
            'description': '在仓库根目录以独立子进程运行一段 Python 代码并返回 stdout/stderr (带超时), 用于自测逻辑或验证导入。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'code': {'type': 'string', 'description': 'Python 源码'},
                    'timeout': {'type': 'integer', 'description': '超时秒数, 默认 30, 上限 120'},
                },
                'required': ['code'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_config',
            'description': '读取框架配置 (settings 或 connections), api_key 会被隐去。',
            'parameters': {
                'type': 'object',
                'properties': {'file': {'type': 'string', 'enum': ['settings', 'connections']}},
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'set_config',
            'description': '修改框架配置项并保存 (热加载生效)。key 为点号路径。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file': {'type': 'string', 'enum': ['settings', 'connections']},
                    'key': {'type': 'string', 'description': '如 web.framework_name'},
                    'value': {'description': '要设置的值 (字符串/数字/布尔/列表/对象)'},
                },
                'required': ['file', 'key', 'value'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'system_info',
            'description': '检查操作系统与框架运行状态 (OS/Python/CPU/内存/插件数)。',
            'parameters': {'type': 'object', 'properties': {}},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'send_qq_message',
            'description': '通过 OneBot 主动发送一条 QQ 消息。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'target_type': {'type': 'string', 'enum': ['group', 'private']},
                    'target_id': {'type': 'string', 'description': '群号或 QQ 号'},
                    'text': {'type': 'string'},
                },
                'required': ['target_type', 'target_id', 'text'],
            },
        },
    },
]
