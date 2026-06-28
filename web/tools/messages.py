"""消息管理 — 聊天列表 / 历史 / 发送 / 撤回 (OneBot 适配)"""

import asyncio
import contextlib
import json
import os
import time
from datetime import datetime

from aiohttp import web

from web.tools import _common

_base_dir = ''
_chat_cache: dict = {}
_CHAT_TTL = 30


def set_context(app_instance, base_dir=''):
    global _base_dir
    _common.set_app(app_instance)
    if base_dir:
        _base_dir = base_dir


def _api():
    from core.onebot.api import get_api

    return get_api()


def _primary_id():
    ids = _common.connected_ids()
    return ids[0] if ids else ''


def _q(sql, params=None):
    return _common.query_log('message', sql, params)


# ──────────── 昵称 ────────────

async def handle_get_nickname(request: web.Request):
    body = await request.json()
    uid = str(body.get('user_id', ''))
    if not uid:
        return web.json_response({'success': False, 'message': '缺少用户ID'}, status=400)
    nick = await _common.get_nickname(uid)
    return web.json_response({'success': True, 'data': {'user_id': uid, 'nickname': nick}})


async def handle_get_nicknames_batch(request: web.Request):
    body = await request.json()
    uids = body.get('user_ids', [])
    if not isinstance(uids, list) or not uids:
        return web.json_response({'success': False, 'message': '缺少用户ID列表'}, status=400)
    result = await _common.batch_nicknames(uids)
    return web.json_response({'success': True, 'data': {'nicknames': result}})


# ──────────── 聊天列表 ────────────

def _db_stats(chat_type):
    """从消息日志聚合每个会话的最近时间与消息数, 返回 {chat_id: {...}}"""
    if chat_type == 'user':
        sql = ("SELECT user_id AS chat_id, MAX(id) AS last_id, MAX(timestamp) AS last_time, "
               "COUNT(*) AS msg_count FROM log WHERE user_id != '' AND group_id = '' GROUP BY user_id")
    else:
        sql = ("SELECT group_id AS chat_id, MAX(id) AS last_id, MAX(timestamp) AS last_time, "
               "COUNT(*) AS msg_count FROM log WHERE group_id != '' GROUP BY group_id")
    rows = _q(sql)
    stats = {}
    for r in rows:
        cid = str(r.get('chat_id', ''))
        if cid:
            stats[cid] = {
                'last_id': r.get('last_id', 0) or 0,
                'last_time': r.get('last_time', '') or '',
                'msg_count': r.get('msg_count', 0) or 0,
            }
    return stats


def _chat_from_stats(chat_type, stats, remarks):
    """OneBot 接口不可用时, 退化为仅根据消息日志构造会话列表"""
    appid = _primary_id()
    chats = []
    for cid, st in stats.items():
        item = {
            'chat_id': cid, 'appid': appid, 'bot_name': appid,
            'last_id': st['last_id'], 'last_time': st['last_time'],
            'last_date': (st['last_time'] or '')[:10], 'msg_count': st['msg_count'],
            'remark': '', 'is_full_access': False,
        }
        if chat_type == 'group':
            rv = remarks.get(cid)
            item['nickname'] = _remark_name(rv) or f'群{cid[-6:]}'
            item['remark'] = _remark_name(rv)
            item['group_qq'] = _remark_qq(rv)
        else:
            item['nickname'] = f'用户{cid[-6:]}'
        chats.append(item)
    return chats


async def _fetch_chats(chat_type):
    """群 / 好友列表统一从 OneBot 接口获取, 并合并消息日志的最近时间与计数"""
    appid = _primary_id()
    stats = await asyncio.get_running_loop().run_in_executor(None, _db_stats, chat_type)
    remarks = _load_remarks()
    api = _api()

    try:
        if chat_type == 'user':
            resp = await api.get_friend_list()
        else:
            resp = await api.get_group_list()
    except Exception:
        resp = None

    data = (resp or {}).get('data') or [] if resp and resp.get('retcode') == 0 else []

    # 接口无数据时退化为消息日志聚合, 保证已有聊天记录仍可查看
    if not data:
        chats = _chat_from_stats(chat_type, stats, remarks)
        chats.sort(key=lambda c: c['last_time'] or '', reverse=True)
        return chats

    chats = []
    if chat_type == 'user':
        for f in data:
            uid = str(f.get('user_id', ''))
            if not uid:
                continue
            st = stats.get(uid, {})
            nick = f.get('remark') or f.get('nickname') or f'用户{uid[-6:]}'
            chats.append({
                'chat_id': uid, 'appid': appid, 'bot_name': appid,
                'nickname': nick, 'remark': f.get('remark', '') or '',
                'last_id': st.get('last_id', 0), 'last_time': st.get('last_time', ''),
                'last_date': (st.get('last_time', '') or '')[:10],
                'msg_count': st.get('msg_count', 0),
            })
    else:
        for g in data:
            gid = str(g.get('group_id', ''))
            if not gid:
                continue
            st = stats.get(gid, {})
            rv = remarks.get(gid)
            name = _remark_name(rv) or g.get('group_name') or f'群{gid[-6:]}'
            chats.append({
                'chat_id': gid, 'appid': appid, 'bot_name': appid,
                'nickname': name, 'remark': _remark_name(rv),
                'group_qq': _remark_qq(rv), 'is_full_access': False,
                'last_id': st.get('last_id', 0), 'last_time': st.get('last_time', ''),
                'last_date': (st.get('last_time', '') or '')[:10],
                'msg_count': st.get('msg_count', 0),
            })

    # 有聊天记录的排在前面 (按最近时间), 其余保持接口顺序
    chats.sort(key=lambda c: (c['last_time'] or '', c['msg_count']), reverse=True)
    return chats


