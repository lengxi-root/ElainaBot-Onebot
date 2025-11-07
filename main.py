#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, time, shutil

def check_python_version():
    required_version = (3, 9)
    current_version = sys.version_info[:2]
    if current_version < required_version:
        print(f"❌ Python版本不符合要求！当前: {current_version[0]}.{current_version[1]}, 要求: {required_version[0]}.{required_version[1]}+")
        sys.exit(1)
    print(f"✅ Python版本检查通过: Python {current_version[0]}.{current_version[1]}")
    return True

def check_dependencies():
    try:
        from importlib.metadata import version, PackageNotFoundError
    except ImportError:
        try:
            from importlib_metadata import version, PackageNotFoundError
        except ImportError:
            print("⚠️  警告: 无法导入依赖检查模块，跳过依赖检查")
            return True
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    requirements_file = os.path.join(base_dir, 'requirements.txt')
    if not os.path.exists(requirements_file):
        print("⚠️  警告: 未找到 requirements.txt 文件，跳过依赖检查")
        return True
    
    print("🔍 正在检查依赖包...")
    missing_packages = []
    try:
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = f.readlines()
        
        for line in requirements:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '==' in line:
                package_name = line.split('==')[0].strip()
            elif '>=' in line:
                package_name = line.split('>=')[0].strip()
            elif '[' in line:  # 处理 uvicorn[standard] 这样的包
                package_name = line.split('[')[0].strip()
            else:
                package_name = line.strip()
            
            possible_names = [
                package_name, package_name.lower(),
                package_name.lower().replace('_', '-'),
                package_name.lower().replace('-', '_'),
            ]
            
            installed = False
            for check_name in possible_names:
                try:
                    version(check_name)
                    installed = True
                    break
                except PackageNotFoundError:
                    continue
            
            if not installed:
                missing_packages.append(package_name)
        
        if not missing_packages:
            print("✅ 所有依赖包检查通过！")
            return True
        
        print("\n❌ 缺少依赖包:", ', '.join(missing_packages))
        print("💡 pip install -r requirements.txt")
        print("\n按 Enter 继续或 Ctrl+C 退出...")
        try:
            input()
        except KeyboardInterrupt:
            sys.exit(0)
        return True
    except:
        return True

def check_and_replace_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_new_path = os.path.join(base_dir, 'web', 'config_new.py')
    config_path = os.path.join(base_dir, 'config.py')
    backup_dir = os.path.join(base_dir, 'data', 'config')
    
    if os.path.exists(config_new_path):
        if os.path.exists(config_path):
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            shutil.copy2(config_path, os.path.join(backup_dir, f'config_backup_{timestamp}.py'))
        shutil.move(config_new_path, config_path)

check_python_version()
check_and_replace_config()
check_dependencies()

import json, gc, threading, logging, traceback, warnings, signal, asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from config import LOG_CONFIG, LOG_DB_CONFIG, SERVER_CONFIG, WEB_SECURITY, ONEBOT_CONFIG
from function.httpx_pool import get_pool_manager

warnings.filterwarnings("ignore", category=UserWarning)

# 创建主框架 logger
logger = logging.getLogger('ElainaBot')

try:
    from function.log_db import add_log_to_db
except:
    add_log_to_db = lambda *a, **k: False

_logging_initialized = False
_app_initialized = False
http_pool = get_pool_manager()
_gc_counter = 0
_message_handler_ready = threading.Event()
_plugins_preloaded = False

# OneBot Adapter 实例
_onebot_adapter = None

def log_error(error_msg, tb_str=None):
    logger.error(f"{error_msg}\n{tb_str or traceback.format_exc()}")

def cleanup_gc():
    global _gc_counter
    _gc_counter += 1
    if _gc_counter >= 100:
        gc.collect(0)
        _gc_counter = 0

def log_to_console(message):
    logger.info(message)

