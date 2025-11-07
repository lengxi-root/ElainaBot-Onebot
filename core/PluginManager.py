#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import importlib.util
import sys
import traceback
import time
import gc
import weakref
import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from config import OWNER_IDS
from web.app import add_plugin_log, add_framework_log, add_error_log
from function.log_db import add_log_to_db

# 获取日志记录器
_logger = logging.getLogger('ElainaBot.core.PluginManager')
logger = _logger  # 别名，方便使用

def _log_error(error_msg, error_trace=None):
    if error_trace:
        _logger.error(f"{error_msg}\n{error_trace}")
    else:
        _logger.error(error_msg)
    
    # 同时推送到Web前台
    try:
        add_error_log(error_msg, error_trace or "")
    except:
        pass

_last_plugin_gc_time = 0
_plugin_gc_interval = 30
_last_quick_check_time = 0
_plugins_loaded = False
_last_cache_cleanup = 0
_plugin_executor = ThreadPoolExecutor(max_workers=300, thread_name_prefix="PluginWorker")

class Plugin:
    priority = 10
    import_from_main = False

    @staticmethod
    def get_regex_handlers():
        raise NotImplementedError("子类必须实现get_regex_handlers方法")

class PluginManager:
    _regex_handlers = {}
    _plugins = {}
    _file_last_modified = {}
    _unloaded_modules = []
    _regex_cache = {}
    _sorted_handlers = []
    _handler_patterns_cache = {}
    _web_routes = {}  # 存储web插件路由信息
    _api_routes = {}  # 存储插件自定义API路由

    @classmethod
    def _safe_execute(cls, func, error_msg_template, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _log_error(error_msg_template.format(error=str(e)), traceback.format_exc())
            return None
    
    @classmethod
    def _extract_module_info(cls, file_path):
        if not file_path:
            return "未知目录", "未知模块", "unknown"
        dir_name = os.path.basename(os.path.dirname(file_path))
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        return dir_name, module_name, f"plugins.{dir_name}.{module_name}"
    
    @classmethod
    def _check_permissions(cls, handler_info, is_owner, is_group):
        if handler_info.get('owner_only', False) and not is_owner:
            return False, 'owner_denied'
        if handler_info.get('group_only', False) and not is_group:
            return False, 'group_denied'
        return True, None
    
    @classmethod
    def _cleanup_resources(cls, obj, context=""):
        for method_name in ['cleanup', 'close', 'shutdown']:
            if hasattr(obj, method_name) and callable(getattr(obj, method_name)):
                try:
                    method = getattr(obj, method_name)
                    if method_name == 'shutdown' and hasattr(method, '__code__') and 'wait' in method.__code__.co_varnames:
                        method(wait=False)
                    else:
                        method()
                    if context:
                        add_framework_log(f"{context}：清理 {method_name}")
                    return True
                except:
                    pass
        return False
    
    @classmethod
    def _enhance_pattern(cls, pattern):
        return pattern if pattern.startswith('^') else f"^{pattern}"
    
    @classmethod
    def _compile_and_cache_regex(cls, pattern, error_context=""):
        try:
            compiled_regex = re.compile(pattern, re.DOTALL)
            cls._regex_cache[pattern] = compiled_regex
            return compiled_regex
        except Exception as e:
            if error_context:
                _log_error(f"{error_context}正则 '{pattern}' 编译失败: {e}")
            return None

    @classmethod
    def reload_plugin(cls, plugin_class):
        try:
            if not hasattr(plugin_class, '_source_file'):
                add_error_log(f"插件 {plugin_class.__name__} 无 _source_file", "")
                return False
            
            file_path = plugin_class._source_file
            if not os.path.exists(file_path):
                add_error_log(f"插件文件不存在: {file_path}", "")
                return False
            
            dir_name, module_name, _ = cls._extract_module_info(file_path)
            add_framework_log(f"热加载: {dir_name}/{module_name}.py")
            
            loaded_count = cls._load_plugin_file(file_path, dir_name)
            if loaded_count > 0:
                add_framework_log(f"✅ {dir_name}/{module_name}.py")
                return True
            add_framework_log(f"❌ {dir_name}/{module_name}.py")
            return False
        except Exception as e:
            _log_error(f"插件热加载失败: {e}", traceback.format_exc())
            return False
    
    @classmethod
    def load_plugins(cls):
        global _last_plugin_gc_time, _last_quick_check_time, _plugins_loaded, _last_cache_cleanup
        
        current_time = time.time()
        if _plugins_loaded and current_time - _last_quick_check_time < 2:
            return len(cls._plugins)
        
        _last_quick_check_time = current_time
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        plugins_dir = os.path.join(script_dir, 'plugins')
        
        if not os.path.exists(plugins_dir):
            logger.error(f"❌ 插件目录不存在: {plugins_dir}")
            os.makedirs(plugins_dir, exist_ok=True)
            return 0
        
        cls._cleanup_deleted_files()
        
        loaded_count = 0
        plugin_dirs = os.listdir(plugins_dir)
        
        for dir_name in plugin_dirs:
            dir_path = os.path.join(plugins_dir, dir_name)
            if os.path.isdir(dir_path):
                count = cls._load_plugins_from_directory(script_dir, dir_name)
                loaded_count += count
        
        main_module_loaded = cls._import_main_module_instances()
        cls._periodic_gc()
        
        if current_time - _last_cache_cleanup > 300:
            if len(cls._regex_cache) > 200:
                cls._regex_cache.clear()
            if len(cls._handler_patterns_cache) > 200:
                cls._handler_patterns_cache.clear()
            _last_cache_cleanup = current_time
        
        _plugins_loaded = True
        return loaded_count + main_module_loaded
    
    @classmethod
    def _cleanup_deleted_files(cls):
        deleted_files = [fp for fp in cls._file_last_modified.keys() if not os.path.exists(fp)]
        for file_path in deleted_files:
            dir_name, module_name, _ = cls._extract_module_info(file_path)
            removed_count = cls._unregister_file_plugins(file_path)
            if file_path in cls._file_last_modified:
                del cls._file_last_modified[file_path]
            if removed_count > 0:
                add_framework_log(f"删除 {dir_name}/{module_name}.py，注销 {removed_count}")
    
    @classmethod
    def _periodic_gc(cls):
        global _last_plugin_gc_time
        current_time = time.time()
        if cls._unloaded_modules and (current_time - _last_plugin_gc_time >= _plugin_gc_interval):
            try:
                for module in cls._unloaded_modules[:]:
                    try:
                        for attr_name in list(dir(module)):
                            if not attr_name.startswith('__'):
                                try:
                                    delattr(module, attr_name)
                                except:
                                    pass
                        del module
                    except:
                        pass
                cls._unloaded_modules.clear()
                gc.collect()
            except:
                pass
            finally:
                _last_plugin_gc_time = current_time
    
    @classmethod
    def _import_main_module_instances(cls):
        loaded_count = 0
        for plugin_class in list(cls._plugins.keys()):
            if hasattr(plugin_class, 'import_from_main') and plugin_class.import_from_main:
                try:
                    module_name = plugin_class.__module__
                    if module_name.startswith('plugins.'):
                        module = sys.modules.get(module_name)
                        if module:
                            loaded_count += cls._register_module_instances(plugin_class, module)
                except Exception as e:
                    _log_error(f"导入主模块实例失败: {e}", traceback.format_exc())
        return loaded_count
    
    @classmethod
    def _register_module_instances(cls, plugin_class, module):
        loaded_count = 0
        for attr_name in dir(module):
            if attr_name.startswith('__'):
                continue
            try:
                attr = getattr(module, attr_name)
                if not isinstance(attr, type) and hasattr(attr, 'get_regex_handlers'):
                    handlers = cls._register_instance_handlers(plugin_class, attr)
                    if handlers > 0:
                        loaded_count += 1
            except Exception as e:
                _log_error(f"注册实例失败: {attr_name} - {e}", traceback.format_exc())
                try:
                    add_log_to_db('error', {
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'plugin_name': plugin_class.__name__,
                        'instance_name': attr_name,
                        'content': f"注册实例失败: {e}",
                        'traceback': traceback.format_exc()
                    })
                except:
                    pass
        return loaded_count

    @classmethod
    def _register_instance_handlers(cls, plugin_class, instance):
        def _register_handlers():
            handlers = instance.get_regex_handlers()
            if not handlers:
                return 0
            handlers_count = 0
            for pattern, handler_info in handlers.items():
                if isinstance(handler_info, str):
                    method_name = handler_info
                    owner_only = group_only = False
                else:
                    method_name = handler_info.get('handler')
                    owner_only = handler_info.get('owner_only', False)
                    group_only = handler_info.get('group_only', False)
                if not hasattr(instance, method_name):
                    continue
                def create_handler(inst, method):
                    def handler_method(event):
                        return getattr(inst, method)(event)
                    return handler_method
                unique_method_name = f"_instance_handler_{handlers_count}_{method_name}"
                setattr(plugin_class, unique_method_name, create_handler(instance, method_name))
                enhanced_pattern = cls._enhance_pattern(pattern)
                compiled_regex = cls._compile_and_cache_regex(enhanced_pattern)
                if not compiled_regex:
                    continue
                cls._regex_handlers[enhanced_pattern] = {
                    'class': plugin_class,
                    'handler': unique_method_name,
                    'owner_only': owner_only,
                    'group_only': group_only,
                    'original_pattern': pattern,
                    'from_instance': True,
                    'instance_method': method_name
                }
                handlers_count += 1
            return handlers_count
        return cls._safe_execute(_register_handlers, "注册实例失败: {error}") or 0

    @classmethod
    def _load_plugins_from_directory(cls, script_dir, dir_name):
        plugin_dir = os.path.join(script_dir, 'plugins', dir_name)
        if not os.path.exists(plugin_dir) or not os.path.isdir(plugin_dir):
            cls._unregister_directory_plugins(plugin_dir)
            return 0
        py_files = [f for f in os.listdir(plugin_dir) if f.endswith('.py') and f != '__init__.py']
        loaded_count = 0
        current_files = {os.path.join(plugin_dir, py_file) for py_file in py_files}
        cls._cleanup_directory_deleted_files(plugin_dir, current_files, dir_name)
        for py_file in py_files:
            file_path = os.path.join(plugin_dir, py_file)
            if os.path.exists(file_path):
                try:
                    last_modified = os.path.getmtime(file_path)
                    if file_path not in cls._file_last_modified or cls._file_last_modified[file_path] < last_modified:
                        cls._file_last_modified[file_path] = last_modified
                        loaded_count += cls._load_plugin_file(file_path, dir_name)
                except (OSError, IOError) as e:
                    _log_error(f"获取文件时间失败: {file_path}, {e}")
        return loaded_count
    
    @classmethod
    def _cleanup_directory_deleted_files(cls, plugin_dir, current_files, dir_name):
        dir_files_to_delete = []
        for file_path in list(cls._file_last_modified.keys()):
            if file_path.startswith(plugin_dir) and (file_path not in current_files or not os.path.exists(file_path)):
                dir_files_to_delete.append(file_path)
        for file_path in dir_files_to_delete:
            removed_count = cls._unregister_file_plugins(file_path)
            if file_path in cls._file_last_modified:
                del cls._file_last_modified[file_path]
            module_name = os.path.splitext(os.path.basename(file_path))[0]
            add_framework_log(f"删除 {dir_name}/{module_name}.py，注销 {removed_count}")
    
    @classmethod
    def _unregister_directory_plugins(cls, plugin_dir):
        removed_count = 0
        dir_files_to_delete = [fp for fp in cls._file_last_modified.keys() if fp.startswith(plugin_dir)]
        for file_path in dir_files_to_delete:
            removed_count += cls._unregister_file_plugins(file_path)
            if file_path in cls._file_last_modified:
                del cls._file_last_modified[file_path]
        if removed_count > 0:
            dir_name = os.path.basename(plugin_dir)
            add_framework_log(f"目录删除 {dir_name}，注销 {removed_count}")
        return removed_count

    @classmethod
    def _load_plugin_file(cls, plugin_file, dir_name):
        dir_name, module_name, module_fullname = cls._extract_module_info(plugin_file)
        plugin_name = os.path.basename(plugin_file)
        loaded_count = 0
        
        try:
            is_hot_reload = module_fullname in sys.modules
            cls._unregister_file_plugins(plugin_file)
            last_modified = os.path.getmtime(plugin_file)
            cls._file_last_modified[plugin_file] = last_modified
            old_module = sys.modules.get(module_fullname)
            if old_module:
                del sys.modules[module_fullname]
            spec = importlib.util.spec_from_file_location(module_fullname, plugin_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_fullname] = module
                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    if old_module:
                        sys.modules[module_fullname] = old_module
                    else:
                        del sys.modules[module_fullname]
                    raise e
                if old_module:
                    cls._unloaded_modules.append(old_module)
                loaded_count = cls._register_module_plugins(module, plugin_file, dir_name, plugin_name, is_hot_reload)
        except Exception as e:
            error_msg = f"插件{'热更新' if module_fullname in sys.modules else '加载'}: {dir_name}/{plugin_name} 失败: {e}"
            _log_error(error_msg, traceback.format_exc())
            try:
                add_log_to_db('error', {
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'plugin_name': plugin_name,
                    'plugin_file': plugin_file,
                    'content': error_msg,
                    'traceback': traceback.format_exc()
                })
            except:
                pass
        return loaded_count
    
    @classmethod
    def _register_module_plugins(cls, module, plugin_file, dir_name, plugin_name, is_hot_reload):
        loaded_count = 0
        plugin_load_results = []
        plugin_classes_found = False
        for attr_name in dir(module):
            if attr_name.startswith('__'):
                continue
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and attr.__module__ == module.__name__ and hasattr(attr, 'get_regex_handlers'):
                try:
                    plugin_classes_found = True
                    loaded_count += 1
                    attr._source_file = plugin_file
                    attr._is_hot_reload = True
                    handlers_count = cls.register_plugin(attr)
                    priority = getattr(attr, 'priority', 10)
                    plugin_load_results.append(f"{attr_name}(优先级:{priority},处理器:{handlers_count})")
                except Exception as e:
                    error_msg = f"插件 {attr_name} 注册失败: {e}"
                    plugin_load_results.append(f"{attr_name}(失败:{e})")
                    _log_error(error_msg, traceback.format_exc())
                    try:
                        add_log_to_db('error', {
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'plugin_name': attr_name,
                            'plugin_file': plugin_file,
                            'content': error_msg,
                            'traceback': traceback.format_exc()
                        })
                    except:
                        pass
        if plugin_classes_found:
            status = "热更新" if is_hot_reload else "加载"
            if plugin_load_results:
                add_framework_log(f"{status}: {dir_name}/{plugin_name} - {', '.join(plugin_load_results)}")
            else:
                add_framework_log(f"{status}: {dir_name}/{plugin_name}")
        else:
            add_framework_log(f"{dir_name}/{plugin_name} 无有效插件类")
        return loaded_count

    @classmethod
    def _unregister_file_plugins(cls, plugin_file):
        dir_name, module_name, module_fullname = cls._extract_module_info(plugin_file)
        removed = []
        plugin_classes_to_remove = []
        for pattern, handler_info in list(cls._regex_handlers.items()):
            try:
                plugin_class = handler_info.get('class') if isinstance(handler_info, dict) else handler_info[0]
                if hasattr(plugin_class, '_source_file') and plugin_class._source_file == plugin_file:
                    removed.append((plugin_class.__name__, pattern))
                    if plugin_class not in plugin_classes_to_remove:
                        plugin_classes_to_remove.append(plugin_class)
            except Exception as e:
                _log_error(f"查找插件类错误: {e}", traceback.format_exc())
        for pattern, handler_info in list(cls._regex_handlers.items()):
            try:
                plugin_class = handler_info.get('class') if isinstance(handler_info, dict) else handler_info[0]
                if plugin_class in plugin_classes_to_remove:
                    del cls._regex_handlers[pattern]
                    if pattern in cls._regex_cache:
                        del cls._regex_cache[pattern]
            except Exception as e:
                _log_error(f"清理处理器错误: {e}", traceback.format_exc())
        for route_path, route_info in list(cls._web_routes.items()):
            try:
                plugin_class = route_info.get('class')
                if plugin_class in plugin_classes_to_remove:
                    del cls._web_routes[route_path]
                    add_framework_log(f"注销Web: {route_path}")
            except Exception as e:
                _log_error(f"清理Web路由错误: {e}", traceback.format_exc())
        for api_path, api_info in list(cls._api_routes.items()):
            try:
                plugin_class = api_info.get('class')
                if plugin_class in plugin_classes_to_remove:
                    del cls._api_routes[api_path]
                    add_framework_log(f"注销API: {api_path}")
            except Exception as e:
                _log_error(f"清理API路由错误: {e}", traceback.format_exc())
        for plugin_class in plugin_classes_to_remove:
            cls._cleanup_plugin_class(plugin_class)
        if module_fullname != "unknown" and module_fullname in sys.modules:
            cls._cleanup_module(module_fullname, os.path.exists(plugin_file))
        return len(removed)
    
    @classmethod
    def _cleanup_plugin_class(cls, plugin_class):
        try:
            if plugin_class in cls._plugins:
                del cls._plugins[plugin_class]
            cls._cleanup_resources(plugin_class, f"插件清理：{plugin_class.__name__}")
            for attr_name in dir(plugin_class):
                if not attr_name.startswith('__'):
                    try:
                        attr = getattr(plugin_class, attr_name)
                        if not isinstance(attr, type):
                            cls._cleanup_resources(attr, f"插件清理：{plugin_class.__name__}.{attr_name}")
                    except:
                        pass
        except Exception as e:
            _log_error(f"清理插件类错误: {e}", traceback.format_exc())
    
    @classmethod
    def _cleanup_module(cls, module_fullname, file_exists):
        try:
            module = sys.modules[module_fullname]
            cls._cleanup_resources(module, f"模块清理：{module_fullname}")
            for attr_name in dir(module):
                if not attr_name.startswith('__'):
                    try:
                        attr = getattr(module, attr_name)
                        if not isinstance(attr, type):
                            cls._cleanup_resources(attr, f"模块清理：{module_fullname}.{attr_name}")
                    except:
                        pass
            cls._unloaded_modules.append(module)
            if module_fullname in sys.modules:
                del sys.modules[module_fullname]
        except Exception as e:
            _log_error(f"清理模块错误: {e}", traceback.format_exc())

    @classmethod 
    def _rebuild_sorted_handlers(cls):
        handlers_with_priority = []
        
        for pattern, handler_info in cls._regex_handlers.items():
            plugin_class = handler_info.get('class')
            priority = cls._plugins.get(plugin_class, 10)
            
            handlers_with_priority.append({
                'pattern': pattern,
                'handler_info': handler_info,
                'priority': priority
            })
        
        cls._sorted_handlers = sorted(handlers_with_priority, key=lambda x: x['priority'])
    
    @classmethod
    def _rebuild_handler_patterns_cache(cls):
        cls._handler_patterns_cache.clear()
        
        for i, handler_data in enumerate(cls._sorted_handlers):
            pattern = handler_data['pattern']
            handler_info = handler_data['handler_info']
            priority = handler_data['priority']
            
            compiled_regex = cls._regex_cache.get(pattern)
            if not compiled_regex:
                compiled_regex = cls._compile_and_cache_regex(pattern)
                if not compiled_regex:
                    continue
            
            handler_key = f"{priority}_{i}_{pattern}"
            cls._handler_patterns_cache[handler_key] = {
                'regex': compiled_regex,
                'handler_info': handler_info,
                'priority': priority,
                'pattern': pattern
            }

    # === 插件注册 ===
    @classmethod
    def register_plugin(cls, plugin_class, skip_log=False):
        priority = getattr(plugin_class, 'priority', 10)
        cls._plugins[plugin_class] = priority
        handlers = plugin_class.get_regex_handlers()
        handlers_count = 0
        
        for pattern, handler_info in handlers.items():
            if isinstance(handler_info, str):
                handler_name = handler_info
                owner_only = group_only = False
            else:
                handler_name = handler_info.get('handler')
                owner_only = handler_info.get('owner_only', False)
                group_only = handler_info.get('group_only', False)
                
            enhanced_pattern = cls._enhance_pattern(pattern)
            compiled_regex = cls._compile_and_cache_regex(enhanced_pattern)
            if not compiled_regex:
                continue
                
            cls._regex_handlers[enhanced_pattern] = {
                'class': plugin_class,
                'handler': handler_name,
                'owner_only': owner_only,
                'group_only': group_only,
                'original_pattern': pattern
            }
            handlers_count += 1
        
        # 检查并注册web路由
        if hasattr(plugin_class, 'get_web_routes') and callable(getattr(plugin_class, 'get_web_routes')):
            try:
                web_route_info = plugin_class.get_web_routes()
                if web_route_info and isinstance(web_route_info, dict):
                    route_path = web_route_info.get('path')
                    if route_path:
                        cls._web_routes[route_path] = {
                            'class': plugin_class,
                            'menu_name': web_route_info.get('menu_name', route_path),
                            'menu_icon': web_route_info.get('menu_icon', 'bi-puzzle'),
                            'description': web_route_info.get('description', ''),
                            'handler': web_route_info.get('handler', 'render_page'),
                            'priority': web_route_info.get('priority', 100)
                        }
                        add_framework_log(f"插件 {plugin_class.__name__} 注册Web路由: {route_path}")
                        
                        # 检查并注册API路由
                        api_routes = web_route_info.get('api_routes', [])
                        if api_routes and isinstance(api_routes, list):
                            for api_route in api_routes:
                                api_path = api_route.get('path')
                                if api_path:
                                    cls._api_routes[api_path] = {
                                        'class': plugin_class,
                                        'handler': api_route.get('handler'),
                                        'methods': api_route.get('methods', ['GET']),
                                        'require_auth': api_route.get('require_auth', True),
                                        'require_token': api_route.get('require_token', True)
                                    }
                                    add_framework_log(f"插件 {plugin_class.__name__} 注册API路由: {api_path}")
            except Exception as e:
                _log_error(f"注册Web路由失败: {plugin_class.__name__} - {str(e)}", traceback.format_exc())
        
        cls._rebuild_sorted_handlers()
        cls._handler_patterns_cache.clear()
        return handlers_count

    # === 消息分发 ===
    @classmethod
    def dispatch_message(cls, event):
        try:
            cls.load_plugins()
            
            if hasattr(event, 'handled') and event.handled:
                return True
                
            is_owner = event.user_id in OWNER_IDS
            is_group = cls._is_group_chat(event)
            
            result = cls._process_message(event, is_owner, is_group)
            return result
            
        except Exception as e:
            error_msg = f"消息分发处理失败: {str(e)}"
            error_trace = traceback.format_exc()
            _log_error(error_msg, error_trace)
            
            # 记录到数据库
            try:
                add_log_to_db('error', {
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'user_id': getattr(event, 'user_id', ''),
                    'group_id': getattr(event, 'group_id', 'c2c'),
                    'message_content': getattr(event, 'content', '')[:500],
                    'content': error_msg,
                    'traceback': error_trace
                })
            except:
                pass
            
            return False

    @classmethod
    def _process_message(cls, event, is_owner, is_group):
        permission_denied = {'owner_denied': False, 'group_denied': False}
        matched_handlers = cls._find_matched_handlers(
            event.content, event, is_owner, is_group, permission_denied
        )
        
        if matched_handlers:
            return cls._execute_handlers(event, matched_handlers)
        
        return cls._handle_unmatched_message(event, permission_denied, event.content)
    
    @classmethod
    def _handle_unmatched_message(cls, event, permission_denied, original_content):
        return False

    @classmethod
    def _find_matched_handlers(cls, event_content, event, is_owner, is_group, permission_denied=None):
        matched_handlers = []
        
        if not cls._handler_patterns_cache:
            cls._rebuild_handler_patterns_cache()
        
        for handler_key, handler_cache in cls._handler_patterns_cache.items():
            compiled_regex = handler_cache['regex']
            handler_info = handler_cache['handler_info']
            priority = handler_cache['priority']
            pattern = handler_cache['pattern']
            
            match = compiled_regex.search(event_content)
            if not match:
                continue
            
            has_permission, deny_reason = cls._check_permissions(handler_info, is_owner, is_group)
            
            if not has_permission:
                if permission_denied is not None:
                    permission_denied[deny_reason] = True
                continue
                
            matched_handlers.append({
                'pattern': pattern,
                'match': match,
                'plugin_class': handler_info.get('class'),
                'handler_name': handler_info.get('handler'),
                'priority': priority
            })
            
        return matched_handlers

    @classmethod
    def _execute_handlers(cls, event, matched_handlers, original_content=None):
        matched = False
        
        for handler in matched_handlers:
            plugin_class = handler['plugin_class']
            handler_name = handler['handler_name']
            match = handler['match']
            plugin_name = plugin_class.__name__
            
            try:
                event.matches = match.groups()
                result = cls._call_plugin_handler_with_logging(plugin_class, handler_name, event, plugin_name)
                matched = True
                
                if result is not True:
                    break
            except Exception as e:
                error_msg = f"插件 {plugin_class.__name__} 处理消息时出错：{str(e)}"
                error_trace = traceback.format_exc()
                _log_error(error_msg, error_trace)
                
                # 记录详细的错误信息到数据库
                try:
                    add_log_to_db('error', {
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'plugin_name': plugin_class.__name__,
                        'handler_name': handler_name,
                        'user_id': getattr(event, 'user_id', ''),
                        'group_id': getattr(event, 'group_id', 'c2c'),
                        'message_content': getattr(event, 'content', '')[:500],
                        'content': error_msg,
                        'traceback': error_trace
                    })
                except:
                    pass
                    
                matched = True
                break
        
        return matched

    @classmethod
    def _is_group_chat(cls, event):
        if event.event_type in ["GROUP_AT_MESSAGE_CREATE", "AT_MESSAGE_CREATE", "GROUP_MESSAGE"]:
            return True
        elif event.event_type == "INTERACTION_CREATE":
            chat_type = event.get('d/chat_type') if hasattr(event, 'get') else None
            if chat_type is not None:
                return chat_type == 1
            scene = event.get('d/scene') if hasattr(event, 'get') else None
            if scene is not None:
                return scene == 'group'
            if hasattr(event, 'is_group'):
                return event.is_group
            if hasattr(event, 'group_id') and event.group_id and event.group_id != "c2c":
                return True
            return False
        elif hasattr(event, 'is_group'):
            return event.is_group
        elif hasattr(event, 'group_id') and event.group_id and event.group_id != "c2c":
            return True
        return False

    @classmethod
    def _call_plugin_handler_with_logging(cls, plugin_class, handler_name, event, plugin_name):
        global _plugin_executor
        
        original_methods = {
            'reply': event.reply,
            'reply_image': getattr(event, 'reply_image', None),
            'reply_voice': getattr(event, 'reply_voice', None),
            'reply_video': getattr(event, 'reply_video', None),
            'reply_ark': getattr(event, 'reply_ark', None)
        }
        
        is_first_reply = [True]
        wrapped_methods = cls._create_method_logger(original_methods, plugin_name, is_first_reply, event)
        
        for method_name, wrapped_method in wrapped_methods.items():
            if wrapped_method:
                setattr(event, method_name, wrapped_method)
        
        try:
            handler = getattr(plugin_class, handler_name)
            
            def execute_handler():
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_closed():
                                raise RuntimeError()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(result)
                        finally:
                            try:
                                loop.close()
                            except:
                                pass
                    return result
                except Exception as e:
                    # 捕获插件内部的所有错误并推送到前台
                    error_msg = f"插件 {plugin_name} 执行异常: {str(e)}"
                    error_trace = traceback.format_exc()
                    _log_error(error_msg, error_trace)
                    
                    # 同时记录到数据库以便查询
                    try:
                        add_log_to_db('error', {
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'plugin_name': plugin_name,
                            'handler_name': handler_name,
                            'user_id': getattr(event, 'user_id', ''),
                            'group_id': getattr(event, 'group_id', 'c2c'),
                            'content': error_msg,
                            'traceback': error_trace
                        })
                    except:
                        pass
                    
                    return False
            
            future = _plugin_executor.submit(execute_handler)
            
            try:
                from concurrent.futures import TimeoutError
                result = future.result(timeout=3.0)
                return result
            except TimeoutError:
                # 插件执行超时，直接返回不记录
                return True
                
        finally:
            for method_name, original_method in original_methods.items():
                if original_method:
                    setattr(event, method_name, original_method)
    
    @classmethod
    def _create_method_logger(cls, original_methods_dict, plugin_name, is_first_reply, event):
        def _create_logged_method(original_method, method_name):
            def logged_method(*args, **kwargs):
                content_extractors = {
                    'reply': lambda a, k: a[0] if a else k.get('content', ''),
                    'reply_image': lambda a, k: f"[图片] {a[1] if len(a) > 1 else k.get('content', '')}".strip(),
                    'reply_voice': lambda a, k: f"[语音] {a[1] if len(a) > 1 else k.get('content', '')}".strip(),
                    'reply_video': lambda a, k: f"[视频] {a[1] if len(a) > 1 else k.get('content', '')}".strip(),
                    'reply_ark': lambda a, k: f"[ARK] {a[0] if a else k.get('template_id', '')}"
                }
                
                extractor = content_extractors.get(method_name)
                text_content = extractor(args, kwargs) if extractor else f"[{method_name}]"
                if method_name == 'reply' and not isinstance(text_content, str):
                    text_content = "[非文本内容]"
                user_id = getattr(event, 'user_id', '')
                group_id = getattr(event, 'group_id', 'c2c')
                add_plugin_log(text_content, user_id=user_id, group_id=group_id, plugin_name=plugin_name)
                if is_first_reply[0]:
                    is_first_reply[0] = False
                return original_method(*args, **kwargs)
            return logged_method
        wrapped_methods = {}
        for method_name, original_method in original_methods_dict.items():
            if original_method:
                wrapped_methods[method_name] = _create_logged_method(original_method, method_name)
        
        return wrapped_methods
    
    @classmethod
    def get_web_routes(cls):
        sorted_routes = sorted(cls._web_routes.items(), key=lambda x: x[1].get('priority', 100))
        return {path: info for path, info in sorted_routes}
    
    @classmethod
    def get_api_routes(cls):
        return cls._api_routes.copy() 