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

# 仓库根目录: plugins/ai_dev/app/tools.py -> 上溯四层 (app -> ai_dev -> plugins -> 根)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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


def _render_message(message) -> str:
    """把 OneBot 消息 (字符串或消息段列表) 渲染成可读文本, 非文本段以 [类型] 表示"""
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        parts = []
        for seg in message:
            if isinstance(seg, dict):
                t = seg.get('type')
                if t == 'text':
                    parts.append(seg.get('data', {}).get('text', ''))
                else:
                    parts.append(f'[{t}]')
            else:
                parts.append(str(seg))
        return ''.join(parts)
    return str(message)


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


async def _t_test_command(text: str, user_id: str = '10000001', group_id=None,
                          as_owner: bool = True, timeout: int = 15) -> dict:
    """主动构造一条消息事件并真实触发匹配的处理器, 实地验证指令功能是否正常。

    与 reload_plugin (只做热重载自检) 不同, 本工具会真正执行处理器逻辑:
    插件内的网络请求、定时器等都会真实运行 (在框架进程内, 走服务器的网络),
    处理器的回复会被捕获返回而不会真正发往 QQ; 不受冷却限制。
    """
    pm = _plugin_manager()
    if not pm:
        raise ValueError('插件管理器不可用')
    if not text or not str(text).strip():
        raise ValueError('缺少要测试的指令文本 text')
    from core.onebot.event import MessageEvent

    is_group = group_id is not None
    uid = int(user_id) if str(user_id).isdigit() else user_id
    gid = (int(group_id) if str(group_id).isdigit() else group_id) if is_group else None
    event = MessageEvent({
        'post_type': 'message',
        'message_type': 'group' if is_group else 'private',
        'sub_type': 'normal',
        'message_id': 0,
        'user_id': uid,
        'group_id': gid,
        'message': [{'type': 'text', 'data': {'text': str(text)}}],
        'raw_message': str(text),
        'sender': {'user_id': uid, 'nickname': 'AI测试'},
        'self_id': 0,
    })

    captured = []

    class _CaptureAPI:
        async def send_group_msg(self, group_id, message, **kw):
            captured.append({'action': 'send_group_msg', 'group_id': group_id, 'text': _render_message(message)})
            return {'status': 'ok', 'retcode': 0, 'data': {'message_id': 0}}

        async def send_private_msg(self, user_id, message, **kw):
            captured.append({'action': 'send_private_msg', 'user_id': user_id, 'text': _render_message(message)})
            return {'status': 'ok', 'retcode': 0, 'data': {'message_id': 0}}

        async def call_api(self, action, params=None, **kw):
            captured.append({'action': action, 'params': params})
            return {'status': 'ok', 'retcode': 0, 'data': {}}

    event._api = _CaptureAPI()

    try:
        to = min(int(timeout), 120)
    except (TypeError, ValueError):
        to = 15

    # 与 dispatch 相同的筛选: 场景 / 权限 / 正则, 取第一个匹配的处理器
    match = None
    for h in pm._all_handlers:
        if h['group_only'] and not is_group:
            continue
        if h['private_only'] and is_group:
            continue
        if h['owner_only'] and not as_owner:
            continue
        m = h['compiled'].search(str(text))
        if m:
            match = (h, m)
            break

    if not match:
        return {'matched': False, 'message': '没有处理器匹配该指令 (检查正则/场景/权限)', 'replies': []}

    h, m = match
    start = time.time()
    error = ''
    tb = ''
    timed_out = False
    try:
        if h['is_coro']:
            await asyncio.wait_for(h['func'](event, m), timeout=to)
        else:
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(loop.run_in_executor(None, h['func'], event, m), timeout=to)
    except asyncio.TimeoutError:
        timed_out = True
        error = f'处理器执行超时 ({to}s)'
    except Exception as e:  # noqa: BLE001 — 把处理器内部异常回报给模型
        import traceback
        error = f'{type(e).__name__}: {e}'
        tb = traceback.format_exc()[-3000:]
    return {
        'matched': True,
        'handler': h['name'],
        'plugin': h.get('_plugin', ''),
        'pattern': h['pattern'],
        'duration_ms': int((time.time() - start) * 1000),
        'timed_out': timed_out,
        'error': error,
        'traceback': tb,
        'reply_count': len(captured),
        'replies': captured,
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
    'test_command': _t_test_command,
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
            'name': 'test_command',
            'description': (
                '主动模拟用户发送一条指令并真实触发匹配的处理器, 验证功能是否正常 '
                '(网络请求/定时器等会真实运行)。编写或修改插件并 reload_plugin 自检通过后, '
                '应再用本工具实际跑一遍指令, 检查 matched/error/replies 确认功能无异常。'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'text': {'type': 'string', 'description': '要测试的指令文本, 如 "ping" 或 "天气 北京"'},
                    'user_id': {'type': 'string', 'description': '模拟的发送者 QQ 号, 默认 10000001'},
                    'group_id': {'type': 'string', 'description': '群号; 提供则模拟群聊, 不提供则模拟私聊'},
                    'as_owner': {'type': 'boolean', 'description': '是否以主人身份触发 (可测试 owner_only 指令), 默认 true'},
                    'timeout': {'type': 'integer', 'description': '处理器执行超时秒数, 默认 15, 上限 120'},
                },
                'required': ['text'],
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
