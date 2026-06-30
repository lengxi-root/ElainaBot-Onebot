"""OneBot v11 API 调用封装 (含常见扩展动作; 未封装的动作可直接用 call_api)"""

import asyncio
import json
import logging
import uuid

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
    """OneBot v11 API (内置常见扩展动作封装)"""

    def __init__(self, adapter=None):
        self._adapter = adapter or _adapter_ref

    async def call_api(self, action: str, params: dict = None, self_id: str = None) -> dict | None:
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
            send = getattr(ws, 'send_str', None) or ws.send_text
            await send(json.dumps(payload, ensure_ascii=False))
            async with asyncio.timeout(30):
                return await future
        except TimeoutError:
            logger.warning(f'API 超时: {action}')
            self._adapter.api_responses.pop(echo, None)
            return None
        except Exception as e:
            logger.error(f'API 错误: {action} - {e}')
            self._adapter.api_responses.pop(echo, None)
            return None

    async def send_group_msg(self, group_id, message, **kwargs) -> dict | None:
        return await self.call_api('send_group_msg', {
            'group_id': int(group_id),
            'message': message,
            **kwargs
        })

    async def send_private_msg(self, user_id, message, **kwargs) -> dict | None:
        return await self.call_api('send_private_msg', {
            'user_id': int(user_id),
            'message': message,
            **kwargs
        })

    async def send_msg(self, message_type: str, target_id, message, **kwargs) -> dict | None:
        params = {'message_type': message_type, 'message': message, **kwargs}
        if message_type == 'group':
            params['group_id'] = int(target_id)
        else:
            params['user_id'] = int(target_id)
        return await self.call_api('send_msg', params)

    async def delete_msg(self, message_id) -> dict | None:
        return await self.call_api('delete_msg', {'message_id': int(message_id)})

    async def get_msg(self, message_id) -> dict | None:
        return await self.call_api('get_msg', {'message_id': int(message_id)})

    async def get_login_info(self) -> dict | None:
        return await self.call_api('get_login_info')

    async def get_stranger_info(self, user_id) -> dict | None:
        return await self.call_api('get_stranger_info', {'user_id': int(user_id)})

    async def get_friend_list(self) -> dict | None:
        return await self.call_api('get_friend_list')

    async def get_group_list(self) -> dict | None:
        return await self.call_api('get_group_list')

    async def get_group_info(self, group_id) -> dict | None:
        return await self.call_api('get_group_info', {'group_id': int(group_id)})

    async def get_group_member_list(self, group_id) -> dict | None:
        return await self.call_api('get_group_member_list', {'group_id': int(group_id)})

    async def get_group_member_info(self, group_id, user_id) -> dict | None:
        return await self.call_api('get_group_member_info', {
            'group_id': int(group_id),
            'user_id': int(user_id)
        })

    async def set_group_kick(self, group_id, user_id, reject_add=False) -> dict | None:
        return await self.call_api('set_group_kick', {
            'group_id': int(group_id),
            'user_id': int(user_id),
            'reject_add_request': reject_add
        })

    async def set_group_ban(self, group_id, user_id, duration=1800) -> dict | None:
        return await self.call_api('set_group_ban', {
            'group_id': int(group_id),
            'user_id': int(user_id),
            'duration': duration
        })

    async def set_group_whole_ban(self, group_id, enable=True) -> dict | None:
        return await self.call_api('set_group_whole_ban', {
            'group_id': int(group_id),
            'enable': enable
        })

    async def set_friend_add_request(self, flag, approve=True) -> dict | None:
        return await self.call_api('set_friend_add_request', {
            'flag': flag,
            'approve': approve
        })

    async def set_group_add_request(self, flag, sub_type, approve=True) -> dict | None:
        return await self.call_api('set_group_add_request', {
            'flag': flag,
            'sub_type': sub_type,
            'approve': approve
        })

    # ── 消息扩展 ──
    async def send_forward_msg(self, messages, **kwargs) -> dict | None:
        return await self.call_api('send_forward_msg', {'messages': messages, **kwargs})

    async def send_group_forward_msg(self, group_id, messages, **kwargs) -> dict | None:
        return await self.call_api('send_group_forward_msg', {'group_id': int(group_id), 'messages': messages, **kwargs})

    async def send_private_forward_msg(self, user_id, messages, **kwargs) -> dict | None:
        return await self.call_api('send_private_forward_msg', {'user_id': int(user_id), 'messages': messages, **kwargs})

    async def get_forward_msg(self, message_id) -> dict | None:
        return await self.call_api('get_forward_msg', {'message_id': message_id})

    async def get_group_msg_history(self, group_id, message_seq=0, count=20, reverse_order=False) -> dict | None:
        return await self.call_api('get_group_msg_history', {'group_id': int(group_id), 'message_seq': message_seq, 'count': count, 'reverseOrder': reverse_order})

    async def get_friend_msg_history(self, user_id, message_seq=0, count=20, reverse_order=False) -> dict | None:
        return await self.call_api('get_friend_msg_history', {'user_id': int(user_id), 'message_seq': message_seq, 'count': count, 'reverseOrder': reverse_order})

    async def mark_group_msg_as_read(self, group_id) -> dict | None:
        return await self.call_api('mark_group_msg_as_read', {'group_id': int(group_id)})

    async def mark_private_msg_as_read(self, user_id) -> dict | None:
        return await self.call_api('mark_private_msg_as_read', {'user_id': int(user_id)})

    async def set_msg_emoji_like(self, message_id, emoji_id, enable=True) -> dict | None:
        return await self.call_api('set_msg_emoji_like', {'message_id': message_id, 'emoji_id': str(emoji_id), 'set': enable})

    async def send_poke(self, user_id, group_id=None) -> dict | None:
        params = {'user_id': int(user_id)}
        if group_id is not None:
            params['group_id'] = int(group_id)
        return await self.call_api('send_poke', params)

    # ── 群组扩展 ──
    async def set_group_card(self, group_id, user_id, card='') -> dict | None:
        return await self.call_api('set_group_card', {'group_id': int(group_id), 'user_id': int(user_id), 'card': card})

    async def set_group_name(self, group_id, group_name) -> dict | None:
        return await self.call_api('set_group_name', {'group_id': int(group_id), 'group_name': group_name})

    async def set_group_admin(self, group_id, user_id, enable=True) -> dict | None:
        return await self.call_api('set_group_admin', {'group_id': int(group_id), 'user_id': int(user_id), 'enable': enable})

    async def set_group_special_title(self, group_id, user_id, special_title='') -> dict | None:
        return await self.call_api('set_group_special_title', {'group_id': int(group_id), 'user_id': int(user_id), 'special_title': special_title})

    async def set_group_leave(self, group_id, is_dismiss=False) -> dict | None:
        return await self.call_api('set_group_leave', {'group_id': int(group_id), 'is_dismiss': is_dismiss})

    async def set_group_portrait(self, group_id, file) -> dict | None:
        return await self.call_api('set_group_portrait', {'group_id': int(group_id), 'file': file})

    async def set_group_sign(self, group_id) -> dict | None:
        return await self.call_api('set_group_sign', {'group_id': int(group_id)})

    async def get_group_honor_info(self, group_id, honor_type='all') -> dict | None:
        return await self.call_api('get_group_honor_info', {'group_id': int(group_id), 'type': honor_type})

    async def get_group_at_all_remain(self, group_id) -> dict | None:
        return await self.call_api('get_group_at_all_remain', {'group_id': int(group_id)})

    async def get_group_system_msg(self) -> dict | None:
        return await self.call_api('get_group_system_msg')

    async def get_essence_msg_list(self, group_id) -> dict | None:
        return await self.call_api('get_essence_msg_list', {'group_id': int(group_id)})

    async def set_essence_msg(self, message_id) -> dict | None:
        return await self.call_api('set_essence_msg', {'message_id': int(message_id)})

    async def delete_essence_msg(self, message_id) -> dict | None:
        return await self.call_api('delete_essence_msg', {'message_id': int(message_id)})

    # ── 用户扩展 ──
    async def send_like(self, user_id, times=1) -> dict | None:
        return await self.call_api('send_like', {'user_id': int(user_id), 'times': int(times)})

    async def delete_friend(self, user_id) -> dict | None:
        return await self.call_api('delete_friend', {'user_id': int(user_id)})

    async def set_qq_avatar(self, file) -> dict | None:
        return await self.call_api('set_qq_avatar', {'file': file})

    async def set_qq_profile(self, **kwargs) -> dict | None:
        return await self.call_api('set_qq_profile', kwargs)

    async def get_unidirectional_friend_list(self) -> dict | None:
        return await self.call_api('get_unidirectional_friend_list')

    async def ocr_image(self, image) -> dict | None:
        return await self.call_api('ocr_image', {'image': image})

    # ── 系统扩展 ──
    async def get_version_info(self) -> dict | None:
        return await self.call_api('get_version_info')

    async def get_status(self) -> dict | None:
        return await self.call_api('get_status')

    async def can_send_image(self) -> dict | None:
        return await self.call_api('can_send_image')

    async def can_send_record(self) -> dict | None:
        return await self.call_api('can_send_record')

    async def get_cookies(self, domain='') -> dict | None:
        return await self.call_api('get_cookies', {'domain': domain})

    async def get_csrf_token(self) -> dict | None:
        return await self.call_api('get_csrf_token')

    async def clean_cache(self) -> dict | None:
        return await self.call_api('clean_cache')

    # ── 文件扩展 ──
    async def upload_group_file(self, group_id, file, name, folder='') -> dict | None:
        return await self.call_api('upload_group_file', {'group_id': int(group_id), 'file': file, 'name': name, 'folder': folder})

    async def upload_private_file(self, user_id, file, name) -> dict | None:
        return await self.call_api('upload_private_file', {'user_id': int(user_id), 'file': file, 'name': name})

    async def get_group_root_files(self, group_id) -> dict | None:
        return await self.call_api('get_group_root_files', {'group_id': int(group_id)})

    async def get_group_files_by_folder(self, group_id, folder_id) -> dict | None:
        return await self.call_api('get_group_files_by_folder', {'group_id': int(group_id), 'folder_id': folder_id})

    async def get_group_file_url(self, group_id, file_id, busid=None) -> dict | None:
        params = {'group_id': int(group_id), 'file_id': file_id}
        if busid is not None:
            params['busid'] = busid
        return await self.call_api('get_group_file_url', params)

    async def delete_group_file(self, group_id, file_id, busid=None) -> dict | None:
        params = {'group_id': int(group_id), 'file_id': file_id}
        if busid is not None:
            params['busid'] = busid
        return await self.call_api('delete_group_file', params)

    async def create_group_file_folder(self, group_id, name) -> dict | None:
        return await self.call_api('create_group_file_folder', {'group_id': int(group_id), 'name': name})


def get_api() -> OneBotAPI:
    return OneBotAPI(_adapter_ref)



