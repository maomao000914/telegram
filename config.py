"""
Telegram API 配置文件
请在Telegram官网 https://my.telegram.org/ 创建应用获取API ID和API Hash
"""

# Telegram API 配置
API_ID = 
API_HASH = ''

# 会话文件名
SESSION_NAME = "telegram_session"

# QQ机器人配置 (用于消息转发)
QQ_BOT_UIN = ""        # 用于登录的QQ号
QQ_TARGET_GROUP = ""   # 目标QQ群号码
QQ_WS_URI = "ws://localhost:3001"  # NapCat的WebSocket地址
QQ_BOT_TOKEN = ""               # 如果设置了access_token，请填写
