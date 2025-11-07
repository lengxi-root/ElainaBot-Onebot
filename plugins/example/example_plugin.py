#!/usr/bin/env python
# -*- coding: utf-8 -*-

from core.PluginManager import Plugin
from core.MessageEvent import MessageSegment, Message
from core.onebot.api import get_onebot_api, run_async_api
import re
import logging

logger = logging.getLogger('ElainaBot.plugin.example')


class ExamplePlugin(Plugin):
    priority = 100
    
    @staticmethod
    def get_regex_handlers():
        return {
            r'^(帮助|help|菜单)$': {'handler': 'run', 'master_only': True},
            r'^ping$': 'run',
            r'^我的信息$': {'handler': 'run', 'master_only': True},
            r'^群信息$': {'handler': 'run', 'group_only': True, 'master_only': True},
            r'^群成员$': {'handler': 'run', 'group_only': True, 'master_only': True},
            r'^好友列表$': {'handler': 'run', 'master_only': True},
            r'^群列表$': {'handler': 'run', 'master_only': True},
            r'^禁言\s*(\d+)\s*(\d+)?$': {'handler': 'run', 'group_only': True, 'master_only': True},
            r'^改名片\s+(\d+)\s+(.+)$': {'handler': 'run', 'group_only': True, 'master_only': True},
            r'^测试撤回$': {'handler': 'run', 'master_only': True},
            r'^测试消息段$': {'handler': 'run', 'master_only': True},
            r'^测试文本$': {'handler': 'run', 'master_only': True},
            r'^测试at$': {'handler': 'run', 'master_only': True},
            r'^测试at全体$': {'handler': 'run', 'group_only': True, 'master_only': True},
            r'^测试表情$': {'handler': 'run', 'master_only': True},
            r'^测试图片$': {'handler': 'run', 'master_only': True},
            r'^测试回复$': {'handler': 'run', 'master_only': True},
            r'^测试组合$': {'handler': 'run', 'master_only': True},
        }
    
    @classmethod
    def run(cls, event):
        content = event.content.strip()
        
        if content in ['帮助', 'help', '菜单']:
            cls.show_help(event)
            return True
        
        if content == 'ping':
            event.reply('pong! 🏓')
            return True
        
        if content == '我的信息':
            cls.get_my_info(event)
            return True
        
        if content == '群信息' and event.is_group:
            cls.get_group_info(event)
            return True
        
        if content == '群成员' and event.is_group:
            cls.get_group_members(event)
            return True
        
        ban_match = re.match(r'^禁言\s*(\d+)\s*(\d+)?$', content)
        if ban_match and event.is_group:
            cls.ban_user(event, ban_match)
            return True
        
        card_match = re.match(r'^改名片\s+(\d+)\s+(.+)$', content)
        if card_match and event.is_group:
            cls.set_card(event, card_match)
            return True
        
        if content == '测试撤回':
            event.reply('这条消息将在3秒后撤回', auto_delete_time=3)
            return True
        
        if content == '好友列表':
            cls.get_friend_list(event)
            return True
        
        if content == '群列表':
            cls.get_group_list(event)
            return True
        
        if content == '测试消息段':
            cls.show_message_segment_menu(event)
            return True
        
        if content == '测试文本':
            cls.test_text(event)
            return True
        
        if content == '测试at':
            cls.test_at(event)
            return True
        
        if content == '测试at全体' and event.is_group:
            cls.test_at_all(event)
            return True
        
        if content == '测试表情':
            cls.test_face(event)
            return True
        
        if content == '测试图片':
            cls.test_image(event)
            return True
        
        if content == '测试回复':
            cls.test_reply(event)
            return True
        
        if content == '测试组合':
            cls.test_combined(event)
            return True
        
        return False
    
    @classmethod
    def show_help(cls, event):
        help_text = """
🤖 OneBot 示例插件（仅主人可用）

📌 基础：
• ping - 测试响应（所有人可用）
• 帮助/help/菜单

📊 查询：
• 我的信息 - 获取你的信息
• 群信息 - 当前群信息（群聊）
• 群成员 - 群成员列表（群聊）
• 好友列表 - 获取好友列表
• 群列表 - 获取群列表

⚙️ 管理：
• 禁言 <QQ号> <秒数>（群聊）
• 改名片 <QQ号> <名片>（群聊）

🧪 测试：
• 测试撤回 - 3秒后自动撤回
• 测试消息段 - 查看消息段测试菜单
• 测试文本/at/表情/图片/回复/组合
        """.strip()
        event.reply(help_text)
    
    @classmethod
    def show_message_segment_menu(cls, event):
        """显示消息段测试菜单"""
        menu = """
🧪 消息段测试菜单

发送以下指令测试不同类型的消息：

• 测试文本 - 纯文本消息
• 测试at - @消息
• 测试at全体 - @全体成员（群聊）
• 测试表情 - QQ表情
• 测试图片 - 图片消息
• 测试回复 - 回复消息
• 测试组合 - 组合多种消息段
        """.strip()
        event.reply(menu)
    
    @classmethod
    def test_text(cls, event):
        """测试纯文本消息"""
        msg = Message([MessageSegment.text("这是一条纯文本消息！✅")])
        event.reply(msg)
    
    @classmethod
    def test_at(cls, event):
        """测试@消息"""
        msg = Message([
            MessageSegment.at(event.user_id),
            MessageSegment.text(" 这是@你的消息！")
        ])
        event.reply(msg)
    
    @classmethod
    def test_at_all(cls, event):
        """测试@全体成员"""
        msg = Message([
            MessageSegment.at_all(),
            MessageSegment.text(" 这是@全体成员的消息！")
        ])
        event.reply(msg)
    
    @classmethod
    def test_face(cls, event):
        """测试QQ表情"""
        msg = Message([
            MessageSegment.text("QQ表情演示："),
            MessageSegment.face(1),   # 微笑
            MessageSegment.face(2),   # 撇嘴
            MessageSegment.face(14),  # 微笑
            MessageSegment.face(21),  # 可爱
            MessageSegment.face(66),  # 爱心
        ])
        event.reply(msg)
    
    @classmethod
    def test_image(cls, event):
        """测试图片消息"""
        msg = Message([
            MessageSegment.text("这是一张图片：\n"),
            MessageSegment.image("https://q1.qlogo.cn/g?b=qq&nk=10001&s=640")
        ])
        event.reply(msg)
    
    @classmethod
    def test_reply(cls, event):
        """测试回复消息"""
        msg = Message([
            MessageSegment.reply(event.message_id),
            MessageSegment.text("这是一条回复消息！")
        ])
        event.reply(msg)
    
    @classmethod
    def test_combined(cls, event):
        """测试组合消息"""
        msg = Message([
            MessageSegment.text("组合消息示例："),
            MessageSegment.at(event.user_id),
            MessageSegment.text(" 你好！"),
            MessageSegment.face(21),  # 可爱
            MessageSegment.text("\n下面是一张图片：\n"),
            MessageSegment.image("https://q1.qlogo.cn/g?b=qq&nk=10001&s=100")
        ])
        event.reply(msg)
    
    @classmethod
    def get_my_info(cls, event):
        api = get_onebot_api()
        try:
            result = run_async_api(api.get_stranger_info(event.user_id))
            if result and result.get('retcode') == 0:
                data = result.get('data', {})
                info = f"""👤 你的信息：
• QQ号：{data.get('user_id', event.user_id)}
• 昵称：{data.get('nickname', '未知')}
• 年龄：{data.get('age', '未知')}
• 性别：{data.get('sex', '未知')}"""
                event.reply(info)
            else:
                event.reply('❌ 获取信息失败')
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
    
    @classmethod
    def get_group_info(cls, event):
        api = get_onebot_api()
        try:
            result = run_async_api(api.get_group_info(event.group_id))
            if result and result.get('retcode') == 0:
                data = result.get('data', {})
                info = f"""👥 群信息：
• 群号：{data.get('group_id', event.group_id)}
• 群名：{data.get('group_name', '未知')}
• 成员数：{data.get('member_count', '未知')}
• 最大人数：{data.get('max_member_count', '未知')}"""
                event.reply(info)
            else:
                event.reply('❌ 获取群信息失败')
        except Exception as e:
            logger.error(f"获取群信息失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
    
    @classmethod
    def get_group_members(cls, event):
        api = get_onebot_api()
        try:
            members = run_async_api(api.get_group_member_list(event.group_id))
            if members:
                count = len(members)
                preview = members[:10]
                member_list = '\n'.join([
                    f"• {m.get('nickname', '未知')} ({m.get('user_id', '')})"
                    for m in preview
                ])
                text = f"👥 群成员列表（共{count}人）：\n\n{member_list}\n\n{'...' if count > 10 else ''}"
                event.reply(text)
            else:
                event.reply('❌ 获取群成员列表失败')
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
    
    @classmethod
    def ban_user(cls, event, match):
        api = get_onebot_api()
        user_id = match.group(1)
        duration = int(match.group(2)) if match.group(2) else 60
        try:
            result = run_async_api(api.set_group_ban(event.group_id, user_id, duration))
            if result and result.get('retcode') == 0:
                event.reply(f'✅ 已禁言用户 {user_id}，时长 {duration} 秒')
            else:
                event.reply('❌ 禁言失败，可能权限不足')
        except Exception as e:
            logger.error(f"禁言失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
    
    @classmethod
    def set_card(cls, event, match):
        api = get_onebot_api()
        user_id = match.group(1)
        card = match.group(2)
        try:
            result = run_async_api(api.set_group_card(event.group_id, user_id, card))
            if result and result.get('retcode') == 0:
                event.reply(f'✅ 已将用户 {user_id} 的群名片修改为：{card}')
            else:
                event.reply('❌ 修改失败，可能权限不足')
        except Exception as e:
            logger.error(f"设置群名片失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
    
    @classmethod
    def get_friend_list(cls, event):
        api = get_onebot_api()
        try:
            friends = run_async_api(api.get_friend_list())
            if friends:
                count = len(friends)
                preview = friends[:10]
                friend_list = '\n'.join([
                    f"• {f.get('nickname', '未知')} ({f.get('user_id', '')})"
                    for f in preview
                ])
                text = f"👥 好友列表（共{count}人）：\n\n{friend_list}\n\n{'...' if count > 10 else ''}"
                event.reply(text)
            else:
                event.reply('❌ 获取好友列表失败')
        except Exception as e:
            logger.error(f"获取好友列表失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
    
    @classmethod
    def get_group_list(cls, event):
        api = get_onebot_api()
        try:
            groups = run_async_api(api.get_group_list())
            if groups:
                count = len(groups)
                preview = groups[:10]
                group_list = '\n'.join([
                    f"• {g.get('group_name', '未知')} ({g.get('group_id', '')})"
                    for g in preview
                ])
                text = f"👥 群列表（共{count}个群）：\n\n{group_list}\n\n{'...' if count > 10 else ''}"
                event.reply(text)
            else:
                event.reply('❌ 获取群列表失败')
        except Exception as e:
            logger.error(f"获取群列表失败: {e}")
            event.reply(f'❌ 错误：{str(e)}')
