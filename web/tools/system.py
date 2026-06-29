"""系统信息采集 + 重启"""

import asyncio
import contextlib
import gc
import logging
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime

import psutil
from aiohttp import web

from web.tools import _common

log = logging.getLogger('ElainaBot.web.sysinfo')

_IS_WINDOWS = platform.system() == 'Windows'
_start_time = datetime.now()
_last_gc = 0.0
_GC_INTERVAL = 30
_info_cache = (0.0, None)
_INFO_CACHE_TTL = 5
_app = None
_cpu_model_cache = None


def set_context(app_instance, start_time=None):
    global _app, _start_time
    _app = app_instance
    _common.set_app(app_instance)
    if start_time:
        _start_time = start_time


def _cpu_model():
    global _cpu_model_cache
    if _cpu_model_cache:
        return _cpu_model_cache
    model = ''
    try:
        if _IS_WINDOWS:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r'HARDWARE\DESCRIPTION\System\CentralProcessor\0',
            )
            model = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
            winreg.CloseKey(key)
        else:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if line.startswith('model name'):
                        model = line.split(':', 1)[1].strip()
                        break
    except Exception:
        pass
    if not model:
        with contextlib.suppress(Exception):
            model = platform.processor() or ''
    if not model:
        model = f'{psutil.cpu_count(logical=True)} 核处理器'
    _cpu_model_cache = model
    return model


async def _message_stats():
    """从 message.db 聚合今日消息统计"""
    today = datetime.now().strftime('%Y-%m-%d')
    out = {'today_messages': 0, 'today_active': 0, 'active_groups': 0,
           'total_users': 0, 'total_groups': 0}
    rows = await _common.query_log(
        'message',
        "SELECT COUNT(*) AS cnt, "
        "COUNT(DISTINCT CASE WHEN user_id!='' THEN user_id END) AS users, "
        "COUNT(DISTINCT CASE WHEN group_id!='' THEN group_id END) AS groups_ "
        "FROM log WHERE timestamp LIKE ?",
        (today + '%',),
    )
    if rows:
        out['today_messages'] = rows[0].get('cnt', 0) or 0
        out['today_active'] = rows[0].get('users', 0) or 0
        out['active_groups'] = rows[0].get('groups_', 0) or 0
    total = await _common.query_log(
        'message',
        "SELECT COUNT(DISTINCT CASE WHEN user_id!='' THEN user_id END) AS users, "
        "COUNT(DISTINCT CASE WHEN group_id!='' THEN group_id END) AS groups_ FROM log",
    )
    if total:
        out['total_users'] = total[0].get('users', 0) or 0
        out['total_groups'] = total[0].get('groups_', 0) or 0
    return out


def _get_hw_info() -> dict:
    """CPU/内存/磁盘等硬件信息 (同步, 可在 executor 运行)"""
    global _last_gc
    proc = psutil.Process(os.getpid())
    now = time.time()
    if now - _last_gc >= _GC_INTERVAL:
        gc.collect(0)
        _last_gc = now

    mem = proc.memory_info()
    sys_mem = psutil.virtual_memory()
    rss_mb = mem.rss / (1024**2)
    mem_total_mb = sys_mem.total / (1024**2)

    try:
        cpu_cores = psutil.cpu_count(logical=True)
        cpu_pct = max(proc.cpu_percent(interval=0.05), 1.0)
        sys_cpu = max(psutil.cpu_percent(interval=0.05), 5.0)
    except Exception:
        cpu_cores, cpu_pct, sys_cpu = 1, 1.0, 5.0

    uptime = int((datetime.now() - _start_time).total_seconds())
    try:
        boot = datetime.fromtimestamp(psutil.boot_time())
        sys_uptime = int((datetime.now() - boot).total_seconds())
    except Exception:
        sys_uptime = uptime

    disk = psutil.disk_usage(os.path.abspath(os.getcwd()))

    plugins_count = bots_count = 0
    if _app:
        pm = getattr(_app, 'plugin_manager', None)
        if pm:
            plugins_count = getattr(pm, 'handler_count', 0)
        bots_count = len(_common.connected_ids())

    return {
        'cpu_percent': round(sys_cpu, 1),
        'framework_cpu_percent': round(cpu_pct, 1),
        'cpu_cores': cpu_cores,
        'cpu_model': _cpu_model(),
        'memory_percent': round(sys_mem.percent, 1),
        'memory_used': round(sys_mem.used / (1024**2), 1),
        'memory_total': round(mem_total_mb, 1),
        'framework_memory_percent': round((rss_mb / mem_total_mb) * 100 if mem_total_mb else 0, 1),
        'framework_memory_total': round(rss_mb, 1),
        'disk_info': {'total': disk.total, 'used': disk.used, 'free': disk.free, 'percent': disk.percent},
        'uptime': uptime,
        'system_uptime': sys_uptime,
        'start_time': _start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'system_version': platform.platform(),
        'plugins_count': plugins_count,
        'bots_count': bots_count,
    }


