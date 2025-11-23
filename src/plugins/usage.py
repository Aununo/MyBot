import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

from zoneinfo import ZoneInfo
from nonebot import on_command, get_bot, logger
from nonebot.adapters.onebot.v11 import MessageEvent, Bot, Message
from nonebot.message import event_preprocessor
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


# 数据结构：
# {
#     "commands": {
#         "command_name": [
#             {"timestamp": 1234567890, "hour": 14, "date": "2024-01-01"},
#             ...
#         ]
#     }
# }
usage_data: Dict[str, List[Dict]] = {"commands": {}}


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
                # 确保数据结构正确
                if isinstance(loaded_data, dict) and "commands" in loaded_data:
                    usage_data = loaded_data
                else:
                    usage_data = {"commands": {}}
                    save_data()
        else:
            usage_data = {"commands": {}}
            save_data()
    except Exception as e:
        logger.error(f"加载使用数据失败: {e}")
        usage_data = {"commands": {}}
        save_data()


def record_command(command_name: str):
    """记录命令调用"""
    if "commands" not in usage_data:
        usage_data["commands"] = {}
    
    if command_name not in usage_data["commands"]:
        usage_data["commands"][command_name] = []
    
    # 使用中国时区获取当前时间
    now = datetime.now(TARGET_TZ) if TARGET_TZ else datetime.now()
    record = {
        "timestamp": int(now.timestamp()),
        "hour": now.hour,
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A")  # Monday, Tuesday, etc.
    }
    
    usage_data["commands"][command_name].append(record)
    
    # 只保留最近 90 天的数据，避免文件过大
    cutoff_time = int((now - timedelta(days=90)).timestamp())
    usage_data["commands"][command_name] = [
        r for r in usage_data["commands"][command_name]
        if r["timestamp"] >= cutoff_time
    ]
    
    save_data()


@event_preprocessor
async def record_command_usage(event: MessageEvent):
    """预处理所有消息事件，记录命令调用"""
    # 只处理群消息和私聊消息
    if event.message_type not in ["group", "private"]:
        return
    
    # 获取消息文本
    msg_text = event.get_plaintext().strip()
    if not msg_text:
        return
    
    # 检查是否是命令（以 /、！、! 开头）
    if msg_text.startswith("/"):
        command = msg_text.split()[0][1:]  # 去掉 "/"
        if command:
            record_command(command)
    elif msg_text.startswith("！") or msg_text.startswith("!"):
        command = msg_text.split()[0][1:]  # 去掉 "！" 或 "!"
        if command:
            record_command(command)


# 加载数据
load_data()


# --- 查看使用统计 ---
usage = on_command("usage", aliases={"使用统计", "统计"}, priority=1, block=True)


@usage.handle()
async def usage_handle(matcher: Matcher, bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """显示命令使用统计"""
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
        elif arg_str.startswith("cmd ") or arg_str.startswith("命令 "):
            # 查看特定命令的统计
            cmd_name = arg_str.split(maxsplit=1)[1] if len(arg_str.split()) > 1 else ""
            if cmd_name:
                await show_command_stats(matcher, cmd_name)
            else:
                await matcher.finish("请指定要查看的命令名称，例如：/usage cmd ping")
        elif arg_str == "top" or arg_str == "热门":
            # 显示最常用的命令
            await show_top_commands(matcher)
        else:
            await matcher.finish(
                "用法：/usage [选项]\n"
                "选项：\n"
                "  (无)      - 显示总体统计\n"
                "  hour      - 按小时统计活跃时间段\n"
                "  day       - 按日期统计\n"
                "  weekday   - 按星期统计\n"
                "  top       - 显示最常用的命令\n"
                "  cmd <名称> - 查看特定命令的统计"
            )
    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"处理 /usage 命令时发生错误: {e}", exc_info=True)
        await matcher.finish(f"处理命令时发生错误，请查看日志。错误: {str(e)}")


async def show_overview(matcher: Matcher):
    """显示总体统计"""
    if not usage_data.get("commands"):
        await matcher.finish("暂无使用数据。")
        return
    
    total_calls = sum(len(records) for records in usage_data["commands"].values())
    total_commands = len(usage_data["commands"])
    
    # 计算最近 7 天的调用次数
    now = datetime.now(TARGET_TZ) if TARGET_TZ else datetime.now()
    cutoff_time = int((now - timedelta(days=7)).timestamp())
    recent_calls = 0
    for records in usage_data["commands"].values():
        recent_calls += sum(1 for r in records if r["timestamp"] >= cutoff_time)
    
    message = (
        f"📊 Bot 使用统计\n"
        f"━━━━━━━━\n"
        f"总命令数: {total_commands}\n"
        f"总调用次数: {total_calls}\n"
        f"最近 7 天调用: {recent_calls}\n"
        f"\n使用 /usage top 查看最常用的命令\n"
        f"使用 /usage hour 查看活跃时间段"
    )
    
    await matcher.finish(message)


async def show_hourly_stats(matcher: Matcher):
    """按小时统计活跃时间段"""
    if not usage_data.get("commands"):
        await matcher.finish("暂无使用数据。")
        return
    
    hour_counts = defaultdict(int)
    for records in usage_data["commands"].values():
        for record in records:
            hour_counts[record["hour"]] += 1
    
    if not hour_counts:
        await matcher.finish("暂无使用数据。")
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
        message += f"  {hour:02d}-{next_hour:02d}: {count} 次\n"
    
    await matcher.finish(message)


