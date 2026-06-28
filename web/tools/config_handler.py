"""配置文件管理 — YAML 配置读写"""

import os
import shutil

import yaml
from aiohttp import web

_base_dir = ''


def set_context(base_dir: str):
    global _base_dir
    _base_dir = base_dir


def _config_dir():
    return os.path.join(_base_dir, 'config')


async def handle_get_config(request: web.Request):
    """返回所有配置文件的原始文本"""
    cdir = _config_dir()
    result = {}
    for name in ('settings',):
        path = os.path.join(cdir, f'{name}.yaml')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                result[name] = f.read()
        else:
            example = os.path.join(cdir, f'{name}.example.yaml')
            if os.path.exists(example):
                with open(example, encoding='utf-8') as f:
                    result[name] = f.read()
            else:
                result[name] = ''
    return web.json_response({'success': True, **result})


async def handle_save_config(request: web.Request):
    try:
        body = await request.json()
        file_name = body.get('file', 'settings')
        content = body.get('content', '')
        if file_name not in ('settings',):
            return web.json_response({'success': False, 'error': 'invalid config file'}, status=400)
        if not content:
            return web.json_response({'success': False, 'error': 'content is empty'}, status=400)

        # validate YAML
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return web.json_response({'success': False, 'error': f'YAML error: {e}'}, status=400)

        cdir = _config_dir()
        path = os.path.join(cdir, f'{file_name}.yaml')

        if os.path.exists(path):
            shutil.copy2(path, path + '.bak')

        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        return web.json_response({'success': True, 'message': 'saved'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)
