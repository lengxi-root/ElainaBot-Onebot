#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, platform, subprocess, psutil, time, threading
from datetime import datetime


def execute_bot_restart(restart_status=None):
    current_pid = os.getpid()
    current_dir = os.getcwd()
    main_py_path = os.path.join(current_dir, 'main.py')
    
    if not os.path.exists(main_py_path):
        return {'success': False, 'error': 'main.py文件不存在！'}
    
    def _get_restart_status_file():
        plugin_dir = os.path.join(current_dir, 'plugins', 'system')
        data_dir = os.path.join(plugin_dir, 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        return os.path.join(data_dir, 'restart_status.json')
    
    if restart_status is None:
        restart_status = {
            'restart_time': datetime.now().isoformat(),
            'completed': False,
            'message_id': None,
            'user_id': 'web_admin',
            'group_id': 'web_panel'
        }
    
    restart_status_file = _get_restart_status_file()
    with open(restart_status_file, 'w', encoding='utf-8') as f:
        json.dump(restart_status, f, ensure_ascii=False)
    
    def _create_restart_python_script(main_py_path):
        is_windows = platform.system().lower() == 'windows'
        
        if is_windows:
            script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess

def main():
    main_py_path = r"{main_py_path}"
    
    try:
        print("等待3秒后启动新进程...")
        time.sleep(3)
        
        os.chdir(os.path.dirname(main_py_path))
        print(f"正在重新启动主程序: {{main_py_path}}")
        
        subprocess.Popen(
            [sys.executable, main_py_path],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=os.path.dirname(main_py_path)
        )
        
        print("重启命令已执行")
        time.sleep(1)
        
        try:
            script_path = __file__
            if os.path.exists(script_path):
                os.remove(script_path)
        except:
            pass
        sys.exit(0)
        
    except Exception as e:
        print(f"重启失败: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        else:
            # Linux/Unix 重启脚本
            script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess

def main():
    main_py_path = r"{main_py_path}"
    
    try:
        print("等待1秒后启动新进程...")
        time.sleep(1)
        
        os.chdir(os.path.dirname(main_py_path))
        print(f"正在重新启动主程序: {{main_py_path}}")
        
        try:
            script_path = __file__
            if os.path.exists(script_path):
                os.remove(script_path)
        except:
            pass
        
        os.execv(sys.executable, [sys.executable, main_py_path])
        
    except Exception as e:
        print(f"重启失败: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
        
        return script_content
    
    try:
        restart_script_content = _create_restart_python_script(main_py_path)
        restart_script_path = os.path.join(current_dir, 'bot_restarter.py')
        
        with open(restart_script_path, 'w', encoding='utf-8') as f:
            f.write(restart_script_content)
        
        is_windows = platform.system().lower() == 'windows'
        
        if is_windows:
            subprocess.Popen([sys.executable, restart_script_path], cwd=current_dir,
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            def delayed_exit():
                time.sleep(1)
                os._exit(0)
            
            threading.Thread(target=delayed_exit, daemon=True).start()
            return {
                'success': True,
                'message': '🔄 正在重启机器人...\n⏱️ 主进程将在1秒后退出，新进程将在3秒后启动'
            }
        else:
            subprocess.Popen([sys.executable, restart_script_path], cwd=current_dir,
                           start_new_session=True)
            return {
                'success': True,
                'message': '🔄 正在重启机器人...\n⏱️ 预计重启时间: 1秒'
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

