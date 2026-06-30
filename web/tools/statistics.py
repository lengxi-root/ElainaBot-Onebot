"""统计数据 — 基于 message.db 聚合 (异步架构)"""

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


def _resolve_bot(request: web.Request) -> str:
    """取前端选中的 bot_qq, 缺省回退到首个已连接机器人

    统计数据按 QQ 分库存储, 必须用用户在面板选中的机器人来查询, 否则多机器人
    或选中非首个连接时会查到空库, 导致活跃用户/群聊等全部显示 0。
    """
    return request.query.get('bot_qq', '') or _common.primary_bot_qq()


async def _q(sql, params=None, bot=None):
    return await _common.query_log('message', sql, params, bot_qq=bot if bot is not None else _common.primary_bot_qq())


async def _ql(sql, params=None, bot=None):
    return await _common.query_log('lifecycle', sql, params, bot_qq=bot if bot is not None else _common.primary_bot_qq())


def _today():
    return datetime.now().strftime('%Y-%m-%d')


def _bots_count():
    return len(_common.connected_ids())


# ──────────── 聚合函数 ────────────

async def _gather_summary(date, bot=None):
    rows = await _q(
        "SELECT COUNT(*) AS cnt, "
        "COUNT(CASE WHEN group_id='' THEN 1 END) AS private "
        "FROM log WHERE timestamp LIKE ?",
        (date + '%',),
        bot,
    )
    total = rows[0].get('cnt', 0) if rows else 0
    priv = rows[0].get('private', 0) if rows else 0
    return {'total_messages': total, 'private_messages': priv, 'bots_count': _bots_count()}


async def _gather_active(date, bot=None):
    rows = await _q(
        "SELECT COUNT(DISTINCT CASE WHEN user_id!='' THEN user_id END) AS users, "
        "COUNT(DISTINCT CASE WHEN group_id!='' THEN group_id END) AS groups_ "
        "FROM log WHERE timestamp LIKE ?",
        (date + '%',),
        bot,
    )
    return {
        'active_users': rows[0].get('users', 0) if rows else 0,
        'active_groups': rows[0].get('groups_', 0) if rows else 0,
    }


async def _gather_top(date, bot=None):
    like = (date + '%',)
    groups = await _q("SELECT group_id AS k, COUNT(*) AS c FROM log WHERE group_id!='' AND timestamp LIKE ? GROUP BY k ORDER BY c DESC LIMIT 10", like, bot)
    users = await _q("SELECT user_id AS k, COUNT(*) AS c FROM log WHERE user_id!='' AND timestamp LIKE ? GROUP BY k ORDER BY c DESC LIMIT 10", like, bot)
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


async def _gather_events(date, bot=None):
    ev = {'group_join_count': 0, 'group_leave_count': 0, 'friend_add_count': 0, 'friend_remove_count': 0}
    rows = await _ql("SELECT message_type AS t, COUNT(*) AS c FROM log WHERE timestamp LIKE ? GROUP BY t", (date + '%',), bot)
    for r in rows:
        key = _LIFECYCLE_MAP.get(r.get('t', ''))
        if key:
            ev[key] += r.get('c', 0)
    return ev


async def _gather_totals(bot=None):
    rows = await _q(
        "SELECT COUNT(DISTINCT CASE WHEN user_id!='' THEN user_id END) AS users, "
        "COUNT(DISTINCT CASE WHEN group_id!='' THEN group_id END) AS groups_ FROM log",
        None,
        bot,
    )
    return {
        'total_users': rows[0].get('users', 0) if rows else 0,
        'total_groups': rows[0].get('groups_', 0) if rows else 0,
    }


_friend_cache: dict = {}
_FRIEND_TTL = 60


async def _friend_count(bot=None) -> int:
    """通过 OneBot get_friend_list 获取好友总数 (带短缓存, 失败返回 0)"""
    self_id = bot if bot is not None else _common.primary_bot_qq()
    if not self_id:
        return 0
    now = time.time()
    c = _friend_cache.get(self_id)
    if c and now - c[0] < _FRIEND_TTL:
        return c[1]
    count = 0
    try:
        from core.onebot.api import OneBotAPI

        resp = await OneBotAPI(_common.adapter()).call_api('get_friend_list', self_id=str(self_id))
        if resp and resp.get('retcode') == 0:
            count = len(resp.get('data') or [])
    except Exception:
        count = 0
    _friend_cache[self_id] = (now, count)
    return count


