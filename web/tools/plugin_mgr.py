"""插件管理 — scan / toggle / read / save / create / upload / reload"""

import ast
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime

from aiohttp import web

_bot_manager = None
_base_dir = ''

ENTRY_CANDIDATES = ('main.py', 'index.py', 'app.py')


def set_context(bot_manager, base_dir: str):
    global _bot_manager, _base_dir
    _bot_manager = bot_manager
    _base_dir = base_dir


def _plugins_dir():
    return os.path.join(_base_dir, 'plugins')


def _get_pm():
    if _bot_manager and _bot_manager.plugin_manager:
        return _bot_manager.plugin_manager
    return None


def _find_entry(plugin_dir):
    for name in ENTRY_CANDIDATES:
        p = os.path.join(plugin_dir, name)
        if os.path.isfile(p):
            return p
    return None


def _read_file_meta(py_path):
    try:
        with open(py_path, encoding='utf-8') as f:
            tree = ast.parse(f.read())
        for node in ast.iter_child_nodes(tree):
            if (isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id == '__plugin_meta__'):
                meta = ast.literal_eval(node.value)
                if isinstance(meta, dict):
                    allowed = {'name', 'version', 'author', 'description'}
                    return {k: str(v) for k, v in meta.items() if k in allowed and v}
    except Exception:
        pass
    return None


