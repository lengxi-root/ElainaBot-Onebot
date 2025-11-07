#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger('ElainaBot.core.onebot')


class OneBotClient:
    def __init__(self, ws_url: str = "ws://localhost:2536/OneBotv11"):
        self.ws_url = ws_url
        self.websocket = None
        self.connected = False
        self.running = False
        self.message_handler = None
        self.connect_handler = None
        self.disconnect_handler = None
        self.echo_callbacks = {}
        self.self_id = None
        
    async def connect(self) -> bool:
        try:
            logger.info(f"连接到 OneBot: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            logger.info(f"✅ OneBot 连接成功")
            
            if self.connect_handler:
                await self.connect_handler()
            
            return True
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        self.running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.websocket = None
        self.connected = False
        logger.info("🔌 OneBot 断开连接")
        
        if self.disconnect_handler:
            try:
                await self.disconnect_handler()
            except:
                pass
    
    async def send(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.connected or not self.websocket:
            logger.warning("⚠️ 未连接")
            return None
        
        try:
            await self.websocket.send(json.dumps(data))
            return data
        except Exception as e:
            logger.error(f"❌ 发送失败: {e}")
            await self.disconnect()
            return None
    
    async def call_api(self, action: str, **params) -> Optional[Dict[str, Any]]:
        if not self.connected:
            logger.warning("⚠️ 未连接")
            return None
        
        import time
        echo = f"{time.time()}_{action}"
        request = {"action": action, "params": params, "echo": echo}
        
        future = asyncio.Future()
        self.echo_callbacks[echo] = future
        
        try:
            await self.send(request)
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ API 超时: {action}")
            return None
        except Exception as e:
            logger.error(f"❌ API 失败: {e}")
            return None
        finally:
            if echo in self.echo_callbacks:
                del self.echo_callbacks[echo]
    
    async def run(self):
        self.running = True
        
        while self.running:
            if not self.connected:
                await self.connect()
                if not self.connected:
                    await asyncio.sleep(5)
                    continue
            
            try:
                async for message in self.websocket:
                    if not self.running:
                        break
                    
                    try:
                        data = json.loads(message)
                        
                        if "echo" in data and data["echo"] in self.echo_callbacks:
                            future = self.echo_callbacks.pop(data["echo"])
                            if not future.done():
                                future.set_result(data)
                        elif "post_type" in data and self.message_handler:
                            await self.message_handler(data)
                    except:
                        pass
            except websockets.exceptions.ConnectionClosed:
                logger.warning("⚠️ 连接断开")
                await self.disconnect()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ 接收消息异常: {e}")
                await self.disconnect()
                await asyncio.sleep(5)
        
        await self.disconnect()
    
    def on_message(self, handler: Callable):
        self.message_handler = handler
    
    def on_connect(self, handler: Callable):
        self.connect_handler = handler
    
    def on_disconnect(self, handler: Callable):
        self.disconnect_handler = handler
    
    async def send_private_msg(self, user_id: int, message: Any) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_private_msg", user_id=user_id, message=message)
    
    async def send_group_msg(self, group_id: int, message: Any) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_group_msg", group_id=group_id, message=message)
