<p>
<img src="https://download.nature.qq.com/SnsShare/SocialProfile/1779098988_1264b08a.png" width="200" align="left" style="border-radius:50%; margin-right:16px" />

<h1>ElainaBot OneBot</h1>

ElainaBot OneBot 是一个基于 Python 的 QQ 机器人框架，采用 **OneBot v11** 协议标准，纯异步架构，支持 NapCat / LLOneBot / go-cqhttp 等多种 OneBot 实现，具备插件热重载、模块化扩展、插件市场、Web 面板管理等特性。

[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![QQ群](https://img.shields.io/badge/QQ交流群-631348711-blue)](https://qm.qq.com/q/qSErOcGf2o)

- **纯异步架构** — 基于 aiohttp，反向/正向 WebSocket 与 HTTP 多种接入方式
- **插件市场** — 基于 GitHub 插件库，一键浏览、安装、更新插件
- **Web 管理面板** — 实时日志、系统监控、插件管理、配置编辑、网络连接管理

</p>
<br clear="left" />

> 项目仅供学习交流使用，严禁用于任何商业用途和非法行为。

## 📢 交流群

**Elaina Bot 框架交流群：[631348711](https://qm.qq.com/q/qSErOcGf2o)**

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Git
- NapCat / LLOneBot / go-cqhttp 等任意 OneBot v11 实现

### 安装

```bash
git clone https://github.com/lengxi-root/ElainaBot-Onebot.git
cd ElainaBot-Onebot
pip install -r requirements.txt
python main.py
```

首次启动会自动从 `config/*.example.yaml` 生成 `config/settings.yaml` 与 `config/connections.yaml`。配置文件均支持**热加载**，修改后无需重启。

启动后访问 Web 面板完成配置：

```
http://localhost:5201/web/?token=admin
```

> 默认端口 `5201`、令牌 `admin`，可在 `config/settings.yaml` 的 `server` / `web` 区块修改。主人 QQ 号填在 `owner.ids`。

### 连接 OneBot 实现

框架在主服务端口内置反向 WS 入口 `/OneBotv11`，在 NapCat / LLOneBot 中把**反向 WebSocket 客户端**指向：

```
ws://127.0.0.1:5201/OneBotv11
```

也可在 Web 面板「网络配置」页面可视化添加反向 WS、正向 WS、HTTP 上报 / HTTP 客户端等连接，每条连接可单独配置 `token` / `secret`。

## 🌐 Web 管理面板

启动框架后访问：

```
http://localhost:5201/web/?token=<access_token>
```

面板提供：实时消息与日志、系统状态监控、插件启停/热重载、插件市场、配置编辑、网络连接管理等。

## 📁 框架结构

```
ElainaBot-Onebot/
├── main.py          # 主程序入口
├── config/          # 配置文件 (settings.yaml / connections.yaml)
├── core/            # 核心框架
│   ├── base/        #   配置、日志、上下文
│   ├── onebot/      #   OneBot v11 适配器 / API / 连接
│   ├── plugin/      #   插件加载、分发、热重载、装饰器
│   ├── module/      #   模块系统
│   ├── server/      #   HTTP / WS 服务器
│   └── storage/     #   日志数据库等存储
├── plugins/         # 插件目录 (热加载)
└── web/             # Web 面板 (后端 + 前端 dist)
```

## 🔌 插件开发

详见 **[插件开发文档 (PLUGIN_DEVELOPMENT.md)](PLUGIN_DEVELOPMENT.md)** — 包含完整的装饰器、Event 事件对象、OneBot 消息发送 API、插件上下文、元数据、Web 面板扩展等参考。

最简插件 `plugins/hello/main.py`：

```python
from core.plugin.decorators import handler


@handler(r'^你好$', name='打招呼', desc='回复一句问候')
async def say_hello(event, match):
    await event.reply("你好!")
```

## 🛒 插件市场

框架内置插件市场，从 [ElainaCore/Elaina-plugins](https://github.com/ElainaCore/Elaina-plugins) 获取插件列表。

- **Web 面板** — 在线浏览、搜索、一键安装/更新
- **镜像加速** — 自动选用可用的 GitHub 镜像下载

**插件开发者** 可前往 [Elaina-plugins](https://github.com/ElainaCore/Elaina-plugins) 提交 PR，将你的插件加入市场。

## 📄 开源协议

本项目采用 MIT 协议开源，详见 [LICENSE](LICENSE) 文件。

## ⚠️ 免责声明

本项目仅供学习交流使用，使用本框架所产生的一切后果由使用者自行承担，与开发者无关。请勿将本框架用于任何违法违规用途。

---

<div align="center">

**如果这个项目对你有帮助，请给个 Star ⭐️**

Made with ❤️ by Elaina Bot Team

</div>
