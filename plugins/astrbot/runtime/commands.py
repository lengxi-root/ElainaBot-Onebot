"""filter 装饰器 (command/regex/event_message_type 等) 收集 -> 注册为 ElainaBot
handler -> 分发执行。"""

from __future__ import annotations

import inspect
import re
import types
import typing

from . import sending, session, state
from .events import AstrBotConfig, AstrMessageEvent, Context

log = state.log


# ==================== 参数解析 (复刻 AstrBot) ====================

class GreedyStr(str):
    """标记接收其余全部文本的参数类型。"""


def _unwrap_optional(annotation) -> tuple:
    return tuple(a for a in typing.get_args(annotation) if a is not type(None))


def build_handler_params(func) -> dict:
    """{参数名: 注解(必填) 或 默认值(选填)}, 跳过 self/event。"""
    params: dict = {}
    for idx, (k, v) in enumerate(inspect.signature(func).parameters.items()):
        if idx < 2 or v.kind in (v.VAR_POSITIONAL, v.VAR_KEYWORD):
            continue
        params[k] = v.annotation if v.default is inspect.Parameter.empty else v.default
    return params


def validate_and_convert_params(tokens: list, param_type: dict) -> dict:
    """与 AstrBot 一致的参数强转; 抛 ValueError 表示参数不合法。"""
    result: dict = {}
    for i, (name, td) in enumerate(param_type.items()):
        if td is GreedyStr:
            result[name] = " ".join(tokens[i:])
            break
        if i >= len(tokens):
            if (
                isinstance(td, (type, types.UnionType))
                or typing.get_origin(td) is typing.Union
                or td is inspect.Parameter.empty
            ):
                raise ValueError("必要参数缺失")
            result[name] = td
            continue
        raw = tokens[i]
        try:
            if td is None:
                result[name] = int(raw) if raw.lstrip("-").isdigit() else raw
            elif isinstance(td, bool):
                low = str(raw).lower()
                if low in ("true", "yes", "1"):
                    result[name] = True
                elif low in ("false", "no", "0"):
                    result[name] = False
                else:
                    raise ValueError(f"参数 {name} 必须是布尔值")
            elif isinstance(td, str):
                result[name] = raw
            elif isinstance(td, int):
                result[name] = int(raw)
            elif isinstance(td, float):
                result[name] = float(raw)
            else:
                origin = typing.get_origin(td)
                if origin in (typing.Union, types.UnionType):
                    nn = _unwrap_optional(td)
                    result[name] = nn[0](raw) if len(nn) == 1 else raw
                elif isinstance(td, type):
                    result[name] = td(raw)
                else:
                    result[name] = raw
        except ValueError:
            raise ValueError(f"参数 {name} 类型错误") from None
    return result


# ==================== filter 枚举 ====================

class PermissionType:
    ADMIN = "admin"
    MEMBER = "member"


class EventMessageType:
    GROUP_MESSAGE = "group"
    PRIVATE_MESSAGE = "private"
    ALL = "all"


# ==================== filter 装饰器 ====================

def _add_command(func, entry: dict):
    cmds = getattr(func, "_astrbot_commands", None)
    if cmds is None:
        cmds = func._astrbot_commands = []
    cmds.append(entry)
    return func


def _command_decorator(command_name: str, alias=None, **_kw):
    names = [command_name] + sorted(alias) if alias else [command_name]

    def deco(func):
        return _add_command(func, {"kind": "command", "names": names})
    return deco


def _regex_decorator(pattern: str, **_kw):
    def deco(func):
        return _add_command(func, {"kind": "regex", "pattern": pattern})
    return deco


def _event_message_type_decorator(msg_type, **_kw):
    value = getattr(msg_type, "value", msg_type)

    def deco(func):
        func._astrbot_msg_type = value
        _add_command(func, {"kind": "listen", "msg_type": value})
        return func
    return deco


def _permission_type_decorator(perm_type, **_kw):
    value = getattr(perm_type, "value", perm_type)

    def deco(func):
        func._astrbot_perm = value
        return func
    return deco


