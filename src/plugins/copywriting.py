import os
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.log import logger
import google.generativeai as genai
from nonebot.exception import FinishedException


# 配置 Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None
    logger.warning("未配置 GEMINI_API_KEY，文案生成功能不可用")

# 注册命令
copywriting = on_command("文案", aliases={"copywriting"}, priority=5, block=True)

@copywriting.handle()
async def handle_copywriting(event: MessageEvent, args: Message = CommandArg()):
    """
    文案仿写功能
    使用方法：/文案 <主题1> <主题2>
    例如：/文案 冰激凌 火锅
    """
    
    # 检查是否配置了 API Key
    if not GEMINI_API_KEY or not model:
        await copywriting.finish("❌ 未配置 GEMINI_API_KEY，请管理员先在 .env 文件中配置 Gemini API 密钥。")
        return
    
    # 获取参数
    arg_text = args.extract_plain_text().strip()
    
    if not arg_text:
        await copywriting.finish(
            "📝 文案仿写功能\n\n"
            "使用方法：/文案 <主题1> <主题2>\n"
            "例如：/文案 冰激凌 火锅\n\n"
            "我会按照特定句式为你创作有趣的文案～"
        )
        return
    
    # 解析参数
    themes = arg_text.split()
    
    if len(themes) < 2:
        await copywriting.finish("❌ 请提供至少两个主题词，用空格分隔。\n例如：/文案 冰激凌 火锅")
        return
    
    theme1 = themes[0]
    theme2 = themes[1]
    
    # 构建提示词
    prompt = f"""请你用"{theme1}"和"{theme2}"按照以下句式进行创意仿写：

原句式：我把大便拉在男朋友头上，男朋友暴跳如雷，我转头把大便拉在厕所里，厕所甘之如饴。爱你老厕明天见！

要求：
1. 保持原句式的结构和对比关系
2. 要生动有趣、富有创意
3. 直接给出仿写结果，不需要解释和额外说明

直接输出仿写的句子即可。"""
    
    try:
        await copywriting.send("✍️ 正在创作中，请稍候...")
        
        # 调用 Gemini API 生成文案
        response = model.generate_content(prompt)
        
        # 检查响应状态
        if not response:
            await copywriting.finish("❌ 生成失败：未收到 API 响应，请稍后再试。")
            return
            
        # 检查是否被安全过滤拦截
        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
            if hasattr(response.prompt_feedback, 'block_reason'):
                block_reason = response.prompt_feedback.block_reason
                if block_reason:
                    logger.warning(f"内容被安全过滤拦截: {block_reason}")
                    await copywriting.finish("❌ 生成失败：内容被安全过滤拦截，请尝试其他主题词。")
                    return
        
        # 尝试获取生成的文本
        try:
            result_text = response.text.strip()
            if result_text:
                await copywriting.finish(f"📝 文案创作完成：\n\n{result_text}")
            else:
                await copywriting.finish("❌ 生成失败：返回内容为空，请稍后再试。")
        except FinishedException as fe:
            # 处理无法访问 response.text 的情况
            logger.error(f"生成过程完成但无有效文本: {fe}")
            await copywriting.finish("❌ 生成失败：API 返回空结果或未生成有效文案。")
        except Exception as text_error:
        # 处理无法访问 response.text 的情况
            logger.error(f"无法获取响应文本: {text_error}")

            # 检查是否有候选结果但被安全过滤了
            if hasattr(response, 'candidates') and response.candidates:
                finish_reason = getattr(response.candidates[0], 'finish_reason', None)
                logger.warning(f"生成完成原因: {finish_reason}")
                
                if finish_reason == 4:  # SAFETY
                    await copywriting.finish("❌ 生成失败：内容触发了安全过滤，请尝试其他主题词。")
                else:
                    await copywriting.finish(f"❌ 生成失败：{text_error}\n请检查 API 配置或稍后重试。")
            else:
                await copywriting.finish("❌ 生成失败：无法获取生成结果，请稍后再试。")
            
    except FinishedException as e:
        logger.error(f"生成失败，模型返回 FinishedException: {e}")
        await copywriting.finish(f"❌ 生成失败：{type(e).__name__}\n请检查 API 配置或稍后重试。")
    
    except Exception as e:
        logger.error(f"调用 Gemini API 失败: {e}")
        await copywriting.finish(f"❌ 生成失败: {type(e).__name__}\n请检查 API 配置或稍后重试。")
