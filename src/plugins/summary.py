"""
群聊内容总结插件
使用 AI 自动总结群聊中的消息内容
实时获取历史消息，无需持续缓存
"""
import os
from typing import Optional, List
from dataclasses import dataclass
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message, Bot
from nonebot.params import CommandArg
from nonebot.log import logger
import google.generativeai as genai

# ==================== 配置 ====================

# Gemini API 配置
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    logger.warning("未配置 GEMINI_API_KEY，群聊总结功能不可用")

# 默认获取的消息数量
DEFAULT_MESSAGE_COUNT = 50

# 最大获取消息数量
MAX_MESSAGE_COUNT = 200

# ==================== 数据结构 ====================

@dataclass
class ChatMessage:
    """聊天消息数据类"""
    sender_name: str
    sender_id: int
    content: str
    
    def to_text(self) -> str:
        """转换为文本格式用于总结"""
        return f"[{self.sender_name}]: {self.content}"


# ==================== 消息获取 ====================

async def fetch_group_messages(bot: Bot, group_id: int, count: int = DEFAULT_MESSAGE_COUNT) -> List[ChatMessage]:
    """
    从群聊获取最近的历史消息
    
    Args:
        bot: Bot 实例
        group_id: 群号
        count: 获取的消息数量
    
    Returns:
        ChatMessage 列表
    """
    messages = []
    
    try:
        # 使用 get_group_msg_history 获取群消息历史
        # 注意：此 API 可能需要特定的 OneBot 实现支持（如 go-cqhttp, NapCat 等）
        history = await bot.get_group_msg_history(group_id=group_id, count=count)
        
        if not history or 'messages' not in history:
            logger.warning(f"获取群 {group_id} 消息历史失败或为空")
            return messages
        
        for msg_data in history['messages']:
            try:
                # 提取发送者信息
                sender_id = msg_data.get('user_id', 0)
                sender_info = msg_data.get('sender', {})
                sender_name = sender_info.get('card') or sender_info.get('nickname') or str(sender_id)
                
                # 提取消息内容（纯文本）
                raw_message = msg_data.get('raw_message', '') or msg_data.get('message', '')
                
                # 如果 message 是列表格式，需要解析
                if isinstance(raw_message, list):
                    content_parts = []
                    for seg in raw_message:
                        if isinstance(seg, dict) and seg.get('type') == 'text':
                            content_parts.append(seg.get('data', {}).get('text', ''))
                    content = ''.join(content_parts)
                else:
                    content = str(raw_message)
                
                content = content.strip()
                
                # 跳过空消息和命令消息
                if not content or content.startswith('/'):
                    continue
                
                # 限制单条消息长度
                if len(content) > 500:
                    content = content[:500] + "..."
                
                messages.append(ChatMessage(
                    sender_name=sender_name,
                    sender_id=sender_id,
                    content=content
                ))
                
            except Exception as e:
                logger.debug(f"解析消息失败: {e}")
                continue
        
        logger.info(f"成功获取群 {group_id} 的 {len(messages)} 条消息")
        
    except Exception as e:
        logger.error(f"获取群消息历史失败: {e}")
    
    return messages


# ==================== 总结命令 ====================

summary_cmd = on_command("总结", aliases={"summary", "群聊总结", "聊天总结"}, priority=5, block=True)

# 总结提示词模板
SUMMARY_PROMPT = """你是一个群聊内容总结助手。请根据以下群聊记录，生成一个简洁清晰的内容总结。

[任务要求]
1. 概括聊天的主要话题和讨论内容
2. 提取关键信息和重要观点
3. 如果有争议或不同意见，请客观呈现
4. 总结应当简洁明了，使用bullet points
5. 使用中文回复
6. 如果聊天内容比较零散，请指出主要的几个话题
7. 不要逐条翻译消息，而是提炼精华

[群聊记录]
{chat_content}

[你的总结]
请生成一个结构清晰的总结，不能含有任何 Markdown 语法！例如 * 星号，# 井号，- 减号，> 引号等："""

# 话题分析提示词
TOPIC_PROMPT = """你是一个群聊话题分析助手。请分析以下群聊记录中讨论的话题。

[任务要求]
1. 识别聊天中的主要话题（最多5个）
2. 对每个话题给出简短描述
3. 估计每个话题的讨论热度（高/中/低）
4. 使用中文回复
5. 以清晰的列表形式呈现

[群聊记录]
{chat_content}

[话题分析]
请列出本次群聊中的主要话题，不能含有任何 Markdown 语法！例如 * 星号，# 井号，- 减号，> 引号等："""

# 活跃度分析提示词
ACTIVITY_PROMPT = """你是一个群聊活跃度分析助手。请分析以下群聊记录中的活跃情况。

[任务要求]
1. 统计最活跃的发言者（按发言次数）
2. 分析聊天的整体氛围（活跃/平淡/紧张等）
3. 找出聊天中的"热点"时刻（如果有）
4. 使用中文回复

[群聊记录]
{chat_content}

[活跃度分析]
请分析本次群聊的活跃情况，不能含有任何 Markdown 语法！例如 * 星号，# 井号，- 减号，> 引号等："""