def _passthrough_decorator(*_a, **_k):
    def deco(func):
        return func
    return deco


class CommandGroup:
    """模拟 @filter.command_group; 子指令名拼成 "<组名> <子名>"。"""

    def __init__(self, name: str):
        self.name = name

    def command(self, command_name, alias=None, **kw):
        full = f"{self.name} {command_name}"
        aliases = [f"{self.name} {a}" for a in alias] if alias else None
        return _command_decorator(full, alias=aliases, **kw)

    def group(self, name, *_a, **_k):
        return _group_decorator(f"{self.name} {name}")


def _group_decorator(name: str):
    """@filter.command_group(name) / group.group(name): 返回装饰器, 产出 CommandGroup。"""
    grp = CommandGroup(name)

    def deco(_func):
        return grp
    return deco


class _FilterModule(types.ModuleType):
    """模拟 astrbot.api.event.filter 命名空间。"""

    def __init__(self, name="astrbot.api.event.filter"):
        super().__init__(name)
        self.GreedyStr = GreedyStr
        self.PermissionType = PermissionType
        self.EventMessageType = EventMessageType

    def command(self, command_name, alias=None, **kw):
        return _command_decorator(command_name, alias=alias, **kw)

    def regex(self, pattern, **kw):
        return _regex_decorator(pattern, **kw)

    def event_message_type(self, msg_type, **kw):
        return _event_message_type_decorator(msg_type, **kw)

    def permission_type(self, perm_type, **kw):
        return _permission_type_decorator(perm_type, **kw)

    def command_group(self, name, *_a, **_k):
        return _group_decorator(name)

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        log.debug(f"[astrbot基座] 未适配的 filter.{item}, 该装饰器将被忽略")
        return _passthrough_decorator


# ==================== 指令收集 ====================

def _build_command_pattern(names: list) -> str:
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return rf"^\s*/?(?:{alt})(?=\s|$)"


_all_registered_cmd_names: set[str] = set()


def _build_exclusive_pattern(cmd: CommandSpec) -> str:
    prefix_esc = re.escape(cmd.prefix) if cmd.prefix else ""
    parts: list[str] = []
    for name in cmd.match_names:
        name_esc = re.escape(name)
        own = set(cmd.match_names)
        suffixes = sorted(
            (re.escape(other[len(name):])
             for other in _all_registered_cmd_names
             if other not in own and other.startswith(name) and len(other) > len(name)),
            key=len, reverse=True,
        )
        if suffixes:
            neg = "|".join(suffixes)
            parts.append(f"{name_esc}(?!{neg})")
        else:
            parts.append(name_esc)
    alt = "|".join(parts)
    if cmd.prefix:
        return rf"^\s*/?{prefix_esc}\s*(?:{alt})(?=\s|$)"
    return rf"^\s*/?(?:{alt})(?=\s|$)"


class CommandSpec:
    def __init__(self, kind, names, method_name, handler_params, pattern, *,
                 msg_type="all", perm=""):
        self.kind = kind                      # "command" | "regex" | "listen"
        self.names = names
        self.method_name = method_name
        self.handler_params = handler_params
        self.pattern = pattern
        self.match_names = sorted(names, key=len, reverse=True)
        self.msg_type = msg_type
        self.perm = perm
        self.prefix = ""
        self._exclude_names: frozenset[str] | None = None

    def effective_pattern(self) -> str:
        if self.kind == "listen":
            return r"[\s\S]*"
        if not self.prefix:
            return self.pattern
        esc = re.escape(self.prefix)
        if self.kind == "command":
            alt = "|".join(re.escape(n) for n in self.match_names)
            return rf"^\s*/?{esc}\s*(?:{alt})(?=\s|$)"
        base = self.pattern[1:] if self.pattern.startswith("^") else self.pattern
        return rf"^\s*{esc}\s*{base}"

    @classmethod
    def from_entry(cls, entry: dict, method_name: str, func) -> CommandSpec:
        perm = getattr(func, "_astrbot_perm", "")
        if entry["kind"] == "regex":
            return cls("regex", [method_name], method_name, {}, entry["pattern"], perm=perm)
        if entry["kind"] == "listen":
            return cls("listen", [method_name], method_name, {}, r"[\s\S]*",
                       msg_type=entry.get("msg_type", "all"), perm=perm)
        return cls("command", entry["names"], method_name,
                   build_handler_params(func), _build_command_pattern(entry["names"]),
                   perm=perm)


