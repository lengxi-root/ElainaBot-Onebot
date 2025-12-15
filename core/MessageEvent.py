#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OneBot v11 协议的 MessageEvent 实现
包含消息段（MessageSegment）和消息事件（MessageEvent）
"""

import json
import random
import time
import re
import logging
from typing import Dict, Any, Optional, List, Union, Iterable
from pathlib import Path
from core.onebot.api import get_onebot_api, run_async_api

logger = logging.getLogger('ElainaBot.core.event.MessageEvent_OneBot')
def escape(s: str, *, escape_comma: bool = True) -> str:
    """转义特殊字符"""
    s = s.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")
    if escape_comma:
        s = s.replace(",", "&#44;")
    return s


def unescape(s: str) -> str:
    """反转义特殊字符"""
    return (
        s.replace("&#44;", ",")
        .replace("&#91;", "[")
        .replace("&#93;", "]")
        .replace("&amp;", "&")
    )
class MessageSegment:
    """OneBot v11 消息段，用于构建富文本消息"""
    
    def __init__(self, type: str, data: Dict[str, Any]):
        self.type = type
        self.data = data
    
    def __str__(self) -> str:
        """转换为 CQ 码字符串"""
        if self.is_text():
            return escape(self.data.get("text", ""), escape_comma=False)
        params = ",".join(f"{k}={escape(str(v))}" for k, v in self.data.items() if v is not None)
        return f"[CQ:{self.type}{',' if params else ''}{params}]"
    
    def __repr__(self) -> str:
        return f"MessageSegment(type={self.type!r}, data={self.data!r})"
    
    def __eq__(self, other) -> bool:
        return isinstance(other, MessageSegment) and self.type == other.type and self.data == other.data
    
    def __add__(self, other: Union[str, "MessageSegment", "Message"]) -> "Message":
        return Message(self) + other
    
    def __radd__(self, other: Union[str, "MessageSegment", "Message"]) -> "Message":
        return Message(other) + self
    
    def is_text(self) -> bool:
        return self.type == "text"
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": self.type, "data": self.data.copy()}
    
    # 消息段工厂方法
    @classmethod
    def text(cls, text: str) -> "MessageSegment":
        return cls("text", {"text": text})
    
    @classmethod
    def at(cls, user_id: Union[int, str]) -> "MessageSegment":
        return cls("at", {"qq": str(user_id)})
    
    @classmethod
    def at_all(cls) -> "MessageSegment":
        return cls("at", {"qq": "all"})
    
    @classmethod
    def face(cls, id: int) -> "MessageSegment":
        return cls("face", {"id": str(id)})
    
    @classmethod
    def image(cls, file: str, type: Optional[str] = None, cache: bool = True, 
              proxy: bool = True, timeout: Optional[int] = None) -> "MessageSegment":
        data = {"file": file}
        if type:
            data["type"] = type
        if not cache:
            data["cache"] = "0"
        if not proxy:
            data["proxy"] = "0"
        if timeout:
            data["timeout"] = str(timeout)
        return cls("image", data)
    
    @classmethod
    def record(cls, file: str, magic: bool = False, cache: bool = True, 
               proxy: bool = True, timeout: Optional[int] = None) -> "MessageSegment":
        data = {"file": file}
        if magic:
            data["magic"] = "1"
        if not cache:
            data["cache"] = "0"
        if not proxy:
            data["proxy"] = "0"
        if timeout:
            data["timeout"] = str(timeout)
        return cls("record", data)
    
    @classmethod
    def video(cls, file: str, cache: bool = True, 
              proxy: bool = True, timeout: Optional[int] = None) -> "MessageSegment":
        data = {"file": file}
        if not cache:
            data["cache"] = "0"
        if not proxy:
            data["proxy"] = "0"
        if timeout:
            data["timeout"] = str(timeout)
        return cls("video", data)
    
    @classmethod
    def reply(cls, id: Union[int, str]) -> "MessageSegment":
        return cls("reply", {"id": str(id)})
    
    @classmethod
    def forward(cls, id: str) -> "MessageSegment":
        return cls("forward", {"id": id})
    
    @classmethod
    def share(cls, url: str, title: str, content: Optional[str] = None, 
              image: Optional[str] = None) -> "MessageSegment":
        data = {"url": url, "title": title}
        if content:
            data["content"] = content
        if image:
            data["image"] = image
        return cls("share", data)


class Message:
    """OneBot v11 消息，由多个 MessageSegment 组成"""
    
    def __init__(self, message: Union[str, MessageSegment, Iterable[MessageSegment], None] = None):
        self.segments: List[MessageSegment] = []
        
        if message is None:
            pass
        elif isinstance(message, str):
            self.segments.append(MessageSegment.text(message))
        elif isinstance(message, MessageSegment):
            self.segments.append(message)
        elif isinstance(message, Message):
            self.segments = message.segments.copy()
        elif isinstance(message, Iterable):
            for seg in message:
                if isinstance(seg, MessageSegment):
                    self.segments.append(seg)
                elif isinstance(seg, dict):
                    self.segments.append(MessageSegment(seg["type"], seg.get("data", {})))
    
    def __str__(self) -> str:
        return "".join(str(seg) for seg in self.segments)
    
    def __add__(self, other: Union[str, MessageSegment, "Message"]) -> "Message":
        result = Message(self)
        if isinstance(other, str):
            result.segments.append(MessageSegment.text(other))
        elif isinstance(other, MessageSegment):
            result.segments.append(other)
        elif isinstance(other, Message):
            result.segments.extend(other.segments)
        return result
    
    def append(self, segment: Union[str, MessageSegment]) -> "Message":
        if isinstance(segment, str):
            self.segments.append(MessageSegment.text(segment))
        elif isinstance(segment, MessageSegment):
            self.segments.append(segment)
        return self
    
    def extract_plain_text(self) -> str:
        return "".join(seg.data.get("text", "") for seg in self.segments if seg.is_text())
    
    def to_onebot_array(self) -> List[Dict[str, Any]]:
        return [seg.to_dict() for seg in self.segments]


# ==================== MessageEvent ====================


class OneBotMessageEvent:
    """OneBot v11 事件类（支持 message/notice/request）"""
    
    # 消息类型常量
    GROUP_MESSAGE = 'group'
    PRIVATE_MESSAGE = 'private'
    UNKNOWN_MESSAGE = 'unknown'
    
    # OneBot 事件类型到内部类型的映射
    _ONEBOT_MESSAGE_TYPES = {
        'group': GROUP_MESSAGE,
        'private': PRIVATE_MESSAGE,
    }
    
    def __init__(self, data, skip_recording=False, http_context=None):
        self.raw_data = data
        self.skip_recording = skip_recording
        
        # 解析数据
        if isinstance(data, str):
            try:
                self.data = json.loads(data)
            except:
                self.data = {}
        else:
            self.data = data
        
        # 基本信息
        self.post_type = self.data.get('post_type', '')  # message/notice/request/meta_event
        self.time = self.data.get('time', int(time.time()))
        self.self_id = str(self.data.get('self_id', ''))
        
        # 用户和群组信息（所有事件都可能有）
        self.user_id = str(self.data.get('user_id', '')) if self.data.get('user_id') else None
        self.group_id = str(self.data.get('group_id', '')) if self.data.get('group_id') else None
        
        # === 消息事件特有字段 ===
        if self.post_type == 'message':
            self.message_type = self._parse_message_type()
            self.message_id = self.data.get('message_id', '')
            
            # 发送者信息
            self.sender = self.data.get('sender', {})
            self.sender_nickname = self.sender.get('nickname', '')
            self.sender_card = self.sender.get('card', '')
            
            # 消息内容
            self.message = self.data.get('message', [])
            self.raw_message = self.data.get('raw_message', '')
            self.content = self._parse_content()
            
            # 消息类型判断
            self.is_group = self.message_type == self.GROUP_MESSAGE
            self.is_private = self.message_type == self.PRIVATE_MESSAGE
            
            # event_type 属性
            if self.is_group:
                self.event_type = "GROUP_MESSAGE"
            elif self.is_private:
                self.event_type = "PRIVATE_MESSAGE"
            else:
                self.event_type = "MESSAGE"
        
        # === 通知事件特有字段 ===
        elif self.post_type == 'notice':
            self.notice_type = self.data.get('notice_type', '')  # group_increase/group_decrease等
            self.sub_type = self.data.get('sub_type', '')
            self.operator_id = str(self.data.get('operator_id', '')) if self.data.get('operator_id') else None
            
            # 调试日志
            import logging
            logger = logging.getLogger('ElainaBot')
            logger.debug(f"解析通知事件: notice_type={self.notice_type}, group_id={self.group_id}, user_id={self.user_id}")
            
            # 设置默认值
            self.message_type = self.UNKNOWN_MESSAGE
            self.message_id = ''
            self.sender = {}
            self.sender_nickname = ''
            self.sender_card = ''
            self.message = []
            self.raw_message = ''
            self.content = ''
            self.is_group = bool(self.group_id)
            self.is_private = False
            self.event_type = f"NOTICE_{self.notice_type.upper()}"
        
        # === 请求事件特有字段 ===
        elif self.post_type == 'request':
            self.request_type = self.data.get('request_type', '')  # friend/group
            self.sub_type = self.data.get('sub_type', '')
            self.comment = self.data.get('comment', '')  # 验证消息
            self.flag = self.data.get('flag', '')  # 请求标识
            
            # 调试日志
            import logging
            logger = logging.getLogger('ElainaBot')
            logger.debug(f"解析请求事件: request_type={self.request_type}, group_id={self.group_id}, user_id={self.user_id}, comment={self.comment}")
            
            # 设置默认值
            self.message_type = self.UNKNOWN_MESSAGE
            self.message_id = ''
            self.sender = {}
            self.sender_nickname = ''
            self.sender_card = ''
            self.message = []
            self.raw_message = ''
            self.content = self.comment  # 请求事件的内容就是验证消息
            self.is_group = self.request_type == 'group'
            self.is_private = False
            self.event_type = f"REQUEST_{self.request_type.upper()}"
        
        # === 元事件 ===
        else:
            # meta_event 或未知类型
            self.message_type = self.UNKNOWN_MESSAGE
            self.message_id = ''
            self.sender = {}
            self.sender_nickname = ''
            self.sender_card = ''
            self.message = []
            self.raw_message = ''
            self.content = ''
            self.is_group = False
            self.is_private = False
            self.event_type = self.post_type.upper()
        
        # 其他通用属性
        self.ignore = False
        self.matches = None
        self._api = None
        self.is_master = self._check_is_master()
        self.timestamp = str(self.time)
    
    def _parse_message_type(self) -> str:
        """解析消息类型"""
        if self.data.get('post_type') != 'message':
            return self.UNKNOWN_MESSAGE
        
        message_type = self.data.get('message_type', '')
        return self._ONEBOT_MESSAGE_TYPES.get(message_type, self.UNKNOWN_MESSAGE)
    
    def _parse_content(self) -> str:
        """解析消息内容"""
        content_parts = []
        for segment in self.message:
            if isinstance(segment, dict):
                seg_type = segment.get('type', '')
                seg_data = segment.get('data', {})
                if seg_type == 'text':
                    content_parts.append(seg_data.get('text', ''))
                elif seg_type == 'image':
                    url = seg_data.get('url', seg_data.get('file', ''))
                    if url:
                        content_parts.append(f"<{url}>")
        
        content = ''.join(content_parts).strip()
        if not content and self.raw_message:
            content = self.raw_message
        if content and content[0] == '/':
            content = content[1:]
        return content
    
    @property
    def api(self):
        """获取 API 实例"""
        if self._api is None:
            self._api = get_onebot_api()
        return self._api
    
    def get(self, path):
        """从数据中获取值"""
        try:
            data = self.data
            for key in path.split('/'):
                if not key:
                    continue
                data = data.get(key) if isinstance(data, dict) else None
                if data is None:
                    return None
            return data
        except:
            return None
    
    def reply(self, content='', auto_delete_time=None, **kwargs):
        """回复消息"""
        if not content:
            return None
        
        message = self._build_message(content)
        
        if self.is_group:
            result = run_async_api(self.api.send_group_msg(self.group_id, message, **kwargs))
            chat_id = self.group_id
        elif self.is_private:
            result = run_async_api(self.api.send_private_msg(self.user_id, message, **kwargs))
            chat_id = self.user_id
        else:
            return None
        
        if result and result.get('retcode') == 0:
            message_id = result.get('data', {}).get('message_id')
            
            # 输出控制台日志
            try:
                from main import log_sent_message
                log_sent_message(message, self.is_group, chat_id)
            except:
                pass
            
            if auto_delete_time and message_id:
                import threading
                threading.Timer(auto_delete_time, self._auto_recall, args=[message_id]).start()
            return message_id
        return None
    
    def _build_message(self, content):
        """构建消息格式"""
        if isinstance(content, str):
            return [{"type": "text", "data": {"text": content}}]
        if isinstance(content, Message):
            return content.to_onebot_array()
        if isinstance(content, list):
            return content
        if isinstance(content, dict):
            return [content]
        return [{"type": "text", "data": {"text": str(content)}}]
    
    def _auto_recall(self, message_id):
        """自动撤回消息"""
        try:
            run_async_api(self.api.delete_msg(message_id))
        except:
            pass
    
    def recall_message(self, message_id):
        """撤回消息"""
        try:
            result = run_async_api(self.api.delete_msg(message_id))
            return result and result.get('retcode') == 0
        except:
            return False
    
    def _record_message_to_db_only(self):
        """记录消息到数据库"""
        try:
            from function.log_db import add_log_to_db
            import datetime
            
            reply_id = None
            for segment in self.message:
                if isinstance(segment, dict) and segment.get('type') == 'reply':
                    reply_id = segment.get('data', {}).get('id')
                    break
            
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            add_log_to_db('received', {
                'timestamp': timestamp,
                'content': self.content or "",
                'user_id': self.user_id or "unknown",
                'group_id': self.group_id or "private",
                'message_id': str(self.message_id),
                'real_seq': str(self.data.get('real_seq', '')),
                'reply_id': str(reply_id) if reply_id else None,
                'raw_message': json.dumps(self.data, ensure_ascii=False),
                'message_segments': json.dumps(self.message, ensure_ascii=False),
                'message_type': 'group' if self.is_group else 'private'
            })
        except:
            pass
    
    def _record_user_and_group(self):
        pass
    
    def record_last_message_id(self):
        pass
    
    def _check_is_master(self):
        """检查是否是主人"""
        try:
            from config import OWNER_IDS
            return str(self.user_id) in OWNER_IDS
        except:
            return False
    
    async def call_api(self, api_name, params=None):
        """调用 OneBot API"""
        try:
            from core.onebot.api import call_onebot_api
            return await call_onebot_api(api_name, params or {})
        except Exception as e:
            logger.error(f"API 调用失败: {api_name}, {str(e)}")
            return None
    
    def get_at_users(self):
        """获取所有被 @ 的用户 ID"""
        at_users = []
        for segment in self.message:
            if isinstance(segment, dict) and segment.get('type') == 'at':
                qq = segment.get('data', {}).get('qq', '')
                if qq and qq != 'all':
                    at_users.append(str(qq))
        return at_users
    
    def get_first_at_user(self):
        """获取第一个被 @ 的用户 ID"""
        at_users = self.get_at_users()
        return at_users[0] if at_users else None
    
    def has_at_all(self):
        """检查是否包含 @全体成员"""
        for segment in self.message:
            if isinstance(segment, dict) and segment.get('type') == 'at':
                if segment.get('data', {}).get('qq') == 'all':
                    return True
        return False
    
    def has_at_bot(self):
        """检查是否 @ 了机器人"""
        for segment in self.message:
            if isinstance(segment, dict) and segment.get('type') == 'at':
                if segment.get('data', {}).get('qq') == str(self.self_id):
                    return True
        return False
    
    def _notify_web_display(self, timestamp):
        """通知Web界面显示消息"""
        try:
            from web.tools.log_handler import add_display_message
            
            msg_type = "群聊" if self.is_group else "私聊"
            sender = self.sender_card or self.sender_nickname or str(self.user_id)
            location = f"群({self.group_id})" if self.is_group else f"私聊({self.user_id})"
            
            # 简单解析消息内容
            content_parts = []
            for segment in self.message:
                if isinstance(segment, dict):
                    seg_type = segment.get('type', '')
                    seg_data = segment.get('data', {})
                    if seg_type == 'text':
                        content_parts.append(seg_data.get('text', '').strip())
                    elif seg_type == 'at':
                        qq = seg_data.get('qq', '')
                        content_parts.append('@全体' if qq == 'all' else f'@{qq}')
                    elif seg_type == 'image':
                        content_parts.append('[图片]')
                    elif seg_type == 'reply':
                        content_parts.append('↩️')
                    else:
                        content_parts.append(f'[{seg_type}]')
            
            content = ''.join(content_parts) or self.content or "[空消息]"
            display_content = content[:100] + "..." if len(content) > 100 else content
            formatted_message = f"{msg_type} | {location} | {sender}: {display_content}"
            
            add_display_message(
                formatted_message=formatted_message,
                timestamp=timestamp,
                user_id=str(self.user_id),
                group_id=str(self.group_id) if self.is_group else None,
                message_content=content
            )
        except:
            pass
    


# 为了兼容性，导出为 MessageEvent
MessageEvent = OneBotMessageEvent

