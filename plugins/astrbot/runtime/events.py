"""AstrBot 事件 / 上下文 / 工具 (适配 OneBot v11)。"""

from __future__ import annotations

import asyncio
import inspect
import os

from . import sending, state
from .components import (
    At,
    AtAll,
    Face,
    Image,
    MessageChain,
    MessageEventResult,
    Plain,
    Record,
    Reply,
    Video,
)

log = state.log


# ==================== 平台元数据 ====================

class PlatformMetadata:
    def __init__(self, name="aiocqhttp", description="", id="aiocqhttp"):
        self.name = name
        self.description = description
        self.id = id


# ==================== 入站消息解析 ====================

def _parse_segment(seg: dict):
    if not isinstance(seg, dict):
        return None
    t = seg.get("type")
    d = seg.get("data", {}) or {}
    if t == "text":
        return Plain(d.get("text", ""))
    if t == "image":
        return Image(file=d.get("file", ""), url=d.get("url", "") or d.get("file", ""))
    if t == "at":
        qq = d.get("qq")
        if str(qq) == "all":
            return AtAll()
        return At(qq=qq)
    if t == "face":
        return Face(id=d.get("id"))
    if t == "record":
        return Record(file=d.get("file", ""), url=d.get("url", ""))
    if t == "video":
        return Video(file=d.get("file", ""), url=d.get("url", ""))
    if t == "reply":
        return Reply(id=d.get("id"))
    return None


def parse_message(raw_message) -> tuple[list, str]:
    """OneBot message 数组 -> (组件列表, 纯文本)。"""
    chain: list = []
    texts: list[str] = []
    if isinstance(raw_message, list):
        for seg in raw_message:
            comp = _parse_segment(seg)
            if comp is None:
                continue
            chain.append(comp)
            if isinstance(comp, Plain):
                texts.append(comp.text)
    elif isinstance(raw_message, str):
        chain.append(Plain(raw_message))
        texts.append(raw_message)
    return chain, "".join(texts).strip()


# ==================== AstrBotMessage (message_obj) ====================

class MessageMember:
    def __init__(self, user_id="", nickname=""):
        self.user_id = str(user_id or "")
        self.nickname = nickname or ""


class Group:
    def __init__(self, group_id="", group_name=""):
        self.group_id = str(group_id or "")
        self.group_name = group_name or ""
        self.group_avatar = ""
        self.group_owner = None
        self.group_admins = None
        self.members = None


class AstrBotMessage:
    """AstrBot 消息对象 (event.message_obj)。"""

    def __init__(self, elaina_event):
        e = elaina_event
        self.self_id = str(getattr(e, "self_id", "") or "")
        self.message_id = str(getattr(e, "message_id", "") or "")
        self.message, self.message_str = parse_message(getattr(e, "message", []))
        self.raw_message = getattr(e, "raw_data", None) or {}
        sender = getattr(e, "sender", {}) or {}
        self.sender = MessageMember(
            user_id=getattr(e, "user_id", "") or sender.get("user_id", ""),
            nickname=sender.get("nickname", "") or sender.get("card", ""),
        )
        gid = getattr(e, "group_id", None)
        self.group = Group(group_id=gid) if gid else None
        self.session_id = str(gid) if gid else self.sender.user_id
        self.timestamp = int(getattr(e, "time", 0) or 0)
        self.type = "GroupMessage" if gid else "FriendMessage"

    @property
    def group_id(self) -> str:
        return self.group.group_id if self.group else ""


# ==================== bot 代理 (aiocqhttp CQHttp 风格) ====================

class _BotProxy:
    """模拟 aiocqhttp 的 CQHttp 客户端: 任意 ``await bot.<action>(**params)``
    或 ``bot.call_action(action, **params)`` 都转发到框架 OneBot API。"""

    def __init__(self, self_id: str = ""):
        self._self_id = str(self_id or "")

    async def call_action(self, action: str, **params):
        api = state.get_api(self._self_id)
        if api is None:
            return None
        return await api.call_api(action, params, self_id=self._self_id or None)

    # 上游部分插件用 api.call_action
    @property
    def api(self):
        return self

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)

        async def _action(**params):
            return await self.call_action(name, **params)

        return _action


# ==================== AstrMessageEvent ====================