class PluginSpec:
    def __init__(self, cls, meta: dict, app_name: str = ""):
        self.cls = cls
        self.app_name = app_name or cls.__module__
        self.name = meta.get("name") or app_name or cls.__name__
        self.author = meta.get("author", "")
        self.desc = meta.get("desc", "")
        self.version = meta.get("version", "")
        self.repo = meta.get("repo", "")
        self.module = cls.__module__
        self.commands: list[CommandSpec] = []
        self.instance = None


def register(name="", author="", desc="", version="", repo="", *args, **kwargs):
    """@register(...) 装饰 Star 类: 仅记录元数据 (实际收集在 collect_app_specs)。"""
    meta = {"name": name, "author": author, "desc": desc, "version": version, "repo": repo}

    def deco(cls):
        cls._astrbot_meta = meta
        return cls
    return deco


def _collect_commands(cls) -> list:
    """沿 MRO 扫描带 _astrbot_commands 的方法, 生成 CommandSpec 列表。"""
    cmds: list = []
    seen: set[str] = set()
    for klass in cls.__mro__:
        for attr_name, member in vars(klass).items():
            if attr_name in seen:
                continue
            entries = getattr(member, "_astrbot_commands", None)
            if not entries:
                continue
            seen.add(attr_name)
            for entry in entries:
                cmds.append(CommandSpec.from_entry(entry, attr_name, member))
    return cmds


def _read_metadata_yaml(app_dir: str) -> dict:
    import os
    for fn in ("metadata.yaml", "metadata.yml"):
        path = os.path.join(app_dir, fn)
        if not os.path.isfile(path):
            continue
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                return data
        except Exception as e:
            log.warning(f"[astrbot基座] 读取 {fn} 失败: {e}")
    return {}


def collect_app_specs(app_name: str, module_name: str, app_dir: str) -> int:
    """import app 之后调用: 把属于该 app 的 Star 子类登记成 PluginSpec。

    同时支持 @register 与仅 metadata.yaml 的插件。
    """
    pkg_prefix = module_name.rsplit(".", 1)[0] + "."
    meta_yaml = _read_metadata_yaml(app_dir)
    found = 0
    existing = {id(s.cls) for s in state.PLUGIN_SPECS}
    for cls in state.STAR_SUBCLASSES:
        if id(cls) in existing:
            continue
        mod = getattr(cls, "__module__", "") or ""
        if not (mod == module_name or mod.startswith(pkg_prefix)):
            continue
        meta = dict(getattr(cls, "_astrbot_meta", {}) or {})
        if not meta.get("name"):
            meta["name"] = (meta_yaml.get("name") or meta_yaml.get("display_name")
                            or app_name)
        meta.setdefault("author", meta_yaml.get("author", ""))
        meta.setdefault("desc", meta_yaml.get("desc", "") or meta_yaml.get("description", ""))
        meta.setdefault("version", meta_yaml.get("version", ""))
        meta.setdefault("repo", meta_yaml.get("repo", ""))
        spec = PluginSpec(cls, meta, app_name=app_name)
        spec.commands = _collect_commands(cls)
        state.PLUGIN_SPECS.append(spec)
        existing.add(id(cls))
        found += 1
        log.info(f"[astrbot基座] 发现插件 [{spec.name}] v{spec.version}, 指令 {len(spec.commands)} 条")
    return found


# ==================== 分发 ====================

