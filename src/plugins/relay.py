import json
from pathlib import Path
from typing import Dict

from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent, Message
from nonebot.params import CommandArg


plugin_dir = Path(__file__).parent

data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir

data_file = data_dir / "relay_data.json"


# 数据结构: {group_id: {"event": "事件名", "participants": [{"user_id": "123", "nickname": "昵称"}]}}
relay_data: Dict[str, Dict] = {}


def save_data():
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(relay_data, f, ensure_ascii=False, indent=4)


def load_data():
    global relay_data
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            try:
                relay_data = json.load(f)
            except json.JSONDecodeError:
                relay_data = {}
    else:
        relay_data = {}


def get_user_nickname(event: MessageEvent) -> str:
    """获取用户昵称，优先使用群昵称，否则使用QQ昵称"""
    if isinstance(event, GroupMessageEvent):
        # 群聊：优先使用群昵称（card），如果没有则使用QQ昵称
        return event.sender.card or event.sender.nickname or f"用户{event.user_id}"
    else:
        return event.sender.nickname or f"用户{event.user_id}"


load_data()

relay = on_command("接龙", priority=5, block=True)


@relay.handle()
async def handle_relay(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    if not isinstance(event, GroupMessageEvent):
        await matcher.finish("接龙功能仅在群聊中可用哦！")
        return
    
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    nickname = get_user_nickname(event)
    event_text = args.extract_plain_text().strip()

    if event_text:
        parts = event_text.split(maxsplit=1)
        subcommand = parts[0].lower()
        
        # 删除接龙
        if subcommand in ["删除", "del", "delete", "clear"]:
            if group_id not in relay_data or not relay_data[group_id]:
                await matcher.finish("当前群还没有接龙任务哦！")
                return
            
            current_event = relay_data[group_id].get("event", "")
            del relay_data[group_id]
            save_data()
            await matcher.finish(f"✅ 已删除接龙任务：{current_event}")
            return
        
        # 查看接龙
        if subcommand in ["查看", "view", "list", "显示"]:
            if group_id not in relay_data or not relay_data[group_id]:
                await matcher.finish("当前群还没有接龙任务哦！")
                return
            
            current_relay = relay_data[group_id]
            current_event = current_relay.get("event", "")
            participants = current_relay.get("participants", [])
            
            if not participants:
                await matcher.finish(f"接龙：{current_event}\n\n（暂无参与者）")
                return
            
            reply = f"📝 接龙：{current_event}\n\n"
            for i, p in enumerate(participants, 1):
                reply += f"{i}. {p['nickname']}\n"
            
            await matcher.finish(reply.strip())
            return
    
    # 如果当前群没有接龙，需要创建新的
    if group_id not in relay_data or not relay_data[group_id]:
        if not event_text:
            await matcher.finish("请指定接龙事件！\n用法：/接龙 xxx事件")
            return
        
        # 创建新接龙
        relay_data[group_id] = {
            "event": event_text,
            "participants": [{"user_id": user_id, "nickname": nickname}]
        }
        save_data()
        
        reply = f"📝 接龙：{event_text}\n\n1. {nickname}"
        await matcher.finish(reply)
    
    # 如果当前群已有接龙
    current_relay = relay_data[group_id]
    current_event = current_relay.get("event", "")
    participants = current_relay.get("participants", [])
    
    # 如果提供了新的事件名，且与当前不同，则创建新接龙
    if event_text and event_text != current_event:
        relay_data[group_id] = {
            "event": event_text,
            "participants": [{"user_id": user_id, "nickname": nickname}]
        }
        save_data()
        
        reply = f"📝 接龙：{event_text}\n\n1. {nickname}"
        await matcher.finish(reply)
    
    # 检查用户是否已经参与
    existing_index = -1
    for i, p in enumerate(participants):
        if p["user_id"] == user_id:
            existing_index = i
            break
    
    if existing_index >= 0:
        participants[existing_index]["nickname"] = nickname
        save_data()
        await matcher.finish(f"你已经参与过这个接龙了！\n当前接龙：{current_event}\n你的位置：第{existing_index + 1}位")
        return
    
    participants.append({"user_id": user_id, "nickname": nickname})
    relay_data[group_id]["participants"] = participants
    save_data()
    
    # 生成回复消息
    reply = f"📝 接龙：{current_event}\n\n"
    for i, p in enumerate(participants, 1):
        reply += f"{i}. {p['nickname']}\n"
    
    await matcher.finish(reply.strip())

