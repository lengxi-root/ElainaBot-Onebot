#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from flask import request, jsonify

received_messages = None
plugin_logs = None
framework_logs = None
error_logs = None

def set_log_queues(received, plugin, framework, error):
    global received_messages, plugin_logs, framework_logs, error_logs
    received_messages = received
    plugin_logs = plugin
    framework_logs = framework
    error_logs = error

def set_config(log_db_config, error_log_func):
    pass  # SQLite不需要额外配置

def handle_get_logs(log_type):
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('size', 50, type=int)
    
    logs_map = {
        'received': received_messages,
        'plugin': plugin_logs,
        'framework': framework_logs,
        'error': error_logs
    }
    
    if log_type not in logs_map:
        return jsonify({'error': '无效的日志类型'}), 400
    
    logs = list(logs_map[log_type])
    logs.reverse()
    
    start = (page - 1) * page_size
    page_logs = logs[start:start + page_size]
    
    return jsonify({
        'logs': page_logs,
        'total': len(logs),
        'page': page,
        'page_size': page_size,
        'total_pages': (len(logs) + page_size - 1) // page_size
    })

def get_today_logs_from_db(log_type, limit=100):
    try:
        from function.log_db import get_log_from_db
        
        # 从 SQLite 获取日志
        results = get_log_from_db(log_type, limit=limit)
        
        if not results:
            return []
        
        if not isinstance(results, list):
            results = [results]
        
        # 转换格式
        logs = []
        for row in results:
            log_entry = {
                'timestamp': row.get('timestamp', ''),
                'content': row.get('content', '')
            }
            
            if log_type == 'received':
                log_entry.update({
                    'user_id': row.get('user_id', ''),
                    'group_id': row.get('group_id', ''),
                    'message_type': row.get('message_type', ''),
                    'message_id': row.get('message_id', '')
                })
            elif log_type == 'plugin':
                log_entry.update({
                    'user_id': row.get('user_id', ''),
                    'group_id': row.get('group_id', ''),
                    'plugin_name': row.get('plugin_name', '')
                })
            elif log_type == 'error':
                log_entry.update({
                    'traceback': row.get('traceback', '')
                })
            
            logs.append(log_entry)
        
        return logs
    except Exception as e:
        print(f"获取数据库日志失败: {e}")
        return []

def get_today_message_logs_from_db(limit=100):
    return get_today_logs_from_db('received', limit)

def handle_get_today_logs():
    try:
        limit = request.args.get('limit', type=int, default=50)
        
        result = {}
        log_types = ['received', 'plugin', 'framework', 'error']
        
        for log_type in log_types:
            # 从数据库获取今日日志
            db_logs = get_today_logs_from_db(log_type, limit)
            result[log_type] = db_logs
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        import traceback
        return jsonify({
            'success': False,
            'message': f'获取日志失败: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

def handle_combined_logs():
    try:
        limit = request.args.get('limit', type=int, default=100)
        
        result = {}
        log_types = ['received', 'plugin', 'framework', 'error']
        
        for log_type in log_types:
            # 从内存获取
            logs_map = {
                'received': received_messages,
                'plugin': plugin_logs,
                'framework': framework_logs,
                'error': error_logs
            }
            
            if log_type in logs_map and logs_map[log_type]:
                memory_logs = list(logs_map[log_type])[-limit:]
            else:
                memory_logs = []
            
            # 从数据库获取
            db_logs = get_today_logs_from_db(log_type, limit)
            
            # 合并并去重
            combined = []
            seen = set()
            
            for log in memory_logs + db_logs:
                log_key = f"{log.get('timestamp', '')}_{log.get('content', '')[:50]}"
                if log_key not in seen:
                    seen.add(log_key)
                    combined.append(log)
            
            # 按时间戳排序
            combined.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            result[log_type] = combined[:limit]
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取日志失败: {str(e)}'
        }), 500