@summary_cmd.handle()
async def handle_summary(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    群聊总结功能
    使用方法：
    - /总结 [数量] - 总结最近N条消息（默认50条，最大200条）
    - /总结 话题 [数量] - 分析话题
    - /总结 活跃 [数量] - 分析活跃度
    """
    
    # 检查是否为群聊
    if not isinstance(event, GroupMessageEvent):
        await summary_cmd.finish("❌ 此功能仅支持群聊使用")
        return
    
    # 检查 API Key
    if not GEMINI_API_KEY or not model:
        await summary_cmd.finish("❌ 未配置 GEMINI_API_KEY，请管理员先在 .env 文件中配置 Gemini API 密钥。")
        return
    
    group_id = event.group_id
    arg_text = args.extract_plain_text().strip()
    
    # 解析参数
    args_list = arg_text.split() if arg_text else []
    
    # 确定总结类型和消息数量
    summary_type = "default"
    count = DEFAULT_MESSAGE_COUNT
    
    if args_list:
        first_arg = args_list[0]
        
        if first_arg in ["话题", "topic", "topics"]:
            summary_type = "topic"
            if len(args_list) > 1 and args_list[1].isdigit():
                count = min(int(args_list[1]), MAX_MESSAGE_COUNT)
        elif first_arg in ["活跃", "activity", "active"]:
            summary_type = "activity"
            if len(args_list) > 1 and args_list[1].isdigit():
                count = min(int(args_list[1]), MAX_MESSAGE_COUNT)
        elif first_arg.isdigit():
            count = min(int(first_arg), MAX_MESSAGE_COUNT)
        elif first_arg in ["帮助", "help"]:
            await summary_cmd.finish(
                "群聊总结功能\n"
                "━━━━━━━━━━━━━━\n"
                "使用方法:\n"
                f"• /总结 - 总结最近 {DEFAULT_MESSAGE_COUNT} 条消息\n"
                f"• /总结 <数量> - 总结指定数量消息（最大 {MAX_MESSAGE_COUNT}）\n"
                "• /总结 话题 [数量] - 分析讨论话题\n"
                "• /总结 活跃 [数量] - 分析活跃度\n\n"
                "示例:\n"
                "• /总结 100\n"
                "• /总结 话题 150"
            )
            return
    
    # 发送加载提示
    await summary_cmd.send(f"⏳ 正在获取最近 {count} 条消息...")
    
    # 实时获取消息历史
    messages = await fetch_group_messages(bot, group_id, count)
    
    if len(messages) < 5:
        await summary_cmd.finish(
            f"❌ 消息记录不足\n"
            f"成功获取 {len(messages)} 条消息，至少需要 5 条才能生成总结。"
        )
        return
    
    # 构建聊天内容文本
    chat_content = "\n".join([msg.to_text() for msg in messages])
    
    # 选择提示词
    if summary_type == "topic":
        prompt = TOPIC_PROMPT.format(chat_content=chat_content)
        loading_msg = "🔍 正在分析群聊话题..."
    elif summary_type == "activity":
        prompt = ACTIVITY_PROMPT.format(chat_content=chat_content)
        loading_msg = "📊 正在分析群聊活跃度..."
    else:
        prompt = SUMMARY_PROMPT.format(chat_content=chat_content)
        loading_msg = f"📝 正在总结 {len(messages)} 条消息..."
    
    try:
        await summary_cmd.send(loading_msg)
        
        # 调用 Gemini API
        response = model.generate_content(prompt)
        
        if not response:
            await summary_cmd.finish("❌ 生成失败：未收到 API 响应，请稍后再试。")
            return
        
        # 检查安全过滤
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            if hasattr(response.prompt_feedback, 'block_reason'):
                block_reason = response.prompt_feedback.block_reason
                if block_reason:
                    logger.warning(f"内容被安全过滤拦截: {block_reason}")
                    await summary_cmd.finish("❌ 生成失败：内容被安全过滤拦截。")
                    return
        
        # 获取结果
        try:
            result_text = response.text.strip()
            if result_text:
                # 构建响应标题
                if summary_type == "topic":
                    header = "🔍 群聊话题分析"
                elif summary_type == "activity":
                    header = "📊 群聊活跃度分析"
                else:
                    header = "📋 群聊内容总结"
                
                await summary_cmd.finish(
                    f"{header}\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"📊 分析了 {len(messages)} 条消息\n\n"
                    f"{result_text}"
                )
            else:
                await summary_cmd.finish("❌ 生成失败：返回内容为空，请稍后再试。")
                
        except Exception as text_error:
            logger.error(f"无法获取响应文本: {text_error}")
            #await summary_cmd.finish("❌ 生成失败：无法解析 API 响应。")
            
    except Exception as e:
        logger.error(f"调用 Gemini API 失败: {e}")
        #await summary_cmd.finish(f"❌ 生成失败：{str(e)}")