def _scan_plugins():
    pdir = _plugins_dir()
    result = []
    if not os.path.isdir(pdir):
        return result

    pm = _get_pm()
    for dir_name in sorted(os.listdir(pdir)):
        plugin_dir = os.path.join(pdir, dir_name)
        if not os.path.isdir(plugin_dir) or dir_name.startswith(('.', '_')):
            continue

        entry_path = _find_entry(plugin_dir)
        if not entry_path:
            py_files = [f for f in os.listdir(plugin_dir) if f.endswith('.py') and not f.startswith('_')]
            if not py_files:
                continue
            entry_path = os.path.join(plugin_dir, py_files[0])

        meta = _read_file_meta(entry_path) or {}
        mtime = datetime.fromtimestamp(os.path.getmtime(entry_path)).strftime('%Y-%m-%d %H:%M:%S')
        loaded = dir_name in (pm._plugins if pm else {})

        # scan files
        files = []
        for fname in sorted(os.listdir(plugin_dir)):
            if fname.startswith('_') or not fname.endswith('.py'):
                continue
            fpath = os.path.join(plugin_dir, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    'name': fname,
                    'path': fpath.replace('\\', '/'),
                    'size': stat.st_size,
                    'last_modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                })

        handlers_count = 0
        if pm and dir_name in pm._plugins:
            pi = pm._plugins[dir_name]
            handlers_count = len(pi.get('handlers', []))

        result.append({
            'name': dir_name,
            'directory': dir_name,
            'status': 'loaded' if loaded else 'unloaded',
            'enabled': loaded,
            'path': entry_path.replace('\\', '/'),
            'last_modified': mtime,
            'handlers': handlers_count,
            'files': files,
            'meta': meta,
            'description': meta.get('description', ''),
            'commands': [],
        })

    result.sort(key=lambda x: (0 if x['status'] == 'loaded' else 1))
    return result


async def handle_scan_plugins(request: web.Request):
    return web.json_response({'success': True, 'plugins': _scan_plugins()})


async def handle_list_plugins(request: web.Request):
    """Legacy API"""
    plugins = _scan_plugins()
    return web.json_response({'success': True, 'data': plugins})


async def handle_read_plugin(request: web.Request):
    body = await request.json()
    plugin_path = os.path.normpath(body.get('path', ''))
    if not plugin_path:
        return web.json_response({'success': False, 'message': 'missing path'}, status=400)

    pdir = os.path.abspath(_plugins_dir())
    abs_path = os.path.abspath(plugin_path)
    if not abs_path.startswith(pdir) or not os.path.isfile(abs_path):
        return web.json_response({'success': False, 'message': 'invalid path'}, status=403)

    with open(abs_path, encoding='utf-8') as f:
        content = f.read()
    return web.json_response({
        'success': True,
        'content': content,
        'path': plugin_path.replace('\\', '/'),
        'filename': os.path.basename(plugin_path),
    })


async def handle_save_plugin(request: web.Request):
    body = await request.json()
    plugin_path = os.path.normpath(body.get('path', ''))
    content = body.get('content')
    if not plugin_path or content is None:
        return web.json_response({'success': False, 'message': 'missing params'}, status=400)

    pdir = os.path.abspath(_plugins_dir())
    abs_path = os.path.abspath(plugin_path)
    if not abs_path.startswith(pdir):
        return web.json_response({'success': False, 'message': 'invalid path'}, status=403)

    if os.path.exists(abs_path):
        shutil.copy2(abs_path, abs_path + '.backup')
    with open(abs_path, 'w', encoding='utf-8') as f:
        f.write(content)
    return web.json_response({'success': True, 'message': 'saved'})


_PLUGIN_TEMPLATE = '''from core.plugin.decorators import handler


@handler(r"^command$", name="example", desc="example plugin")
async def handle_command(event, match):
    await event.reply("Hello, World!")
'''


async def handle_create_plugin(request: web.Request):
    body = await request.json()
    directory = body.get('directory', '')
    filename = body.get('filename', '')
    if not directory or not filename:
        return web.json_response({'success': False, 'message': 'missing params'}, status=400)
    if not filename.endswith('.py'):
        filename += '.py'

    pdir = _plugins_dir()
    target_dir = os.path.join(pdir, directory)
    if not os.path.abspath(target_dir).startswith(os.path.abspath(pdir)):
        return web.json_response({'success': False, 'message': 'invalid directory'}, status=403)

    plugin_path = os.path.join(target_dir, filename)
    if os.path.exists(plugin_path):
        return web.json_response({'success': False, 'message': 'file exists'}, status=409)

    os.makedirs(target_dir, exist_ok=True)
    with open(plugin_path, 'w', encoding='utf-8') as f:
        f.write(_PLUGIN_TEMPLATE)
    return web.json_response({
        'success': True,
        'message': 'created',
        'path': plugin_path.replace('\\', '/'),
    })


async def handle_create_folder(request: web.Request):
    body = await request.json()
    folder_name = body.get('folder_name', '')
    if not folder_name:
        return web.json_response({'success': False, 'message': 'missing folder name'}, status=400)

    pdir = _plugins_dir()
    target = os.path.join(pdir, folder_name)
    if not os.path.abspath(target).startswith(os.path.abspath(pdir)):
        return web.json_response({'success': False, 'message': 'invalid path'}, status=403)
    if os.path.exists(target):
        return web.json_response({'success': False, 'message': 'folder exists'}, status=409)

    os.makedirs(target, exist_ok=True)
    return web.json_response({'success': True, 'message': 'created'})


async def handle_get_folders(request: web.Request):
    pdir = _plugins_dir()
    folders = []
    if os.path.isdir(pdir):
        for item in sorted(os.listdir(pdir)):
            if os.path.isdir(os.path.join(pdir, item)) and not item.startswith(('.', '__')):
                folders.append({'name': item, 'path': item})
    return web.json_response({'success': True, 'folders': folders})


async def handle_reload_plugin(request: web.Request):
    body = await request.json()
    name = body.get('name', '')
    if not name:
        return web.json_response({'success': False, 'error': 'missing name'}, status=400)

    pm = _get_pm()
    if not pm:
        return web.json_response({'success': False, 'error': 'plugin manager not ready'}, status=503)

    try:
        result = await pm.reload_plugin(name)
        return web.json_response({'success': result})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def handle_upload_plugin(request: web.Request):
    reader = await request.multipart()
    file_data = None
    filename = None
    directory = 'alone'
    async for field in reader:
        if field.name == 'file':
            filename = field.filename
            file_data = await field.read()
        elif field.name == 'directory':
            directory = (await field.text()).strip() or 'alone'

    if not file_data or not filename:
        return web.json_response({'success': False, 'message': 'no file'}, status=400)

    is_zip = filename.lower().endswith('.zip')
    is_py = filename.lower().endswith('.py')
    if not is_zip and not is_py:
        return web.json_response({'success': False, 'message': 'only .py or .zip'}, status=400)

    pdir = _plugins_dir()

    if is_py:
        safe_name = re.sub(r'[^\w\u4e00-\u9fa5\-\.]', '_', filename)
        target_dir = os.path.join(pdir, directory)
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, safe_name)
        with open(dest, 'wb') as f:
            f.write(file_data)
        return web.json_response({'success': True, 'message': f'uploaded: {safe_name}'})

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            tmp.write(file_data)

        if not zipfile.is_zipfile(tmp.name):
            return web.json_response({'success': False, 'message': 'invalid zip'}, status=400)

        with zipfile.ZipFile(tmp.name, 'r') as zf:
            names = zf.namelist()
            top_dirs = set()
            for n in names:
                parts = n.replace('\\', '/').strip('/').split('/')
                if len(parts) > 1 and parts[0]:
                    top_dirs.add(parts[0])

            zip_stem = os.path.splitext(filename)[0]
            safe_folder = re.sub(r'[^\w\u4e00-\u9fa5\-]', '_', zip_stem)
            target_dir = os.path.join(pdir, safe_folder)

            os.makedirs(pdir, exist_ok=True)
            if len(top_dirs) == 1:
                extract_tmp = tempfile.mkdtemp()
                zf.extractall(extract_tmp)
                src = os.path.join(extract_tmp, list(top_dirs)[0])
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.move(src, target_dir)
                shutil.rmtree(extract_tmp, ignore_errors=True)
            else:
                os.makedirs(target_dir, exist_ok=True)
                zf.extractall(target_dir)

        return web.json_response({'success': True, 'message': f'uploaded: {safe_folder}'})
    except Exception as e:
        return web.json_response({'success': False, 'message': str(e)}, status=500)
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
