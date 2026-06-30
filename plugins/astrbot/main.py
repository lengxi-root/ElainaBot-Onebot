"""AstrBot 插件基座 — 让 ElainaBot-Onebot 直接运行 AstrBot 框架插件。

把 AstrBot 插件放到 ``plugins/astrbot/apps/<插件名>/`` 下 (含 ``main.py``),
本基座会在加载期注入 astrbot 兼容层、发现并 import 各插件、把其 ``@filter.command``
/ ``@filter.regex`` / ``@filter.event_message_type`` 注册为框架 handler。
"""

from __future__ import annotations

import importlib
import json
import os

from core.base.logger import PLUGIN, get_logger
from core.plugin.context import ctx
from core.plugin.decorators import on_load, on_unload

from .runtime import commands as _cmd
from .runtime import deps, state
from .runtime.shim import install as install_shim

__plugin_meta__ = {
    "name": "AstrBot 基座",
    "author": "Devin",
    "description": "AstrBot 插件适配器: 直接运行 AstrBot 框架插件",
    "version": "1.0.0",
}

log = get_logger(PLUGIN, "astrbot基座")

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_APPS_DIR = os.path.join(_PLUGIN_DIR, "apps")

_DEFAULT_CONFIG = {
    "command_prefixes": {},   # {插件名: 指令前缀}
    "disabled_apps": [],      # 停用的插件名 (不加载)
    "apps": {},               # {插件名: 配置覆盖 dict}
}


def _load_config() -> dict:
    """读取基座配置 (data/config.json), 不存在则写入默认值。"""
    try:
        data_dir = ctx.data_dir if ctx else os.path.join(_PLUGIN_DIR, "data")
    except Exception:
        data_dir = os.path.join(_PLUGIN_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "config.json")
    if not os.path.isfile(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(_DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return dict(_DEFAULT_CONFIG)
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        return {**_DEFAULT_CONFIG, **(cfg if isinstance(cfg, dict) else {})}
    except Exception as e:
        log.warning(f"[astrbot基座] 读取配置失败, 使用默认: {e}")
        return dict(_DEFAULT_CONFIG)


def _discover_apps() -> list[str]:
    if not os.path.isdir(_APPS_DIR):
        os.makedirs(_APPS_DIR, exist_ok=True)
        return []
    apps: list[str] = []
    for name in sorted(os.listdir(_APPS_DIR)):
        app_dir = os.path.join(_APPS_DIR, name)
        if name.startswith((".", "_")) or not os.path.isdir(app_dir):
            continue
        if os.path.isfile(os.path.join(app_dir, "main.py")):
            apps.append(name)
    return apps


def _setup():
    """import 期同步装配 (必须在此注册 handler)。"""
    state.reset()
    state.set_config(_load_config())

    base_data = os.path.join(_PLUGIN_DIR, "data")
    apps_data = os.path.join(base_data, "apps")
    os.makedirs(apps_data, exist_ok=True)
    state.set_data_root(base_data)
    state.set_apps_data_root(apps_data)
    state.set_apps_dir(_APPS_DIR)

    # 注入兼容层 (import 插件前必须就位)
    install_shim()

    apps = _discover_apps()
    if not apps:
        log.warning(f"[astrbot基座] apps/ 下未发现可加载的插件: {_APPS_DIR}")
    for app in apps:
        if not state.is_app_enabled(app):
            log.info(f"[astrbot基座] app [{app}] 已停用, 跳过")
            continue
        app_dir = os.path.join(_APPS_DIR, app)
        try:
            deps.ensure_requirements(app, app_dir)
        except Exception as e:
            log.warning(f"[astrbot基座] [{app}] 依赖检查异常 (继续加载): {e}")
        mod_name = f"{__package__}.apps.{app}.main"
        try:
            importlib.import_module(mod_name)
            n = _cmd.collect_app_specs(app, mod_name, app_dir)
            log.info(f"[astrbot基座] 已加载 app: {app} (插件 {n} 个)")
        except Exception as e:
            log.error(f"[astrbot基座] 加载 app [{app}] 失败: {e}", exc_info=True)

    _cmd.build_handlers()


@on_load
async def _on_load():
    """加载期: 实例化所有插件并调用 initialize()。"""
    await _cmd.instantiate_all()
    log.info(f"[astrbot基座] 启动完成, 共 {len(state.PLUGIN_SPECS)} 个 AstrBot 插件")


@on_unload
async def _on_unload():
    await _cmd.terminate_all()


# 入口 import 期装配
_setup()
