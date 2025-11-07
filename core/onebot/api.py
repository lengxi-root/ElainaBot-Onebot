#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger('ElainaBot.core.onebot')


class OneBotAPI:
    def __init__(self, client=None):
        self.client = client
    
    async def call_api(self, action: str, **params) -> Optional[Dict[str, Any]]:
        try:
            from core.onebot.adapter import get_adapter
            adapter = get_adapter()
            
            if not adapter.bots:
                logger.warning("⚠️ 没有已连接的 Bot")
                return None
            
            bot_id = list(adapter.bots.keys())[0]
            bot_info = adapter.bots[bot_id]
            
            if bot_info.get("type") != "websocket":
                return None
            
            ws = bot_info.get("ws")
            if not ws:
                return None
            
            echo = f"{time.time()}_{action}"
            request = {"action": action, "params": params, "echo": echo}
            
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            adapter.api_responses[echo] = future
            
            try:
                await ws.send_text(json.dumps(request))
            except Exception as e:
                logger.error(f"❌ API 请求失败: {action} - {e}")
                if echo in adapter.api_responses:
                    del adapter.api_responses[echo]
                return None
            
            try:
                response = await asyncio.wait_for(future, timeout=30.0)
                return response
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ API 超时: {action}")
                if echo in adapter.api_responses:
                    del adapter.api_responses[echo]
                return None
        except Exception as e:
            logger.error(f"❌ API 调用异常: {action} - {e}")
            return None
    
    async def send_private_msg(self, user_id: Union[str, int], message: Any, **kwargs) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_private_msg", user_id=str(user_id), message=message, **kwargs)
    
    async def send_group_msg(self, group_id: Union[str, int], message: Any, **kwargs) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_group_msg", group_id=str(group_id), message=message, **kwargs)
    
    async def send_msg(self, message_type: str = None, user_id: Union[str, int] = None, 
                      group_id: Union[str, int] = None, message: Any = None, **kwargs) -> Optional[Dict[str, Any]]:
        params = {"message": message}
        if message_type:
            params["message_type"] = message_type
        if user_id:
            params["user_id"] = str(user_id)
        if group_id:
            params["group_id"] = str(group_id)
        params.update(kwargs)
        return await self.call_api("send_msg", **params)
    
    async def send_group_forward_msg(self, group_id: Union[str, int], messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_group_forward_msg", group_id=str(group_id), messages=messages)
    
    async def send_private_forward_msg(self, user_id: Union[str, int], messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_private_forward_msg", user_id=str(user_id), messages=messages)
    
    async def delete_msg(self, message_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        return await self.call_api("delete_msg", message_id=str(message_id))
    
    async def get_msg(self, message_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_msg", message_id=str(message_id))
    
    async def get_login_info(self) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_login_info")
    
    async def get_stranger_info(self, user_id: Union[str, int], no_cache: bool = False) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_stranger_info", user_id=str(user_id), no_cache=no_cache)
    
    async def get_friend_list(self) -> Optional[List[Dict[str, Any]]]:
        result = await self.call_api("get_friend_list")
        if result and result.get("retcode") == 0:
            return result.get("data", [])
        return []
    
    async def get_group_list(self) -> Optional[List[Dict[str, Any]]]:
        result = await self.call_api("get_group_list")
        if result and result.get("retcode") == 0:
            return result.get("data", [])
        return []
    
    async def get_group_info(self, group_id: Union[str, int], no_cache: bool = False) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_info", group_id=str(group_id), no_cache=no_cache)
    
    async def get_group_member_info(self, group_id: Union[str, int], user_id: Union[str, int], 
                                   no_cache: bool = False) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_member_info", group_id=str(group_id), 
                                  user_id=str(user_id), no_cache=no_cache)
    
    async def get_group_member_list(self, group_id: Union[str, int]) -> Optional[List[Dict[str, Any]]]:
        result = await self.call_api("get_group_member_list", group_id=str(group_id))
        if result and result.get("retcode") == 0:
            return result.get("data", [])
        return []
    
    async def set_group_ban(self, group_id: Union[str, int], user_id: Union[str, int], 
                           duration: int = 30 * 60) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_ban", group_id=str(group_id), 
                                  user_id=str(user_id), duration=duration)
    
    async def set_group_whole_ban(self, group_id: Union[str, int], enable: bool = True) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_whole_ban", group_id=str(group_id), enable=enable)
    
    async def set_group_admin(self, group_id: Union[str, int], user_id: Union[str, int], 
                             enable: bool = True) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_admin", group_id=str(group_id), 
                                  user_id=str(user_id), enable=enable)
    
    async def set_group_card(self, group_id: Union[str, int], user_id: Union[str, int], 
                            card: str = "") -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_card", group_id=str(group_id), 
                                  user_id=str(user_id), card=card)
    
    async def set_group_name(self, group_id: Union[str, int], group_name: str) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_name", group_id=str(group_id), group_name=group_name)
    
    async def set_group_leave(self, group_id: Union[str, int], is_dismiss: bool = False) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_leave", group_id=str(group_id), is_dismiss=is_dismiss)
    
    async def set_group_special_title(self, group_id: Union[str, int], user_id: Union[str, int], 
                                     special_title: str = "", duration: int = -1) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_special_title", group_id=str(group_id), 
                                  user_id=str(user_id), special_title=special_title, duration=duration)
    
    async def set_group_kick(self, group_id: Union[str, int], user_id: Union[str, int], 
                            reject_add_request: bool = False) -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_kick", group_id=str(group_id), 
                                  user_id=str(user_id), reject_add_request=reject_add_request)
    
    async def delete_friend(self, user_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        return await self.call_api("delete_friend", user_id=str(user_id))
    
    async def set_friend_add_request(self, flag: str, approve: bool = True, 
                                    remark: str = "") -> Optional[Dict[str, Any]]:
        return await self.call_api("set_friend_add_request", flag=flag, 
                                  approve=approve, remark=remark)
    
    async def set_group_add_request(self, flag: str, sub_type: str, approve: bool = True, 
                                   reason: str = "") -> Optional[Dict[str, Any]]:
        return await self.call_api("set_group_add_request", flag=flag, sub_type=sub_type, 
                                  approve=approve, reason=reason)
    
    async def upload_group_file(self, group_id: Union[str, int], file: str, 
                               name: str, folder: str = "/") -> Optional[Dict[str, Any]]:
        return await self.call_api("upload_group_file", group_id=str(group_id), 
                                  file=file, name=name, folder=folder)
    
    async def upload_private_file(self, user_id: Union[str, int], file: str, 
                                  name: str) -> Optional[Dict[str, Any]]:
        return await self.call_api("upload_private_file", user_id=str(user_id), 
                                  file=file, name=name)
    
    async def get_group_file_system_info(self, group_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_file_system_info", group_id=str(group_id))
    
    async def get_group_root_files(self, group_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_root_files", group_id=str(group_id))
    
    async def get_group_files_by_folder(self, group_id: Union[str, int], 
                                       folder_id: str) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_files_by_folder", group_id=str(group_id), 
                                  folder_id=folder_id)
    
    async def get_group_file_url(self, group_id: Union[str, int], file_id: str, 
                                busid: int) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_file_url", group_id=str(group_id), 
                                  file_id=file_id, busid=busid)
    
    async def get_version_info(self) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_version_info")
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_status")
    
    async def can_send_image(self) -> Optional[Dict[str, Any]]:
        return await self.call_api("can_send_image")
    
    async def can_send_record(self) -> Optional[Dict[str, Any]]:
        return await self.call_api("can_send_record")
    
    async def ocr_image(self, image: str) -> Optional[Dict[str, Any]]:
        return await self.call_api("ocr_image", image=image)
    
    async def get_group_honor_info(self, group_id: Union[str, int], 
                                   type: str = "all") -> Optional[Dict[str, Any]]:
        return await self.call_api("get_group_honor_info", group_id=str(group_id), type=type)
    
    async def send_group_sign(self, group_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        return await self.call_api("send_group_sign", group_id=str(group_id))
    
    async def get_cookies(self, domain: str = "") -> Optional[Dict[str, Any]]:
        return await self.call_api("get_cookies", domain=domain)
    
    async def get_csrf_token(self) -> Optional[Dict[str, Any]]:
        return await self.call_api("get_csrf_token")
    
    async def get_credentials(self, domain: str = "") -> Optional[Dict[str, Any]]:
        return await self.call_api("get_credentials", domain=domain)


_onebot_api_instance: Optional[OneBotAPI] = None


def get_onebot_api() -> OneBotAPI:
    global _onebot_api_instance
    if _onebot_api_instance is None:
        _onebot_api_instance = OneBotAPI()
    return _onebot_api_instance


_main_loop = None

def set_main_loop(loop):
    global _main_loop
    _main_loop = loop
    logger.debug("🔄 设置主事件循环")

def run_async_api(coro):
    import threading
    import concurrent.futures
    
    try:
        try:
            loop = asyncio.get_running_loop()
            if _main_loop and _main_loop != loop:
                logger.debug("🔄 提交到主事件循环")
                future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
                try:
                    return future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    logger.error("❌ API 超时")
                    return None
            else:
                new_loop = asyncio.new_event_loop()
                def run_in_thread():
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    try:
                        return future.result(timeout=30)
                    except concurrent.futures.TimeoutError:
                        logger.error("❌ API 超时")
                        return None
        except RuntimeError:
            if _main_loop:
                logger.debug("🔄 从工作线程提交")
                future = asyncio.run_coroutine_threadsafe(coro, _main_loop)
                try:
                    return future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    logger.error("❌ API 超时")
                    return None
            else:
                new_loop = asyncio.new_event_loop()
                def run_in_thread():
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    try:
                        return future.result(timeout=30)
                    except concurrent.futures.TimeoutError:
                        logger.error("❌ API 超时")
                        return None
    except Exception as e:
        logger.error(f"❌ run_async_api 异常: {e}")
        return None


def send_private_msg_sync(user_id: Union[str, int], message: Any, **kwargs) -> Optional[Dict[str, Any]]:
    api = get_onebot_api()
    return run_async_api(api.send_private_msg(user_id, message, **kwargs))

def send_group_msg_sync(group_id: Union[str, int], message: Any, **kwargs) -> Optional[Dict[str, Any]]:
    api = get_onebot_api()
    return run_async_api(api.send_group_msg(group_id, message, **kwargs))

def send_msg_sync(message_type: str = None, user_id: Union[str, int] = None, 
                 group_id: Union[str, int] = None, message: Any = None, **kwargs) -> Optional[Dict[str, Any]]:
    api = get_onebot_api()
    return run_async_api(api.send_msg(message_type, user_id, group_id, message, **kwargs))

def delete_msg_sync(message_id: Union[str, int]) -> Optional[Dict[str, Any]]:
    api = get_onebot_api()
    return run_async_api(api.delete_msg(message_id))

def get_login_info_sync() -> Optional[Dict[str, Any]]:
    api = get_onebot_api()
    return run_async_api(api.get_login_info())

async def call_onebot_api(action: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
    api = get_onebot_api()
    return await api.call_api(action, **(params or {}))
