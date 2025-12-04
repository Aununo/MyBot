import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

from zoneinfo import ZoneInfo
from nonebot import on_command, get_bot, logger
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, Message
from nonebot.params import CommandArg
from nonebot.matcher import Matcher
from nonebot.exception import FinishedException

# 设置目标时区为中国时区（UTC+8）
try:
    TARGET_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    logger.error("加载时区 'Asia/Shanghai' 失败，请确保 Python 版本 >= 3.9 或已安装 tzdata (pip install tzdata)。")
    TARGET_TZ = None


plugin_dir = Path(__file__).parent

data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir

usage_data_file = data_dir / "usage_data.json"


# 新的数据结构：
# {
#     "sent_messages": [
#         {"timestamp": 1234567890, "hour": 14, "date": "2024-01-01", "weekday": "Monday"},
#         ...
#     ]
# }
usage_data: Dict[str, List[Dict]] = {"sent_messages": []}


def save_data():
    """保存使用数据到文件"""
    try:
        with open(usage_data_file, "w", encoding="utf-8") as f:
            json.dump(usage_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存使用数据失败: {e}")


def load_data():
    """从文件加载使用数据"""
    global usage_data
    try:
        if usage_data_file.exists():
            with open(usage_data_file, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict) and "sent_messages" in loaded_data:
                    usage_data = loaded_data
                else:
                    usage_data = {"sent_messages": []}
                    save_data()
        else:
            usage_data = {"sent_messages": []}
            save_data()
    except Exception as e:
        logger.error(f"加载使用数据失败: {e}")
        usage_data = {"sent_messages": []}
        save_data()


def record_message_send():
    """记录机器人发送消息"""
    if "sent_messages" not in usage_data:
        usage_data["sent_messages"] = []

    now = datetime.now(TARGET_TZ) if TARGET_TZ else datetime.now()
    record = {
        "timestamp": int(now.timestamp()),
        "hour": now.hour,
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A")  # Monday, Tuesday, etc.
    }
    
    usage_data["sent_messages"].append(record)
    
    # 只保留最近 90 天的数据，避免文件过大
    cutoff_time = int((now - timedelta(days=90)).timestamp())
    usage_data["sent_messages"] = [
        r for r in usage_data["sent_messages"]
        if r["timestamp"] >= cutoff_time
    ]
    
    save_data()



@Bot.on_called_api
async def record_sent_message(
    bot: Bot, exception: Exception | None, api: str, data: dict, result: dict
):
    """记录机器人发送的消息"""
    if exception:
        return

    if api in ["send_msg", "send_private_msg", "send_group_msg"]:
        record_message_send()


# 加载数据
load_data()


# --- 查看使用统计 ---
usage = on_command("usage", aliases={"使用统计", "统计"}, priority=1, block=True)


@usage.handle()
async def usage_handle(matcher: Matcher, bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """显示消息发送统计"""
    try:
        arg_str = args.extract_plain_text().strip() if args else ""
        
        if not arg_str:
            # 显示总体统计
            await show_overview(matcher)
        elif arg_str == "hour" or arg_str == "小时":
            # 按小时统计
            await show_hourly_stats(matcher)
        elif arg_str == "day" or arg_str == "天" or arg_str == "日期":
            # 按日期统计
            await show_daily_stats(matcher)
        elif arg_str == "weekday" or arg_str == "星期":
            # 按星期统计
            await show_weekday_stats(matcher)
        
        
        else:
            await matcher.finish(
                "用法：/usage [选项]\n"
                "选项：\n"
                "  (无)      - 显示总体统计\n"
                "  hour      - 按小时统计活跃时间段\n"
                "  day       - 按日期统计\n"
                "  weekday   - 按星期统计"
            )
    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"处理 /usage 命令时发生错误: {e}", exc_info=True)
        await matcher.finish(f"处理命令时发生错误，请查看日志。错误: {str(e)}")


async def show_overview(matcher: Matcher):
    """显示总体统计"""
    records = usage_data.get("sent_messages")
    if not records:
        await matcher.finish("暂无消息发送数据。")
        return
    
    total_calls = len(records)
    
    # 计算最近 7 天的调用次数
    now = datetime.now(TARGET_TZ) if TARGET_TZ else datetime.now()
    cutoff_time = int((now - timedelta(days=7)).timestamp())
    recent_calls = sum(1 for r in records if r["timestamp"] >= cutoff_time)
    
    message = (
        f"📊 Bot 消息发送统计\n"
        f"━━━━━━━━\n"
        f"总发送次数: {total_calls}\n"
        f"最近 7 天发送: {recent_calls}\n"
        f"\n使用 /usage hour 查看活跃时间段"
    )
    
    await matcher.finish(message)


async def show_hourly_stats(matcher: Matcher):
    """按小时统计活跃时间段"""
    records = usage_data.get("sent_messages")
    if not records:
        await matcher.finish("暂无消息发送数据。")
        return
    
    hour_counts = defaultdict(int)
    for record in records:
        hour_counts[record["hour"]] += 1
    
    if not hour_counts:
        await matcher.finish("暂无消息发送数据。")
        return
    
    # 按小时排序
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)
    
    message = "⏰ 按小时统计活跃时间段\n━━━━━━━━\n"
    
    max_count = max(hour_counts.values()) if hour_counts else 1
    # 缩短柱状图长度以适应手机端，避免换行
    max_bar_length = 8
    
    # 显示所有小时段的统计
    for hour in range(24):
        count = hour_counts[hour]
        bar_length = int(count / max_count * max_bar_length) if max_count > 0 else 0
        # 使用全角字符，确保对齐
        bar = "█" * bar_length
        # 用全角空格填充剩余部分，确保右端对齐
        padding = "　" * (max_bar_length - bar_length)  # 全角空格
        # 缩短时间格式，避免换行
        next_hour = hour + 1
        message += f"{hour:02d}-{next_hour:02d} |{bar}{padding}| {count}\n"
    
    message += f"\n🔥 最活跃时间段（前 5）：\n"
    for hour, count in sorted_hours[:5]:
        next_hour = hour + 1
        message += f"  {hour:02d}-{next_hour:02d}: {count} 次\n"
    
    await matcher.finish(message)


