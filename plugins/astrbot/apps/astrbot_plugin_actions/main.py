from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlparse

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import File, Image, Reply
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register
from astrbot.api.util import SessionController, session_waiter
from astrbot.core.utils.quoted_message.image_refs import normalize_image_ref
from astrbot.core.utils.quoted_message_parser import extract_quoted_message_images


@register(
    "astrbot_plugin_actions",
    "teatube",
    "基于 AstrBot Provider 的可配置指令触发单次对话插件。参考自旧版 chatluna-actions",
    "1.0.0",
)
class ActionsPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.context = context
        self.config = config or {}

    @filter.command("actions")
    async def actions_help(self, event: AstrMessageEvent):
        """显示当前已配置的指令。"""
        event.stop_event()
        commands = self._enabled_commands()
        if not commands:
            yield event.plain_result("当前没有已配置的指令。")
            return

        trigger_type_labels = {
            "prefix": "前缀",
            "regex": "正则",
        }
        mode_labels = {
            "chat": "对话",
            "agent": "Agent",
        }

        lines = ["已启用指令："]
        for command in commands:
            trigger_type = str(command.get("triggerType", "prefix")).strip()
            trigger = str(command.get("command", "")).strip()
            mode = str(command.get("chatMode", "chat")).strip() or "chat"
            description = str(command.get("description", "")).strip()
            trigger_type_label = trigger_type_labels.get(trigger_type, trigger_type)
            mode_label = mode_labels.get(mode, mode)
            if description:
                lines.append(
                    f"- {trigger} [{trigger_type_label}/{mode_label}]：{trigger} | {description}"
                )
            else:
                lines.append(f"- {trigger} [{trigger_type_label}/{mode_label}]：{trigger}")
        yield event.plain_result("\n".join(lines))

    @filter.regex(r".*")
    async def dispatch_action(self, event: AstrMessageEvent):
        """根据配置的前缀或正则规则分发动作。"""
        message = event.get_message_str().strip()
        if not message:
            return

        matched = self._match_command(message)
        if not matched:
            return

        command, action_input = matched
        event.stop_event()
        image_urls = await self._collect_image_urls(event)
        logger.info(
            "Action `%s` collected %d image(s).",
            command.get("command", ""),
            len(image_urls),
        )
        if bool(command.get("requireImage", False)) and not image_urls:
            wait_timeout = self._get_wait_for_image_timeout(command)
            if bool(command.get("waitForImage", True)):
                yield event.plain_result(
                    f"这条指令需要图片，请在 {wait_timeout} 秒内发送下一条消息补图。"
                )
                await self._wait_for_image(
                    event,
                    command,
                    action_input,
                    wait_timeout=wait_timeout,
                )
            else:
                yield event.plain_result("这条指令需要图片，请直接附带图片发送。")
            return

        result = await self._run_command(event, command, action_input, image_urls)
        yield result

    def _enabled_commands(self) -> list[dict[str, Any]]:
        commands = self.config.get("commands")
        if not isinstance(commands, list):
            legacy_actions = self.config.get("actions", [])
            if not isinstance(legacy_actions, list):
                return []
            commands = [self._convert_legacy_action(item) for item in legacy_actions]

        result: list[dict[str, Any]] = []
        for command in commands:
            if not isinstance(command, dict):
                continue
            if not command.get("enabled", True):
                continue
            trigger = str(command.get("command", "")).strip()
            if not trigger:
                continue
            result.append(command)
        return result

    def _convert_legacy_action(self, action: dict[str, Any]) -> dict[str, Any]:
        return {
            "command": action.get("trigger", ""),
            "model": action.get("provider_id", ""),
            "enabled": action.get("enabled", True),
            "description": action.get("description", ""),
            "chatMode": action.get("mode", "chat"),
            "promptType": "instruction",
            "preset": "",
            "prompt": action.get("system_prompt", ""),
            "inputPrompt": action.get("input_template", "{input}"),
            "allowExecuteWithoutMessage": action.get("allow_empty_input", False),
            "triggerType": action.get("trigger_type", "prefix"),
            "requireImage": action.get("require_image", False),
            "waitForImage": action.get("wait_for_image", True),
            "waitForImageTimeout": action.get("wait_for_image_timeout", 60),
            "maxSteps": action.get("max_steps", 12),
            "toolCallTimeout": action.get("tool_call_timeout", 120),
        }

    def _match_command(self, message: str) -> tuple[dict[str, Any], str] | None:
        for command in self._enabled_commands():
            trigger_type = str(command.get("triggerType", "prefix")).strip().lower()
            trigger = str(command.get("command", "")).strip()
            if not trigger:
                continue

            if trigger_type == "regex":
                try:
                    matched = re.match(trigger, message, re.DOTALL)
                except re.error as exc:
                    logger.warning("指令正则配置无效 `%s`: %s", trigger, exc)
                    continue
                if not matched:
                    continue
                if matched.lastindex:
                    return command, (matched.group(1) or "").strip()
                return command, message.strip()

            if message == trigger:
                return command, ""
            if message.startswith(f"{trigger} "):
                return command, message[len(trigger) :].strip()
        return None

    async def _run_command(
        self,
        event: AstrMessageEvent,
        command: dict[str, Any],
        action_input: str,
        image_urls: list[str] | None = None,
    ):
        if not action_input and not bool(
            command.get("allowExecuteWithoutMessage", False)
        ):
            return event.plain_result("这个指令需要额外输入内容。")

        provider_id = await self._resolve_provider_id(event, command)
        if not provider_id:
            return event.plain_result("这个指令没有可用的模型提供商。")

        if image_urls is None:
            image_urls = await self._collect_image_urls(event)

        input_template = str(command.get("inputPrompt", "{input}") or "{input}")
        try:
            prompt = input_template.format(input=action_input)
        except Exception:
            prompt = action_input

        prompt_type = str(command.get("promptType", "instruction")).strip().lower()
        if prompt_type == "preset":
            system_prompt = str(command.get("preset", "") or "")
        else:
            system_prompt = str(command.get("prompt", "") or "")
        mode = str(command.get("chatMode", "chat")).strip().lower() or "chat"

        try:
            if mode == "agent":
                tool_set = self.context.get_llm_tool_manager().get_full_tool_set()
                response = await self.context.tool_loop_agent(
                    event=event,
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    image_urls=image_urls,
                    system_prompt=system_prompt,
                    tools=tool_set if not tool_set.empty() else None,
                    max_steps=int(command.get("maxSteps", 12) or 12),
                    tool_call_timeout=int(
                        command.get("toolCallTimeout", 120) or 120
                    ),
                )
            else:
                response = await self.context.llm_generate(
                    chat_provider_id=provider_id,
                    prompt=prompt,
                    image_urls=image_urls,
                    system_prompt=system_prompt,
                )
        except Exception as exc:
            logger.error("指令执行失败: %s", exc, exc_info=True)
            return event.plain_result(f"指令执行失败：{exc}")

        return self._response_to_result(event, response)

    async def _resolve_provider_id(
        self, event: AstrMessageEvent, command: dict[str, Any]
    ) -> str | None:
        provider_id = str(command.get("model", "") or "").strip()
        if provider_id:
            provider = self.context.get_provider_by_id(provider_id)
            if provider is not None:
                return provider_id
            logger.warning("未找到已配置的 Provider: %s", provider_id)

        try:
            return await self.context.get_current_chat_provider_id(
                event.unified_msg_origin
            )
        except Exception:
            return None

    async def _collect_image_urls(self, event: AstrMessageEvent) -> list[str]:
        image_urls: list[str] = []
        component_image_urls: list[str] = []
        for component in self._iter_message_components(event):
            ref = await self._resolve_component_image_ref(component)
            if ref:
                normalized_ref = normalize_image_ref(ref)
                if normalized_ref:
                    component_image_urls.append(normalized_ref)

        image_urls.extend(component_image_urls)
        quoted_image_urls: list[str] = []
        if not component_image_urls:
            try:
                quoted_image_urls = await extract_quoted_message_images(event)
            except Exception as exc:
                logger.warning("Failed to extract quoted message images: %s", exc)
            else:
                image_urls.extend(quoted_image_urls)

        raw_message_image_urls = self._collect_raw_message_image_urls(event)
        image_urls.extend(raw_message_image_urls)

        raw_message = getattr(getattr(event, "message_obj", None), "raw_message", None)
        raw_message_attrs: dict[str, Any] = {}
        raw_message_dict_keys: list[str] = []
        message_reference_attrs: dict[str, Any] = {}
        message_reference_keys: list[str] = []
        if raw_message is not None:
            raw_message_dict = getattr(raw_message, "__dict__", None)
            if isinstance(raw_message_dict, dict):
                raw_message_dict_keys = sorted(str(key) for key in raw_message_dict.keys())
            for attr in (
                "id",
                "content",
                "attachments",
                "message_reference",
                "reference",
                "referenced_message",
                "message_id",
                "msg_id",
            ):
                if hasattr(raw_message, attr):
                    value = getattr(raw_message, attr)
                    if isinstance(value, (str, int, float, bool)) or value is None:
                        raw_message_attrs[attr] = value
                    elif isinstance(value, list):
                        raw_message_attrs[attr] = f"list[{len(value)}]"
                    else:
                        raw_message_attrs[attr] = type(value).__name__

            message_reference = getattr(raw_message, "message_reference", None)
            if message_reference is not None:
                message_reference_dict = getattr(message_reference, "__dict__", None)
                if isinstance(message_reference_dict, dict):
                    message_reference_keys = sorted(
                        str(key) for key in message_reference_dict.keys()
                    )
                for attr in (
                    "message_id",
                    "id",
                    "ignore_get_message_error",
                    "content",
                    "attachments",
                    "url",
                ):
                    if hasattr(message_reference, attr):
                        value = getattr(message_reference, attr)
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            message_reference_attrs[attr] = value
                        elif isinstance(value, list):
                            message_reference_attrs[attr] = f"list[{len(value)}]"
                        else:
                            message_reference_attrs[attr] = type(value).__name__

        logger.info(
            "Action image extraction: components=%d quoted=%d raw_message=%d component_types=%s raw_message_type=%s raw_message_attrs=%s raw_message_keys=%s message_reference_attrs=%s message_reference_keys=%s",
            len(component_image_urls),
            len(quoted_image_urls),
            len(raw_message_image_urls),
            [type(component).__name__ for component in event.get_messages()],
            type(raw_message).__name__ if raw_message is not None else None,
            raw_message_attrs,
            raw_message_dict_keys,
            message_reference_attrs,
            message_reference_keys,
        )

        return self._dedupe_preserve_order(image_urls)

    def _iter_message_components(self, event: AstrMessageEvent) -> Iterable[Any]:
        message = getattr(getattr(event, "message_obj", None), "message", None)
        if isinstance(message, list):
            yield from self._flatten_message_components(message)
            return

        yield from event.get_messages()

    def _flatten_message_components(self, components: list[Any]) -> Iterable[Any]:
        for component in components:
            yield component
            if isinstance(component, Reply) and component.chain:
                yield from self._flatten_message_components(component.chain)

    def _collect_raw_message_image_urls(self, event: AstrMessageEvent) -> list[str]:
        raw_message = getattr(getattr(event, "message_obj", None), "raw_message", None)
        if raw_message is None:
            return []

        collected: list[str] = []
        self._walk_raw_message_for_images(raw_message, collected, seen=set(), depth=0)
        normalized: list[str] = []
        for ref in collected:
            normalized_ref = normalize_image_ref(ref)
            if normalized_ref:
                normalized.append(normalized_ref)
        return self._dedupe_preserve_order(normalized)

    def _walk_raw_message_for_images(
        self,
        value: Any,
        collected: list[str],
        *,
        seen: set[int],
        depth: int,
    ) -> None:
        if value is None or depth > 6:
            return

        value_id = id(value)
        if value_id in seen:
            return
        seen.add(value_id)

        if isinstance(value, str):
            if self._looks_like_image_ref(value):
                collected.append(value.strip())
            return

        if isinstance(value, dict):
            for item in value.values():
                self._walk_raw_message_for_images(item, collected, seen=seen, depth=depth + 1)
            return

        if isinstance(value, (list, tuple, set)):
            for item in value:
                self._walk_raw_message_for_images(item, collected, seen=seen, depth=depth + 1)
            return

        for attr in (
            "url",
            "file",
            "path",
            "filename",
            "content_type",
            "attachments",
            "attachment",
            "message_reference",
            "reference",
            "referenced_message",
            "message",
            "resolved",
            "data",
        ):
            if hasattr(value, attr):
                self._walk_raw_message_for_images(
                    getattr(value, attr),
                    collected,
                    seen=seen,
                    depth=depth + 1,
                )

        value_dict = getattr(value, "__dict__", None)
        if isinstance(value_dict, dict):
            self._walk_raw_message_for_images(value_dict, collected, seen=seen, depth=depth + 1)

    def _looks_like_image_ref(self, value: str) -> bool:
        candidate = value.strip()
        if not candidate:
            return False

        parsed = urlparse(candidate)
        path = parsed.path.lower() if parsed.path else candidate.lower()
        return path.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic"))

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _get_wait_for_image_timeout(self, command: dict[str, Any]) -> int:
        value = command.get("waitForImageTimeout", 60)
        try:
            return max(1, int(value))
        except Exception:
            return 60

    async def _resolve_component_image_ref(self, component: Any) -> str | None:
        if isinstance(component, Image):
            return await self._resolve_image_component(component)

        if isinstance(component, File):
            return await self._resolve_image_file_component(component)

        converter = getattr(component, "convert_to_file_path", None)
        if callable(converter):
            try:
                ref = await converter()
            except Exception:
                ref = None
            if isinstance(ref, str) and ref.strip():
                return ref.strip()

        return None

    def _response_to_result(self, event: AstrMessageEvent, response: LLMResponse):
        if response.result_chain:
            chain = list(response.result_chain.chain)
            image_or_file_chain = [
                component for component in chain if isinstance(component, (Image, File))
            ]
            if image_or_file_chain:
                return event.chain_result(image_or_file_chain)
            return event.chain_result(chain)
        return event.plain_result(response.completion_text or "")

    async def _resolve_image_component(self, component: Image) -> str | None:
        try:
            return await component.convert_to_file_path()
        except Exception as exc:
            logger.warning("图片转换本地路径失败，尝试回退原始引用: %s", exc)

        for attr in ("url", "file", "path"):
            value = getattr(component, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    async def _resolve_image_file_component(self, component: File) -> str | None:
        name = str(getattr(component, "name", "") or "").lower()
        file_path = str(getattr(component, "file_", "") or "").strip()
        url = str(getattr(component, "url", "") or "").strip()
        candidates = [name, file_path, url]
        image_exts = (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".bmp",
            ".heic",
        )
        if any(candidate.lower().endswith(image_exts) for candidate in candidates):
            if file_path:
                return file_path
            if url:
                return url
            try:
                downloaded = await component.get_file()
            except Exception:
                downloaded = ""
            return downloaded or None
        return None

    async def _wait_for_image(
        self,
        event: AstrMessageEvent,
        command: dict[str, Any],
        action_input: str,
        wait_timeout: int = 60,
    ):
        @session_waiter(wait_timeout)
        async def image_waiter(
            controller: SessionController,
            next_event: AstrMessageEvent,
        ) -> None:
            image_urls = await self._collect_image_urls(next_event)
            if not image_urls:
                logger.info(
                    "Action wait-for-image canceled, no image detected in next message. components=%s",
                    [type(component).__name__ for component in next_event.get_messages()],
                )
                next_event.set_result(
                    next_event.plain_result("没有检测到图片，已取消本次等待。")
                )
                next_event.stop_event()
                controller.stop()
                return

            result = await self._run_command(next_event, command, action_input, image_urls)
            next_event.set_result(result)
            next_event.stop_event()
            controller.stop()

        try:
            await image_waiter(event)
        except TimeoutError:
            pass
        except Exception as exc:
            logger.error("等待补图时发生错误: %s", exc, exc_info=True)
