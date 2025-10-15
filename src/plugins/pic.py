import os
import re
import httpx
import random
import shutil
from pathlib import Path

from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.typing import T_State


plugin_dir = Path(__file__).parent
assets_dir = plugin_dir / "assets"


SUBFOLDER_MAP = {
    "--eat": "food_images",
    "--latex": "latex"
}


default_pics_dir = assets_dir / "pics"
default_pics_dir.mkdir(parents=True, exist_ok=True)


for folder in SUBFOLDER_MAP.values():
    (assets_dir / folder).mkdir(parents=True, exist_ok=True)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS.union(VIDEO_EXTENSIONS)

def parse_args_for_dir(raw_args: str) -> tuple[Path, str, str]:
    arg_parts = raw_args.split(maxsplit=1)
    
    target_dir = default_pics_dir
    display_name = "默认表情"
    remaining_arg = raw_args

    if arg_parts and arg_parts[0] in SUBFOLDER_MAP:
        folder_name = SUBFOLDER_MAP[arg_parts[0]]
        target_dir = assets_dir / folder_name
        display_name = folder_name
        remaining_arg = arg_parts[1] if len(arg_parts) > 1 else ""
        
    return target_dir, display_name, remaining_arg.strip()


# --- 1. 保存表情 /savepic ---
savepic = on_command("savepic", priority=1, block=True)

@savepic.handle()
async def savepic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    if not event.reply:
        await savepic.finish("请回复一张图片或一个视频来保存。")

    media_url = ""
    for msg_seg in event.reply.message:
        if msg_seg.type in ["image", "video"]:
            media_url = msg_seg.data.get("url")
            break
    if not media_url:
        await savepic.finish("回复的消息中没有找到图片或视频。")

    raw_args = args.extract_plain_text().strip()
    if not raw_args:
        await savepic.finish("请提供参数和文件名，例如：/savepic [--eat] my_file.mp4")

    save_dir, folder_display_name, filename_arg = parse_args_for_dir(raw_args)

    if not filename_arg:
        await savepic.finish("错误：未提供文件名。")
        return

    file_ext = Path(filename_arg).suffix.lower()
    if not file_ext or file_ext not in SUPPORTED_EXTENSIONS:
        await savepic.finish("文件名格式不正确，必须包含支持的图片或视频扩展名。")

    save_path = save_dir / filename_arg
    if save_path.exists():
        await savepic.finish(f"保存失败：名为“{filename_arg}”的文件已在 [{folder_display_name}] 文件夹中存在。")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client: # 延长超时以支持视频
            response = await client.get(media_url)
            response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
    except httpx.HTTPError as e:
        await savepic.finish(f"下载文件失败，网络错误或链接失效: {e}")
        return
    except IOError as e:
        logger.error(f"保存文件时发生IO错误: {e}")
        await savepic.finish("保存文件时发生文件写入错误，请检查后台日志。")
        return

    await savepic.finish(f"文件已保存至 [{folder_display_name}] 文件夹: {filename_arg}")


# --- 2. 发送表情 /sendpic ---
sendpic = on_command("sendpic", priority=1, block=True)

@sendpic.handle()
async def sendpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    if not raw_args:
        await sendpic.finish("请提供要发送的文件名。\n用法: /sendpic [--eat] <文件名>")

    target_dir, display_name, filename_arg = parse_args_for_dir(raw_args)

    if not filename_arg:
        await sendpic.finish("错误：未提供文件名。")
        return

    file_path = target_dir / filename_arg
    
    if file_path.exists() and file_path.is_file():
        msg_segment = None
        try:
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                msg_segment = MessageSegment.image(file=file_path)
            elif file_path.suffix.lower() in VIDEO_EXTENSIONS:
                msg_segment = MessageSegment.video(file=file_path)
            else:
                await sendpic.finish(f"错误：不支持的文件类型: {file_path.suffix}")
                return
        except Exception as e:
            await sendpic.finish(f"发送文件失败了 T_T\n错误：文件处理异常 ({e})。")
            return
        
        await sendpic.finish(msg_segment)
    else:
        await sendpic.finish(f"在 [{display_name}] 库中未找到文件: {filename_arg}")


# --- 3. 删除表情 /rmpic ---
rmpic = on_command("rmpic", priority=1, block=True)

