"""OneBot v11 API 调用封装"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger('ElainaBot.onebot.api')

_main_loop = None
_adapter_ref = None


def set_main_loop(loop):
    global _main_loop
    _main_loop = loop


def set_adapter(adapter):
    global _adapter_ref
    _adapter_ref = adapter


class OneBotAPI:
    """OneBot v11 API"""

    def __init__(self, adapter=None):
        self._adapter = adapter or _adapter_ref

    async def call_api(self, action: str, params: dict = None, self_id: str = None) -> Optional[dict]:
        """调用 OneBot API — 优先走 WebSocket, 无连接时回退到 HTTP 客户端"""
        if not self._adapter:
            return None

        ws = self._adapter.get_bot_ws(self_id)
        if ws is None:  # WebSocketResponse 的 bool() 为 False, 必须用 is None 判空
            # 反向/正向 WS 都不可用时, 尝试 HTTP 客户端 (框架 -> OneBot HTTP API)
            if getattr(self._adapter, 'http_clients', None):
                return await self._adapter.http_call_action(action, params or {})
            logger.warning('API 调用失败: 无可用 WebSocket / HTTP 连接')
            return None

        echo = str(uuid.uuid4())
        payload = {
            "action": action,
            "params": params or {},
            "echo": echo,
        }

        future = asyncio.get_running_loop().create_future()
        self._adapter.api_responses[echo] = future

        try:
            # aiohttp 的 WebSocketResponse/ClientWebSocketResponse 使用 send_str
            send = getattr(ws, 'send_str', None) or getattr(ws, 'send_text')
            await send(json.dumps(payload, ensure_ascii=False))
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except asyncio.TimeoutError:
            logger.warning(f'API 超时: {action}')
            self._adapter.api_responses.pop(echo, None)
            return None
        except Exception as e:
            logger.error(f'API 错误: {action} - {e}')
            self._adapter.api_responses.pop(echo, None)
            return None

    async def send_group_msg(self, group_id, message, **kwargs) -> Optional[dict]:
        return await self.call_api('send_group_msg', {
            'group_id': int(group_id),
            'message': message,
            **kwargs
        })

    async def send_private_msg(self, user_id, message, **kwargs) -> Optional[dict]:
        return await self.call_api('send_private_msg', {
            'user_id': int(user_id),
            'message': message,
            **kwargs
        })

    async def send_msg(self, message_type: str, target_id, message, **kwargs) -> Optional[dict]:
        params = {'message_type': message_type, 'message': message, **kwargs}
        if message_type == 'group':
            params['group_id'] = int(target_id)
        else:
            params['user_id'] = int(target_id)
        return await self.call_api('send_msg', params)

    async def delete_msg(self, message_id) -> Optional[dict]:
        return await self.call_api('delete_msg', {'message_id': int(message_id)})

    async def get_msg(self, message_id) -> Optional[dict]:
        return await self.call_api('get_msg', {'message_id': int(message_id)})

    async def get_login_info(self) -> Optional[dict]:
        return await self.call_api('get_login_info')

    async def get_stranger_info(self, user_id) -> Optional[dict]:
        return await self.call_api('get_stranger_info', {'user_id': int(user_id)})

    async def get_friend_list(self) -> Optional[dict]:
        return await self.call_api('get_friend_list')

    async def get_group_list(self) -> Optional[dict]:
        return await self.call_api('get_group_list')

    async def get_group_info(self, group_id) -> Optional[dict]:
        return await self.call_api('get_group_info', {'group_id': int(group_id)})

    async def get_group_member_list(self, group_id) -> Optional[dict]:
        return await self.call_api('get_group_member_list', {'group_id': int(group_id)})

    async def get_group_member_info(self, group_id, user_id) -> Optional[dict]:
        return await self.call_api('get_group_member_info', {
            'group_id': int(group_id),
            'user_id': int(user_id)
        })

    async def set_group_kick(self, group_id, user_id, reject_add=False) -> Optional[dict]:
        return await self.call_api('set_group_kick', {
            'group_id': int(group_id),
            'user_id': int(user_id),
            'reject_add_request': reject_add
        })

    async def set_group_ban(self, group_id, user_id, duration=1800) -> Optional[dict]:
        return await self.call_api('set_group_ban', {
            'group_id': int(group_id),
            'user_id': int(user_id),
            'duration': duration
        })

    async def set_group_whole_ban(self, group_id, enable=True) -> Optional[dict]:
        return await self.call_api('set_group_whole_ban', {
            'group_id': int(group_id),
            'enable': enable
        })

    async def set_friend_add_request(self, flag, approve=True) -> Optional[dict]:
        return await self.call_api('set_friend_add_request', {
            'flag': flag,
            'approve': approve
        })

    async def set_group_add_request(self, flag, sub_type, approve=True) -> Optional[dict]:
        return await self.call_api('set_group_add_request', {
            'flag': flag,
            'sub_type': sub_type,
            'approve': approve
        })


def get_api() -> OneBotAPI:
    return OneBotAPI(_adapter_ref)


def run_async_api(coro):
    """在同步上下文中调用异步 API"""
    loop = _main_loop
    if loop and loop.is_running():
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)
    return asyncio.run(coro)