def setup_logging():
    global _logging_initialized
    if _logging_initialized:
        return
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    formatter = logging.Formatter('[ElainaBot] %(asctime)s - %(levelname)s - %(message)s', datefmt='%m-%d %H:%M:%S')
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    for logger_name in ['werkzeug', 'socketio', 'engineio', 'urllib3', 'uvicorn.access']:
        log = logging.getLogger(logger_name)
        log.setLevel(logging.ERROR)
        log.propagate = False
    _logging_initialized = True

sys.excepthook = lambda exctype, value, tb: log_error(f"{exctype.__name__}: {value}", "".join(traceback.format_tb(tb)))

def convert_onebot_event_to_message_event(onebot_event):
    """将 OneBot 事件转换为框架的 MessageEvent"""
    from core.onebot.adapter import MessageEvent as OneBotMessageEvent
    
    if not isinstance(onebot_event, OneBotMessageEvent):
        return None
    
    data = onebot_event.to_dict()
    json_str = json.dumps(data, ensure_ascii=False)
    
    from core.MessageEvent import MessageEvent
    return MessageEvent(json_str)

async def process_onebot_event(onebot_event):
    """处理 OneBot 事件（异步版本）"""
    message_event = convert_onebot_event_to_message_event(onebot_event)
    
    if message_event:
        # 记录接收到的消息到日志
        log_received_message(message_event)
        await asyncio.to_thread(process_message_event_internal, message_event)

def log_received_message(event):
    """记录接收到的消息"""
    try:
        msg_type = "群聊" if event.is_group else "私聊"
        sender = event.sender_card or event.sender_nickname or event.user_id
        location = f"群({event.group_id})" if event.is_group else f"私聊({event.user_id})"
        
        # 简单解析消息内容
        content_parts = []
        for segment in event.message:
            if not isinstance(segment, dict):
                continue
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
                content_parts.append(f'↩️')
            else:
                content_parts.append(f'[{seg_type}]')
        
        content = ''.join(content_parts) or event.content or "[空消息]"
        display_content = content[:100] + "..." if len(content) > 100 else content
        
        logger.info(f"📨 {msg_type} | {location} | {sender}: {display_content}")
    except:
        pass

def log_sent_message(message, is_group, chat_id):
    """记录机器人发送的消息"""
    try:
        msg_type = "群聊" if is_group else "私聊"
        location = f"群({chat_id})" if is_group else f"私聊({chat_id})"
        
        # 解析消息内容
        content_parts = []
        if isinstance(message, str):
            content_parts.append(message)
        elif isinstance(message, list):
            for segment in message:
                if not isinstance(segment, dict):
                    continue
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
                elif seg_type == 'face':
                    content_parts.append('[表情]')
                else:
                    content_parts.append(f'[{seg_type}]')
        
        content = ''.join(content_parts) or "[空消息]"
        display_content = content[:100] + "..." if len(content) > 100 else content
        
        logger.info(f"📤 {msg_type} | {location} | Bot: {display_content}")
    except:
        pass

