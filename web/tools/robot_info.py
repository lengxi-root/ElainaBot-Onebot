import requests
from flask import request, jsonify

get_websocket_status = None

def set_config(ws_status_func):
    """设置 WebSocket 状态获取函数"""
    global get_websocket_status
    get_websocket_status = ws_status_func

def handle_get_robot_info():
    """从 OneBot API 获取机器人信息"""
    try:
        from core.onebot.api import get_onebot_api, run_async_api
        api = get_onebot_api()
        
        # 获取登录信息
        result = run_async_api(api.get_login_info())
        
        if result and result.get('retcode') == 0:
            data = result.get('data', {})
            robot_qq = str(data.get('user_id', ''))
            nickname = data.get('nickname', 'OneBot 机器人')
        else:
            robot_qq = ''
            nickname = 'OneBot 机器人'
        
        connection_status = get_websocket_status() if get_websocket_status else '未知'
        avatar_url = f"http://q1.qlogo.cn/g?b=qq&nk={robot_qq}&s=100" if robot_qq else ''
        
        return jsonify({
            'success': True,
            'qq': robot_qq,
            'name': nickname,
            'description': '基于 OneBot v11 协议的机器人',
            'avatar': avatar_url,
            'developer': 'Elaina Framework',
            'link': '',
            'status': connection_status,
            'connection_type': 'OneBot WebSocket',
            'connection_status': connection_status,
            'data_source': 'onebot',
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'qq': '',
            'name': 'OneBot 机器人',
            'description': '基于 OneBot v11 协议的机器人',
            'avatar': '',
            'developer': 'Elaina Framework',
            'link': '',
            'status': '未知',
            'connection_type': 'OneBot WebSocket',
            'connection_status': '未知',
            'data_source': 'fallback',
        })

def handle_get_robot_qrcode():
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': '缺少URL参数'
        }), 400
    
    try:
        response = requests.get(
            f"https://api.2dcode.biz/v1/create-qr-code?data={url}",
            timeout=10
        )
        response.raise_for_status()
        
        return response.content, 200, {
            'Content-Type': 'image/png',
            'Cache-Control': 'public, max-age=3600'
        }
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