class AstrMessageEvent:
    """把 ElainaBot OneBot MessageEvent 包装成 AstrBot 事件接口。"""

    def __init__(self, elaina_event, *, role: str = "member", content: str | None = None):
        self._e = elaina_event
        self.role = role
        self.message_str = (content if content is not None else getattr(elaina_event, "content", "")) or ""
        self.message_obj = AstrBotMessage(elaina_event)
        self.platform_meta = PlatformMetadata()
        self.unified_msg_origin = sending.make_umo(elaina_event)
        self.session_id = self.message_obj.session_id
        self.is_wake = True
        self.is_at_or_wake_command = True
        self._extras: dict = {}
        self._result = None
        self.bot = _BotProxy(self.message_obj.self_id)

    # ---- 基本信息 ----
    def get_sender_id(self) -> str:
        return str(getattr(self._e, "user_id", "") or "")

    def get_sender_name(self) -> str:
        return self.message_obj.sender.nickname

    def get_group_id(self) -> str:
        gid = getattr(self._e, "group_id", None)
        return str(gid) if gid else ""

    def get_self_id(self) -> str:
        return str(getattr(self._e, "self_id", "") or "")

    def get_platform_name(self) -> str:
        return "aiocqhttp"

    def get_platform_id(self) -> str:
        return "aiocqhttp"

    def get_message_str(self) -> str:
        return self.message_str

    def get_message_outline(self) -> str:
        return self.message_str

    def get_messages(self) -> list:
        return self.message_obj.message

    def get_session_id(self) -> str:
        return self.session_id

    def message_id(self):
        return self.message_obj.message_id

    def is_private_chat(self) -> bool:
        return not bool(getattr(self._e, "group_id", None))

    def is_admin(self) -> bool:
        return self.role == "admin" or state.is_bot_owner(self._e)

    async def get_group(self, group_id=None, **_):
        gid = group_id or self.get_group_id()
        if not gid:
            return None
        api = state.get_api(self.get_self_id())
        if api is None:
            return None
        try:
            r = await api.get_group_info(gid)
            data = r.get("data", r) if isinstance(r, dict) else {}
            g = Group(group_id=gid, group_name=data.get("group_name", ""))
            return g
        except Exception:
            return None

    # ---- 结果构造 ----
    def make_result(self) -> MessageEventResult:
        return MessageEventResult()

    def plain_result(self, text: str = "") -> MessageEventResult:
        return MessageEventResult(MessageChain().message(text))

    def image_result(self, url_or_path: str) -> MessageEventResult:
        return MessageEventResult(MessageChain().file_image(url_or_path))

    def chain_result(self, chain) -> MessageEventResult:
        return MessageEventResult(chain)

    def set_result(self, result):
        self._result = result

    def get_result(self):
        return self._result

    def clear_result(self):
        self._result = None

    # ---- 主动发送 ----
    async def send(self, message):
        await sending.send_chain(message, event=self._e)
        return None

    async def send_streaming(self, generator, *_a, **_k):
        async for item in generator:
            await sending.send_result(self._e, item)

    # ---- 杂项 (大多为空操作以兼容上游调用) ----
    def should_call_llm(self, *_a, **_k):
        return None

    def stop_event(self):
        self._force_stopped = True

    def is_stopped(self):
        return getattr(self, "_force_stopped", False)

    def continue_event(self):
        self._force_stopped = False

    def set_extra(self, key, value):
        self._extras[key] = value

    def get_extra(self, key=None):
        if key is None:
            return self._extras
        return self._extras.get(key)

    @property
    def platform(self):
        return self.platform_meta


# ==================== Context / StarTools / Star ====================

class _CronJobStub:
    def __init__(self, job_id=""):
        self.id = job_id or "astrbot_job"
        self.job_id = self.id

    def remove(self, *_a, **_k):
        return None


class _CronManagerStub:
    """定时任务管理器占位: 基座暂不跑调度, 仅保证插件注册任务不报错。"""

    async def add_basic_job(self, *_a, **_k):
        return _CronJobStub()

    async def add_job(self, *_a, **_k):
        return _CronJobStub()

    def remove_job(self, *_a, **_k):
        return None

    def get_jobs(self, *_a, **_k):
        return []