def _strip_command(content: str, match_names: list, prefix: str = "",
                   exclude_names: frozenset[str] | None = None):
    """归一空白, 去掉可选 '/' + 插件前缀 + 命中的指令名, 返回 (matched, tokens)。"""
    msg = " ".join((content or "").split())
    if msg.startswith("/"):
        msg = msg[1:].lstrip()
    if prefix:
        if not msg.startswith(prefix):
            return False, []
        msg = msg[len(prefix):].lstrip()
    for full in match_names:
        if msg == full or msg.startswith(full + " "):
            if exclude_names:
                for longer in exclude_names:
                    if msg == longer or msg.startswith(longer + " "):
                        return False, []
            return True, msg[len(full):].split()
    return False, []


def _strip_prefix(content: str, prefix: str) -> str:
    if not prefix:
        return content
    msg = " ".join((content or "").split())
    body = msg[1:].lstrip() if msg.startswith("/") else msg
    return body[len(prefix):].lstrip() if body.startswith(prefix) else content


def _resolve_role(event) -> str:
    return "admin" if state.is_bot_owner(event) else "member"


def _scene_ok(event, msg_type: str) -> bool:
    if msg_type == "all":
        return True
    is_group = bool(getattr(event, "group_id", None))
    if msg_type == "group":
        return is_group
    if msg_type == "private":
        return not is_group
    return True


async def _invoke(method, astr_event, event, kwargs):
    try:
        if inspect.isasyncgenfunction(method):
            async for result in method(astr_event, **kwargs):
                await sending.send_result(event, result)
        else:
            res = method(astr_event, **kwargs)
            if inspect.isawaitable(res):
                res = await res
            await sending.send_result(event, res)
        if astr_event.get_result() is not None:
            await sending.send_result(event, astr_event.get_result())
    except Exception as e:
        log.error(f"[astrbot基座] 指令 [{astr_event.message_str[:20]}] 执行异常: {e}", exc_info=True)


def make_wrapper(spec: PluginSpec, cmd: CommandSpec):
    async def _wrapper(event, match):
        instance = spec.instance
        method = getattr(instance, cmd.method_name, None) if instance else None
        if method is None:
            return
        if not _scene_ok(event, cmd.msg_type):
            return
        if cmd.perm == "admin" and not state.is_bot_owner(event):
            return

        kwargs: dict = {}
        content = None
        if cmd.kind == "command":
            ok, tokens = _strip_command(event.content, cmd.match_names, cmd.prefix,
                                        exclude_names=cmd._exclude_names)
            if not ok:
                return
            try:
                kwargs = validate_and_convert_params(tokens, cmd.handler_params)
            except ValueError as e:
                await sending.send_chain(str(e), event=event)
                return
            content = _strip_prefix(event.content, cmd.prefix) if cmd.prefix else None

        astr_event = AstrMessageEvent(event, role=_resolve_role(event), content=content)
        await _invoke(method, astr_event, event, kwargs)

    _wrapper.__name__ = f"astrbot_{spec.name}_{cmd.method_name}"
    return _wrapper


def build_handlers():
    """把发现到的指令注册为 ElainaBot handler。"""
    from core.plugin.decorators import handler

    _all_registered_cmd_names.clear()
    for spec in state.PLUGIN_SPECS:
        for cmd in spec.commands:
            if cmd.kind == "command":
                _all_registered_cmd_names.update(cmd.names)

    for spec in state.PLUGIN_SPECS:
        for cmd in spec.commands:
            if cmd.kind == "command":
                longer: set[str] = set()
                own = set(cmd.names)
                for name in cmd.names:
                    for other in _all_registered_cmd_names:
                        if other not in own and other.startswith(name) and len(other) > len(name):
                            longer.add(other)
                cmd._exclude_names = frozenset(longer) if longer else None

    total = 0
    for spec in state.PLUGIN_SPECS:
        prefix = state.command_prefix(spec.name)
        for cmd in spec.commands:
            cmd.prefix = prefix
            if cmd.kind == "command":
                pattern = _build_exclusive_pattern(cmd)
                priority = 10
            elif cmd.kind == "listen":
                pattern = cmd.effective_pattern()
                priority = -10  # 监听类最后处理, 不阻断指令
            else:
                pattern = cmd.effective_pattern()
                priority = 0
            handler(
                pattern,
                name=f"{spec.name}:{cmd.names[0]}",
                desc=f"[{spec.name}] {cmd.names[0]}",
                priority=priority,
            )(make_wrapper(spec, cmd))
            total += 1
    log.info(f"[astrbot基座] 已注册 {total} 条指令处理器")
    session.register_interceptor()
    return total


