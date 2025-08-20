# ========= 导入必要模块 ==========
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from ncatbot.utils import get_log
from config import API_ID, API_HASH, SESSION_NAME, QQ_BOT_UIN, QQ_TARGET_GROUP
# ========== 创建 BotClient ==========
bot = BotClient()
_log = get_log()

# ========= 注册回调函数 ==========
@bot.group_event()
async def on_group_message(msg: GroupMessage):
    _log.info(msg)
    if msg.raw_message == "测试":
        await msg.reply(text="NcatBot 测试成功喵~")

@bot.private_event()
async def on_private_message(msg: PrivateMessage):
    _log.info(msg)
    if msg.raw_message == "测试":
        await bot.api.post_private_msg(msg.user_id, text="NcatBot 测试成功喵~")

# ========== 启动 BotClient==========
if __name__ == "__main__":
    bot.run(bt_uin=QQ_BOT_UIN) # 这里写 Bot 的 QQ 号
