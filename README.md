<div align="center">

# Elaina Bot Framework

Elaina 是一个基于 Python 的轻量级 QQ 机器人框架，采用 **OneBot v11** 协议标准，支持 NapCat、LLOneBot 等多种 OneBot 实现。


</div>

## ✨ 框架特性

- 🚀 **OneBot 协议**：完整支持 OneBot v11 标准，兼容多种 OneBot 实现
- 🔌 **插件化架构**：动态加载与热重载插件，支持插件独立配置
- 📊 **Web 管理面板**：实时监控系统状态、消息日志、插件管理
- 🔐 **安全鉴权**：支持 OneBot access_token 和 secret 签名验证
- 💾 **日志持久化**：SQLite 数据库存储消息记录，支持自动清理
- 🎨 **现代化界面**：Bootstrap 5 响应式设计，支持移动端访问
- 🔄 **消息实时显示**：WebSocket 推送，实时查看消息和日志
- 📝 **完整消息 API**：支持文本、图片、语音、视频等多种消息类型

项目仅供学习交流使用，严禁用于任何商业用途和非法行为

## 📢 交流群

如果你在使用过程中遇到问题或有任何建议，欢迎加入我们的交流群：

**Elaina Bot 框架交流群：[631348711](https://qm.qq.com/q/qSErOcGf2o)**

## 📦 快速开始

### 环境要求

- Python 3.9+
- NapCat / LLOneBot / go-cqhttp 等 OneBot 实现
- Windows / Linux / MacOS

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/lengxi-root/ElainaBot.git
cd ElainaBot
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置框架**

编辑 `config.py` 文件：

```python
# 服务器配置
SERVER_CONFIG = {
    'host': "0.0.0.0",
    'port': 5003,  # OneBot WebSocket + Web 面板统一端口
}

# Web面板安全配置
WEB_SECURITY = {
    'access_token': "your_token_here",  # Web面板访问令牌
    'admin_password': "your_password",   # 管理员密码
}

# OneBot 协议配置
ONEBOT_CONFIG = {
    'access_token': None,  # OneBot 连接鉴权 token（可选）
    'secret': None,        # OneBot 签名密钥（可选）
}
```

4. **启动框架**

```bash
python main.py
```

5. **配置 OneBot 实现**

在 NapCat/LLOneBot 配置中，设置 WebSocket 客户端：

```yaml
#请根据自身情况链接
ws://127.0.0.1:5003/OneBotv11
```

## 🌐 Web 管理面板

启动框架后，访问 Web 管理面板：

```
http://localhost:5003/web/?token=your_access_token
```

## 📂 项目结构

```
ElainaBot/
├── config.py                   # 全局配置文件
├── main.py                     # 主程序入口
├── requirements.txt            # 项目依赖
├── core/                       # 核心模块
│   ├── MessageEvent.py         # 消息事件处理
│   ├── PluginManager.py        # 插件管理器
│   └── onebot/                 # OneBot 协议实现
│       ├── adapter.py          # OneBot 适配器
│       ├── api.py              # OneBot API 封装
│       └── client.py           # WebSocket 客户端
├── function/                   # 工具函数库
│   ├── httpx_pool.py           # HTTP 连接池
│   └── log_db.py               # 日志数据库操作
├── plugins/                    # 插件目录
└── web/                        # Web 控制面板
    ├── app.py                  # Flask 应用主文件
    ├── templates/              # 页面模板
    │   └── pc/                 # PC 端页面
    └── static/                 # 静态资源
```
本项目采用 MIT 协议开源，详见 [LICENSE](LICENSE) 文件。

## ⚠️ 免责声明

本项目仅供学习交流使用，使用本框架所产生的一切后果由使用者自行承担，与开发者无关。请勿将本框架用于任何违法违规用途。

---

<div align="center">

**如果这个项目对你有帮助，请给个 Star ⭐️**

Made with ❤️ by Elaina Bot Team

</div>