# ==================== 生命周期 ====================

def _inject_star_attrs(spec):
    """复刻 AstrBot: 实例化前把 name/author/plugin_id 注入到类上。"""
    cls = spec.cls
    name = (spec.name or cls.__name__).replace("/", "_")
    author = spec.author or "unknown"
    try:
        cls.name = name
        cls.author = author
        cls.plugin_id = f"{author}/{name}"
    except (AttributeError, TypeError):
        pass


def _construct_star(cls, context, config):
    """兼容 Star.__init__ 签名: (context, config) / (context) / ()。"""
    try:
        nparams = len([p for p in inspect.signature(cls.__init__).parameters.values()
                       if p.name != "self"])
    except (ValueError, TypeError):
        nparams = 1
    if nparams >= 2:
        return cls(context, config)
    if nparams == 1:
        return cls(context)
    return cls()


def _app_dir_of(spec: PluginSpec):
    import os
    import sys
    mod = sys.modules.get(spec.module)
    return os.path.dirname(mod.__file__) if mod and getattr(mod, "__file__", None) else None


def _load_app_config(spec: PluginSpec) -> AstrBotConfig:
    """app 的 _conf_schema.json 默认值 + 基座 apps.<name> 覆盖。"""
    import json
    import os
    config = AstrBotConfig()
    try:
        app_dir = _app_dir_of(spec)
        schema_path = os.path.join(app_dir, "_conf_schema.json") if app_dir else ""
        if schema_path and os.path.isfile(schema_path):
            with open(schema_path, encoding="utf-8") as f:
                schema = json.load(f)
            for key, meta in schema.items():
                if isinstance(meta, dict) and "default" in meta:
                    config[key] = meta["default"]
    except Exception as e:
        log.warning(f"[astrbot基座] 读取 [{spec.name}] 配置 schema 失败: {e}")
    apps_cfg = state._CONFIG.get("apps", {}) or {}
    # 优先用 app 目录名 (稳定), 兼容用显示名作 key
    overrides = apps_cfg.get(spec.app_name) or apps_cfg.get(spec.name) or {}
    if isinstance(overrides, dict):
        config.update(overrides)
    return config


async def instantiate_all():
    """实例化所有 Star 并调用 initialize()。"""
    context = Context()
    for spec in state.PLUGIN_SPECS:
        try:
            _inject_star_attrs(spec)
            instance = _construct_star(spec.cls, context, _load_app_config(spec))
            spec.instance = instance
            context._star_instances.append(instance)
            init = getattr(instance, "initialize", None)
            if init and inspect.iscoroutinefunction(init):
                try:
                    await init()
                except Exception as e:
                    log.warning(f"[astrbot基座] [{spec.name}] initialize() 异常: {e}")
            log.info(f"[astrbot基座] 已实例化插件 [{spec.name}]")
        except Exception as e:
            log.error(f"[astrbot基座] 实例化插件 [{spec.name}] 失败: {e}", exc_info=True)
    return context


async def terminate_all():
    for spec in state.PLUGIN_SPECS:
        instance = spec.instance
        term = getattr(instance, "terminate", None) if instance else None
        if term and inspect.iscoroutinefunction(term):
            try:
                await term()
            except Exception as e:
                log.warning(f"[astrbot基座] [{spec.name}] terminate() 异常: {e}")
        spec.instance = None
