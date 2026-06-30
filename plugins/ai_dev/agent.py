"""ai_dev Agent — OpenAI 兼容接口的工具调用循环

通过 aiohttp 调用 /chat/completions, 支持多轮 function-calling:
模型请求工具 -> 本地执行 -> 把结果回灌 -> 直到模型给出最终回答。
每一步都会写入 AIStore 并广播到 Web 面板 (完整调用 + 完整日志)。
"""

import asyncio
import json
import time

import aiohttp

from plugins.ai_dev import aiconfig
from plugins.ai_dev import tools as toolmod

SYSTEM_PROMPT = """你是 ElainaBot OneBot 框架内置的 AI 开发助手, 运行在框架进程内, 拥有一组工具来直接操作本框架的代码与配置。

框架要点:
- 这是基于 OneBot v11 的异步 QQ 机器人框架 (Python, aiohttp)。
- 插件位于 plugins/<名字>/ 目录, 每个插件是一个目录。普通插件可放多个 .py (文件名不以 _ 开头且不叫 main/app/index);
  大型插件用 main.py / app.py / index.py 作为入口。
- 插件用装饰器注册: 从 core.plugin.decorators 导入 handler / on_load / on_unload / interceptor。
  处理器签名为 async def fn(event, match), 用 await event.reply('文本') 回复。
  例: @handler(r'^ping$', name='ping', desc='测试') ; async def h(event, match): await event.reply('pong')
- 修改或新建插件后, 调用 reload_plugin 工具热重载并检查 error 字段与 handler 数来自测。
- 配置在 config/settings.yaml, 通过 get_config / set_config 读写。

工作准则:
1. 动手前可先用 list_dir / read_file / list_plugins 了解现状, 参考 plugins/example/main.py 的写法。
2. 编写插件用 write_file 写完整文件; 改完务必 reload_plugin 自测, 若 error 非空则读取报错并修复后重试。
3. 操作要谨慎, 不要删除或破坏用户已有的插件与核心代码 (core/ web/ 等), 除非用户明确要求。
4. 用中文简洁回复, 最终说明你做了什么、文件路径、以及测试结果。
"""


class OpenAIError(Exception):
    pass


async def _chat_completion(session: aiohttp.ClientSession, messages: list, model: str) -> dict:
    url = aiconfig.base_url() + '/chat/completions'
    payload = {
        'model': model,
        'messages': messages,
        'tools': toolmod.TOOLS_SCHEMA,
        'tool_choice': 'auto',
        'temperature': aiconfig.temperature(),
    }
    headers = {
        'Authorization': f'Bearer {aiconfig.api_key()}',
        'Content-Type': 'application/json',
    }
    timeout = aiohttp.ClientTimeout(total=aiconfig.request_timeout())
    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
        text = await resp.text()
        if resp.status != 200:
            raise OpenAIError(f'HTTP {resp.status}: {text[:500]}')
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise OpenAIError(f'返回非 JSON: {text[:500]}') from e


def _build_messages(history: list, user_text: str, model_prompt: str) -> list:
    messages = []
    sys_prompt = model_prompt or SYSTEM_PROMPT
    if not history or history[0].get('role') != 'system':
        messages.append({'role': 'system', 'content': sys_prompt})
    messages.extend(history)
    messages.append({'role': 'user', 'content': user_text})
    return messages


async def run_agent(store, session_id: str, user_text: str, model: str = '') -> dict:
    """执行一轮多步 Agent 对话。返回 {ok, message, iterations}。

    过程中向 store 写入事件: user / assistant / tool_call / tool_result / error / info
    """
    if not aiconfig.is_configured():
        store.add_event('error', {'message': '未配置 AI api_key (settings.yaml 的 ai.api_key 或环境变量 AI_DEV_API_KEY)'}, session_id)
        return {'ok': False, 'message': '未配置 api_key', 'iterations': 0}

    model = model or aiconfig.model()
    history = store.get_messages(session_id)
    sys_override = aiconfig.system_prompt()
    messages = _build_messages([m for m in history if m.get('role') != 'system'], user_text, sys_override)

    store.add_event('user', {'content': user_text, 'model': model}, session_id)

    max_iter = aiconfig.max_iterations()
    final_text = ''
    async with aiohttp.ClientSession() as session:
        for iteration in range(1, max_iter + 1):
            try:
                resp = await _chat_completion(session, messages, model)
            except (OpenAIError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                store.add_event('error', {'message': f'模型调用失败: {e}'}, session_id)
                return {'ok': False, 'message': str(e), 'iterations': iteration}

            choice = (resp.get('choices') or [{}])[0]
            msg = choice.get('message') or {}
            tool_calls = msg.get('tool_calls') or []
            usage = resp.get('usage') or {}

            # 把助手这一步的消息加入上下文
            assistant_msg = {'role': 'assistant', 'content': msg.get('content') or ''}
            if tool_calls:
                assistant_msg['tool_calls'] = tool_calls
            messages.append(assistant_msg)

            if not tool_calls:
                final_text = msg.get('content') or ''
                store.add_event('assistant', {
                    'content': final_text,
                    'iteration': iteration,
                    'usage': usage,
                    'model': resp.get('model', model),
                }, session_id)
                break

            # 执行所有工具调用
            for tc in tool_calls:
                fn = tc.get('function') or {}
                name = fn.get('name', '')
                raw_args = fn.get('arguments') or '{}'
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                store.add_event('tool_call', {
                    'id': tc.get('id'),
                    'name': name,
                    'arguments': args,
                    'iteration': iteration,
                }, session_id)

                start = time.time()
                try:
                    result = await toolmod.run_tool(name, args)
                    ok = True
                except Exception as e:  # noqa: BLE001 — 工具错误需回灌给模型
                    result = {'error': f'{type(e).__name__}: {e}'}
                    ok = False
                duration_ms = int((time.time() - start) * 1000)

                store.add_event('tool_result', {
                    'id': tc.get('id'),
                    'name': name,
                    'ok': ok,
                    'duration_ms': duration_ms,
                    'result': result,
                }, session_id)

                messages.append({
                    'role': 'tool',
                    'tool_call_id': tc.get('id'),
                    'name': name,
                    'content': json.dumps(result, ensure_ascii=False, default=str)[:12000],
                })
        else:
            final_text = final_text or '(已达到最大迭代步数, 任务可能未完成)'
            store.add_event('assistant', {'content': final_text, 'iteration': max_iter, 'truncated': True}, session_id)

    # 持久化对话历史 (剔除 system, 由下次重建)
    new_history = [m for m in messages if m.get('role') != 'system']
    store.set_messages(session_id, new_history)
    return {'ok': True, 'message': final_text, 'iterations': iteration}