async def get_system_info() -> dict:
    loop = asyncio.get_running_loop()
    hw = await loop.run_in_executor(None, _get_hw_info)
    ms = await _message_stats()
    hw.update({
        'today_active': ms['today_active'],
        'today_messages': ms['today_messages'],
        'active_groups': ms['active_groups'],
        'total_users': ms['total_users'],
        'total_groups': ms['total_groups'],
    })
    return hw


async def handle_system_info(request: web.Request):
    global _info_cache
    try:
        now = time.time()
        ts, data = _info_cache
        if data and now - ts < _INFO_CACHE_TTL:
            return web.json_response(data)
        data = await get_system_info()
        _info_cache = (now, data)
        return web.json_response(data)
    except Exception as e:
        log.error(f'获取系统信息失败: {e}')
        return web.json_response({'error': str(e)}, status=500)


# ──────────────── 重启 ────────────────

_UNIX_TEMPLATE = """import os, sys, time
def main():
    main_path = r"{main_py}"
    time.sleep(1)
    os.chdir(os.path.dirname(main_path))
    try: os.remove(__file__)
    except: pass
    os.execv(sys.executable, [sys.executable, main_path])
if __name__ == "__main__":
    main()
"""

_WIN_TEMPLATE = """import os, sys, time, subprocess
def main():
    time.sleep(3)
    main_path = r"{main_py}"
    os.chdir(os.path.dirname(main_path))
    subprocess.Popen([sys.executable, main_path], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    time.sleep(1)
    try: os.remove(__file__)
    except: pass
    sys.exit(0)
if __name__ == "__main__":
    main()
"""


async def handle_restart(request: web.Request):
    try:
        from core.application import get_app

        app = get_app()
        if app:
            app._restart_requested = True
            if app._stop_event:
                app._stop_event.set()
            return web.json_response({'success': True, 'message': '正在重启...'})
    except Exception:
        pass

    base = _common.base_dir()
    main_py = os.path.join(base, 'main.py')
    if not os.path.exists(main_py):
        return web.json_response({'success': False, 'error': 'main.py 不存在'})

    data_dir = os.path.join(base, 'data')
    os.makedirs(data_dir, exist_ok=True)
    restarter = os.path.join(data_dir, 'bot_restarter.py')
    try:
        script = (_WIN_TEMPLATE if _IS_WINDOWS else _UNIX_TEMPLATE).format(main_py=main_py)
        with open(restarter, 'w', encoding='utf-8') as f:
            f.write(script)
        if _IS_WINDOWS:
            subprocess.Popen([sys.executable, restarter], cwd=base,
                             creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
            threading.Thread(target=lambda: (time.sleep(1), os._exit(0)), daemon=True).start()
        else:
            subprocess.Popen([sys.executable, restarter], cwd=base, start_new_session=True)
        return web.json_response({'success': True, 'message': '正在重启...'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})
