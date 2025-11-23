import imaplib
import email
import os
from email.header import decode_header
import asyncio
from typing import Tuple, Optional
import nonebot
from nonebot import on_command, get_driver, logger
from nonebot.adapters.onebot.v11 import Bot, Message, Event
from nonebot.plugin import PluginMetadata
from pydantic import BaseModel, Extra

# --- 1. 配置模型 (Configuration Model) ---
class Config(BaseModel, extra=Extra.ignore):
    email_imap_server: str = "imap.gmail.com"
    email_imap_port: int = 993
    email_user: str = ""
    email_password: str = ""
    superusers: list[str] = [] # Superusers 仍用于定时任务(如果启用)

# --- 2. 加载配置 (Load Configuration) ---
try:
    driver = get_driver()
    global_config = driver.config
    plugin_config = Config.model_validate(global_config.model_dump())
    
    # 从环境变量读取配置，环境变量优先
    EMAIL_IMAP_SERVER = os.getenv("EMAIL_IMAP_SERVER") or plugin_config.email_imap_server
    EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT") or plugin_config.email_imap_port)
    EMAIL_USER = os.getenv("EMAIL_USER") or plugin_config.email_user
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") or plugin_config.email_password
except Exception as e:
    logger.warning(f"邮箱插件配置加载失败, 请检查 .env 文件: {e}")
    EMAIL_IMAP_SERVER = os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com")
    EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

# --- 3. 插件元数据 (Plugin Metadata) ---
__plugin_meta__ = PluginMetadata(
    name="邮箱通知",
    description="监控邮箱并通知新邮件",
    usage="使用 /check_email 手动检查", 
    config=Config,
)

# --- 4. 命令处理器 (Command Handler) ---
check_email_cmd = on_command("check_email", aliases={"检查邮件"}, priority=10, block=True)


# --- 5. 核心检查函数 (Core Check Function) ---
async def check_and_notify(bot: Bot, event: Optional[Event] = None) -> Tuple[bool, str]:
    """
    检查未读邮件并通知。
    - 如果 event 存在 (手动触发), 则发送通知到 event 来源 (群/私聊)。
    - 如果 event 为 None (如定时任务调用), 则发送通知给 superusers (私聊)。
    返回 (bool: success, str: message)
    """
    # 检查配置
    if not plugin_config.email_imap_server or not plugin_config.email_user or not plugin_config.email_password:
        logger.warning("Email configuration missing. Skipping check.")
        return (False, "邮箱配置缺失，无法检查邮件。")

    mail = None
    try:
        # 1. 连接和登录
        mail = imaplib.IMAP4_SSL(plugin_config.email_imap_server, plugin_config.email_imap_port)
        mail.login(plugin_config.email_user, plugin_config.email_password)
        mail.select("inbox")

        # 2. 搜索未读邮件
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            logger.error("Failed to search emails.")
            return (False, "搜索邮件失败。")

        email_ids = messages[0].split()
        if not email_ids:
            logger.info("No new emails.")
            return (True, "没有新邮件。")

        logger.info(f"Found {len(email_ids)} new emails.")

        # 3. 遍历新邮件并发送通知
        for email_id in email_ids:
            res, msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # 解码主题
                    subject = "无主题"
                    subject_header = decode_header(msg["Subject"])
                    if subject_header[0][0]:
                        subject, encoding = subject_header[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")
                    
                    # 获取发件人
                    from_ = msg.get("From")
                    notify_msg = f"📧 新邮件提醒\n\n来自: {from_}\n主题: {subject}"
                    
                    # 4. 判断通知目标
                    if event:
                        # 手动触发: 发送到命令来源 (群聊或私聊)
                        try:
                            await bot.send(event=event, message=notify_msg)
                        except Exception as e:
                            logger.error(f"Failed to send email notification to event source: {e}")
                    else:
                        # (此分支现在不会被调用，但保留逻辑以备将来使用)
                        # 定时任务: 发送给 superusers
                        for user_id in global_config.superusers:
                            try:
                                await bot.send_private_msg(user_id=int(user_id), message=notify_msg)
                            except Exception as e:
                                logger.error(f"Failed to send email notification to superuser {user_id}: {e}")
        
        return (True, f"检查完成，已通知 {len(email_ids)} 封新邮件。")

    except Exception as e:
        logger.error(f"Error checking email: {e}")
        return (False, f"检查邮件时出错: {e}")

    finally:
        # 5. 关闭连接
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception as e:
                logger.debug(f"Error during mail logout/close: {e}")

# --- 6. 命令处理函数 (Manual Check Handler) ---
@check_email_cmd.handle()
async def handle_check_email(bot: Bot, event: Event): 
    """
    手动检查邮件的命令处理器
    """
    # 回复到触发命令的地方
    await check_email_cmd.send("正在检查邮件...")
    
    # 将 event 传递给核心函数，这样通知就会发到 event 来源
    success, message = await check_and_notify(bot, event) 
    
    if success:
        await check_email_cmd.finish(message)
    else:
        await check_email_cmd.finish(f"检查失败: {message}")

# --- (定时任务代码已移除) ---