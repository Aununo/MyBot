import os
import re
import httpx
import random
import shutil
from pathlib import Path

from nonebot import on_command, on_message, logger
from nonebot.exception import FinishedException
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
    """解析参数以确定目标目录和剩余参数。"""
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


# --- 核心安全修复：路径验证辅助函数 ---

def get_safe_path(base_dir: Path, user_filename: str) -> Path:
    """
    验证用户提供的文件名以防止路径遍历，并返回一个安全的 Path 对象。

    Raises:
        ValueError: 如果文件名无效、为空或包含路径遍历字符。
    """
    # 1. 使用 basename 清理输入。这会剥离所有目录信息。
    #    例如: "../../etc/passwd" -> "passwd"
    sanitized_filename = os.path.basename(user_filename)

    # 2. 检查输入是否尝试遍历或为空。
    if sanitized_filename != user_filename or not sanitized_filename:
        logger.warning(f"检测到潜在的路径遍历或非法文件名: {user_filename}")
        raise ValueError(f"错误：文件名 '{user_filename}' 包含非法路径字符或为空。")

    # 3. 与基础目录安全合并
    target_path = base_dir / sanitized_filename
    
    # 4. 解析（Resolve）基础目录的绝对路径
    resolved_base = base_dir.resolve()
    
    # 5. 解析目标路径的 *父目录* 的绝对路径
    #    此步骤会处理 base_dir 中的任何符号链接或 ".."
    resolved_target_parent = target_path.parent.resolve()

    # 6. 解析后的父目录必须与解析后的基础目录完全相同
    if resolved_target_parent != resolved_base:
        logger.warning(f"路径安全检查失败：解析后的父路径 '{resolved_target_parent}' "
                       f"与基础路径 '{resolved_base}' 不匹配。")
        raise ValueError("错误：文件路径解析后在允许的目录之外。")

    # 7. 返回*未解析*的路径。
    #    它是安全的，因为我们已验证了其目录并使用了清理后的文件名。
    return target_path


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

    try:
        # --- 安全修复 ---
        # 1. 验证路径和文件名
        save_path = get_safe_path(save_dir, filename_arg)
        
        # 2. 在安全路径上检查扩展名
        file_ext = save_path.suffix.lower()
        if not file_ext or file_ext not in SUPPORTED_EXTENSIONS:
            await savepic.finish("文件名格式不正确，必须包含支持的图片或视频扩展名。")

        # 3. 检查文件是否存在
        if save_path.exists():
            await savepic.finish(f"保存失败：名为“{save_path.name}”的文件已在 [{folder_display_name}] 文件夹中存在。")
            
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(media_url)
            response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)

        await savepic.finish(f"文件已保存至 [{folder_display_name}] 文件夹: {save_path.name}")

    except ValueError as e:
        await savepic.finish(str(e))
    except httpx.HTTPError as e:
        await savepic.finish(f"下载文件失败，网络错误或链接失效: {e}")
    except IOError as e:
        logger.error(f"保存文件时发生IO错误: {e}")
        await savepic.finish("保存文件时发生文件写入错误，请检查后台日志。")


# --- 2. 发送表情 /sendpic ---
sendpic = on_command("sendpic", priority=1, block=True)