async def _hourly(date, bot=None):
    rows = await _q("SELECT substr(timestamp,12,2) AS hr, COUNT(*) AS c FROM log WHERE timestamp LIKE ? GROUP BY hr", (date + '%',), bot)
    h = {}
    for r in rows:
        hr = r.get('hr', '')
        if hr:
            h[hr] = h.get(hr, 0) + r.get('c', 0)
    return h


def _hourly_list(h):
    return [h.get(f'{i:02d}', 0) for i in range(24)]


# ──────────── Handlers ────────────

async def handle_get_statistics(request: web.Request):
    force = request.query.get('force_refresh', 'false') == 'true'
    date = request.query.get('date', '') or _today()
    bot = _resolve_bot(request)
    key = (date, bot)
    now = time.time()
    if not force:
        c = _stats_cache.get(key)
        if c and now - c[0] < _CACHE_TTL:
            return web.json_response({'success': True, 'data': c[1]})
    try:
        has_selected = bool(request.query.get('date', ''))
        data = await _gather_all(date, has_selected, bot)
        _stats_cache[key] = (now, data)
        return web.json_response({'success': True, 'data': data})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def _gather_all(date, has_selected, bot=None):
    summary = await _gather_summary(date, bot)
    active = await _gather_active(date, bot)
    top = await _gather_top(date, bot)
    events = await _gather_events(date, bot)
    totals = await _gather_totals(bot)
    hourly = await _hourly(date, bot)
    peak_h = max(hourly, key=hourly.get) if hourly else '00'
    yesterday_dist = None
    if not has_selected:
        yh = await _hourly((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), bot)
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
    return web.json_response({'success': True, 'data': await _gather_summary(date, _resolve_bot(request))})


async def handle_get_active(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _gather_active(date, _resolve_bot(request))})


async def handle_get_top(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _gather_top(date, _resolve_bot(request))})


async def handle_get_events(request: web.Request):
    date = request.query.get('date', '') or _today()
    return web.json_response({'success': True, 'data': await _gather_events(date, _resolve_bot(request))})


async def handle_get_totals(request: web.Request):
    return web.json_response({'success': True, 'data': await _gather_totals(_resolve_bot(request))})


async def handle_get_available_dates(request: web.Request):
    return web.json_response({
        'success': True,
        'dates': [{'value': 'today', 'date': _today(), 'display': '今日数据', 'is_today': True}],
    })


async def handle_get_hourly_statistics(request: web.Request):
    bot = _resolve_bot(request)
    key = ('hourly', bot)
    now = time.time()
    c = _chart_cache.get(key)
    if c and now - c[0] < _CACHE_TTL:
        return web.json_response(c[1])
    payload = await _hourly_payload(bot)
    _chart_cache[key] = (now, payload)
    return web.json_response(payload)


async def _hourly_payload(bot=None):
    today = _today()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    return {
        'success': True,
        'data': {
            'today_hourly_distribution': _hourly_list(await _hourly(today, bot)),
            'yesterday_hourly_distribution': _hourly_list(await _hourly(yesterday, bot)),
        },
    }


async def handle_get_chart_data(request: web.Request):
    days = max(1, min(30, int(request.query.get('days', '7'))))
    bot = _resolve_bot(request)
    key = (f'chart{days}', bot)
    now = time.time()
    c = _chart_cache.get(key)
    if c and now - c[0] < _CACHE_TTL:
        return web.json_response(c[1])
    payload = await _chart_payload(days, bot)
    _chart_cache[key] = (now, payload)
    return web.json_response(payload)


async def _chart_payload(days, bot=None):
    labels, msg_total, msg_private, msg_group = [], [], [], []
    active_users, active_groups = [], []
    ev_join, ev_leave, ev_fadd, ev_frem = [], [], [], []
    today = datetime.now().date()
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        ds = d.strftime('%Y-%m-%d')
        labels.append(d.strftime('%m-%d'))
        s = await _gather_summary(ds, bot)
        a = await _gather_active(ds, bot)
        e = await _gather_events(ds, bot)
        msg_total.append(s['total_messages'])
        msg_private.append(s['private_messages'])
        msg_group.append(s['total_messages'] - s['private_messages'])
        active_users.append(a['active_users'])
        active_groups.append(a['active_groups'])
        ev_join.append(e['group_join_count'])
        ev_leave.append(e['group_leave_count'])
        ev_fadd.append(e['friend_add_count'])
        ev_frem.append(e['friend_remove_count'])
    totals = await _gather_totals(bot)
    total_friends = await _friend_count(bot)
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
            'total_friends': total_friends,
            'ev_group_join': ev_join,
            'ev_group_leave': ev_leave,
            'ev_friend_add': ev_fadd,
            'ev_friend_remove': ev_frem,
        },
    }