def process_message_event_internal(event):
    """内部消息处理函数"""
    global _plugins_preloaded
    if not _plugins_preloaded:
        _message_handler_ready.wait(timeout=5)
    
    if event.ignore:
        return False
    
    # 异步记录数据库
    def async_db_tasks():
        try:
            if not event.skip_recording:
                event._record_user_and_group()
                event._record_message_to_db_only()
                import datetime
                event._notify_web_display(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            event.record_last_message_id()
        except:
            pass
    
    threading.Thread(target=async_db_tasks, daemon=True).start()
    
    # 调用插件处理
    try:
        from core.PluginManager import PluginManager
        PluginManager.dispatch_message(event)
    except Exception as e:
        logger.error(f"插件处理失败: {str(e)}")
    
    del event
    cleanup_gc()
    return False

def process_message_event(data, http_context=None):
    """处理消息事件（兼容旧接口）"""
    if not data:
        return False
    
    try:
        from core.MessageEvent import MessageEvent
        event = MessageEvent(data, http_context=http_context)
        return process_message_event_internal(event)
    except Exception as e:
        log_error(f"消息处理异常: {str(e)}")
        return False

def create_app():
    """创建 FastAPI 应用（使用 nonebot 相同的 ASGI 架构）"""
    global _onebot_adapter
    
    app = FastAPI(title="ElainaBot OneBot Service")
    
    # 初始化 OneBot Adapter（从配置读取 token）
    from core.onebot.adapter import init_adapter
    _onebot_adapter = init_adapter(
        access_token=ONEBOT_CONFIG.get('access_token'),
        secret=ONEBOT_CONFIG.get('secret')
    )
    
    if ONEBOT_CONFIG.get('access_token'):
        logger.info("🔐 OneBot 鉴权已启用 (access_token)")
    if ONEBOT_CONFIG.get('secret'):
        logger.info("🔐 OneBot 签名验证已启用 (secret)")
    
    @app.get("/")
    async def root():
        return {"message": "ElainaBot OneBot Service"}
    
    @app.post("/")
    async def root_post(request: Request):
        """根路径 HTTP POST 回调"""
        data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="No data received")
        
        asyncio.create_task(asyncio.to_thread(process_message_event, data.decode(), None))
        return "OK"
    
    # OneBot v11 HTTP POST 端点（使用 nonebot adapter 逻辑）
    @app.post("/onebot/v11/")
    @app.post("/onebot/v11/http")
    @app.post("/onebot/v11/http/")
    @app.post("/OneBotv11")
    async def onebot_http(
        request: Request,
        x_self_id: Optional[str] = Header(None),
        x_signature: Optional[str] = Header(None)
    ):
        """OneBot v11 HTTP 回调端点"""
        data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="No data received")
        
        # 使用 adapter 处理 HTTP 回调
        headers = dict(request.headers)
        success, event = _onebot_adapter.handle_http_callback(data, headers)
        
        if not success:
            raise HTTPException(status_code=400, detail="Bad Request")
        
        if event:
            asyncio.create_task(process_onebot_event(event))
        
        return JSONResponse(content={}, status_code=204)
    
    # OneBot v11 WebSocket 端点（完全使用 nonebot 逻辑）
    @app.websocket("/onebot/v11/")
    @app.websocket("/onebot/v11/ws")
    @app.websocket("/onebot/v11/ws/")
    @app.websocket("/OneBotv11")
    async def onebot_websocket(
        websocket: WebSocket,
        x_self_id: Optional[str] = Header(None),
        authorization: Optional[str] = Header(None)
    ):
        """OneBot v11 WebSocket 端点（使用标准 ASGI WebSocket，与 nonebot 一致）"""
        # 设置主事件循环引用（用于 run_async_api）
        from core.onebot.api import set_main_loop
        set_main_loop(asyncio.get_running_loop())
        
        # 获取请求头
        headers = dict(websocket.headers)
        client_address = websocket.client.host
        
        # 验证 WebSocket 连接头
        valid, self_id, error_msg = _onebot_adapter.validate_websocket_headers(headers)
        if not valid:
            await websocket.close(code=1008, reason=error_msg or "Bad Request")
            return
        
        # 接受 WebSocket 连接
        await websocket.accept()
        
        # 注册 Bot 连接
        _onebot_adapter.register_bot(self_id, websocket)
        logger.info(f"✅ OneBot 连接: {client_address} | Bot {self_id}")
        
        try:
            while True:
                message = await websocket.receive_text()
                json_data = json.loads(message)
                
                # 转换为事件
                event = _onebot_adapter.json_to_event(json_data)
                if event:
                    asyncio.create_task(process_onebot_event(event))
                else:
                    # API 响应
                    if "echo" in json_data:
                        echo = json_data["echo"]
                        if echo in _onebot_adapter.api_responses:
                            future = _onebot_adapter.api_responses.pop(echo)
                            if not future.done():
                                future.set_result(json_data)
                    
        except WebSocketDisconnect:
            logger.info(f"⚠️ 连接断开: Bot {self_id}")
        except Exception as e:
            logger.error(f"WebSocket 异常: {str(e)}")
        finally:
            _onebot_adapter.unregister_bot(self_id)
    
    # 最后挂载 Web 面板（Flask + Socket.IO）
    try:
        from flask import Flask
        from flask_socketio import SocketIO
        from fastapi.middleware.wsgi import WSGIMiddleware
        from flask_cors import CORS
        
        # 使用 web.app 的配置创建 Flask 应用
        import os
        web_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
        
        from web.app import web as web_blueprint, register_socketio_handlers
        from web.tools import log_handler
        
        # 创建 Flask 应用
        flask_app = Flask(
            __name__,
            static_folder=os.path.join(web_dir, 'static'),
            template_folder=os.path.join(web_dir, 'templates')
        )
        flask_app.config['SECRET_KEY'] = 'elainabot_secret'
        flask_app.config['TEMPLATES_AUTO_RELOAD'] = True
        flask_app.jinja_env.auto_reload = True
        flask_app.logger.disabled = True
        
        # 注册 Blueprint（不使用 url_prefix，因为挂载时会加上 /web）
        flask_app.register_blueprint(web_blueprint, url_prefix='')
        CORS(flask_app, resources={r"/*": {"origins": "*"}})
        
        # 初始化 Socket.IO
        socketio = SocketIO(
            flask_app, 
            cors_allowed_origins="*", 
            logger=False, 
            engineio_logger=False, 
            async_mode='threading',
            path='/socket.io'  # 相对路径，会自动加上 /web 前缀
        )
        flask_app.socketio = socketio
        
        # 设置 Socket.IO 和注册处理器
        log_handler.set_socketio(socketio)
        register_socketio_handlers(socketio)
        
        # 挂载 Flask 应用到 /web 路径
        app.mount("/web", WSGIMiddleware(flask_app))
    except Exception as e:
        logger.error(f"Web 面板挂载失败: {str(e)}")
    
    return app

