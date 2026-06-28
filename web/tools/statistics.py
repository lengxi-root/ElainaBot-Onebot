"""统计数据"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiohttp import web

log = logging.getLogger('ElainaBot.web.stats')

_bot_manager = None
_base_dir = ''


def set_context(bot_manager, base_dir: str):
    global _bot_manager, _base_dir
    _bot_manager = bot_manager
    _base_dir = base_dir


def _ls():
    if _bot_manager and _bot_manager.log_service:
        return _bot_manager.log_service
    return None


async def handle_statistics(request: web.Request):
    ls = _ls()
    if not ls:
        return web.json_response({
            'success': True,
            'today_messages': 0,
            'total_messages': 0,
            'active_users': 0,
            'active_groups': 0,
            'hourly': [0] * 24,
            'daily': [],
        })

    try:
        today = datetime.now().strftime('%Y-%m-%d')

        total_row = ls.query('message', 'SELECT COUNT(*) as cnt FROM log')
        total_messages = total_row[0]['cnt'] if total_row else 0

        today_row = ls.query('message', f"SELECT COUNT(*) as cnt FROM log WHERE timestamp LIKE '{today}%'")
        today_messages = today_row[0]['cnt'] if today_row else 0

        users_row = ls.query('message', f"SELECT COUNT(DISTINCT user_id) as cnt FROM log WHERE timestamp LIKE '{today}%'")
        active_users = users_row[0]['cnt'] if users_row else 0

        groups_row = ls.query('message', f"SELECT COUNT(DISTINCT group_id) as cnt FROM log WHERE group_id != '' AND timestamp LIKE '{today}%'")
        active_groups = groups_row[0]['cnt'] if groups_row else 0

        hourly = [0] * 24
        hourly_rows = ls.query(
            'message',
            f"SELECT SUBSTR(timestamp, 12, 2) as hour, COUNT(*) as cnt FROM log WHERE timestamp LIKE '{today}%' GROUP BY hour"
        )
        for r in (hourly_rows or []):
            try:
                h = int(r['hour'])
                if 0 <= h < 24:
                    hourly[h] = r['cnt']
            except (ValueError, KeyError):
                pass

        daily = []
        for i in range(7):
            dt = (datetime.now() - timedelta(days=6 - i)).strftime('%Y-%m-%d')
            day_row = ls.query('message', f"SELECT COUNT(*) as cnt FROM log WHERE timestamp LIKE '{dt}%'")
            daily.append({
                'date': dt,
                'count': day_row[0]['cnt'] if day_row else 0,
            })

        return web.json_response({
            'success': True,
            'today_messages': today_messages,
            'total_messages': total_messages,
            'active_users': active_users,
            'active_groups': active_groups,
            'hourly': hourly,
            'daily': daily,
        })
    except Exception as e:
        log.error(f'stats error: {e}')
        return web.json_response({
            'success': True,
            'today_messages': 0,
            'total_messages': 0,
            'active_users': 0,
            'active_groups': 0,
            'hourly': [0] * 24,
            'daily': [],
        })
