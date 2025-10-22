import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from zoneinfo import ZoneInfo
from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.params import CommandArg
from nonebot.log import logger


plugin_dir = Path(__file__).parent

data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir

data_file = data_dir / "countdown_data.json"


try:
    TARGET_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    logger.error("加载时区 'Asia/Shanghai' 失败，请确保 Python 版本 >= 3.9 或已安装 tzdata (pip install tzdata)。")
    TARGET_TZ = None


CountdownDataType = Dict[str, Dict[str, Dict[str, Any]]]
countdown_data: CountdownDataType = {}


def save_data():
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(countdown_data, f, ensure_ascii=False, indent=4)


def load_data():
    global countdown_data
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            try:
                countdown_data = json.load(f)
            except json.JSONDecodeError:
                countdown_data = {}
    else:
        countdown_data = {}


def init_user_data(user_id: str):
    if user_id not in countdown_data:
        countdown_data[user_id] = {}


def parse_datetime(date_str: str) -> datetime:
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y.%m.%d",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=TARGET_TZ)
        except ValueError:
            continue
    
    raise ValueError("无法解析时间格式")


def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    
    if total_seconds < 0:
        return None
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}秒")
    
    return "".join(parts)


load_data()


time_matcher = on_command("time", priority=5, block=True)


@time_matcher.handle()
async def handle_time(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = str(event.user_id)
    plain_text = args.extract_plain_text().strip()
    
    init_user_data(user_id)
    
    if not plain_text:
        if not countdown_data[user_id]:
            await matcher.finish(
                "⏰ 倒计时功能使用说明：\n\n"
                "📌 添加事件：\n"
                "/time add <事件名> <截止时间>\n"
                "时间格式支持：\n"
                "  • 2025-12-31\n"
                "  • 2025-12-31 23:59\n"
                "  • 2025/12/31 23:59:59\n\n"
                "🔍 查看事件：\n"
                "/time <事件名>\n\n"
                "📋 查看所有事件：\n"
                "/time list\n\n"
                "🗑️ 删除事件：\n"
                "/time del <事件名>"
            )
        else:
            parts = ["⏰ 你的所有倒计时事件：\n"]
            now = datetime.now(TARGET_TZ)
            active_events = []
            
            for event_name, event_data in countdown_data[user_id].items():
                event_time = datetime.fromisoformat(event_data["time"])
                td = event_time - now
                
                if td.total_seconds() > 0:
                    time_left = format_timedelta(td)
                    active_events.append(f"📌 {event_name}\n   截止：{event_data['time']}\n   剩余：{time_left}")
                else:
                    active_events.append(f"📌 {event_name}\n   截止：{event_data['time']}\n   ⚠️ 已过期")
            
            if active_events:
                parts.append("\n\n".join(active_events))
                await matcher.finish("\n".join(parts))
            else:
                await matcher.finish("你还没有添加任何倒计时事件！\n使用 /time add <事件名> <截止时间> 来添加吧。")
        return
    
    parts = plain_text.split(maxsplit=1)
    command = parts[0].lower()
    
    if command == "add":
        if len(parts) < 2:
            await matcher.finish("❌ 用法：/time add <事件名> <截止时间>\n例如：/time add 考试 2025-12-31 18:00")
            return
        
        event_parts = parts[1].split(maxsplit=1)
        if len(event_parts) < 2:
            await matcher.finish("❌ 请提供事件名和截止时间！\n用法：/time add <事件名> <截止时间>")
            return
        
        event_name = event_parts[0]
        time_str = event_parts[1]
        
        try:
            event_time = parse_datetime(time_str)
        except ValueError:
            await matcher.finish(
                "❌ 时间格式不正确！\n\n"
                "支持的格式：\n"
                "  • 2025-12-31\n"
                "  • 2025-12-31 23:59\n"
                "  • 2025/12/31 23:59:59"
            )
            return
        
        now = datetime.now(TARGET_TZ)
        if event_time <= now:
            await matcher.finish("❌ 截止时间必须是未来的时间！")
            return
        
        countdown_data[user_id][event_name] = {
            "time": event_time.isoformat(),
            "created_at": now.isoformat()
        }
        save_data()
        
        td = event_time - now
        time_left = format_timedelta(td)
        
        await matcher.finish(
            f"✅ 已添加倒计时事件：\n\n"
            f"📌 事件：{event_name}\n"
            f"⏰ 截止：{event_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏳ 剩余：{time_left}"
        )
    
    elif command == "del" or command == "delete":
        if len(parts) < 2:
            await matcher.finish("❌ 用法：/time del <事件名>")
            return
        
        event_name = parts[1].strip()
        
        if event_name not in countdown_data[user_id]:
            await matcher.finish(f"❌ 事件 '{event_name}' 不存在！")
            return
        
        del countdown_data[user_id][event_name]
        save_data()
        
        await matcher.finish(f"🗑️ 已删除事件：{event_name}")
    
    elif command == "list":
        if not countdown_data[user_id]:
            await matcher.finish("你还没有添加任何倒计时事件！\n使用 /time add <事件名> <截止时间> 来添加吧。")
            return
        
        parts_list = ["⏰ 你的所有倒计时事件：\n"]
        now = datetime.now(TARGET_TZ)
        active_events = []
        
        for event_name, event_data in countdown_data[user_id].items():
            event_time = datetime.fromisoformat(event_data["time"])
            td = event_time - now
            
            if td.total_seconds() > 0:
                time_left = format_timedelta(td)
                active_events.append(f"📌 {event_name}\n   截止：{event_data['time']}\n   剩余：{time_left}")
            else:
                active_events.append(f"📌 {event_name}\n   截止：{event_data['time']}\n   ⚠️ 已过期")
        
        parts_list.append("\n\n".join(active_events))
        await matcher.finish("\n".join(parts_list))
    
    else:
        event_name = plain_text
        
        if event_name not in countdown_data[user_id]:
            await matcher.finish(
                f"❌ 事件 '{event_name}' 不存在！\n\n"
                "💡 提示：\n"
                "• 使用 /time list 查看所有事件\n"
                "• 使用 /time add <事件名> <截止时间> 添加新事件"
            )
            return
        
        event_data = countdown_data[user_id][event_name]
        event_time = datetime.fromisoformat(event_data["time"])
        now = datetime.now(TARGET_TZ)
        td = event_time - now
        
        if td.total_seconds() > 0:
            time_left = format_timedelta(td)
            await matcher.finish(
                f"📌 事件：{event_name}\n\n"
                f"⏰ 截止时间：{event_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⏳ 剩余时间：{time_left}"
            )
        else:
            await matcher.finish(
                f"📌 事件：{event_name}\n\n"
                f"⏰ 截止时间：{event_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⚠️ 该事件已过期！"
            )