@rmpic.handle()
async def rmpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    if not raw_args:
        await rmpic.finish("请提供要删除的文件名，或使用 '--all' 清空。\n用法: /rmpic [--eat] <文件名 | --all>")

    target_dir, display_name, action_arg = parse_args_for_dir(raw_args)

    if not action_arg:
         await rmpic.finish("错误：未提供文件名或 '--all' 参数。")
         return

    if action_arg in ["--all", "*"]:
        try:
            all_files = [f for f in os.listdir(target_dir) if os.path.isfile(target_dir / f)]
            if not all_files:
                await rmpic.finish(f"文件夹 [{display_name}] 已经是空的了。")
                return
            
            for filename in all_files:
                os.remove(target_dir / filename)
        except OSError as e:
            logger.error(f"清空文件夹 {display_name} 时发生错误: {e}")
            await rmpic.finish(f"清空文件夹时发生错误，请检查后台日志。")
            return
        
        await rmpic.finish(f"操作成功！已清空文件夹 [{display_name}]。")
        return

    file_path = target_dir / action_arg
    if file_path.exists() and file_path.is_file():
        try:
            os.remove(file_path)
        except OSError as e:
            logger.error(f"删除文件时发生错误: {e}")
            await rmpic.finish(f"删除文件时发生错误，请检查后台日志。")
            return
        
        await rmpic.finish(f"文件“{action_arg}”已从 [{display_name}] 中成功删除。")
    else:
        await rmpic.finish(f"在文件夹 [{display_name}] 中未找到文件: {action_arg}")


# --- 4. 重命名表情 /mvpic ---
mvpic = on_command("mvpic", priority=1, block=True)

@mvpic.handle()
async def mvpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    target_dir, display_name, remaining_args = parse_args_for_dir(raw_args)
    
    parts = remaining_args.split()
    if len(parts) != 2:
        await mvpic.finish("参数格式不正确！\n用法：/mvpic [--eat] <旧文件名> <新文件名>")
        return

    old_filename, new_filename = parts[0], parts[1]
    
    old_path = target_dir / old_filename
    if not old_path.exists() or not old_path.is_file():
        await mvpic.finish(f"在 [{display_name}] 中找不到要重命名的文件: {old_filename}")
        return

    new_path = target_dir / new_filename
    if new_path.exists():
        await mvpic.finish(f"重命名失败: 文件“{new_filename}”已在 [{display_name}] 中存在。")
        return

    try:
        shutil.move(old_path, new_path)
    except OSError as e:
        logger.error(f"重命名文件时发生错误: {e}")
        await mvpic.finish(f"重命名文件时发生错误，请检查后台日志。")
        return
        
    await mvpic.finish(f"在 [{display_name}] 中，已将“{old_filename}”重命名为“{new_filename}”。")


# --- 5. 列出所有表情 /listpic ---
listpic = on_command("listpic", priority=1, block=True)

@listpic.handle()
async def listpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    target_dir, display_name, keyword = parse_args_for_dir(raw_args)
    
    all_files = []
    try:
        all_files = [f for f in os.listdir(target_dir) if os.path.isfile(target_dir / f)]
    except Exception as e:
        await listpic.finish(f"读取文件夹 [{display_name}] 时发生错误: {e}")
        return

    if not all_files:
        await listpic.finish(f"文件夹 [{display_name}] 是空的哦！")
        return

    files = [f for f in all_files if keyword in f] if keyword else all_files
    
    if not files:
        await listpic.finish(f"在 [{display_name}] 中没有找到包含“{keyword}”的文件。")
        return
    
    header = f"文件夹 [{display_name}] 中共有 {len(files)} 个文件{' (含关键词)' if keyword else ''}："
    await listpic.finish(header + "\n" + "\n".join(files))


# --- 6. 随机发送表情 /randpic ---
randpic = on_command("randpic", aliases={"随机表情"}, priority=1, block=True)

@randpic.handle()
async def randpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    target_dir, display_name, keyword = parse_args_for_dir(raw_args)

    all_files = []
    try:
        all_files = [f for f in os.listdir(target_dir) if os.path.isfile(target_dir / f)]
    except Exception as e:
        await randpic.finish(f"读取文件夹 [{display_name}] 失败: {e}")
        return
        
    if not all_files:
        await randpic.finish(f"文件夹 [{display_name}] 是空的！")
        return

    filtered_files = [f for f in all_files if keyword in f] if keyword else all_files
    if not filtered_files:
        await randpic.finish(f"在 [{display_name}] 中没找到含“{keyword}”的文件。")
        return
    
    random_pic_name = random.choice(filtered_files)
    file_path = target_dir / random_pic_name
    
    msg = None
    try:
        if file_path.suffix.lower() in IMAGE_EXTENSIONS:
            msg = MessageSegment.image(file=file_path)
        elif file_path.suffix.lower() in VIDEO_EXTENSIONS:
            msg = MessageSegment.video(file=file_path)
        else:
            await randpic.finish(f"错误：不支持的文件类型: {file_path.suffix}")
            return
    except Exception as e:
        await randpic.finish(f"发送文件失败: {e}")
        return
        
    await randpic.finish(msg)

