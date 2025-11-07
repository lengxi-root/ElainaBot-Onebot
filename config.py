#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""QQ机器人配置文件 - OneBot 协议"""

# 基础配置
OWNER_IDS = ["2218872014"]  # 主人 QQ 号列表，用于权限控制（第一个将用于头像显示）

# 服务器配置
SERVER_CONFIG = {
    'host': "0.0.0.0",  # 服务监听地址
    'port': 5004, 
}

# 日志配置 - 控制台日志输出设置
LOG_CONFIG = {
    'level': "INFO",  # 日志级别: DEBUG/INFO/WARNING/ERROR/CRITICAL
    'format': "%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # 日志格式模板
}

# Web面板安全配置 - 管理界面访问控制
WEB_SECURITY = {
    'access_token': "admin",  # Web面板访问令牌，URL参数验证
    'admin_password': "admin",  # 管理员登录密码
    'production_mode': True,  # 生产环境模式，影响错误信息显示
}

# Web界面外观配置 - 自定义框架名称和网页图标
WEB_INTERFACE = {
    'framework_name': "Elaina",  # 框架名称，显示在页面标题和导航栏中
    'favicon_url': f'http://q1.qlogo.cn/g?b=qq&nk={OWNER_IDS[0]}&s=100',  # 网页图标URL（使用主人QQ头像）
    'mobile_title_suffix': "手机仪表盘",  # 移动端标题后缀
    'pc_title_suffix': "仪表盘",  # PC端标题后缀
    'login_title_suffix': "面板",  # 登录页面标题后缀
}

# 日志配置 - SQLite 日志存储
LOG_DB_CONFIG = {
    'enabled': True,
    'retention_days': 30,  # 日志保留天数
    'auto_cleanup': True,  # 自动清理过期日志
}

# OneBot 协议配置 - WebSocket 连接鉴权
ONEBOT_CONFIG = {
    'access_token': None,  # 访问令牌，用于 WebSocket 连接鉴权（Authorization: Bearer <token>）
    'secret': None,  # 签名密钥，用于 HTTP 回调签名验证（可选）
}
# 使用说明：
# 1. access_token: 在 NapCat 或其他 OneBot 实现的配置中设置相同的 token
# 2. secret: 用于验证 HTTP POST 上报的签名，提高安全性（可选）
# 3. 留空（None）表示不启用鉴权（适合本地测试）
# 框架自动更新配置 - 框架版本更新相关
AUTO_UPDATE_CONFIG = {
    'enabled': False,  # 是否启用自动更新功能（已简化框架，建议手动更新）
    'check_interval': 1800,
    'auto_update': False,
    'backup_enabled': True,
    'skip_files': [
        "config.py",
        "plugins/",
        "data/",
        ".git/",
        "__pycache__/",
        "*.pyc",
    ],
}