"""
消息截图插件
回复消息并使用 /save 命令，将消息渲染成带头像的精美卡片图片
"""
import io
import os
from typing import Optional, Tuple

import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    Bot, 
    MessageEvent, 
    GroupMessageEvent,
    Message, 
    MessageSegment
)
from nonebot.params import CommandArg
from nonebot.log import logger

from PIL import Image, ImageDraw, ImageFont

# ==================== 配置 ====================

# 头像尺寸
AVATAR_SIZE = 50

# 字体配置 - 优先使用系统中文字体
FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",  # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
]

def get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取可用的字体"""
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    # 回退到默认字体
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()

# ==================== 颜色主题 ====================

# 浅色主题配置
THEME = {
    "bg_color": (245, 245, 245),           # 背景浅灰
    "card_bg": (255, 255, 255),            # 卡片背景白色
    "border_color": (230, 230, 230),       # 边框颜色
    "text_color": (51, 51, 51),            # 主文字颜色
    "name_color": (51, 51, 51),            # 名字颜色
    "level_bg": (230, 230, 230),           # 等级标签背景
    "level_color": (102, 102, 102),        # 等级标签文字
}

# ==================== 头像处理 ====================

async def get_qq_avatar(user_id: int, size: int = 100) -> Optional[Image.Image]:
    """
    获取 QQ 头像
    
    Args:
        user_id: QQ 号
        size: 头像尺寸 (40, 100, 140, 640)
    
    Returns:
        PIL Image 对象，失败返回 None
    """
    # QQ 头像 API
    avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={user_id}&s={size}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(avatar_url)
            response.raise_for_status()
            
            # 将字节转换为图片
            avatar_bytes = io.BytesIO(response.content)
            avatar = Image.open(avatar_bytes)
            return avatar.convert("RGBA")
    except Exception as e:
        logger.warning(f"获取头像失败 (QQ: {user_id}): {e}")
        return None


def make_circle_avatar(avatar: Image.Image, size: int) -> Image.Image:
    """
    将头像裁剪为圆形
    
    Args:
        avatar: 原始头像图片
        size: 目标尺寸
    
    Returns:
        圆形头像 (RGBA)
    """
    # 调整尺寸
    avatar = avatar.resize((size, size), Image.Resampling.LANCZOS)
    
    # 创建圆形蒙版
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    
    # 应用蒙版
    result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    result.paste(avatar, (0, 0), mask)
    
    return result


def create_default_avatar(size: int, name: str, color: Tuple[int, int, int] = (100, 149, 237)) -> Image.Image:
    """
    创建默认头像（带首字母）
    
    Args:
        size: 头像尺寸
        name: 用户名（用于提取首字母）
        color: 背景颜色
    
    Returns:
        默认头像图片
    """
    avatar = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(avatar)
    
    # 绘制圆形背景
    draw.ellipse((0, 0, size, size), fill=color)
    
    # 绘制首字母
    initial = name[0].upper() if name else "?"
    font = get_font(int(size * 0.5))
    
    # 获取文字尺寸并居中
    try:
        bbox = font.getbbox(initial)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except Exception:
        text_width = size // 2
        text_height = size // 2
    
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - 5
    
    draw.text((x, y), initial, font=font, fill=(255, 255, 255))
    
    return avatar

# ==================== 文字换行工具 ====================

def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """将文本按指定宽度换行"""
    lines = []
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
            
        current_line = ""
        for char in paragraph:
            test_line = current_line + char
            try:
                bbox = font.getbbox(test_line)
                text_width = bbox[2] - bbox[0]
            except Exception:
                text_width = len(test_line) * font.size
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char
        
        if current_line:
            lines.append(current_line)
    
    return lines if lines else [""]


def get_text_size(text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    """获取文本尺寸"""
    try:
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        return len(text) * font.size, font.size

# ==================== 图片生成 ====================

async def render_quote_image(
    sender_name: str,
    sender_id: int,
    content: str,
    level: Optional[int] = None
) -> bytes:
    """
    渲染消息为带头像的卡片图片（类似微信/QQ截图样式）
    
    Args:
        sender_name: 发送者昵称
        sender_id: 发送者 QQ 号
        content: 消息内容
        level: 等级（可选）
    
    Returns:
        PNG 图片的字节数据
    """
    # 使用浅色主题
    colors = THEME
    
    # 字体设置
    name_font = get_font(16)
    content_font = get_font(18)
    level_font = get_font(11)
    
    # 布局参数
    padding = 20              # 图片边距
    card_padding_h = 15       # 卡片水平内边距
    card_padding_v = 12       # 卡片垂直内边距
    avatar_size = AVATAR_SIZE # 头像尺寸
    avatar_margin = 12        # 头像右侧边距
    max_content_width = 280   # 内容最大宽度
    line_spacing = 6          # 行间距
    
    # 处理内容换行
    content_lines = wrap_text(content, content_font, max_content_width)
    
    # 限制最大行数
    max_lines = 20
    if len(content_lines) > max_lines:
        content_lines = content_lines[:max_lines]
        content_lines[-1] = content_lines[-1][:15] + "..."
    
    # 计算内容区域尺寸
    line_height = content_font.size + line_spacing
    content_height = len(content_lines) * line_height
    
    # 计算卡片尺寸
    # 头部高度：头像尺寸（头像上面对齐名字）
    header_height = 24  # 名字行高度
    content_top_margin = 8  # 名字和内容之间的间距
    
    card_content_width = max_content_width
    card_width = card_padding_h + avatar_size + avatar_margin + card_content_width + card_padding_h
    card_height = card_padding_v + max(avatar_size, header_height + content_top_margin + content_height) + card_padding_v
    
    # 图片尺寸
    img_width = card_width + padding * 2
    img_height = card_height + padding * 2
    
    # 创建图片
    img = Image.new('RGBA', (img_width, img_height), colors["bg_color"])
    draw = ImageDraw.Draw(img)
    
    # 绘制卡片背景
    card_x = padding
    card_y = padding
    
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_width, card_y + card_height],
        radius=12,
        fill=colors["card_bg"],
        outline=colors["border_color"],
        width=1
    )
    
    # 获取并绘制头像
    avatar_x = card_x + card_padding_h
    avatar_y = card_y + card_padding_v
    
    avatar_img = await get_qq_avatar(sender_id, 100)
    if avatar_img:
        circle_avatar = make_circle_avatar(avatar_img, avatar_size)
    else:
        circle_avatar = create_default_avatar(avatar_size, sender_name, colors.get("name_color", (100, 149, 237)))
    
    img.paste(circle_avatar, (avatar_x, avatar_y), circle_avatar)
    
    # 绘制名字
    text_x = avatar_x + avatar_size + avatar_margin
    name_y = avatar_y + 2  # 名字略微下移对齐
    
    draw.text((text_x, name_y), sender_name, font=name_font, fill=colors["name_color"])
    
    # 绘制等级标签（如果有）
    if level is not None:
        name_width, _ = get_text_size(sender_name, name_font)
        level_text = f"LV{level}"
        level_width, level_height = get_text_size(level_text, level_font)
        
        level_padding_h = 6
        level_padding_v = 2
        level_x = text_x + name_width + 8
        level_y = name_y + 2
        
        # 绘制等级标签背景
        draw.rounded_rectangle(
            [level_x, level_y, level_x + level_width + level_padding_h * 2, level_y + level_height + level_padding_v * 2],
            radius=3,
            fill=colors["level_bg"]
        )
        
        # 绘制等级文字
        draw.text((level_x + level_padding_h, level_y + level_padding_v), level_text, font=level_font, fill=colors["level_color"])
    
    # 绘制消息内容
    content_y = name_y + header_height + content_top_margin
    
    for line in content_lines:
        draw.text((text_x, content_y), line, font=content_font, fill=colors["text_color"])
        content_y += line_height
    
    # 转换为字节
    buffer = io.BytesIO()
    img = img.convert("RGB")  # 转换为 RGB 以保存为 PNG
    img.save(buffer, format='PNG', quality=95)
    buffer.seek(0)
    
    return buffer.getvalue()

# ==================== 命令处理 ====================

save_cmd = on_command("save", aliases={"保存", "截图", "quote", "语录"}, priority=5, block=True)

@save_cmd.handle()
async def handle_save(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """
    消息截图保存功能
    使用方法：回复一条消息，然后发送 /save
    """
    
    # 检查是否是回复消息
    reply = event.reply
    if not reply:
        await save_cmd.finish(
            "📸 消息截图功能\n"
            "━━━━━━━━━━━━━━\n"
            "使用方法：回复一条消息后发送 /save"
        )
        return
    
    try:
        # 获取被回复消息的内容
        reply_content = reply.message.extract_plain_text().strip()
        
        if not reply_content:
            await save_cmd.finish("❌ 无法获取消息内容，可能是图片或其他非文本消息")
            return
        
        # 获取发送者信息
        sender_id = reply.sender.user_id
        sender_name = reply.sender.nickname or str(sender_id)
        
        # 群聊中优先使用群名片
        if hasattr(reply.sender, 'card') and reply.sender.card:
            sender_name = reply.sender.card
        
        # 尝试获取用户等级（如果是群聊）
        level = None
        if isinstance(event, GroupMessageEvent):
            try:
                member_info = await bot.get_group_member_info(
                    group_id=event.group_id, 
                    user_id=sender_id
                )
                level = member_info.get('level')
                # 如果获取到群名片，更新名字
                if member_info.get('card'):
                    sender_name = member_info['card']
            except Exception as e:
                logger.debug(f"获取群成员信息失败: {e}")
        
        await save_cmd.send(f"🎨 正在生成截图...")
        
        # 生成图片
        image_bytes = await render_quote_image(
            sender_name=sender_name,
            sender_id=sender_id,
            content=reply_content,
            level=level
        )
        

        
        # 发送图片
        await save_cmd.finish(MessageSegment.image(image_bytes))
        
    except Exception as e:
        logger.error(f"生成消息截图失败: {e}")
        #await save_cmd.finish(f"❌ 生成截图失败: {str(e)}")

