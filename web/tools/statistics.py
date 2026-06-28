"""统计数据 — 基于 message.db 聚合 (OneBot)"""

import asyncio
import time
from datetime import datetime, timedelta

from aiohttp import web

from web.tools import _common

_base_dir = ''
_CACHE_TTL = 10
_stats_cache: dict = {}
_chart_cache: dict = {}


def set_context(app_instance, base_dir=''):
    global _base_dir
    _common.set_app(app_instance)
    if base_dir:
        _base_dir = base_dir


def _q(sql, params=None):
    return _common.query_log('message', sql, params, bot_qq=_common.primary_appid())


def _ql(sql, params=None):
    return _common.query_log('lifecycle', sql, params, bot_qq=_common.primary_appid())


def _today():
    return datetime.now().strftime('%Y-%m-%d')


def _bots_count():
    return len(_common.connected_ids())


# ──────────── 聚合函数 ────────────

def _gather_summary(date):
    rows = _q(
        "SELECT COUNT(*) AS cnt, "
        "COUNT(CASE WHEN group_id='' THEN 1 END) AS private "
        "FROM log WHERE timestamp LIKE ?",
        (date + '%',),
    )
    total = rows[0].get('cnt', 0) if rows else 0
    priv = rows[0].get('private', 0) if rows else 0
    return {'total_messages': total, 'private_messages': priv, 'bots_count': _bots_count()}


def _gather_active(date):
    rows = _q(
        "SELECT COUNT(DISTINCT CASE WHEN user_id!='' THEN user_id END) AS users, "
        "COUNT(DISTINCT CASE WHEN group_id!='' THEN group_id END) AS groups_ "
        "FROM log WHERE timestamp LIKE ?",
        (date + '%',),
    )
    return {
        'active_users': rows[0].get('users', 0) if rows else 0,
        'active_groups': rows[0].get('groups_', 0) if rows else 0,
    }


def _gather_top(date):
    like = (date + '%',)
    groups = _q("SELECT group_id AS k, COUNT(*) AS c FROM log WHERE group_id!='' AND timestamp LIKE ? GROUP BY k ORDER BY c DESC LIMIT 10", like)
    users = _q("SELECT user_id AS k, COUNT(*) AS c FROM log WHERE user_id!='' AND timestamp LIKE ? GROUP BY k ORDER BY c DESC LIMIT 10", like)
    return {
        'top_groups': [{'group_id': r['k'], 'message_count': r['c']} for r in groups],
        'top_users': [{'user_id': r['k'], 'message_count': r['c']} for r in users],
        'top_commands': [],
    }


_LIFECYCLE_MAP = {
    'group_increase': 'group_join_count',
    'group_decrease': 'group_leave_count',
    'friend_add': 'friend_add_count',
    'friend_del': 'friend_remove_count',
}


def _gather_events(date):
    ev = {'group_join_count': 0, 'group_leave_count': 0, 'friend_add_count': 0, 'friend_remove_count': 0}
    rows = _ql("SELECT message_type AS t, COUNT(*) AS c FROM log WHERE timestamp LIKE ? GROUP BY t", (date + '%',))
    for r in rows:
        key = _LIFECYCLE_MAP.get(r.get('t', ''))
        if key:
            ev[key] += r.get('c', 0)
    return ev


def _gather_totals():
    rows = _q(
        "SELECT COUNT(DISTINCT CASE WHEN user_id!='' THEN user_id END) AS users, "
        "COUNT(DISTINCT CASE WHEN group_id!='' THEN group_id END) AS groups_ FROM log",
    )
    return {
        'total_users': rows[0].get('users', 0) if rows else 0,
        'total_groups': rows[0].get('groups_', 0) if rows else 0,
    }


def _hourly(date):
    rows = _q("SELECT substr(timestamp,12,2) AS hr, COUNT(*) AS c FROM log WHERE timestamp LIKE ? GROUP BY hr", (date + '%',))
    h = {}
    for r in rows:
        hr = r.get('hr', '')
        if hr:
            h[hr] = h.get(hr, 0) + r.get('c', 0)
    return h


def _hourly_list(h):
    return [h.get(f'{i:02d}', 0) for i in range(24)]


# ──────────── Handlers ────────────

async def _run(fn, *args):
    return await asyncio.get_running_loop().run_in_executor(None, fn, *args)