async def handle_get_chats(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    chat_type = body.get('type', 'group')
    if chat_type not in ('group', 'user'):
        chat_type = 'group'
    search = body.get('search', '').lower()
    page = max(int(body.get('page', 1)), 1)
    page_size = min(int(body.get('page_size', 50)), 100)

    now = time.time()
    c = _chat_cache.get(chat_type)
    if c and now - c[0] < _CHAT_TTL:
        chats = c[1]
    else:
        chats = await _fetch_chats(chat_type)
        _chat_cache[chat_type] = (now, chats)

    if search:
        chats = [c for c in chats if search in c['chat_id'].lower() or search in c.get('nickname', '').lower()]

    total = len(chats)
    start = (page - 1) * page_size
    return web.json_response({
        'success': True,
        'data': {'chats': chats[start:start + page_size], 'total': total, 'page': page, 'page_size': page_size},
    })


# ──────────── 历史消息 ────────────

def _query_messages(chat_type, chat_id, limit=300):
    if chat_type == 'group':
        sql = f"SELECT * FROM log WHERE group_id = ? ORDER BY id DESC LIMIT {limit}"
        params = (chat_id,)
    else:
        sql = f"SELECT * FROM log WHERE user_id = ? AND group_id = '' ORDER BY id DESC LIMIT {limit}"
        params = (chat_id,)
    rows = _q(sql, params)
    rows.reverse()
    return rows


async def handle_get_chat_history(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    chat_type = body.get('chat_type', 'group')
    chat_id = str(body.get('chat_id', ''))
    if not chat_id:
        return web.json_response({'success': True, 'data': {'messages': [], 'has_more': False}})

    rows = await asyncio.get_running_loop().run_in_executor(None, _query_messages, chat_type, chat_id, 300)

    # 预解析 extra（接收消息为 JSON，发送/撤回为字符串标记）
    parsed = []
    need_nick = set()
    for r in rows:
        ex = r.get('extra', '')
        is_self = ex == 'send'
        recalled = ex == 'recalled'
        meta = {}
        if ex and ex not in ('send', 'recalled') and ex.startswith('{'):
            with contextlib.suppress(Exception):
                meta = json.loads(ex)
        uid = str(r.get('user_id', ''))
        if not is_self and uid and not meta.get('nickname'):
            need_nick.add(uid)
        parsed.append((r, is_self, recalled, meta, uid))

    nicks = await _common.batch_nicknames(list(need_nick)) if need_nick else {}

    messages = []
    last_msg_id = ''
    for r, is_self, recalled, meta, uid in parsed:
        raw = r.get('raw_data', '')
        mid = str(r.get('message_id', ''))
        appid = str(r.get('source', '') or '') if r.get('source') not in ('WebPanel', '') else _primary_id()
        if mid and not is_self:
            last_msg_id = mid
        nickname = meta.get('nickname') or nicks.get(uid, f'用户{uid[-6:]}' if uid else '未知用户')
        messages.append({
            'id': r.get('id', len(messages)),
            'message_id': mid,
            'reference_id': '',
            'user_id': uid,
            'appid': appid,
            'bot_qq': appid if is_self else '',
            'nickname': (_primary_id() or 'Bot') if is_self else nickname,
            'content': r.get('content', ''),
            'timestamp': r.get('timestamp', ''),
            'is_self': is_self,
            'source': 'web_panel' if r.get('source') == 'WebPanel' else 'onebot',
            'raw_message': raw if not recalled else '',
            'recalled': recalled,
        })

    return web.json_response({
        'success': True,
        'data': {'messages': messages, 'last_msg_id': last_msg_id,
                 'oldest_date': datetime.now().strftime('%Y-%m-%d'), 'has_more': False},
    })


# ──────────── 发送 / 撤回 ────────────

def _log_sent(chat_type, chat_id, content, message_id):
    svc = _common.log_service()
    if not svc:
        return
    svc.add('message', {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'content': content,
        'user_id': '' if chat_type == 'group' else chat_id,
        'group_id': chat_id if chat_type == 'group' else '',
        'message_id': str(message_id or ''),
        'message_type': chat_type,
        'source': 'WebPanel',
        'extra': 'send',
    })


async def handle_send_message(request: web.Request):
    try:
        if request.content_type and 'multipart' in request.content_type:
            reader = await request.multipart()
            fields, image_data = {}, None
            while True:
                part = await reader.next()
                if part is None:
                    break
                if part.name == 'image':
                    image_data = await part.read()
                else:
                    fields[part.name] = (await part.read()).decode('utf-8', errors='replace')
        else:
            fields = await request.json()
            image_data = None

        chat_type = fields.get('chat_type', '')
        chat_id = str(fields.get('chat_id', ''))
        msg_type = fields.get('msg_type', 'text')
        content = (fields.get('content', '') or '').strip()

        if not chat_type or not chat_id:
            return web.json_response({'success': False, 'message': '缺少 chat_type/chat_id'}, status=400)
        if not content and not image_data:
            return web.json_response({'success': False, 'message': '消息内容为空'}, status=400)
        if not _common.connected_ids():
            return web.json_response({'success': False, 'message': '无可用机器人连接'}, status=400)

        # 构造 OneBot 消息段
        segments = []
        if content:
            if msg_type == 'media':
                segments.append({'type': 'image', 'data': {'file': content}})
            else:
                segments.append({'type': 'text', 'data': {'text': content}})
        if image_data:
            import base64
            b64 = base64.b64encode(image_data).decode()
            segments.append({'type': 'image', 'data': {'file': f'base64://{b64}'}})

        api = _api()
        if chat_type == 'group':
            resp = await api.send_group_msg(chat_id, segments)
        else:
            resp = await api.send_private_msg(chat_id, segments)

        if resp and resp.get('retcode') == 0:
            mid = (resp.get('data') or {}).get('message_id', '')
            display = content or '[图片]'
            _log_sent(chat_type, chat_id, display, mid)
            return web.json_response({'success': True, 'message': '发送成功'})
        err = (resp or {}).get('message') or (resp or {}).get('wording') or '发送失败'
        return web.json_response({'success': False, 'message': str(err)})
    except Exception as e:
        import traceback

        traceback.print_exc()
        return web.json_response({'success': False, 'message': str(e)}, status=500)


async def handle_recall_message(request: web.Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    message_id = body.get('message_id', '')
    if not message_id:
        return web.json_response({'success': False, 'message': '参数缺失'}, status=400)
    try:
        resp = await _api().delete_msg(message_id)
    except Exception as e:
        return web.json_response({'success': False, 'message': str(e)}, status=500)
    if resp and resp.get('retcode') == 0:
        with contextlib.suppress(Exception):
            _mark_recalled(message_id)
        return web.json_response({'success': True})
    return web.json_response({'success': False, 'message': '撤回失败'})


def _mark_recalled(message_id):
    svc = _common.log_service()
    if not svc:
        return
    with contextlib.suppress(Exception):
        conn = svc._get_conn('message')
        with svc._lock:
            conn.execute("UPDATE log SET extra='recalled' WHERE message_id=?", (str(message_id),))
            conn.commit()


# ──────────── 群备注 ────────────

_remarks_cache = None
_remarks_ts = 0.0


def _remarks_path():
    return os.path.join(_base_dir, 'data', 'group_remarks.json')


def _remark_name(val):
    if isinstance(val, dict):
        return val.get('name', '')
    return str(val) if val else ''


def _remark_qq(val):
    return val.get('qq', '') if isinstance(val, dict) else ''


def _load_remarks() -> dict:
    global _remarks_cache, _remarks_ts
    now = time.time()
    if _remarks_cache is not None and now - _remarks_ts < 60:
        return _remarks_cache
    path = _remarks_path()
    data = {}
    if os.path.isfile(path):
        with contextlib.suppress(Exception), open(path, encoding='utf-8') as f:
            d = json.load(f)
            data = d if isinstance(d, dict) else {}
    _remarks_cache = data
    _remarks_ts = now
    return data


def _save_remarks(remarks):
    global _remarks_cache, _remarks_ts
    path = _remarks_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(remarks, f, ensure_ascii=False, indent=2)
    _remarks_cache = remarks
    _remarks_ts = time.time()


async def handle_get_remarks(request: web.Request):
    return web.json_response({'success': True, 'data': _load_remarks()})


async def handle_set_remark(request: web.Request):
    body = await request.json()
    gid = str(body.get('group_id', '') or body.get('chat_id', ''))
    name = body.get('name', '') or body.get('remark', '')
    qq = body.get('qq', '')
    if not gid:
        return web.json_response({'success': False, 'message': '缺少群号'}, status=400)
    remarks = dict(_load_remarks())
    remarks[gid] = {'name': name, 'qq': qq}
    _save_remarks(remarks)
    _chat_cache.clear()
    return web.json_response({'success': True})


async def handle_delete_remark(request: web.Request):
    body = await request.json()
    gid = str(body.get('group_id', '') or body.get('chat_id', ''))
    remarks = dict(_load_remarks())
    if gid in remarks:
        del remarks[gid]
        _save_remarks(remarks)
        _chat_cache.clear()
    return web.json_response({'success': True})


async def handle_get_group_roles(request: web.Request):
    return web.json_response({'success': True, 'data': {}})
