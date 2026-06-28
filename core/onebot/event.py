"""OneBot v11 事件模型 (异步框架)"""

import time
from typing import List, Optional


class OneBotEvent:
    """OneBot v11 基础事件"""

    def __init__(self, data: dict):
        self.raw_data = data
        self.time = data.get('time', int(time.time()))
        self.self_id = data.get('self_id', '')
        self.post_type = data.get('post_type', '')
        self._api = None  # 由 Application 注入

    def to_dict(self) -> dict:
        return self.raw_data

    @property
    def content(self) -> str:
        return ''


class MessageEvent(OneBotEvent):
    """消息事件"""

    def __init__(self, data: dict):
        super().__init__(data)
        self.message_type = data.get('message_type', '')
        self.sub_type = data.get('sub_type', '')
        self.message_id = data.get('message_id', 0)
        self.user_id = data.get('user_id', 0)
        self.group_id = data.get('group_id')
        self.message: List[dict] = data.get('message', [])
        self.raw_message = data.get('raw_message', '')
        self.sender: dict = data.get('sender', {})
        self.font = data.get('font', 0)

    @property
    def is_group(self) -> bool:
        return self.message_type == 'group'

    @property
    def is_private(self) -> bool:
        return self.message_type == 'private'

    @property
    def sender_nickname(self) -> str:
        return self.sender.get('nickname', '')

    @property
    def sender_card(self) -> str:
        return self.sender.get('card', '')

    @property
    def content(self) -> str:
        """提取纯文本内容"""
        parts = []
        for seg in self.message:
            if isinstance(seg, dict) and seg.get('type') == 'text':
                parts.append(seg.get('data', {}).get('text', ''))
        return ''.join(parts).strip()

    async def reply(self, message, **kwargs):
        """异步回复消息

        Args:
            message: 消息内容 (字符串或消息段列表)
        """
        if self._api is None:
            return None
        if isinstance(message, str):
            message = [{'type': 'text', 'data': {'text': message}}]
        if self.is_group:
            return await self._api.send_group_msg(self.group_id, message, **kwargs)
        else:
            return await self._api.send_private_msg(self.user_id, message, **kwargs)

    async def reply_text(self, text: str, **kwargs):
        """回复纯文本"""
        return await self.reply(text, **kwargs)

    async def reply_image(self, file: str, **kwargs):
        """回复图片"""
        msg = [{'type': 'image', 'data': {'file': file}}]
        return await self.reply(msg, **kwargs)

    async def call_api(self, action: str, params: dict = None):
        """调用 OneBot API"""
        if self._api is None:
            return None
        return await self._api.call_api(action, params, self_id=str(self.self_id))


class NoticeEvent(OneBotEvent):
    """通知事件"""

    def __init__(self, data: dict):
        super().__init__(data)
        self.notice_type = data.get('notice_type', '')
        self.sub_type = data.get('sub_type', '')
        self.user_id = data.get('user_id', 0)
        self.group_id = data.get('group_id')
        self.operator_id = data.get('operator_id', 0)


class RequestEvent(OneBotEvent):
    """请求事件"""

    def __init__(self, data: dict):
        super().__init__(data)
        self.request_type = data.get('request_type', '')
        self.sub_type = data.get('sub_type', '')
        self.user_id = data.get('user_id', 0)
        self.group_id = data.get('group_id')
        self.comment = data.get('comment', '')
        self.flag = data.get('flag', '')


class MetaEvent(OneBotEvent):
    """元事件"""

    def __init__(self, data: dict):
        super().__init__(data)
        self.meta_event_type = data.get('meta_event_type', '')


def parse_event(data: dict) -> Optional[OneBotEvent]:
    """解析 OneBot 事件"""
    if not isinstance(data, dict) or 'post_type' not in data:
        return None

    post_type = data.get('post_type')
    if post_type == 'message':
        return MessageEvent(data)
    elif post_type == 'notice':
        return NoticeEvent(data)
    elif post_type == 'request':
        return RequestEvent(data)
    elif post_type == 'meta_event':
        return MetaEvent(data)
    return OneBotEvent(data)
