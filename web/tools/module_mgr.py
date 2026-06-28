"""模块管理 — scan / toggle / upload"""

import ast
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime

from aiohttp import web

_bot_manager = None
_base_dir = ''


def set_context(bot_manager, base_dir: str):
    global _bot_manager, _base_dir
    _bot_manager = bot_manager
    _base_dir = base_dir


def _modules_dir():
    return os.path.join(_base_dir, 'modules')


def _get_mm():
    if _bot_manager and _bot_manager.module_manager:
        return _bot_manager.module_manager
    return None


def _read_module_meta(entry_path):
    try:
        with open(entry_path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        for node in ast.iter_child_nodes(tree):
            if (isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == '__module_meta__'):
                return ast.literal_eval(node.value)
    except Exception:
        pass
    return {}


def _scan_modules():
    mdir = _modules_dir()
    result = []
    if not os.path.isdir(mdir):
        return result

    runtime = {}
    mm = _get_mm()
    if mm:
        for m in mm.list_modules():
            runtime[m['name']] = m

    persist_map = {}
    enabled_file = os.path.join(mdir, 'modules_enabled.json')
    if os.path.isfile(enabled_file):
        try:
            with open(enabled_file, encoding='utf-8') as f:
                persist_map = json.load(f) or {}
        except Exception:
            pass

    for name in sorted(os.listdir(mdir)):
        mod_dir = os.path.join(mdir, name)
        if not os.path.isdir(mod_dir) or name.startswith('_'):
            continue
        entry = os.path.join(mod_dir, 'main.py')
        if not os.path.isfile(entry):
            continue

        meta = _read_module_meta(entry)
        rt = runtime.get(name, {})
        mtime = datetime.fromtimestamp(os.path.getmtime(entry)).strftime('%Y-%m-%d %H:%M:%S')

        result.append({
            'name': name,
            'display_name': meta.get('name') or rt.get('display_name') or name,
            'description': meta.get('description') or rt.get('description', ''),
            'version': meta.get('version') or rt.get('version', '1.0.0'),
            'author': meta.get('author') or rt.get('author', ''),
            'enabled': rt.get('enabled', False),
            'persist_enabled': rt.get('persist_enabled', persist_map.get(name, False)),
            'error': rt.get('error'),
            'last_modified': mtime,
        })
    return result


async def handle_scan_modules(request: web.Request):
    return web.json_response({'success': True, 'modules': _scan_modules()})


async def handle_list_modules(request: web.Request):
    """Legacy API"""
    return web.json_response({'success': True, 'data': _scan_modules()})


async def handle_module_toggle(request: web.Request):
    body = await request.json()
    name = body.get('name', '')
    action = body.get('action', '')
    enabled = body.get('enabled')

    if not name:
        return web.json_response({'success': False, 'message': 'missing name'}, status=400)

    mm = _get_mm()
    if not mm:
        return web.json_response({'success': False, 'message': 'module manager not ready'}, status=503)

    try:
        if action == 'enable' or enabled is True:
            ok = await mm.enable(name)
        elif action == 'disable' or enabled is False:
            ok = await mm.disable(name)
        else:
            return web.json_response({'success': False, 'message': 'invalid action'}, status=400)
        return web.json_response({'success': ok})
    except Exception as e:
        return web.json_response({'success': False, 'message': str(e)}, status=500)


async def handle_module_upload(request: web.Request):
    reader = await request.multipart()
    field = await reader.next()
    if not field or field.name != 'file':
        return web.json_response({'success': False, 'message': 'missing file'}, status=400)

    filename = field.filename or ''
    if not filename.lower().endswith('.zip'):
        return web.json_response({'success': False, 'message': 'only zip'}, status=400)

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                tmp.write(chunk)

        if not zipfile.is_zipfile(tmp.name):
            return web.json_response({'success': False, 'message': 'invalid zip'}, status=400)

        with zipfile.ZipFile(tmp.name, 'r') as zf:
            mod_name = os.path.splitext(filename)[0]
            names = zf.namelist()

            top_dirs = set()
            for n in names:
                parts = n.replace('\\', '/').split('/')
                if len(parts) > 1 and parts[0]:
                    top_dirs.add(parts[0])

            mdir = _modules_dir()
            os.makedirs(mdir, exist_ok=True)
            target_dir = os.path.join(mdir, mod_name)

            if os.path.exists(target_dir):
                backup = target_dir + '.bak'
                if os.path.exists(backup):
                    shutil.rmtree(backup)
                shutil.move(target_dir, backup)

            if len(top_dirs) == 1:
                extract_tmp = tempfile.mkdtemp()
                zf.extractall(extract_tmp)
                src = os.path.join(extract_tmp, list(top_dirs)[0])
                shutil.move(src, target_dir)
                shutil.rmtree(extract_tmp, ignore_errors=True)
            else:
                os.makedirs(target_dir, exist_ok=True)
                zf.extractall(target_dir)

        return web.json_response({
            'success': True,
            'message': f'module {mod_name} uploaded',
            'module_name': mod_name,
        })
    except Exception as e:
        return web.json_response({'success': False, 'message': str(e)}, status=500)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