class Context:
    """AstrBot 插件上下文 (self.context)。"""

    def __init__(self):
        self._star_instances: list = []
        self._config = state._CONFIG
        self.cron_manager = _CronManagerStub()
        self.provider_manager = None

    async def send_message(self, umo: str, chain) -> bool:
        scene, target = sending.parse_umo(umo)
        if not target:
            log.warning(f"[astrbot基座] 主动消息 umo 解析失败: {umo}")
            return False
        try:
            if scene == "group":
                await sending.send_chain(chain, group_id=target)
            else:
                await sending.send_chain(chain, user_id=target)
            return True
        except Exception as e:
            log.warning(f"[astrbot基座] 主动消息发送失败 umo={umo}: {e}")
            return False

    def get_registered_star(self, name=None):
        for inst in self._star_instances:
            if type(inst).__name__ == name or getattr(inst, "name", None) == name:
                return inst
        return None

    def get_all_stars(self):
        return list(self._star_instances)

    def get_config(self):
        return self._config

    def get_platform(self, *_a, **_k):
        return None

    def get_platforms(self):
        return []

    def get_event_queue(self):
        return None

    def register_task(self, coro, name=""):
        return asyncio.create_task(coro)

    def get_db(self):
        return None

    def get_using_provider(self, *_a, **_k):
        return None

    def get_llm_tool_manager(self):
        return None

    # ---- LLM / Provider (基座无 LLM, 统一返回空, 由插件自行降级) ----
    def get_provider_by_id(self, *_a, **_k):
        return None

    def get_current_chat_provider_id(self, *_a, **_k):
        return None

    def get_all_providers(self):
        return []

    async def llm_generate(self, *_a, **_k):
        log.warning("[astrbot基座] 当前未配置 LLM Provider, llm_generate 返回空")
        return None

    async def tool_loop_agent(self, *_a, **_k):
        log.warning("[astrbot基座] 当前未配置 LLM Provider, tool_loop_agent 返回空")
        return None

    def register_web_api(self, *_a, **_k):
        return None

    @property
    def plugin_manager(self):
        return None


def _current_app_name() -> str:
    """据调用栈推断当前 app 名 (...apps.<app>...)。"""
    for frame in inspect.stack():
        pkg = frame.frame.f_globals.get("__package__", "") or ""
        idx = pkg.find(".apps.")
        if idx != -1:
            return pkg[idx + len(".apps."):].split(".")[0]
    return "shared"


class StarTools:
    @staticmethod
    def get_data_dir(plugin_name: str = "") -> str:
        name = plugin_name or _current_app_name()
        root = state.apps_data_root() or os.path.join(os.getcwd(), "data")
        path = os.path.join(root, name)
        os.makedirs(path, exist_ok=True)
        from pathlib import Path

        return Path(path)

    @staticmethod
    def get_data_path(plugin_name: str = ""):
        return StarTools.get_data_dir(plugin_name)

    @staticmethod
    async def send_message(umo: str, chain) -> bool:
        return await Context().send_message(umo, chain)


class Star:
    """AstrBot 插件基类 (适配版)。"""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # 记录每个 Star 子类 (无论是否用 @register), 供 main 按 app 收集
        if cls not in state.STAR_SUBCLASSES:
            state.STAR_SUBCLASSES.append(cls)

    def __init__(self, context: Context = None, *args, **kwargs):
        self.context = context

    async def text_to_image(self, text: str, return_url: bool = True):
        """文本转图片: 本地无头浏览器渲染; 无浏览器时退化为原文本。"""
        import asyncio

        from . import render
        path = await asyncio.to_thread(render.render_text, text)
        return path or text

    async def html_render(self, tmpl: str, data: dict, return_url: bool = True,
                          options: dict | None = None):
        """HTML(jinja2) 转图片: 本地无头浏览器渲染, 返回本地图片路径。"""
        import asyncio

        from . import render
        return await asyncio.to_thread(render.render_html, tmpl, data or {})

    # ---- KV 存储 (PluginKVStoreMixin 兼容, JSON 文件落盘) ----
    def _kv_path(self) -> str:
        root = state.data_root()
        path = os.path.join(root, "plugin_data", "_kv")
        os.makedirs(path, exist_ok=True)
        pid = str(getattr(self, "plugin_id", None) or type(self).__name__).replace("/", "_")
        return os.path.join(path, f"{pid}.json")

    def _kv_load(self) -> dict:
        import json
        try:
            with open(self._kv_path(), encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _kv_save(self, data: dict):
        import json
        try:
            with open(self._kv_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            log.warning(f"[astrbot基座] KV 存储写入失败: {e}")

    async def put_kv_data(self, key: str, value):
        data = self._kv_load()
        data[key] = value
        self._kv_save(data)

    async def get_kv_data(self, key: str, default=None):
        return self._kv_load().get(key, default)

    async def delete_kv_data(self, key: str):
        data = self._kv_load()
        data.pop(key, None)
        self._kv_save(data)

    async def initialize(self):
        return None

    async def terminate(self):
        return None


class AstrBotConfig(dict):
    """插件配置 (dict 子类, 支持属性访问)。"""

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as e:
            raise AttributeError(item) from e

    def __setattr__(self, key, value):
        self[key] = value

    def save_config(self, *_a, **_k):
        return None
