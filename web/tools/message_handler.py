#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from datetime import datetime
from flask import request, jsonify

def get_chat_avatar(chat_id, chat_type):
    if chat_type == 'user':
        return f"http://q1.qlogo.cn/g?b=qq&nk={chat_id}&s=100"
    else:
        return f"https://p.qlogo.cn/gh/{chat_id}/{chat_id}/640/"

def handle_get_chats():
    try:
        data = request.get_json()
        chat_type = data.get('type', 'user')
        search = data.get('search', '').strip()
        
        from core.onebot.api import get_onebot_api, run_async_api
        api = get_onebot_api()
        
        import logging
        logger = logging.getLogger('ElainaBot.web.message_handler')
        
        if chat_type == 'group':
            # 获取群列表 (API 已经解析过，直接返回列表)
            groups = run_async_api(api.get_group_list())
            logger.info(f"获取群列表返回: {type(groups)}, 长度: {len(groups) if isinstance(groups, list) else 'N/A'}")
            if groups and isinstance(groups, list) and len(groups) > 0:
                logger.info(f"第一个群数据示例: {groups[0]}")
            
            if not groups or not isinstance(groups, list):
                groups = []
            
            chat_list = []
            
            for group in groups:
                if not isinstance(group, dict):
                    continue
                group_id = str(group.get('group_id', ''))
                group_name = group.get('group_name', f'群{group_id}')
                
                # 搜索过滤
                if search and search not in group_id and search not in group_name:
                    continue
                
                chat_list.append({
                    'chat_id': group_id,
                    'nickname': group_name,
                    'avatar': get_chat_avatar(group_id, 'group'),
                    'last_time': ''
                })
        else:
            # 获取好友列表 (API 已经解析过，直接返回列表)
            friends = run_async_api(api.get_friend_list())
            logger.info(f"获取好友列表返回: {type(friends)}, 长度: {len(friends) if isinstance(friends, list) else 'N/A'}")
            if friends and isinstance(friends, list) and len(friends) > 0:
                logger.info(f"第一个好友数据示例: {friends[0]}")
            
            if not friends or not isinstance(friends, list):
                friends = []
            
            chat_list = []
            
            for friend in friends:
                if not isinstance(friend, dict):
                    continue
                user_id = str(friend.get('user_id', ''))
                nickname = friend.get('nickname', f'用户{user_id}')
                remark = friend.get('remark', '')
                display_name = remark if remark else nickname
                
                # 搜索过滤
                if search and search not in user_id and search not in display_name:
                    continue
                
                chat_list.append({
                    'chat_id': user_id,
                    'nickname': display_name,
                    'avatar': get_chat_avatar(user_id, 'user'),
                    'last_time': ''
                })
        
        return jsonify({'success': True, 'data': {'chats': chat_list}})
        
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': f'获取列表失败: {str(e)}', 'traceback': traceback.format_exc()})

