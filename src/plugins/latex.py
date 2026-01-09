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
    raw_formula = args.extract_plain_text().strip()

    if not raw_formula:
        await matcher.finish("请输入需要渲染的LaTeX公式！\n用法: /latex [公式]")

    logger.info(f"接收到LaTeX渲染请求，公式: {raw_formula}")

    try:
        formula, inline_mode = normalize_formula(raw_formula)
        image_bytes = await render_formula_online(formula, inline_mode=inline_mode)
        if image_bytes:
            await matcher.finish(MessageSegment.image(image_bytes))
        else:
            await matcher.finish("在线渲染服务出错，未能生成图片。请检查后台日志。")
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.error(f"LaTeX渲染过程中发生网络异常: {e}")
        await matcher.finish(f"渲染失败")


def normalize_formula(raw_formula: str) -> tuple[str, bool]:
    inline_mode = False
    formula = raw_formula.strip()

    if formula.startswith("$$") and formula.endswith("$$") and len(formula) > 4:
        formula = formula[2:-2].strip()
    elif formula.startswith("$") and formula.endswith("$") and len(formula) > 2:
        inline_mode = True
        formula = formula[1:-1].strip()
    elif formula.startswith("\\[") and formula.endswith("\\]") and len(formula) > 4:
        formula = formula[2:-2].strip()
    elif formula.startswith("\\(") and formula.endswith("\\)") and len(formula) > 4:
        inline_mode = True
        formula = formula[2:-2].strip()

    if "\n" in formula and "\\begin{" not in formula:
        lines = [line.strip() for line in formula.splitlines() if line.strip()]
        formula = "\\begin{aligned}" + " \\\\ ".join(lines) + "\\end{aligned}"

    if "\\boxed" not in formula and "\\fbox" not in formula and "\\framebox" not in formula:
        formula = "\\boxed{\\; " + formula + " \\;}"

    return formula, inline_mode


async def render_formula_online(formula: str, inline_mode: bool = False) -> bytes | None:
    encoded_formula = quote(formula)
    mode_prefix = "\\inline" if inline_mode else ""
    api_url = f"https://latex.codecogs.com/png.image?{mode_prefix}\\dpi{{300}}\\bg{{white}}{encoded_formula}"
    
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
