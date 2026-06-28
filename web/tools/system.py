"""系统信息采集"""

import gc
import logging
import os
import platform
import time
from datetime import datetime

import psutil
from aiohttp import web

log = logging.getLogger('ElainaBot.web.sysinfo')

_start_time = datetime.now()
_bot_manager = None
_info_cache = (0.0, None)
_INFO_CACHE_TTL = 5
_last_gc = 0.0
_GC_INTERVAL = 30

_cpu_model_cache = None


def set_context(bot_manager, start_time=None):
    global _bot_manager, _start_time
    _bot_manager = bot_manager
    if start_time:
        _start_time = start_time


def _cpu_model():
    global _cpu_model_cache
    if _cpu_model_cache:
        return _cpu_model_cache
    model = ''
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('model name'):
                    model = line.split(':', 1)[1].strip()
                    break
    except Exception:
        pass
    if not model:
        try:
            model = platform.processor() or ''
        except Exception:
            pass
    if not model:
        cores = psutil.cpu_count(logical=True)
        model = f'{cores} Core Processor'
    _cpu_model_cache = model
    return model


def get_system_info() -> dict:
    global _last_gc
    proc = psutil.Process(os.getpid())
    now = time.time()
    if now - _last_gc >= _GC_INTERVAL:
        gc.collect(0)
        _last_gc = now

    mem = proc.memory_info()
    sys_mem = psutil.virtual_memory()
    rss_mb = mem.rss / (1024 ** 2)
    mem_total_mb = sys_mem.total / (1024 ** 2)

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

    from core.base.config import cfg
    fw_name = cfg.get('settings', 'web.framework_name', 'ElainaBot')

    plugins_count = 0
    bots_count = 0
    today_messages = 0
    if _bot_manager:
        if _bot_manager.adapter:
            bots_count = len(_bot_manager.adapter.bots)
        if _bot_manager.plugin_manager:
            plugins_count = len(_bot_manager.plugin_manager._plugins)
        if _bot_manager.log_service:
            try:
                rows = _bot_manager.log_service.query(
                    'message',
                    'SELECT COUNT(*) as cnt FROM log',
                )
                if rows:
                    today_messages = rows[0].get('cnt', 0)
            except Exception:
                pass

    return {
        'framework_name': fw_name,
        'platform': platform.system(),
        'python_version': platform.python_version(),
        'system_version': platform.platform(),
        'cpu_percent': round(sys_cpu, 1),
        'framework_cpu_percent': round(cpu_pct, 1),
        'cpu_cores': cpu_cores,
        'cpu_model': _cpu_model(),
        'memory_percent': round(sys_mem.percent, 1),
        'memory_used': round(sys_mem.used / (1024 ** 2), 1),
        'memory_total': round(mem_total_mb, 1),
        'framework_memory_percent': round((rss_mb / mem_total_mb) * 100 if mem_total_mb else 0, 1),
        'framework_memory_total': round(rss_mb, 1),
        'disk_info': {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent,
        },
        'uptime': uptime,
        'system_uptime': sys_uptime,
        'start_time': _start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'plugins_count': plugins_count,
        'bots_count': bots_count,
        'today_messages': today_messages,
        'bot_count': bots_count,
        'plugin_count': plugins_count,
        'module_count': len(_bot_manager.module_manager._modules) if _bot_manager and _bot_manager.module_manager else 0,
    }


async def handle_system_info(request: web.Request):
    import asyncio
    global _info_cache
    try:
        now = time.time()
        ts, data = _info_cache
        if data and now - ts < _INFO_CACHE_TTL:
            return web.json_response({'success': True, 'data': data})
        data = await asyncio.get_running_loop().run_in_executor(None, get_system_info)
        _info_cache = (now, data)
        return web.json_response({'success': True, 'data': data})
    except Exception as e:
        log.error(f'获取系统信息失败: {e}')
        return web.json_response({'success': True, 'data': {'error': str(e)}})
