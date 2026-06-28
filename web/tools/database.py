"""数据库浏览器 — 列出 SQLite 文件, 浏览表, 查询/执行"""

import logging
import os
import sqlite3
from datetime import datetime

from aiohttp import web

log = logging.getLogger('ElainaBot.web.database')

_base_dir = ''


def set_context(base_dir: str):
    global _base_dir
    _base_dir = base_dir


def _data_dir():
    return os.path.join(_base_dir, 'data')


def _validate_db_path(db_path: str) -> str | None:
    """Resolve and validate db path is under data dir"""
    data = os.path.abspath(_data_dir())
    full = os.path.abspath(os.path.join(data, db_path))
    if not full.startswith(data):
        return None
    if not os.path.isfile(full):
        return None
    return full


async def handle_list_databases(request: web.Request):
    data = _data_dir()
    dbs = []
    if not os.path.isdir(data):
        return web.json_response({'success': True, 'databases': dbs})

    for root, _, files in os.walk(data):
        for f in files:
            if f.endswith('.db'):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, data).replace('\\', '/')
                stat = os.stat(full_path)
                dbs.append({
                    'name': f,
                    'path': rel_path,
                    'size': stat.st_size,
                    'last_modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                })
    dbs.sort(key=lambda x: x['path'])
    return web.json_response({'success': True, 'databases': dbs})


async def handle_list_tables(request: web.Request):
    db_path = request.query.get('db', '')
    if not db_path:
        return web.json_response({'success': False, 'error': 'missing db'}, status=400)

    full = _validate_db_path(db_path)
    if not full:
        return web.json_response({'success': False, 'error': 'invalid db path'}, status=400)

    tables = []
    try:
        conn = sqlite3.connect(full, timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        for row in cursor:
            name = row['name']
            cols = []
            for ci in conn.execute(f"PRAGMA table_info('{name}')"):
                cols.append({
                    'name': ci['name'],
                    'type': ci['type'],
                    'notnull': bool(ci['notnull']),
                    'pk': bool(ci['pk']),
                })

            count_row = conn.execute(f"SELECT COUNT(*) as cnt FROM [{name}]").fetchone()
            count = count_row['cnt'] if count_row else 0

            tables.append({
                'name': name,
                'columns': cols,
                'row_count': count,
            })
        conn.close()
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

    return web.json_response({'success': True, 'tables': tables})


async def handle_query_table(request: web.Request):
    body = await request.json()
    db_path = body.get('db', '')
    table = body.get('table', '')
    page = int(body.get('page', 1))
    limit = min(int(body.get('limit', 100)), 1000)
    order_by = body.get('order_by', 'rowid')
    order_dir = body.get('order_dir', 'DESC').upper()
    search = body.get('search', '')

    if not db_path or not table:
        return web.json_response({'success': False, 'error': 'missing params'}, status=400)

    full = _validate_db_path(db_path)
    if not full:
        return web.json_response({'success': False, 'error': 'invalid db'}, status=400)

    if order_dir not in ('ASC', 'DESC'):
        order_dir = 'DESC'

    try:
        conn = sqlite3.connect(full, timeout=5)
        conn.row_factory = sqlite3.Row
        offset = (page - 1) * limit

        where = ''
        params = []
        if search:
            cols = [c['name'] for c in conn.execute(f"PRAGMA table_info('{table}')")]
            conditions = [f"CAST([{col}] AS TEXT) LIKE ?" for col in cols]
            where = 'WHERE ' + ' OR '.join(conditions)
            params = [f'%{search}%'] * len(cols)

        count_sql = f"SELECT COUNT(*) as cnt FROM [{table}] {where}"
        count_row = conn.execute(count_sql, params).fetchone()
        total = count_row['cnt'] if count_row else 0

        sql = f"SELECT * FROM [{table}] {where} ORDER BY [{order_by}] {order_dir} LIMIT ? OFFSET ?"
        cursor = conn.execute(sql, params + [limit, offset])
        rows = [dict(r) for r in cursor]
        conn.close()

        return web.json_response({
            'success': True,
            'rows': rows,
            'total': total,
            'page': page,
            'limit': limit,
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def handle_execute_sql(request: web.Request):
    body = await request.json()
    db_path = body.get('db', '')
    sql = body.get('sql', '').strip()
    read_only = body.get('read_only', True)

    if not db_path or not sql:
        return web.json_response({'success': False, 'error': 'missing params'}, status=400)

    full = _validate_db_path(db_path)
    if not full:
        return web.json_response({'success': False, 'error': 'invalid db'}, status=400)

    try:
        conn = sqlite3.connect(full, timeout=5)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        is_select = sql.upper().lstrip().startswith('SELECT')

        if is_select:
            rows = [dict(r) for r in cursor.fetchmany(500)]
            conn.close()
            return web.json_response({
                'success': True,
                'rows': rows,
                'row_count': len(rows),
            })
        else:
            if read_only:
                conn.rollback()
                conn.close()
                return web.json_response({'success': False, 'error': 'read-only mode'}, status=403)

            conn.commit()
            affected = cursor.rowcount
            conn.close()
            return web.json_response({
                'success': True,
                'affected_rows': affected,
            })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def handle_delete_row(request: web.Request):
    body = await request.json()
    db_path = body.get('db', '')
    table = body.get('table', '')
    conditions = body.get('conditions', {})

    if not db_path or not table or not conditions:
        return web.json_response({'success': False, 'error': 'missing params'}, status=400)

    full = _validate_db_path(db_path)
    if not full:
        return web.json_response({'success': False, 'error': 'invalid db'}, status=400)

    try:
        conn = sqlite3.connect(full, timeout=5)
        where = ' AND '.join([f'[{k}] = ?' for k in conditions.keys()])
        sql = f'DELETE FROM [{table}] WHERE {where}'
        cursor = conn.execute(sql, list(conditions.values()))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        return web.json_response({'success': True, 'deleted': deleted})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)
