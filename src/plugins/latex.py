import re
import httpx
from urllib.parse import quote
from nonebot import on_message
from nonebot.log import logger
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageSegment, GroupMessageEvent

LATEX_PATTERN = re.compile(r"^\s*/latex\s+(.*)", re.DOTALL)

latex_renderer = on_message(priority=50, block=True)

@latex_renderer.handle()
async def _(matcher: Matcher, event: GroupMessageEvent, state: T_State):
    plain_text = event.get_message().extract_plain_text().strip()
    
    match = LATEX_PATTERN.match(plain_text)
    if not match:
        await matcher.skip()
        return

    formula = match.group(1).strip()
    if not formula:
        await matcher.finish("请输入需要渲染的LaTeX公式！")

    logger.info(f"接收到LaTeX渲染请求，公式: {formula}")

    try:
        image_bytes = await render_formula_online(formula)
        if image_bytes:
            await matcher.finish(MessageSegment.image(image_bytes))
        else:
            await matcher.finish("在线渲染服务出错，未能生成图片。请检查后台日志。")
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.error(f"LaTeX渲染过程中发生网络异常: {e}")
        await matcher.finish(f"渲染失败，网络错误: {e}")


async def render_formula_online(formula: str) -> bytes | None:
    """
    使用 latex.codecogs.com 在线服务将LaTeX公式转换为带白色背景的图片。
    """
    encoded_formula = quote(formula)
    
    api_url = f"https://latex.codecogs.com/png.image?\\dpi{{300}}\\bg{{white}}{encoded_formula}"
    
    async with httpx.AsyncClient(timeout=15.0) as client: 
        response = await client.get(api_url)
        
        if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/'):
            logger.info("成功从codecogs.com获取渲染图片。")
            return response.content
        else:
            logger.error(f"codecogs.com请求失败，状态码: {response.status_code}，内容类型: {response.headers.get('Content-Type')}")

            if response.headers.get('Content-Type', '').startswith('image/'):
                return response.content
            return None