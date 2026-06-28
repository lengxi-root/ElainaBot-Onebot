"""Application — 顶层编排, 组合所有子系统"""

import asyncio
import contextlib
import datetime
import json
import os
import signal

from core.base.config import cfg
from core.base.logger import SYSTEM, get_logger
from core.base.logger import setup as setup_logger
from core.module.hook import HookManager
from core.module.manager import ModuleManager
from core.onebot.adapter import OneBotAdapter
from core.onebot.api import set_adapter, set_main_loop
from core.onebot.connection import ConnectionManager
from core.onebot.event import MessageEvent, NoticeEvent, MetaEvent
from core.plugin.manager import PluginManager
from core.server.http_server import HttpServer
from core.services.config_watcher import ConfigWatcherService
from core.storage.log import LogService

log = get_logger(SYSTEM, '启动器')

_app = None


def get_app():
    return _app


class Application:
    """ElainaBot OneBot 应用入口"""

    def __init__(self):
        self._base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._hook_manager = HookManager()
        self._module_manager = None
        self._plugin_manager = None
        self._log_service = None
        self._http_server = None
        self._config_watcher = None
        self._adapter = None
        self._connection_manager = None
        self._stop_event = None
        self._restart_requested = False
        self._web_log_cb = None

    @property
    def adapter(self):
        return self._adapter

    @property
    def connection_manager(self):
        return self._connection_manager

    async def reload_connections(self):
        """重新应用 OneBot 连接配置 (网络配置页面保存后调用)"""
        if self._connection_manager:
            await self._connection_manager.reload()

    @property
    def hook_manager(self):
        return self._hook_manager

    @property
    def module_manager(self):
        return self._module_manager

    @property
    def plugin_manager(self):
        return self._plugin_manager

    @property
    def log_service(self):
        return self._log_service

    def _path(self, *parts):
        return os.path.join(self._base_dir, *parts)

    async def start(self):
        global _app
        _app = self

        # 1) 配置
        cfg.init(self._path('config'))
        fw_name = cfg.get('settings', 'web.framework_name', 'ElainaBot')
        setup_logger(framework_name=fw_name)
        log.info(f'{"=" * 5} {fw_name} OneBot 启动中 {"=" * 5}')

        # 2) OneBot 适配器
        access_token = cfg.get('settings', 'onebot.access_token', '')
        secret = cfg.get('settings', 'onebot.secret', '')
        self._adapter = OneBotAdapter(access_token=access_token, secret=secret)
        set_adapter(self._adapter)
        set_main_loop(asyncio.get_running_loop())

        # 3) HTTP 服务器
        self._http_server = HttpServer(self, self._base_dir)
        self._http_server.init_app()

        # 4) 模块管理器
        self._module_manager = ModuleManager(self._path('modules'), self._hook_manager)
        self._module_manager.discover()
        await self._module_manager.start_enabled()

        # 5) 插件管理器
        self._plugin_manager = PluginManager(self._path('plugins'))
        owner_ids = cfg.get('settings', 'owner_ids', []) or []
        self._plugin_manager.set_owner_ids(owner_ids)
        await self._plugin_manager.load_all()
        self._plugin_manager.start_watcher()

        # 6) 日志服务
        log_base = self._path('data', cfg.get('settings', 'logging.dir', 'log'))
        log_cfg = cfg.get('settings', 'logging') or {}
        self._log_service = LogService(
            base_dir=log_base,
            wal_mode=log_cfg.get('wal_mode', True) if isinstance(log_cfg, dict) else True,
            insert_interval=log_cfg.get('insert_interval', 2) if isinstance(log_cfg, dict) else 2,
            retention_days=log_cfg.get('retention_days', 30) if isinstance(log_cfg, dict) else 30,
        )
        await self._log_service.start()

        # 7) Web 面板
        self._http_server.mount_web_panel()

        # 8) 启动 HTTP 服务
        await self._http_server.start()

        # 8.5) OneBot 连接管理器 (正向 WS 客户端 / HTTP 客户端 / 反向鉴权)
        self._connection_manager = ConnectionManager(self)
        await self._connection_manager.start()

        # 9) 配置监视
        self._config_watcher = ConfigWatcherService(interval=5.0)
        self._config_watcher.start()

        log.info(f'启动完成: {len(self._plugin_manager._plugins)} 个插件, {self._plugin_manager.handler_count} 个处理器')

        # 等待停止信号
        self._stop_event = asyncio.Event()
        self._install_signal_handlers()
        try:
            await self._stop_event.wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self.shutdown()
        return self._restart_requested

    def _install_signal_handlers(self):
        loop = asyncio.get_running_loop()

        def _handle(signame):
            log.info(f'收到 {signame} 信号')
            if self._stop_event and not self._stop_event.is_set():
                self._stop_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _handle, sig.name)
            except (NotImplementedError, RuntimeError):
                with contextlib.suppress(ValueError, OSError):
                    signal.signal(sig, lambda s, f: loop.call_soon_threadsafe(_handle, signal.Signals(s).name))

    async def shutdown(self):
        log.info('正在关闭...')
        if self._plugin_manager:
            self._plugin_manager.stop_watcher()
        if self._connection_manager:
            await self._connection_manager.stop()
        if self._config_watcher:
            self._config_watcher.stop()
        if self._module_manager:
            await self._module_manager.shutdown()
        if self._log_service:
            await self._log_service.shutdown()
        if self._http_server:
            await self._http_server.stop()
        log.info('已关闭')

    async def process_event(self, event):
        """处理 OneBot 事件 (异步分发)"""
        if isinstance(event, MetaEvent):
            return

        # 注入 API 引用, 使插件可通过 event.reply() 调用
        from core.onebot.api import get_api
        event._api = get_api()

        # Hook: on_raw_event
        await self._hook_manager.emit('on_raw_event', event)

        # 日志记录
        self._log_event(event)

        # 异步分发到插件 (消息事件 + 通知/请求事件)
        await self._plugin_manager.dispatch(event)

    def _log_event(self, event):
        """记录事件日志"""
        if isinstance(event, MessageEvent):
            msg_type = "群聊" if event.is_group else "私聊"
            sender = event.sender_card or event.sender_nickname or str(event.user_id)
            location = f"群({event.group_id})" if event.is_group else f"私聊({event.user_id})"

            parts = []
            for seg in event.message:
                if not isinstance(seg, dict):
                    continue
                t, d = seg.get('type', ''), seg.get('data', {})
                if t == 'text':
                    parts.append(d.get('text', '').strip())
                elif t == 'at':
                    parts.append(f"@{d.get('qq', '')}")
                elif t == 'image':
                    parts.append('[图片]')
                elif t == 'face':
                    parts.append('[表情]')
                elif t == 'record':
                    parts.append('[语音]')
                elif t == 'video':
                    parts.append('[视频]')
                elif t == 'reply':
                    parts.append('[回复]')
                else:
                    parts.append(f'[{t}]')

            content = ''.join(parts) or "[空消息]"
            display = content[:100] + "..." if len(content) > 100 else content
            # 消息内容属于「消息记录」(按 QQ 分库), 不应混入「框架日志」: web_skip=True
            log.info(f'[{event.self_id}] {msg_type} | {location} | {sender}: {display}',
                     extra={'web_skip': True})

            # 写入 SQLite
            if self._log_service:
                nickname = ''
                if isinstance(event.sender, dict):
                    nickname = event.sender.get('card') or event.sender.get('nickname') or ''
                self._log_service.add('message', {
                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'content': content,
                    'source': str(event.self_id or ''),
                    'user_id': str(event.user_id),
                    'group_id': str(event.group_id or ''),
                    'message_id': str(event.message_id),
                    'message_type': event.message_type,
                    'raw_data': json.dumps(event.raw_data, ensure_ascii=False),
                    'extra': json.dumps({'nickname': nickname}, ensure_ascii=False),
                }, bot_qq=str(event.self_id or ''))

            # 推送到 Web 面板
            if self._web_log_cb:
                self._web_log_cb('message', {
                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'content': content,
                    'user_id': str(event.user_id),
                    'group_id': str(event.group_id or ''),
                    'message_id': str(event.message_id),
                    'message_type': event.message_type,
                    'sender': sender,
                    'bot_qq': str(event.self_id or ''),
                    'direction': 'receive',
                    'raw_message': json.dumps(event.raw_data, ensure_ascii=False),
                })

        elif isinstance(event, NoticeEvent):
            log.info(f'通知: {event.notice_type} | 群 {event.group_id} | 用户 {event.user_id}')
            # 写入 lifecycle.db 供可视统计「事件统计」使用
            if self._log_service and event.notice_type in (
                'group_increase', 'group_decrease', 'friend_add', 'friend_del',
                'group_recall', 'friend_recall',
            ):
                self._log_service.add('lifecycle', {
                    'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'content': f'{event.notice_type} | 群{event.group_id or ""} | 用户{event.user_id}',
                    'source': str(event.self_id or ''),
                    'user_id': str(event.user_id or ''),
                    'group_id': str(event.group_id or ''),
                    'message_type': event.notice_type,
                    'raw_data': json.dumps(event.raw_data, ensure_ascii=False),
                }, bot_qq=str(event.self_id or ''))
            # 撤回事件：标记对应消息为已撤回
            if self._log_service and event.notice_type in ('group_recall', 'friend_recall'):
                recalled_mid = str(event.raw_data.get('message_id', '') or '')
                if recalled_mid:
                    self._log_service.execute(
                        'message',
                        "UPDATE log SET extra = 'recalled' WHERE message_id = ?",
                        (recalled_mid,),
                        bot_qq=str(event.self_id or ''),
                    )

    def push_web_log(self, log_type: str, entry: dict):
        if self._web_log_cb:
            self._web_log_cb(log_type, entry)