def init_systems():
    """初始化系统"""
    global _message_handler_ready, _plugins_preloaded
    setup_logging()
    gc.enable()
    gc.set_threshold(700, 10, 5)
    gc.collect(0)
    
    def init_critical_systems():
        global _plugins_preloaded
        try:
            from core.PluginManager import PluginManager
            PluginManager.load_plugins()
            loaded_count = len(PluginManager._plugins)
            log_to_console(f"✅ 加载插件: {loaded_count} 个")
            _plugins_preloaded = True
            _message_handler_ready.set()
        except Exception as e:
            logger.error(f"插件加载失败: {str(e)}")
            _message_handler_ready.set()
    
    threading.Thread(target=init_critical_systems, daemon=True).start()
    return True

def signal_handler(signum, frame):
    log_to_console("⚠️ 收到退出信号，正在关闭...")
    sys.exit(0)

def start_main_process():
    """启动主进程"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 初始化系统
    init_systems()
    
    # 创建应用
    app = create_app()
    
    host = SERVER_CONFIG.get('host', '0.0.0.0')
    port = SERVER_CONFIG.get('port', 5004)
    
    logger.info(f"🚀 ElainaBot 启动 | 端口: {port}")
    logger.info(f"📡 OneBot WebSocket: ws://{host}:{port}/OneBotv11")
    logger.info(f"📡 OneBot HTTP POST: http://{host}:{port}/OneBotv11")
    logger.info(f"🌐 Web 管理面板: http://{host}:{port}/web/?token={WEB_SECURITY.get('access_token', 'your_token')}")
    
    # 使用 uvicorn 启动（与 nonebot 相同）
    import uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="error",  # 只显示错误日志
        access_log=False,  # 禁用访问日志
    )

if __name__ == "__main__":
    try:
        start_main_process()
    except KeyboardInterrupt:
        log_to_console("⚠️ 收到中断信号，正在退出...")
    finally:
        sys.exit(0)
