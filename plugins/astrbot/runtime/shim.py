"""把伪 astrbot 模块树注入 sys.modules, 让 AstrBot 插件无改动 import。"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
import types

from core.base.logger import PLUGIN, get_logger

from . import commands as _cmd
from . import components as _comp
from . import events as _ev
from . import paths as _paths
from . import session as _sess

_installed = False


def _new_module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__["__all__"] = []
    sys.modules[name] = mod
    return mod


def _export(mod: types.ModuleType, **attrs):
    for k, v in attrs.items():
        setattr(mod, k, v)
    mod.__all__ = list(attrs.keys())


# ---------- obscure astrbot.* 子模块兜底 (返回宽松 stub) ----------

class _Dummy:
    """既能当类继承, 又能当对象/函数调用的宽松占位。"""

    def __init__(self, *_, **__):
        pass

    def __call__(self, *_, **__):
        return self

    def __getattr__(self, _item):
        return _Dummy()

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


class _StubModule(types.ModuleType):
    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Dummy()


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """为未显式定义的 astrbot.* 子模块提供宽松 stub, 避免缺接口导致 import 失败。"""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "astrbot" or fullname.startswith("astrbot."):
            if fullname in sys.modules:
                return None
            return importlib.machinery.ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):
        mod = _StubModule(spec.name)
        mod.__path__ = []  # 当作包, 允许继续 import 子模块
        get_logger(PLUGIN, "astrbot基座").debug(f"[astrbot基座] 使用兜底 stub 模块: {spec.name}")
        return mod

    def exec_module(self, module):
        return None


def install():
    """构建并注入伪 astrbot 模块树 (幂等)。"""
    global _installed
    if _installed and "astrbot" in sys.modules:
        return
    log = get_logger(PLUGIN, "astrbot基座")

    logger = get_logger(PLUGIN, "astrbot插件")

    # ---- filter 命名空间 ----
    flt = _cmd._FilterModule("astrbot.api.event.filter")
    sys.modules["astrbot.api.event.filter"] = flt

    comp_attrs = {
        "ComponentType": _comp.ComponentType,
        "BaseMessageComponent": _comp.BaseMessageComponent,
        "Plain": _comp.Plain,
        "Text": _comp.Plain,
        "Face": _comp.Face,
        "Image": _comp.Image,
        "At": _comp.At,
        "AtAll": _comp.AtAll,
        "Record": _comp.Record,
        "Video": _comp.Video,
        "File": _comp.File,
        "Reply": _comp.Reply,
        "Poke": _comp.Poke,
        "Json": _comp.Json,
        "Node": _comp.Node,
        "Nodes": _comp.Nodes,
        "Forward": _comp.Forward,
        "Unknown": _comp.Unknown,
    }

    star_attrs = {
        "Context": _ev.Context,
        "Star": _ev.Star,
        "register": _cmd.register,
        "StarTools": _ev.StarTools,
        "StarMetadata": _Dummy,
    }

    event_attrs = {
        "filter": flt,
        "AstrMessageEvent": _ev.AstrMessageEvent,
        "MessageChain": _comp.MessageChain,
        "MessageEventResult": _comp.MessageEventResult,
        "ResultContentType": _Dummy,
        "EventMessageType": _cmd.EventMessageType,
        "MessageType": _cmd.EventMessageType,
    }

    platform_attrs = {
        "AstrMessageEvent": _ev.AstrMessageEvent,
        "AstrBotMessage": _ev.AstrBotMessage,
        "MessageMember": _ev.MessageMember,
        "Group": _ev.Group,
        "PlatformMetadata": _ev.PlatformMetadata,
        "MessageType": _cmd.EventMessageType,
    }

    # ---- 顶层 / api ----
    astrbot = _new_module("astrbot")
    astrbot.logger = logger
    api = _new_module("astrbot.api")
    _export(api, logger=logger, AstrBotConfig=_ev.AstrBotConfig)
    api.__path__ = []

    api_event = _new_module("astrbot.api.event")
    _export(api_event, **event_attrs)
    api_event.__path__ = []
    api_event.filter = flt

    api_star = _new_module("astrbot.api.star")
    _export(api_star, **star_attrs)

    api_msgcomp = _new_module("astrbot.api.message_components")
    _export(api_msgcomp, **comp_attrs)

    api_provider = _new_module("astrbot.api.provider")
    _export(api_provider, Provider=_Dummy, ProviderRequest=_Dummy, LLMResponse=_Dummy)

    api_platform = _new_module("astrbot.api.platform")
    _export(api_platform, **platform_attrs)

    api_all = _new_module("astrbot.api.all")
    _export(api_all, **{**comp_attrs, **star_attrs, **event_attrs,
                        "logger": logger, "AstrBotConfig": _ev.AstrBotConfig})

    # ---- core ----
    core = _new_module("astrbot.core")
    core.logger = logger
    core.__path__ = []

    core_message = _new_module("astrbot.core.message")
    core_message.__path__ = []
    core_components = _new_module("astrbot.core.message.components")
    _export(core_components, **comp_attrs)
    core_mer = _new_module("astrbot.core.message.message_event_result")
    _export(core_mer, MessageChain=_comp.MessageChain,
            MessageEventResult=_comp.MessageEventResult,
            ResultContentType=_Dummy, EventMessageType=_cmd.EventMessageType)

    core_star = _new_module("astrbot.core.star")
    _export(core_star, **star_attrs)
    core_star.__path__ = []
    core_star_tools = _new_module("astrbot.core.star.star_tools")
    _export(core_star_tools, StarTools=_ev.StarTools)

    core_star_filter = _new_module("astrbot.core.star.filter")
    core_star_filter.__path__ = []
    core_filter_emt = _new_module("astrbot.core.star.filter.event_message_type")
    _export(core_filter_emt, EventMessageType=_cmd.EventMessageType)
    core_filter_perm = _new_module("astrbot.core.star.filter.permission_type")
    _export(core_filter_perm, PermissionType=_cmd.PermissionType)

    core_utils = _new_module("astrbot.core.utils")
    core_utils.__path__ = []
    core_utils_waiter = _new_module("astrbot.core.utils.session_waiter")
    _export(core_utils_waiter, session_waiter=_sess.session_waiter,
            SessionController=_sess.SessionController,
            SessionFilter=_Dummy)
    core_utils_path = _new_module("astrbot.core.utils.astrbot_path")
    _export(core_utils_path,
            get_astrbot_root=_paths.get_astrbot_root,
            get_astrbot_path=_paths.get_astrbot_path,
            get_astrbot_data_path=_paths.get_astrbot_data_path,
            get_astrbot_config_path=_paths.get_astrbot_config_path,
            get_astrbot_plugin_path=_paths.get_astrbot_plugin_path,
            get_astrbot_plugin_data_path=_paths.get_astrbot_plugin_data_path,
            get_astrbot_t2i_templates_path=_paths.get_astrbot_t2i_templates_path,
            get_astrbot_temp_path=_paths.get_astrbot_temp_path,
            get_astrbot_system_tmp_path=_paths.get_astrbot_system_tmp_path)

    core_config = _new_module("astrbot.core.config")
    core_config.__path__ = []
    _export(core_config, AstrBotConfig=_ev.AstrBotConfig)
    core_config_ac = _new_module("astrbot.core.config.astrbot_config")
    _export(core_config_ac, AstrBotConfig=_ev.AstrBotConfig)

    # ---- platform ----
    plat = _new_module("astrbot.core.platform")
    _export(plat, **platform_attrs)
    plat.__path__ = []
    plat_ame = _new_module("astrbot.core.platform.astr_message_event")
    _export(plat_ame, AstrMessageEvent=_ev.AstrMessageEvent, MessageSesion=_Dummy)
    plat_abm = _new_module("astrbot.core.platform.astrbot_message")
    _export(plat_abm, AstrBotMessage=_ev.AstrBotMessage, MessageMember=_ev.MessageMember,
            Group=_ev.Group, MessageType=_cmd.EventMessageType)
    plat_meta = _new_module("astrbot.core.platform.platform_metadata")
    _export(plat_meta, PlatformMetadata=_ev.PlatformMetadata)
    plat_mtype = _new_module("astrbot.core.platform.message_type")
    _export(plat_mtype, MessageType=_cmd.EventMessageType)

    plat_sources = _new_module("astrbot.core.platform.sources")
    plat_sources.__path__ = []
    plat_aiocq = _new_module("astrbot.core.platform.sources.aiocqhttp")
    plat_aiocq.__path__ = []
    plat_aiocq_evt = _new_module("astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event")
    _export(plat_aiocq_evt, AiocqhttpMessageEvent=_ev.AstrMessageEvent)

    # ---- 兜底 finder (最后再装, 不影响上面已显式定义的模块) ----
    if not any(isinstance(f, _StubFinder) for f in sys.meta_path):
        sys.meta_path.append(_StubFinder())

    _installed = True
    log.info("[astrbot基座] 已注入 astrbot 兼容层")