@sendpic.handle()
async def sendpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    if not raw_args:
        await sendpic.finish("请提供要发送的文件名。\n用法: /sendpic [--eat] <文件名>")

    target_dir, display_name, filename_arg = parse_args_for_dir(raw_args)

    try:
        file_path = get_safe_path(target_dir, filename_arg)
        
        if file_path.exists() and file_path.is_file():
            msg_segment = None
            try:
                # 使用 resolve() 获取绝对路径以发送文件
                resolved_path = file_path.resolve()
                if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                    msg_segment = MessageSegment.image(file=resolved_path)
                elif file_path.suffix.lower() in VIDEO_EXTENSIONS:
                    msg_segment = MessageSegment.video(file=resolved_path)
                else:
                    await sendpic.finish(f"错误：不支持的文件类型: {file_path.suffix}")
                    return
            except Exception as e:
                await sendpic.finish(f"发送文件失败了 T_T\n错误：文件处理异常 ({e})。")
                return
            
            await sendpic.finish(msg_segment)
        else:
            await sendpic.finish(f"在 [{display_name}] 库中未找到文件: {file_path.name}")

    except ValueError as e:
        await sendpic.finish(str(e))


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

    # --- '--all' 分支---
    if action_arg == "--all":
        try:
            if not target_dir.is_dir():
                await rmpic.finish(f"文件夹 [{display_name}] 不存在。")
                return

            all_files = [f for f in target_dir.iterdir() if f.is_file()]
            
            if not all_files:
                await rmpic.finish(f"文件夹 [{display_name}] 已经是空的了。")
                return
            
            for file_to_delete in all_files:
                os.remove(file_to_delete)
                
        except OSError as e:
            logger.error(f"清空文件夹 {display_name} 时发生错误: {e}")
            await rmpic.finish(f"清空文件夹时发生错误，请检查后台日志。")
            return
        
        await rmpic.finish(f"操作成功！已清空文件夹 [{display_name}]。")
        return

    # --- 单文件删除分支 (使用重构后的安全逻辑) ---
    try:
        # --- 安全修复 ---
        file_path = get_safe_path(target_dir, action_arg)

        if file_path.exists() and file_path.is_file():
            try:
                os.remove(file_path)
            except OSError as e:
                logger.error(f"删除文件时发生错误: {e}")
                await rmpic.finish(f"删除文件时发生错误，请检查后台日志。")
                return
            
            await rmpic.finish(f"文件“{file_path.name}”已从 [{display_name}] 中成功删除。")
        else:
            await rmpic.finish(f"在文件夹 [{display_name}] 中未找到文件: {file_path.name}")

    except ValueError as e:
        # 捕获来自 get_safe_path 的安全错误
        await rmpic.finish(str(e))


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

    try:
        old_filename, new_filename = parts[0], parts[1]
        
        # --- 安全修复 ---
        # 1. 验证旧文件路径
        old_path = get_safe_path(target_dir, old_filename)
        if not old_path.exists() or not old_path.is_file():
            await mvpic.finish(f"在 [{display_name}] 中找不到要重命名的文件: {old_path.name}")
            return
        
        # 2. 验证新文件路径
        new_path = get_safe_path(target_dir, new_filename)

        # 3. 检查新文件扩展名是否有效 (与旧文件类型保持一致)
        old_ext = old_path.suffix.lower()
        new_ext = new_path.suffix.lower()

        if (old_ext in IMAGE_EXTENSIONS and new_ext not in IMAGE_EXTENSIONS) or \
           (old_ext in VIDEO_EXTENSIONS and new_ext not in VIDEO_EXTENSIONS):
            await mvpic.finish(f"重命名失败：新文件扩展名 '{new_ext}' "
                               f"与旧文件类型不兼容或不受支持。")
            return

        if new_path.exists():
            await mvpic.finish(f"重命名失败: 文件“{new_path.name}”已在 [{display_name}] 中存在。")
            return

        # 4. 执行移动
        shutil.move(old_path, new_path)
            
        await mvpic.finish(f"在 [{display_name}] 中，已将“{old_path.name}”重命名为“{new_path.name}”。")

    except ValueError as e:
        # 捕获来自 get_safe_path 的安全错误
        await mvpic.finish(str(e))
    except OSError as e:
        logger.error(f"重命名文件时发生错误: {e}")
        await mvpic.finish(f"重命名文件时发生错误，请检查后台日志。")


# --- 5. 列出所有表情 /listpic ---
listpic = on_command("listpic", priority=1, block=True)

@listpic.handle()
async def listpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    target_dir, display_name, keyword = parse_args_for_dir(raw_args)
    
    all_files_names = []
    try:
        # os.listdir 返回的是文件名列表，不是完整路径，这是安全的
        all_files_names = [f for f in os.listdir(target_dir) 
                           if (target_dir / f).is_file()]
    except Exception as e:
        await listpic.finish(f"读取文件夹 [{display_name}] 时发生错误: {e}")
        return

    if not all_files_names:
        await listpic.finish(f"文件夹 [{display_name}] 是空的哦！")
        return

    files = [f for f in all_files_names if keyword in f] if keyword else all_files_names
    
    if not files:
        await listpic.finish(f"在 [{display_name}] 中没有找到包含“{keyword}”的文件。")
        return
    
    # 构建合并转发消息
    FILES_PER_NODE = 10
    
    # 构造转发消息节点
    forward_nodes = []
    
    # 第一个节点：概要信息
    header = f"📁 文件夹 [{display_name}] 中共有 {len(files)} 个文件{' (含关键词)' if keyword else ''}"
    forward_nodes.append({
        "type": "node",
        "data": {
            "uin": str(bot.self_id),
            "content": header
        }
    })
    
    # 将文件列表分组
    for i in range(0, len(files), FILES_PER_NODE):
        chunk = files[i:i + FILES_PER_NODE]
        page_num = (i // FILES_PER_NODE) + 1
        total_pages = (len(files) + FILES_PER_NODE - 1) // FILES_PER_NODE
        
        content = f"📄 第 {page_num}/{total_pages} 页\n" + "─" * 15 + "\n"
        content += "\n".join(chunk)
        
        forward_nodes.append({
            "type": "node",
            "data": {
                "uin": str(bot.self_id),
                "content": content
            }
        })
    
    try:
        # 根据消息类型选择合适的转发方式
        if event.message_type == "group":
            await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=forward_nodes)
        else:
            await bot.call_api("send_private_forward_msg", user_id=event.user_id, messages=forward_nodes)
    except Exception as e:
        logger.error(f"发送合并转发消息失败: {e}")
        # 降级：如果转发消息发送失败，尝试发送普通消息
        fallback_msg = header + "\n" + "\n".join(files[:50])
        if len(files) > 50:
            fallback_msg += f"\n... 共 {len(files)} 个文件，仅显示前 50 个"
        await listpic.finish(fallback_msg)