async def show_daily_stats(matcher: Matcher):
    """按日期统计"""
    records = usage_data.get("sent_messages")
    if not records:
        await matcher.finish("暂无消息发送数据。")
        return
    
    date_counts = defaultdict(int)
    for record in records:
        date_counts[record["date"]] += 1
    
    if not date_counts:
        await matcher.finish("暂无消息发送数据。")
        return
    
    # 按日期排序
    sorted_dates = sorted(date_counts.items(), key=lambda x: x[0], reverse=True)
    
    message = "📅 按日期统计（最近 30 天）\n━━━━━━━━\n"
    
    # 只显示最近 30 天
    now = datetime.now(TARGET_TZ) if TARGET_TZ else datetime.now()
    cutoff_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    recent_dates = [(d, c) for d, c in sorted_dates if d >= cutoff_date]
    
    if not recent_dates:
        await matcher.finish("最近 30 天暂无消息发送数据。")
        return
    
    for date, count in recent_dates[:30]:
        message += f"{date}: {count} 次\n"
    
    await matcher.finish(message)


async def show_weekday_stats(matcher: Matcher):
    """按星期统计"""
    records = usage_data.get("sent_messages")
    if not records:
        await matcher.finish("暂无消息发送数据。")
        return
    
    weekday_counts = defaultdict(int)
    weekday_names = {
        "Monday": "周一",
        "Tuesday": "周二",
        "Wednesday": "周三",
        "Thursday": "周四",
        "Friday": "周五",
        "Saturday": "周六",
        "Sunday": "周日"
    }
    
    for record in records:
        weekday_counts[record["weekday"]] += 1
    
    if not weekday_counts:
        await matcher.finish("暂无消息发送数据。")
        return
    
    # 按星期顺序显示
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    message = "📆 按星期统计\n━━━━━━━━\n"
    
    max_count = max(weekday_counts.values()) if weekday_counts else 1
    max_bar_length = 8
    
    for weekday in weekday_order:
        if weekday in weekday_counts:
            count = weekday_counts[weekday]
            bar_length = int(count / max_count * max_bar_length)
            bar = "█" * bar_length
            padding = "　" * (max_bar_length - bar_length)  
            message += f"{weekday_names[weekday]}: |{bar}{padding}| {count}\n"
    
    await matcher.finish(message)