# astrbot_plugin_actions 快捷指令动作

这个插件用于把特定触发词映射成单次无上下文的对话，而不是进入默认大模型对话。

适合配置这类能力：

- 生图
- 嵌字翻译
- 总结文本
- 固定格式改写

## 工作方式

当消息命中某条已配置指令后：

1. 插件会拦截这条消息，不再进入默认 LLM 对话。
2. 按配置选择 Provider、提示词和模式执行。
3. 如果返回结构化结果，优先发送图片或文件。

## 示例

### 生图

可参考下面这组配置：

- `command`: `生图`
- `model`: `google_gemini/gemini-3.1-flash-image-preview`
- `enabled`: `true`
- `triggerType`: `prefix`
- `chatMode`: `chat`
- `promptType`: `instruction`
- `preset`: 留空
- `prompt`: 留空，或按需填写风格约束
- `inputPrompt`: `{input}`
- `allowExecuteWithoutMessage`: `false`
- `requireImage`: `false`
- `waitForImage`: `true`
- `waitForImageTimeout`: `60`
- `maxSteps`: `12`
- `toolCallTimeout`: `120`

发送示例：

- `生图 make a cherry blossom picture`
- `生图 画一张樱花小路的春日风景图`
- `生图 将这张图变成晚上（这里可以附加要变更的图片）`

### 嵌字翻译

可参考下面这组配置：

- `command`: `嵌字翻译`
- `model`: `google_gemini/gemini-3.1-flash-image-preview`
- `enabled`: `true`
- `triggerType`: `prefix`
- `chatMode`: `chat`
- `promptType`: `instruction`
- `preset`: 留空
- `prompt`: `你是一个翻译嵌字助手，你需要将我发送的所有图片上的文字都翻译成中文，并嵌入回原位置进行替换，并保留字体和样式。只返回图片即可。`
- `inputPrompt`: `{input}`
- `allowExecuteWithoutMessage`: `true`
- `requireImage`: `true`
- `waitForImage`: `true`
- `waitForImageTimeout`: `60`
- `maxSteps`: `12`
- `toolCallTimeout`: `0` 或按你的 Provider 需求设置

推荐用法：

- 直接发送图片并附带 `嵌字翻译`
- 或先发送 `嵌字翻译`，再在等待时间内补发图片

## 主要配置项

- `command`: 触发词或正则表达式
- `model`: 执行该指令的 Provider
- `triggerType`: `prefix` 或 `regex`
- `chatMode`: `chat` 或 `agent`
- `promptType`: `instruction` 或 `preset`
- `prompt`: 自定义提示词
- `inputPrompt`: 输入模板，使用 `{input}` 占位
- `allowExecuteWithoutMessage`: 是否允许空文本触发
- `requireImage`: 是否要求消息中至少包含一张图片
- `waitForImage`: 缺少图片时是否等待补图
- `waitForImageTimeout`: 等待补图的秒数，默认 `60`
- `maxSteps`: Agent 模式最大工具循环步数
- `toolCallTimeout`: Agent 模式工具调用超时秒数

## 图片相关说明

如果启用了 `requireImage`：

- 当前消息带图时，直接执行
- 当前消息不带图且 `waitForImage=true` 时，会提示用户在指定秒数内补图
- 当前消息不带图且 `waitForImage=false` 时，会直接提示“请直接附带图片发送”

## 已知限制

### 引用图片

部分平台无法从“引用的上一条消息”里回查图片。建议：

- 把图片和指令放在同一条消息发送
- 或先发指令，再在等待时间内单独补发图片

### 补图等待会消费下一条消息

如果进入补图等待状态，下一条消息会优先被当作补图处理。
如果它不是图片，会直接取消本次等待，这条消息不会再继续进入默认对话或其他指令。
