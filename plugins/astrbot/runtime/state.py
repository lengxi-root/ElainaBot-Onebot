"""全局状态 + 框架访问 (main.py 在 import 期重置)。"""

from __future__ import annotations

from core.base.logger import PLUGIN, get_logger

log = get_logger(PLUGIN, "astrbot基座")

PLUGIN_SPECS: list = []          # 发现到的 AstrBot 插件 (PluginSpec)
STAR_SUBCLASSES: list = []       # 所有定义过的 Star 子类 (按 import 顺序)
_CONFIG: dict = {}               # 基座配置
_DATA_ROOT = {"path": ""}        # 基座数据根 (= plugins/astrbot/data)
_APPS_DATA_ROOT = {"path": ""}   # apps 数据根目录 (StarTools.get_data_dir 用)
_APPS_DIR = {"path": ""}         # apps 源码目录 (= plugins/astrbot/apps, 插件本体所在)


def reset():
    PLUGIN_SPECS.clear()
    STAR_SUBCLASSES.clear()


def set_config(cfg: dict):
    _CONFIG.clear()
    _CONFIG.update(cfg or {})


def set_apps_data_root(path: str):
    _APPS_DATA_ROOT["path"] = path


def apps_data_root() -> str:
    return _APPS_DATA_ROOT["path"]


def set_apps_dir(path: str):
    _APPS_DIR["path"] = path


def apps_dir() -> str:
    return _APPS_DIR["path"]


def set_data_root(path: str):
    _DATA_ROOT["path"] = path


def data_root() -> str:
    import os
    return _DATA_ROOT["path"] or os.path.join(os.getcwd(), "data")


# ---- 框架内部访问 ----

def get_api(self_id: str | None = None):
    """取框架的 OneBot API 调用器 (主动发送/调用动作)。"""
    try:
        from core.onebot.api import get_api as _get_api

        return _get_api()
    except Exception as e:
        log.warning(f"[astrbot基座] 获取 OneBot API 失败: {e}")
        return None


def owner_ids() -> list[str]:
    try:
        from core.base.config import cfg as core_cfg

        ids = core_cfg.get("settings", "owner.ids", []) or []
        return [str(x) for x in ids if str(x).strip()]
    except Exception:
        return []


def is_bot_owner(event) -> bool:
    uid = str(getattr(event, "user_id", "") or "")
    return bool(uid) and uid in owner_ids()


# ---- 基座配置项 ----

def command_prefix(name: str) -> str:
    """某插件配置的指令前缀 (留空=无前缀)。"""
    m = _CONFIG.get("command_prefixes")
    return str(m.get(name) or "").strip() if isinstance(m, dict) else ""


def disabled_apps() -> set:
    d = _CONFIG.get("disabled_apps")
    return {str(x) for x in d} if isinstance(d, (list, tuple, set)) else set()


def is_app_enabled(name: str) -> bool:
    return str(name) not in disabled_apps()