async def handle_get_statistics(request: web.Request):
    force = request.query.get('force_refresh', 'false') == 'true'
    date = request.query.get('date', '') or _today()
    key = date
    now = time.time()
    if not force:
        c = _stats_cache.get(key)
        if c and now - c[0] < _CACHE_TTL:
            return web.json_response({'success': True, 'data': c[1]})
    try:
        data = await _run(_gather_all, date, bool(request.query.get('date', '')))
        _stats_cache[key] = (now, data)
        return web.json_response({'success': True, 'data': data})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


def _gather_all(date, has_selected):
    summary = _gather_summary(date)
    active = _gather_active(date)
    top = _gather_top(date)
    events = _gather_events(date)
    totals = _gather_totals()
    hourly = _hourly(date)
    peak_h = max(hourly, key=hourly.get) if hourly else '00'
    yesterday_dist = None
    if not has_selected:
        yh = _hourly((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'))
        yesterday_dist = _hourly_list(yh)
    return {
        'today': {
            'message_stats': {
                'total_messages': summary['total_messages'],
                'private_messages': summary['private_messages'],
                'active_users': active['active_users'],
                'active_groups': active['active_groups'],
                'peak_hour': int(peak_h) if peak_h.isdigit() else 0,
                'peak_hour_count': hourly.get(peak_h, 0),
            },
            'hourly_distribution': _hourly_list(hourly),
            'yesterday_hourly_distribution': yesterday_dist,
            'top_groups': top['top_groups'],
            'top_users': top['top_users'],
            'top_commands': top['top_commands'],
            'event_stats': events,
            'total_users': totals['total_users'],
            'total_groups': totals['total_groups'],
        },
        'bots_count': summary['bots_count'],
        'cache_date': date,
    }


async def handle_get_summary(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _run(_gather_summary, date)})


async def handle_get_active(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _run(_gather_active, date)})


async def handle_get_top(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _run(_gather_top, date)})


async def handle_get_events(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _run(_gather_events, date)})


async def handle_get_totals(request: web.Request):
    return web.json_response({'success': True, 'data': await _run(_gather_totals)})


async def handle_get_available_dates(request: web.Request):
    return web.json_response({
        'success': True,
        'dates': [{'value': 'today', 'date': _today(), 'display': '今日数据', 'is_today': True}],
    })


async def handle_get_hourly_statistics(request: web.Request):
    key = 'hourly'
    now = time.time()
    c = _chart_cache.get(key)
    if c and now - c[0] < _CACHE_TTL:
        return web.json_response(c[1])
    payload = await _run(_hourly_payload)
    _chart_cache[key] = (now, payload)
    return web.json_response(payload)


def _hourly_payload():
    today = _today()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    return {
        'success': True,
        'data': {
            'today_hourly_distribution': _hourly_list(_hourly(today)),
            'yesterday_hourly_distribution': _hourly_list(_hourly(yesterday)),
        },
    }


async def handle_get_chart_data(request: web.Request):
    days = max(1, min(30, int(request.query.get('days', '7'))))
    key = f'chart{days}'
    now = time.time()
    c = _chart_cache.get(key)
    if c and now - c[0] < _CACHE_TTL:
        return web.json_response(c[1])
    payload = await _run(_chart_payload, days)
    _chart_cache[key] = (now, payload)
    return web.json_response(payload)


def _chart_payload(days):
    labels, msg_total, msg_private, msg_group = [], [], [], []
    active_users, active_groups = [], []
    ev_join, ev_leave, ev_fadd, ev_frem = [], [], [], []
    today = datetime.now().date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime('%Y-%m-%d')
        labels.append(d.strftime('%m-%d'))
        s = _gather_summary(ds)
        a = _gather_active(ds)
        e = _gather_events(ds)
        msg_total.append(s['total_messages'])
        msg_private.append(s['private_messages'])
        msg_group.append(s['total_messages'] - s['private_messages'])
        active_users.append(a['active_users'])
        active_groups.append(a['active_groups'])
        ev_join.append(e['group_join_count'])
        ev_leave.append(e['group_leave_count'])
        ev_fadd.append(e['friend_add_count'])
        ev_frem.append(e['friend_remove_count'])
    totals = _gather_totals()
    return {
        'success': True,
        'data': {
            'labels': labels,
            'msg_total': msg_total,
            'msg_private': msg_private,
            'msg_group': msg_group,
            'active_users': active_users,
            'active_groups': active_groups,
            'total_users': totals['total_users'],
            'total_groups': totals['total_groups'],
            'total_friends': 0,
            'ev_group_join': ev_join,
            'ev_group_leave': ev_leave,
            'ev_friend_add': ev_fadd,
            'ev_friend_remove': ev_frem,
        },
    }
