import httpx
from urllib.parse import quote
from nonebot import on_command
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message, MessageSegment

latex_renderer = on_command("latex", aliases={"tex"}, priority=1, block=True)

@latex_renderer.handle()
async def _(matcher: Matcher, args: Message = CommandArg()):
    formula = args.extract_plain_text().strip()

    if not formula:
        await matcher.finish("请输入需要渲染的LaTeX公式！\n用法: /latex [公式]")

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
    encoded_formula = quote(formula)
    api_url = f"https://latex.codecogs.com/png.image?\\dpi{{300}}\\bg{{white}}{encoded_formula}"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(api_url)
            response.raise_for_status()
            
            if response.headers.get('Content-Type', '').startswith('image/'):
                logger.info("成功从codecogs.com获取渲染图片。")
                return response.content
            else:
                logger.error(f"codecogs.com返回的不是图片，内容类型: {response.headers.get('Content-Type')}")
                return None
        except httpx.RequestError as e:
            logger.error(f"请求 codecogs.com 时出错: {e}")
            return None