def handle_get_chat_history():
    try:
        data = request.get_json()
        chat_type = data.get('chat_type')
        chat_id = data.get('chat_id')
        
        if not chat_type or not chat_id:
            return jsonify({'success': False, 'message': '缺少必要参数'})
        
        from function.log_db import get_log_from_db
        
        # 从 SQLite 获取消息记录
        if chat_type == 'group':
            messages = get_log_from_db('received', group_id=chat_id, limit=100)
        else:
            messages = get_log_from_db('received', user_id=chat_id, limit=100)
        
        if not messages:
            messages = []
        elif not isinstance(messages, list):
            messages = [messages]
        
        message_list = []
        for msg in messages:
            user_id = msg.get('user_id', '')
            group_id = msg.get('group_id', '')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', '')
            
            # 判断是否是机器人发送的消息
            is_self = user_id == 'BOT' or (chat_type == 'user' and group_id == 'c2c')
            display_user_id = '机器人' if is_self else user_id
            
            # 时间格式化
            try:
                if isinstance(timestamp, str):
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%H:%M:%S')
                else:
                    time_str = timestamp.strftime('%H:%M:%S') if timestamp else ''
            except:
                time_str = str(timestamp)[-8:] if timestamp else ''
            
            message_list.append({
                'user_id': display_user_id,
                'content': content,
                'timestamp': time_str,
                'avatar': get_chat_avatar('robot' if is_self else user_id, 'user'),
                'is_self': is_self
            })
        
        return jsonify({
            'success': True,
            'data': {
                'messages': message_list,
                'chat_info': {
                    'chat_id': chat_id,
                    'chat_type': chat_type,
                    'avatar': get_chat_avatar(chat_id, chat_type)
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取聊天记录失败: {str(e)}'})

def handle_send_message():
    try:
        data = request.get_json()
        chat_type = data.get('chat_type')
        chat_id = data.get('chat_id')
        send_method = data.get('send_method', 'text')
        
        if not chat_type or not chat_id:
            return jsonify({'success': False, 'message': '缺少必要参数'})
        
        from core.onebot.api import get_onebot_api, run_async_api
        from core.MessageEvent import Message, MessageSegment
        api = get_onebot_api()
        
        # 根据发送类型构建消息
        if send_method == 'text':
            content = data.get('content', '').strip()
            if not content:
                return jsonify({'success': False, 'message': '消息内容不能为空'})
            message = content
        elif send_method == 'image':
            image_url = data.get('image_url', '').strip()
            image_text = data.get('image_text', '').strip()
            if not image_url:
                return jsonify({'success': False, 'message': '图片URL不能为空'})
            segments = []
            if image_text:
                segments.append(MessageSegment.text(image_text + '\n'))
            segments.append(MessageSegment.image(image_url))
            message = Message(segments).to_onebot_array()
        elif send_method == 'voice':
            voice_url = data.get('voice_url', '').strip()
            if not voice_url:
                return jsonify({'success': False, 'message': '语音URL不能为空'})
            message = Message([MessageSegment.record(voice_url)]).to_onebot_array()
        elif send_method == 'video':
            video_url = data.get('video_url', '').strip()
            if not video_url:
                return jsonify({'success': False, 'message': '视频URL不能为空'})
            message = Message([MessageSegment.video(video_url)]).to_onebot_array()
        else:
            return jsonify({'success': False, 'message': f'不支持的发送类型: {send_method}'})
        
        # 发送消息
        if chat_type == 'group':
            result = run_async_api(api.send_group_msg(chat_id, message))
        else:
            result = run_async_api(api.send_private_msg(chat_id, message))
        
        if not result or result.get('retcode') != 0:
            error_msg = result.get('message', '发送失败') if result else '发送失败'
            return jsonify({'success': False, 'message': error_msg})
        
        # 立即写入数据库（不使用批量队列）
        try:
            import sqlite3
            from pathlib import Path
            
            # 构建日志内容
            if send_method == 'text':
                log_content = data.get('content', '')
            elif send_method == 'image':
                log_content = f"[图片] {data.get('image_text', '')}"
            elif send_method == 'voice':
                log_content = "[语音消息]"
            elif send_method == 'video':
                log_content = "[视频消息]"
            else:
                log_content = f"[{send_method}]"
            
            # 构建日志数据
            log_data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': 'BOT' if chat_type == 'group' else chat_id,
                'group_id': chat_id if chat_type == 'group' else 'c2c',
                'content': log_content.strip(),
                'message_type': chat_type,
                'message_id': result.get('data', {}).get('message_id', ''),
                'raw_message': ''
            }
            
            # 确定数据库路径
            log_dir = Path('data/log')
            log_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime('%Y%m%d')
            db_path = log_dir / f"log_received_{date_str}.db"
            
            # 立即写入数据库
            conn = sqlite3.connect(str(db_path), timeout=10)
            try:
                cursor = conn.cursor()
                
                # 确保表存在
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS log_received (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        user_id TEXT,
                        group_id TEXT,
                        content TEXT NOT NULL,
                        message_type TEXT,
                        message_id TEXT,
                        raw_message TEXT
                    )
                ''')
                
                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_received_time ON log_received (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_received_user ON log_received (user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_received_group ON log_received (group_id)')
                
                # 插入数据
                cursor.execute('''
                    INSERT INTO log_received (timestamp, user_id, group_id, content, message_type, message_id, raw_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    log_data['timestamp'],
                    log_data['user_id'],
                    log_data['group_id'],
                    log_data['content'],
                    log_data.get('message_type', ''),
                    log_data.get('message_id', ''),
                    log_data.get('raw_message', '')
                ))
                
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            # 如果立即写入失败，记录错误但不影响返回结果
            import logging
            logging.getLogger('ElainaBot').error(f"立即写入消息到数据库失败: {e}")
            pass
        
        return jsonify({
            'success': True,
            'message': '消息发送成功',
            'data': {
                'message_id': result.get('data', {}).get('message_id'),
                'content': content,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'发送消息失败: {str(e)}'})

def handle_get_nickname():
    try:
        user_id = request.get_json().get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '缺少用户ID'})
        
        from core.onebot.api import get_onebot_api, run_async_api
        api = get_onebot_api()
        
        result = run_async_api(api.get_stranger_info(user_id))
        if result and result.get('retcode') == 0:
            data = result.get('data', {})
            nickname = data.get('nickname', f'用户{user_id}')
        else:
            nickname = f'用户{user_id}'
        
        return jsonify({'success': True, 'data': {'user_id': user_id, 'nickname': nickname}})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取昵称失败: {str(e)}'})

def handle_get_nicknames_batch():
    try:
        data = request.get_json()
        user_ids = data.get('user_ids', [])
        
        if not user_ids or not isinstance(user_ids, list):
            return jsonify({'success': False, 'message': '缺少用户ID列表'})
        
        from core.onebot.api import get_onebot_api, run_async_api
        api = get_onebot_api()
        
        nicknames = {}
        for user_id in user_ids:
            try:
                result = run_async_api(api.get_stranger_info(user_id))
                if result and result.get('retcode') == 0:
                    data = result.get('data', {})
                    nicknames[user_id] = data.get('nickname', f'用户{user_id}')
                else:
                    nicknames[user_id] = f'用户{user_id}'
            except:
                nicknames[user_id] = f'用户{user_id}'
        
        return jsonify({'success': True, 'data': {'nicknames': nicknames}})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'批量获取昵称失败: {str(e)}'})

def handle_get_group_info():
    """获取群信息 - 实时从 OneBot API 获取"""
    try:
        data = request.get_json()
        group_id = data.get('group_id')
        
        if not group_id:
            return jsonify({'success': False, 'message': '缺少群ID'})
        
        from core.onebot.api import get_onebot_api, run_async_api
        api = get_onebot_api()
        
        result = run_async_api(api.get_group_info(group_id, no_cache=False))
        
        if result and result.get('retcode') == 0:
            group_data = result.get('data', {})
            group_name = group_data.get('group_name', f'群{group_id}')
            return jsonify({
                'success': True, 
                'data': {
                    'group_id': group_id,
                    'group_name': group_name,
                    'member_count': group_data.get('member_count', 0),
                    'max_member_count': group_data.get('max_member_count', 0)
                }
            })
        else:
            return jsonify({'success': False, 'message': '获取群信息失败'})
        
    except Exception as e:
        import traceback
        return jsonify({'success': False, 'message': f'获取群信息失败: {str(e)}', 'traceback': traceback.format_exc()})