async def show_daily_stats(matcher: Matcher):
    """按日期统计"""
    if not usage_data.get("commands"):
        await matcher.finish("暂无使用数据。")
        return
    
    date_counts = defaultdict(int)
    for records in usage_data["commands"].values():
        for record in records:
            date_counts[record["date"]] += 1
    
    if not date_counts:
        await matcher.finish("暂无使用数据。")
        return
    
    # 按日期排序
    sorted_dates = sorted(date_counts.items(), key=lambda x: x[0], reverse=True)
    
    message = "📅 按日期统计（最近 30 天）\n━━━━━━━━\n"
    
    # 只显示最近 30 天
    now = datetime.now(TARGET_TZ) if TARGET_TZ else datetime.now()
    cutoff_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    recent_dates = [(d, c) for d, c in sorted_dates if d >= cutoff_date]
    
    if not recent_dates:
        await matcher.finish("最近 30 天暂无使用数据。")
        return
    
    for date, count in recent_dates[:30]:
        message += f"{date}: {count} 次\n"
    
    await matcher.finish(message)


async def show_weekday_stats(matcher: Matcher):
    """按星期统计"""
    if not usage_data.get("commands"):
        await matcher.finish("暂无使用数据。")
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
    
    for records in usage_data["commands"].values():
        for record in records:
            weekday_counts[record["weekday"]] += 1
    
    if not weekday_counts:
        await matcher.finish("暂无使用数据。")
        return
    
    # 按星期顺序显示
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    message = "📆 按星期统计\n━━━━━━━━\n"
    
    max_count = max(weekday_counts.values()) if weekday_counts else 1
    # 缩短柱状图长度以适应手机端，避免换行
    max_bar_length = 8
    
    for weekday in weekday_order:
        if weekday in weekday_counts:
            count = weekday_counts[weekday]
            bar_length = int(count / max_count * max_bar_length)
            # 使用全角字符，确保对齐
            bar = "█" * bar_length
            # 用全角空格填充剩余部分，确保右端对齐
            padding = "　" * (max_bar_length - bar_length)  # 全角空格
            # 使用固定宽度格式，确保对齐
            message += f"{weekday_names[weekday]}: |{bar}{padding}| {count}\n"
    
    await matcher.finish(message)


async def show_command_stats(matcher: Matcher, cmd_name: str):
    """显示特定命令的统计"""
    if cmd_name not in usage_data.get("commands", {}):
        await matcher.finish(f"未找到命令 '{cmd_name}' 的使用记录。")
        return
    
    records = usage_data["commands"][cmd_name]
    if not records:
        await matcher.finish(f"命令 '{cmd_name}' 暂无使用记录。")
        return
    
    total_calls = len(records)
    
    # 按小时统计
    hour_counts = defaultdict(int)
    for record in records:
        hour_counts[record["hour"]] += 1
    
    # 最活跃的小时
    if hour_counts:
        top_hour = max(hour_counts.items(), key=lambda x: x[1])
        top_hour_str = f"{top_hour[0]:02d}:00 - {top_hour[0]+1:02d}:00"
    else:
        top_hour_str = "无"
    
    # 最近调用时间
    if records:
        last_call_time = max(r["timestamp"] for r in records)
        dt = datetime.fromtimestamp(last_call_time, tz=TARGET_TZ) if TARGET_TZ else datetime.fromtimestamp(last_call_time)
        last_call_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        last_call_str = "无"
    
    message = (
        f"📊 命令 '{cmd_name}' 统计\n"
        f"━━━━━━━━\n"
        f"总调用次数: {total_calls}\n"
        f"最活跃时间段: {top_hour_str} ({hour_counts[top_hour[0]] if hour_counts else 0} 次)\n"
        f"最近调用: {last_call_str}"
    )
    
    await matcher.finish(message)


async def show_top_commands(matcher: Matcher):
    """显示最常用的命令"""
    if not usage_data.get("commands"):
        await matcher.finish("暂无使用数据。")
        return
    
    # 计算每个命令的总调用次数
    command_counts = {
        cmd: len(records)
        for cmd, records in usage_data["commands"].items()
    }
    
    # 按调用次数排序
    sorted_commands = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_commands:
        await matcher.finish("暂无使用数据。")
        return
    
    message = "🔥 最常用的命令（Top 10）\n━━━━━━━━\n"
    
    max_count = sorted_commands[0][1] if sorted_commands else 1
    # 缩短柱状图长度以适应手机端，避免换行
    max_bar_length = 8
    
    for i, (cmd, count) in enumerate(sorted_commands[:10], 1):
        bar_length = int(count / max_count * max_bar_length)
        # 使用全角字符，确保对齐
        bar = "█" * bar_length
        # 用全角空格填充剩余部分，确保右端对齐
        padding = "　" * (max_bar_length - bar_length)  # 全角空格
        # 限制命令名称长度，避免过长
        cmd_display = cmd[:10] + "..." if len(cmd) > 10 else cmd
        # 使用固定宽度格式，确保对齐
        message += f"{i}. {cmd_display:12s} |{bar}{padding}| {count}\n"
    
    await matcher.finish(message)

