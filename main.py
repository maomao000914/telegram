import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (
    Chat, Channel, User
)
from telethon import events
from ncatbot.core import BotClient, GroupMessage, PrivateMessage


from config import API_ID, API_HASH, SESSION_NAME, QQ_BOT_UIN, QQ_TARGET_GROUP
bot = BotClient()
api = bot.run_blocking(bt_uin=QQ_BOT_UIN, root="1524366734")
# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramMonitor:
    def __init__(self):
        """
        初始化Telegram监控器
        """
        # Telegram客户端
        self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        self.me = None
        self.is_monitoring = False
        
        # 监听配置
        self.target_group_ids = []  # 目标群组ID列表
        self.target_user_ids = []   # 目标用户ID列表
        
        # QQ转发配置
        self.qq_target_group = QQ_TARGET_GROUP

    async def start_client(self):
        """
        启动Telegram客户端并登录
        """
        logger.info("正在连接到Telegram...")
        await self.client.start()
        self.me = await self.client.get_me()
        logger.info(f"成功登录到账号 {self.me.first_name} (@{self.me.username})")

    async def keep_alive(self):
        """
        保持连接活跃
        """
        while self.is_monitoring:
            try:
                # 定期获取自己的信息以保持连接活跃
                await self.client.get_me()
                # 获取一些群组信息以保持连接活跃
                if self.target_group_ids:
                    await self.client.get_entity(self.target_group_ids[0])
                await asyncio.sleep(60)  # 每60秒执行一次
            except Exception as e:
                logger.warning(f"保持连接活跃时出错: {e}")
                await asyncio.sleep(60)

    async def get_groups_list(self):
        """
        获取群组列表
        """
        groups = []
        logger.info("正在获取群组列表...")
        
        # 获取所有对话
        async for dialog in self.client.iter_dialogs():
            # 只获取群组和频道
            if isinstance(dialog.entity, (Chat, Channel)) and not getattr(dialog.entity, 'broadcast', False):
                groups.append({
                    'id': dialog.id,
                    'title': dialog.name,
                    'type': 'group' if isinstance(dialog.entity, Chat) else 'supergroup',
                    'username': getattr(dialog.entity, 'username', None)
                })
        
        return groups

    async def list_groups_formatted(self):
        """
        格式化输出群组列表
        """
        groups = await self.get_groups_list()
        if not groups:
            print("没有找到群组")
            return []

        print("\n=== 群组列表 ===")
        for i, group in enumerate(groups):
            username_str = f" (@{group['username']})" if group['username'] else ""
            print(f"[{i+1}] ID: {group['id']}")
            print(f"    名称: {group['title']}{username_str}")
            print(f"    类型: {group['type']}")
            print("-" * 30)
        
        return groups

    def send_to_qq_group(self, message_text):
        """
        将消息发送到QQ群
        
        Args:
            message_text (str): 要发送的消息文本
        """
        try:
            bot.api.post_group_msg_sync(group_id=QQ_TARGET_GROUP, text=message_text)
        except Exception as e:
            logger.error(f"发送QQ消息时出错: {e}")

    def format_links(self, text):
        """
        格式化文本中的链接，防止在QQ中被自动识别为可点击的超链接
        
        Args:
            text (str): 包含链接的原始文本
            
        Returns:
            str: 格式化后的文本，链接不再可点击
        """
        if not text:
            return text
            
        # 将http://和https://链接中的点号替换为特殊字符，防止链接被识别
        import re
        
        # 使用零宽空格(\u200B)插入到链接中，防止链接被识别
        def replace_url(match):
            url = match.group(0)
            # 在特定位置插入零宽空格，防止链接被识别
            if "https://" in url:
                return url.replace("https://", "https://\u200B")
            elif "http://" in url:
                return url.replace("http://", "http://\u200B")
            return url
            
        # 匹配http和https链接
        formatted_text = re.sub(r'https?://[^\s]+', replace_url, text)
        return formatted_text

    async def format_message_as_json(self, message, group_title, is_edited=False):
        """
        将消息格式化为JSON格式
        """
        sender = await message.get_sender()
        
        # 获取发送者信息
        sender_info = {
            "id": None,
            "first_name": None,
            "last_name": None,
            "username": None,
            "full_name": "未知用户"
        }
        
        if sender:
            if isinstance(sender, User):
                sender_info["id"] = sender.id
                sender_info["first_name"] = getattr(sender, 'first_name', None)
                sender_info["last_name"] = getattr(sender, 'last_name', None)
                sender_info["username"] = getattr(sender, 'username', None)
                
                # 构建完整姓名
                name_parts = []
                if sender_info["first_name"]:
                    name_parts.append(sender_info["first_name"])
                if sender_info["last_name"]:
                    name_parts.append(sender_info["last_name"])
                
                if name_parts:
                    sender_info["full_name"] = " ".join(name_parts)
                elif sender_info["username"]:
                    sender_info["full_name"] = sender_info["username"]
                else:
                    sender_info["full_name"] = str(sender.id)

        # 构建消息JSON
        message_json = {
            "timestamp": datetime.now().isoformat(),
            "group": {
                "id": message.chat_id,
                "title": group_title
            },
            "sender": sender_info,
            "message": {
                "id": message.id,
                "text": message.text,
                "date": message.date.isoformat() if message.date else None,
                "edited": message.edit_date.isoformat() if message.edit_date else None,
                "is_edited": is_edited
            }
        }
        
        return message_json

    async def monitor_groups_messages(self):
        """
        监听指定群组中指定用户的消息，并以JSON格式打印
        """
        if not self.target_group_ids:
            logger.error("未配置目标群组ID")
            return

        try:
            # 获取群组信息
            group_entities = {}
            for group_id in self.target_group_ids:
                try:
                    entity = await self.client.get_entity(group_id)
                    group_entities[group_id] = entity
                    group_title = entity.title
                    print(f"\n开始监听群组 '{group_title}' (ID: {group_id}) 的消息...")
                except Exception as e:
                    logger.error(f"无法获取群组 {group_id} 的信息: {e}")
                    continue

            if not group_entities:
                logger.error("无法获取任何目标群组的信息")
                return

            # 显示监听配置
            print(f"监听的群组数量: {len(group_entities)}")
            if self.target_user_ids:
                print(f"监听的用户ID: {self.target_user_ids}")
            else:
                print("监听所有用户的消息")
            print("按 Ctrl+C 可提前停止监听")
            print("提示: 为了确保能够接收实时消息，请保持手机端Telegram在线并打开需要监听的群组")

            # 设置监控状态
            self.is_monitoring = True
            
            # 启动保持活跃任务
            keep_alive_task = asyncio.create_task(self.keep_alive())

            # 定义处理新消息的回调函数
            async def handler(event):
                message = event.message
                group_id = message.chat_id
                
                # 检查是否是指定监听的群组
                if group_id not in group_entities:
                    return
                
                # 如果消息没有文本内容，跳过
                if not message.text:
                    return
                
                # 获取发送者
                sender = await message.get_sender()
                
                # 如果指定了特定用户，则检查发送者是否匹配
                if self.target_user_ids:
                    is_target_user = False
                    if sender and isinstance(sender, User):
                        # 检查ID是否匹配
                        if sender.id in self.target_user_ids:
                            is_target_user = True
                    
                    # 如果不是目标用户，跳过
                    if not is_target_user:
                        return

                # 格式化并打印消息
                try:
                    group_title = group_entities[group_id].title
                    message_json = await self.format_message_as_json(message, group_title)
                    # 以美化的JSON格式打印
                    json_output = json.dumps(message_json, ensure_ascii=False, indent=2)
                    print(json_output)
                    
                    # 转发消息到QQ群
                    # 构造要发送的文本消息
                    sender_name = message_json['sender']['full_name']
                    message_text = message_json['message']['text']
                    # 获取消息时间并格式化
                    message_time = message_json['message']['date']
                    if message_time:
                        # 将ISO格式时间转换为更易读的格式
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(message_time.replace('Z', '+00:00'))
                            # 转换为北京时间 (UTC+8)
                            beijing_time = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
                            formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            formatted_time = message_time
                    else:
                        formatted_time = "未知时间"
                    
                    # 格式化链接，防止在QQ中被自动识别为可点击的超链接
                    formatted_message_text = self.format_links(message_text)
                    message_type = "[Telegram转发-编辑消息]" if message_json['message']['is_edited'] else "[Telegram转发]"
                    formatted_message = f"时间: {formatted_time}\n内容: {formatted_message_text}"
                    self.send_to_qq_group(formatted_message)
                except Exception as e:
                    logger.error(f"格式化消息时出错: {e}")
            
            # 定义处理编辑消息的回调函数
            async def edit_handler(event):
                message = event.message
                group_id = message.chat_id
                
                # 检查是否是指定监听的群组
                if group_id not in group_entities:
                    return
                
                # 如果消息没有文本内容，跳过
                if not message.text:
                    return
                
                # 获取发送者
                sender = await message.get_sender()
                
                # 如果指定了特定用户，则检查发送者是否匹配
                if self.target_user_ids:
                    is_target_user = False
                    if sender and isinstance(sender, User):
                        # 检查ID是否匹配
                        if sender.id in self.target_user_ids:
                            is_target_user = True
                    
                    # 如果不是目标用户，跳过
                    if not is_target_user:
                        return

                # 格式化并打印消息
                try:
                    group_title = group_entities[group_id].title
                    message_json = await self.format_message_as_json(message, group_title, is_edited=True)
                    # 以美化的JSON格式打印
                    json_output = json.dumps(message_json, ensure_ascii=False, indent=2)
                    print(json_output)
                    
                    # 转发消息到QQ群
                    # 构造要发送的文本消息
                    sender_name = message_json['sender']['full_name']
                    message_text = message_json['message']['text']
                    # 获取消息时间并格式化
                    message_time = message_json['message']['edited'] or message_json['message']['date']
                    if message_time:
                        # 将ISO格式时间转换为更易读的格式
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(message_time.replace('Z', '+00:00'))
                            # 转换为北京时间 (UTC+8)
                            beijing_time = dt.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
                            formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            formatted_time = message_time
                    else:
                        formatted_time = "未知时间"
                    
                    # 格式化链接，防止在QQ中被自动识别为可点击的超链接
                    formatted_message_text = self.format_links(message_text)
                    formatted_message = f"时间: {formatted_time}\n内容: {formatted_message_text}"
                    self.send_to_qq_group(formatted_message)
                except Exception as e:
                    logger.error(f"格式化编辑消息时出错: {e}")
                
            # 为每个群组注册事件处理器
            for group_id in self.target_group_ids:
                self.client.add_event_handler(
                    handler, 
                    events.NewMessage(chats=group_id)
                )
                # 注册编辑消息事件处理器
                self.client.add_event_handler(
                    edit_handler,
                    events.MessageEdited(chats=group_id)
                )
            
            # 保持监听
            await self.client.run_until_disconnected()
                
        except KeyboardInterrupt:
            print("\n用户中断监听")
            self.is_monitoring = False
        except Exception as e:
            logger.error(f"监听消息时出错: {e}")
            self.is_monitoring = False
        finally:
            self.is_monitoring = False

    def parse_input_ids(self, input_str):
        """
        解析用户输入的ID字符串，支持逗号分隔和范围
        """
        ids = []
        parts = input_str.split(',')
        for part in parts:
            part = part.strip()
            if part.isdigit() or (part.startswith('-') and part[1:].isdigit()):
                ids.append(int(part))
            else:
                logger.warning(f"无效的ID格式: {part}")
        return ids

    async def run(self):
        """
        运行主程序
        """
        try:
            # 启动客户端
            await self.start_client()
            
            # 显示群组列表
            groups = await self.list_groups_formatted()
            
            if not groups:
                print("没有可监听的群组")
                return
            
            # 询问用户输入目标群组编号（支持多个，用逗号分隔）
            print("\n请输入要监听的群组编号（多个编号用逗号分隔）:")
            print("例如: 1, 3, 5")
            group_indices_input = input("群组编号: ")
            
            try:
                # 解析群组编号输入
                selected_indices = []
                for part in group_indices_input.split(','):
                    part = part.strip()
                    if part.isdigit():
                        selected_indices.append(int(part))
                    else:
                        logger.warning(f"无效的群组编号格式: {part}")
                
                # 转换为实际的群组ID
                for index in selected_indices:
                    if 1 <= index <= len(groups):
                        self.target_group_ids.append(groups[index-1]['id'])
                    else:
                        logger.warning(f"群组编号超出范围: {index}")
                
                if not self.target_group_ids:
                    print("未选择有效的群组")
                    return
                    
            except Exception as e:
                print(f"处理群组编号时出错: {e}")
                return
            
            # 询问用户输入目标用户ID（可选，多个用逗号分隔）
            print("\n请输入要监听的用户ID（多个ID用逗号分隔），直接回车表示监听所有用户:")
            print("例如: 123456789, 987654321")
            user_ids_input = input("用户ID: ").strip()
            
            if user_ids_input:
                try:
                    # 处理用户ID输入
                    self.target_user_ids = self.parse_input_ids(user_ids_input)
                except Exception as e:
                    print(f"处理用户ID时出错: {e}")
                    return
            
            print(f"\n配置完成:")
            print(f"监听群组数量: {len(self.target_group_ids)}")
            if self.target_user_ids:
                print(f"监听用户ID: {self.target_user_ids}")
            else:
                print("监听所有用户")
            
            # 开始监听
            await self.monitor_groups_messages()
            
        except SessionPasswordNeededError:
            logger.error("需要两步验证密码，请在代码中添加密码处理")
        except Exception as e:
            logger.error(f"运行时出错: {e}")
        finally:
            await self.client.disconnect()


async def main():
    """
    主函数
    """
    monitor = TelegramMonitor()
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
