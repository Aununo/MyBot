import random
import os
import json
from pathlib import Path
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.matcher import Matcher


plugin_dir = Path(__file__).parent

data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir

data_file = data_dir / "eat_data.json"

image_folder = plugin_dir / "assets" / "food_images"
image_folder.mkdir(parents=True, exist_ok=True) 


food_data = {}

shuffled_lists = {}
last_recommended = {}  # 记录每个列表上次推荐的食物
original_lists_snapshot = {}  # 记录原始列表的快照，用于检测列表是否被修改

def save_data():
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(food_data, f, ensure_ascii=False, indent=4)

def load_data():
    global food_data
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            food_data = json.load(f)
    else:
        food_data = {
            "android": [],
            "apple": []
        }
        save_data()

load_data()


android = on_command("android", priority=1)
apple = on_command("apple", priority=1)


async def handle_food_command(matcher: Matcher, bot: Bot, event: MessageEvent, list_name: str, args: Message = CommandArg()):
    arg_str = args.extract_plain_text().strip()
    parts = arg_str.split(maxsplit=1)
    subcommand = parts[0] if parts else ""

    if subcommand == "list":
        food_list = food_data.get(list_name, [])
        if not food_list:
            await matcher.finish(f"[{list_name}] 的食物列表是空的哦！")
        
        # 构建合并转发消息
        ITEMS_PER_NODE = 10
        forward_nodes = []
        
        # 第一个节点：概要信息
        header = f"📋 [{list_name}] 食物列表共有 {len(food_list)} 项"
        forward_nodes.append({
            "type": "node",
            "data": {
                "uin": str(bot.self_id),
                "content": header
            }
        })
        
        # 将食物列表分组
        for i in range(0, len(food_list), ITEMS_PER_NODE):
            chunk = food_list[i:i + ITEMS_PER_NODE]
            page_num = (i // ITEMS_PER_NODE) + 1
            total_pages = (len(food_list) + ITEMS_PER_NODE - 1) // ITEMS_PER_NODE
            
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
            if event.message_type == "group":
                await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=forward_nodes)
            else:
                await bot.call_api("send_private_forward_msg", user_id=event.user_id, messages=forward_nodes)
        except Exception as e:
            # 降级：发送普通消息
            fallback_msg = header + "\n" + "\n".join(food_list[:50])
            if len(food_list) > 50:
                fallback_msg += f"\n... 共 {len(food_list)} 项，仅显示前 50 项"
            await matcher.finish(fallback_msg)
        return

    # --- 添加食物 ---
    elif subcommand == "add" and len(parts) > 1:
        food_to_add = parts[1].strip()
        if food_to_add in food_data[list_name]:
            await matcher.finish(f"“{food_to_add}”已经在列表里啦！")
        
        food_data[list_name].append(food_to_add)
        save_data()
        await matcher.finish(f"已将“{food_to_add}”添加到 [{list_name}] 列表！")

    # --- 删除食物 ---
    elif subcommand == "del" and len(parts) > 1:
        food_to_del = parts[1].strip()
        if food_to_del not in food_data[list_name]:
            await matcher.finish(f"列表里没有“{food_to_del}”哦。")
        
        food_data[list_name].remove(food_to_del)
        save_data()
        await matcher.finish(f"已从 [{list_name}] 列表中删除“{food_to_del}”！")

    # --- 随机推荐 (默认行为) ---
    elif not subcommand:
        current_list = food_data.get(list_name, [])
        if not current_list:
            await matcher.finish(f"[{list_name}] 的食物列表是空的，快去添加一些吧！")
            return
        
        # 判断是否需要重新洗牌：
        # 1. 列表为空（抽完了）
        # 2. 原始列表被修改了（用户添加/删除了食物）
        need_reshuffle = False
        
        if not shuffled_lists.get(list_name):
            # 情况1：首次使用或抽完了
            need_reshuffle = True
        elif set(original_lists_snapshot.get(list_name, [])) != set(current_list):
            # 情况2：原始列表被修改了（和快照不一致）
            need_reshuffle = True
            print(f"[{list_name}] 检测到食物列表被修改")
        
        if need_reshuffle:
            print(f"[{list_name}] 正在重新洗牌...")
            shuffled_lists[list_name] = current_list.copy()
            random.shuffle(shuffled_lists[list_name])
            original_lists_snapshot[list_name] = current_list.copy()  # 保存快照
            
            # 避免连续推荐相同食物：如果上次推荐的食物在列表末尾，就把它换到其他位置
            if len(shuffled_lists[list_name]) > 1 and list_name in last_recommended:
                last_food = last_recommended[list_name]
                if shuffled_lists[list_name][-1] == last_food:
                    # 把末尾的食物和第一个食物交换位置
                    shuffled_lists[list_name][0], shuffled_lists[list_name][-1] = \
                        shuffled_lists[list_name][-1], shuffled_lists[list_name][0]
                    print(f"[{list_name}] 避免连续推荐 {last_food}，已重新排列")
        
        food = shuffled_lists[list_name].pop()
        last_recommended[list_name] = food  # 记录本次推荐

        image_path = image_folder / f"{food}.jpg"

        greeting = "上学辛苦了！" if list_name == "android" else "假期要好好休息哦！"
        message_text = f"{greeting}浅浅推荐你吃：{food}"

        if image_path.exists():
            await matcher.finish(Message(message_text + "\n") + MessageSegment.image(file=image_path))
        else:
            await matcher.finish(message_text + "（没有找到图片）")

    else:
        await matcher.finish(f"无效指令。可用指令：\n/{list_name} list\n/{list_name} add <食物>\n/{list_name} del <食物>")


@android.handle()
async def _(matcher: Matcher, bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    await handle_food_command(matcher, bot, event, "android", args)

@apple.handle()
async def _(matcher: Matcher, bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    await handle_food_command(matcher, bot, event, "apple", args)