# --- 6. 随机发送表情 /randpic ---
randpic = on_command("randpic", aliases={"随机表情"}, priority=1, block=True)

@randpic.handle()
async def randpic_handle(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    raw_args = args.extract_plain_text().strip()
    target_dir, display_name, keyword = parse_args_for_dir(raw_args)

    all_files_names = []
    try:
        all_files_names = [f for f in os.listdir(target_dir) 
                           if (target_dir / f).is_file()]
    except Exception as e:
        await randpic.finish(f"读取文件夹 [{display_name}] 失败: {e}")
        return
        
    if not all_files_names:
        await randpic.finish(f"文件夹 [{display_name}] 是空的！")
        return

    filtered_files = [f for f in all_files_names if keyword in f] if keyword else all_files_names
    if not filtered_files:
        await randpic.finish(f"在 [{display_name}] 中没找到含“{keyword}”的文件。")
        return
    
    random_pic_name = random.choice(filtered_files)
    # 路径是安全的，因为它由 safe_dir 和 listdir 返回的安全文件名组成
    file_path = target_dir / random_pic_name
    
    msg = None
    try:
        resolved_path = file_path.resolve() # 解析为绝对路径以发送
        if file_path.suffix.lower() in IMAGE_EXTENSIONS:
            msg = MessageSegment.image(file=resolved_path)
        elif file_path.suffix.lower() in VIDEO_EXTENSIONS:
            msg = MessageSegment.video(file=resolved_path)
        else:
            await randpic.finish(f"错误：不支持的文件类型: {file_path.suffix}")
            return
    except Exception as e:
        await randpic.finish(f"发送文件失败: {e}")
        return
        
    await randpic.finish(msg)


# --- 7. 自动回复表情（关键词触发） ---
autopic_shuffled_lists = {}
autopic_original_snapshots = {}
autopic_last_sent = {}

autopic = on_message(priority=99, block=False)

@autopic.handle()
async def autopic_handle(bot: Bot, event: MessageEvent):
    if event.message_type != "group":
        return
    
    msg_text = event.get_plaintext().strip()
    if not msg_text:
        return
    
    if msg_text.startswith("/") or msg_text.startswith("！") or msg_text.startswith("!"):
        return
    
    try:
        all_files = [f for f in os.listdir(default_pics_dir)
                     if (default_pics_dir / f).is_file()]
    except Exception as e:
        logger.error(f"读取默认文件夹时发生错误: {e}")
        return
    
    if not all_files:
        return
    
    matched_files = []
    keywords = msg_text.split()
    
    for filename in all_files:
        name_without_ext = Path(filename).stem
        
        if name_without_ext in msg_text:
            matched_files.append(filename)
            continue
        
        name_parts = re.split(r'[._-]', name_without_ext)
        name_parts = [part for part in name_parts if part]
        
        matched = False
        for keyword in keywords:
            if keyword in name_parts:
                matched = True
                break
        
        if matched:
            matched_files.append(filename)
    
    if not matched_files:
        return
    
    matched_files_set = frozenset(matched_files)
    set_key = matched_files_set
    
    need_reshuffle = False
    
    if not autopic_shuffled_lists.get(set_key):
        need_reshuffle = True
    elif autopic_original_snapshots.get(set_key) != matched_files_set:
        need_reshuffle = True
        logger.debug(f"检测到匹配文件集合被修改，重新洗牌")
    
    if need_reshuffle:
        autopic_shuffled_lists[set_key] = list(matched_files_set)
        random.shuffle(autopic_shuffled_lists[set_key])
        autopic_original_snapshots[set_key] = matched_files_set
        
        if len(autopic_shuffled_lists[set_key]) > 1 and set_key in autopic_last_sent:
            last_file = autopic_last_sent[set_key]
            if autopic_shuffled_lists[set_key][-1] == last_file:
                autopic_shuffled_lists[set_key][0], autopic_shuffled_lists[set_key][-1] = \
                    autopic_shuffled_lists[set_key][-1], autopic_shuffled_lists[set_key][0]
                logger.debug(f"避免连续发送 {last_file}，已重新排列")
    
    selected_file = autopic_shuffled_lists[set_key].pop()
    autopic_last_sent[set_key] = selected_file
    
    if len(matched_files) > 1:
        logger.debug(f"关键词 '{msg_text}' 匹配到 {len(matched_files)} 个文件，已选择: {selected_file}")
    
    # 路径是安全的，因为它由 safe_dir 和 listdir 返回的安全文件名组成
    file_path = default_pics_dir / selected_file
    
    try:
        resolved_path = file_path.resolve() # 解析为绝对路径以发送
        if file_path.suffix.lower() in IMAGE_EXTENSIONS:
            msg_segment = MessageSegment.image(file=resolved_path)
        elif file_path.suffix.lower() in VIDEO_EXTENSIONS:
            msg_segment = MessageSegment.video(file=resolved_path)
        else:
            return
        
        await autopic.finish(msg_segment)
    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"自动发送文件失败: {e}")
        return