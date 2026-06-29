"""OneBot v11 适配器 — WebSocket/HTTP 连接管理"""

import hmac
import json
import asyncio
import logging
from typing import Any, Optional, Dict

from core.onebot.event import parse_event, OneBotEvent

logger = logging.getLogger('ElainaBot.onebot.adapter')


class OneBotAdapter:
    """OneBot v11 协议适配器"""

    def __init__(self):
        self.bots: Dict[str, Any] = {}
        self.websockets: Dict[str, Any] = {}
        self.api_responses: Dict[str, asyncio.Future] = {}
        # HTTP 客户端: name -> {url, token} (框架主动调用 OneBot HTTP API)
        self.http_clients: Dict[str, Dict[str, str]] = {}
        # 每个反向 WS / HTTP 上报连接的鉴权: (port, path) -> token/secret
        # 鉴权必须按连接区分, 否则某条连接配的 token 会被错误地应用到其它连接
        self.reverse_ws_tokens: Dict[tuple, str] = {}
        self.reverse_http_secrets: Dict[tuple, str] = {}

    def expected_ws_token(self, port=None, path=None) -> str:
        """返回指定 (端口, 路径) 反向 WS 入口应校验的 token; 找不到则不校验"""
        m = self.reverse_ws_tokens
        if port is not None and (port, path) in m:
            return m[(port, path)]
        if port is not None:  # 同端口的别名路径 (如 /onebot/v11/ws) 复用该端口的 token
            for (p, _pa), t in m.items():
                if p == port:
                    return t
        return ''

    def expected_http_secret(self, port=None, path=None) -> str:
        m = self.reverse_http_secrets
        if port is not None and (port, path) in m:
            return m[(port, path)]
        if port is not None:
            for (p, _pa), s in m.items():
                if p == port:
                    return s
        return ''

    def _check_signature(self, body: bytes, signature: Optional[str], secret: str = '') -> bool:
        if not secret:
            return True
        if not signature:
            return False
        sig = hmac.new(secret.encode('utf-8'), body, 'sha1').hexdigest()
        return signature == "sha1=" + sig

    def _check_access_token(self, auth_header: Optional[str], token: str = '') -> bool:
        if not token:
            return True
        if not auth_header:
            return False
        parts = auth_header.split(' ', 1)
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return False
        return parts[1] == token

    def parse_event(self, data: dict) -> Optional[OneBotEvent]:
        """解析 OneBot 事件"""
        return parse_event(data)

    def handle_http_callback(self, body: bytes, headers: dict, port=None, path=None) -> tuple:
        """处理 HTTP 回调"""
        self_id = headers.get("x-self-id") or headers.get("X-Self-ID")
        if not self_id:
            return False, None

        signature = headers.get("x-signature") or headers.get("X-Signature")
        if not self._check_signature(body, signature, self.expected_http_secret(port, path)):
            return False, None

        try:
            json_data = json.loads(body)
        except Exception:
            return False, None

        event = self.parse_event(json_data)
        if not event:
            return False, None

        if self_id not in self.bots:
            self.bots[self_id] = {"self_id": self_id, "type": "http"}
            logger.info(f'Bot {self_id} HTTP 连接')

        return True, event

    def validate_websocket_headers(self, headers: dict, port=None, path=None) -> tuple:
        """验证 WebSocket 连接头 (按 端口+路径 选取该连接配置的 token)"""
        self_id = headers.get("x-self-id") or headers.get("X-Self-ID")
        if not self_id:
            return False, None, "Missing X-Self-ID"

        auth_header = headers.get("authorization") or headers.get("Authorization")
        if not self._check_access_token(auth_header, self.expected_ws_token(port, path)):
            return False, self_id, "Unauthorized"

        return True, self_id, None

    def register_bot(self, self_id: str, ws=None):
        # 注意: aiohttp 的 WebSocketResponse 定义了 __len__→0, bool(ws) 为 False,
        # 必须用 `is not None` 判断, 否则反向 WS 会被误判为 http 且不进入 websockets
        is_ws = ws is not None
        self.bots[self_id] = {"self_id": self_id, "type": "websocket" if is_ws else "http", "ws": ws}
        if is_ws:
            self.websockets[self_id] = ws

    def unregister_bot(self, self_id: str):
        self.bots.pop(self_id, None)
        self.websockets.pop(self_id, None)

    def get_bot_ws(self, self_id: str = None):
        """获取 bot WebSocket 连接"""
        if self_id:
            return self.websockets.get(self_id)
        # 返回第一个
        if self.websockets:
            return next(iter(self.websockets.values()))
        return None

    def register_http_client(self, name: str, url: str, token: str = ''):
        """注册 HTTP 客户端目标 (框架 -> OneBot HTTP API)"""
        self.http_clients[name] = {'url': (url or '').rstrip('/'), 'token': token or ''}

    def clear_http_clients(self):
        self.http_clients.clear()

    async def http_call_action(self, action: str, params: dict = None) -> Optional[dict]:
        """通过 HTTP 调用 OneBot API (POST {url}/{action})"""
        if not self.http_clients:
            return None
        import aiohttp
        client = next(iter(self.http_clients.values()))
        url = f"{client['url']}/{action}"
        headers = {'Content-Type': 'application/json'}
        if client.get('token'):
            headers['Authorization'] = 'Bearer ' + client['token']
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=params or {}, headers=headers) as resp:
                    return await resp.json()
        except Exception as e:
            logger.warning(f'HTTP API 调用失败: {action} - {e}')
            return None
