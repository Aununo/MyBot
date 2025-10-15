import json
import re
import uuid
from pathlib import Path
from datetime import datetime, timedelta


from zoneinfo import ZoneInfo
from nonebot import get_driver, on_command, require
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    Message,
    MessageSegment,
)
from nonebot.log import logger
from nonebot.params import ArgPlainText, Matcher, CommandArg


try:
    TARGET_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    logger.error("加载时区 'Asia/Shanghai' 失败，请确保 Python 版本 >= 3.9 或已安装 tzdata (pip install tzdata)。")
    TARGET_TZ = None


try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
    from apscheduler.jobstores.base import JobLookupError
except (ImportError, RuntimeError):
    logger.error("插件 nonebot_plugin_apscheduler 未安装或加载，提醒插件将无法正常工作！")
    scheduler = None


plugin_dir = Path(__file__).parent

data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir
data_file = data_dir / "reminders_data.json"
reminders_data = {}
active_snooze_contexts = {}

def save_data():
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(reminders_data, f, ensure_ascii=False, indent=4)

def load_data():
    global reminders_data
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            try:
                reminders_data = json.load(f)
            except json.JSONDecodeError:
                reminders_data = {}
    else:
        reminders_data = {}


async def send_reminder(bot: Bot, session_id: str, user_id: int, event_text: str, job_id: str, is_group: bool):
    logger.info(f"执行提醒任务({job_id}): Session({session_id}) -> 用户({user_id}) -> 事件({event_text})")
    
    if is_group:
        msg = MessageSegment.at(user_id) + Message(f"该 {event_text} 啦！")
        await bot.send_group_msg(group_id=int(session_id), message=msg)
    else:
        msg = Message(f"该 {event_text} 啦！")
        await bot.send_private_msg(user_id=int(session_id), message=msg)


    active_snooze_contexts[session_id] = {
        "event": event_text,
        "timestamp": datetime.now().timestamp()
    }
    logger.debug(f"为 Session({session_id}) 设置事件'{event_text}'的 snooze 上下文")

    user_reminders = reminders_data.get(str(user_id), [])
    reminder_to_check = next((r for r in user_reminders if r.get("job_id") == job_id), None)

    if reminder_to_check and not reminder_to_check.get("is_daily"):
        reminders_to_keep = [r for r in user_reminders if r.get("job_id") != job_id]
        reminders_data[str(user_id)] = reminders_to_keep
        save_data()
        logger.info(f"已移除执行完毕的一次性提醒任务({job_id})")


remind = on_command("remind", priority=5, block=True)
not_ready = on_command("notready", priority=5, block=True)
list_reminders = on_command("listreminders", aliases={"我的提醒"}, priority=5, block=True)
cancel_reminder = on_command("cancelremind", aliases={"取消提醒"}, priority=5, block=True)


def parse_date(date_str: str, now: datetime) -> datetime:
    """解析日期字符串，返回对应的日期"""
    if date_str == "明天":
        return (now + timedelta(days=1)).date()
    elif date_str == "后天":
        return (now + timedelta(days=2)).date()
    elif date_str == "大后天":
        return (now + timedelta(days=3)).date()
    
    if re.match(r'^\d+天后$', date_str):
        days = int(date_str[:-2])
        return (now + timedelta(days=days)).date()
    
    if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None
    
    if re.match(r'^\d{1,2}-\d{1,2}$', date_str):
        try:
            month, day = map(int, date_str.split('-'))
            year = now.year
            target_date = datetime(year, month, day).date()
            if target_date < now.date():
                target_date = datetime(year + 1, month, day).date()
            return target_date
        except ValueError:
            return None
    
    return None

@remind.handle()
async def handle_remind(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    if not scheduler or not TARGET_TZ:
        await remind.finish("抱歉，定时提醒功能未准备就绪，请联系管理员。")
    
    plain_text = args.extract_plain_text().strip()

    is_daily = False
    if plain_text.endswith("--everyday"):
        is_daily = True
        plain_text = plain_text.removesuffix("--everyday").strip()

    tokens = plain_text.split()
    if not tokens:
        await remind.finish(
            "格式不对哦！\n"
            "正确格式: /remind <事件> <时间> [日期] [--everyday]\n"
            "例如: /remind 吃药 13:00\n"
            "      /remind 开会 14:30 明天\n"
            "      /remind 复习 09:00 2025-10-20\n"
            "      /remind 运动 07:00 --everyday"
        )
        return

    time_str = None
    date_str = None
    event_tokens = []
    
    for i, token in enumerate(tokens):
        if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", token):
            time_str = token
        elif parse_date(token, datetime.now(TARGET_TZ)) is not None or token in ["明天", "后天", "大后天"] or re.match(r'^\d+天后$', token) or re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', token) or re.match(r'^\d{1,2}-\d{1,2}$', token):
            date_str = token
        else:
            event_tokens.append(token)
    
    if not time_str:
        await remind.finish("请指定时间（HH:MM 格式），例如：13:00")
        return
    
    if not event_tokens:
        await remind.finish("格式不对哦！请输入要提醒的事件名称。")
        return
        
    event_text = " ".join(event_tokens)
    hour, minute = map(int, time_str.split(':'))
    
    target_date = None
    if date_str and not is_daily:
        now = datetime.now(TARGET_TZ)
        target_date = parse_date(date_str, now)
        if target_date is None:
            await remind.finish(f"日期格式 \"{date_str}\" 不正确哦！\n支持格式：明天、后天、3天后、2025-10-20、10-20")
            return
    
    user_id = str(event.user_id)
    is_group = isinstance(event, GroupMessageEvent)
    session_id = str(event.group_id) if is_group else user_id

    reminders_data.setdefault(user_id, [])
    user_reminders = reminders_data[user_id]
    
    existing_reminder_index = -1
    for i, r in enumerate(user_reminders):
        if r.get("event") == event_text:
            existing_reminder_index = i
            break
            
    if existing_reminder_index != -1:
        old_job_id = user_reminders[existing_reminder_index].get("job_id")
        if old_job_id:
            try:
                scheduler.remove_job(old_job_id)
                logger.info(f"为更新提醒，已移除旧任务({old_job_id})")
            except JobLookupError:
                logger.warning(f"尝试移除旧任务({old_job_id})失败: 任务不存在。")
        del user_reminders[existing_reminder_index]

    job_id = f"reminder_{user_id}_{uuid.uuid4()}"
    job_args = [bot, session_id, event.user_id, event_text, job_id, is_group]

    if is_daily:
        try:
            scheduler.add_job(
                send_reminder, "cron", hour=hour, minute=minute,
                id=job_id, args=job_args, timezone=TARGET_TZ, replace_existing=True
            )
        except (ValueError, TypeError) as e:
            logger.error(f"添加每日提醒任务到调度器失败: {e}")
            await remind.finish("哎呀，添加提醒失败了，请稍后再试。")
            return
    else:
        now = datetime.now(TARGET_TZ)
        if target_date:
            reminder_time = datetime.combine(target_date, datetime.min.time()).replace(
                hour=hour, minute=minute, second=0, microsecond=0, tzinfo=TARGET_TZ
            )
        else:
            reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if reminder_time < now:
            if target_date:
                await remind.finish(f"设置失败：时间 {target_date} {time_str} 已经过去了。")
            else:
                await remind.finish(f"设置失败：时间 {time_str} 在今天已经过去了。")
            return
        
        try:
            scheduler.add_job(
                send_reminder, "date", run_date=reminder_time,
                id=job_id, args=job_args, timezone=TARGET_TZ
            )
        except (ValueError, TypeError) as e:
            logger.error(f"添加一次性提醒任务到调度器失败: {e}")
            await remind.finish("哎呀，添加提醒失败了，请稍后再试。")
            return

    new_reminder = {
        "event": event_text, "hour": hour, "minute": minute,
        "job_id": job_id, "is_daily": is_daily,
        "session_id": session_id, "is_group": is_group
    }
    if target_date:
        new_reminder["date"] = target_date.strftime("%Y-%m-%d")
    
    user_reminders.append(new_reminder)
    save_data()

    logger.info(f"为用户({user_id})在 Session({session_id}) 中设置了提醒: {new_reminder}")

    if is_daily:
        time_desc = f"每天的 {time_str}"
    elif target_date:
        time_desc = f"{target_date.strftime('%Y年%m月%d日')} {time_str}"
    else:
        time_desc = f"今天的 {time_str}"
    
    action_verb = "更新" if existing_reminder_index != -1 else "设置"
    await remind.finish(f"提醒{action_verb}成功！我会在{time_desc}提醒你【{event_text}】。")


@not_ready.handle()
async def handle_not_ready(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    if not scheduler or not TARGET_TZ:
        await not_ready.finish("抱歉，定时提醒功能未准备就绪，请联系管理员。")

    user_id = str(event.user_id)
    is_group = isinstance(event, GroupMessageEvent)
    session_id = str(event.group_id) if is_group else user_id

    context = active_snooze_contexts.get(session_id)

    SNOOZE_WINDOW = 600 
    if not context or (datetime.now().timestamp() - context.get("timestamp", 0)) > SNOOZE_WINDOW:
        await not_ready.finish("现在没有等待你回复的提醒哦。")
        return

    plain_text = args.extract_plain_text().strip()
    match = re.match(r"^\s*((?:[01]\d|2[0-3]):[0-5]\d)\s*$", plain_text)
    
    if not match:
        await not_ready.finish("时间格式不对哦，请发送 HH:MM 格式的时间。")
        return
        
    time_str = match.group(1)
    hour, minute = map(int, time_str.split(':'))
    event_text = context["event"]
    
    now = datetime.now(TARGET_TZ)
    snooze_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if snooze_time <= now:
        await not_ready.finish(f"推迟失败：时间 {time_str} 已经过去了。")
        return
        
    snooze_job_id = f"snooze_{session_id}_{uuid.uuid4()}"
    job_args = [bot, session_id, event.user_id, event_text, snooze_job_id, is_group]

    try:
        scheduler.add_job(
            send_reminder, "date", run_date=snooze_time,
            id=snooze_job_id, args=job_args, timezone=TARGET_TZ
        )
    except (ValueError, TypeError) as e:
        logger.error(f"添加 snooze 任务失败: {e}")
        await not_ready.finish("哎呀，设置推迟提醒失败了，请稍后再试。")
        return
        
    del active_snooze_contexts[session_id]
    
    logger.info(f"用户({user_id})将事件'{event_text}'的提醒推迟到 {time_str}")
    await not_ready.finish(f"好的，我会在今天 {time_str} 再次提醒你【{event_text}】。")


@list_reminders.handle()
async def handle_list_reminders(event: MessageEvent):
    user_id = str(event.user_id)
    
    user_reminders = reminders_data.get(user_id, [])
    
    if not user_reminders:
        await list_reminders.finish("你还没有设置任何提醒哦。")
        return
        
    reply_msg = "你当前的提醒有：\n"
    
    def sort_key(r):
        date_str = r.get('date', '')
        if date_str:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            return (0, date_obj, r['hour'], r['minute'])
        elif r.get('is_daily', False):
            return (2, datetime.max.date(), r['hour'], r['minute'])
        else:
            return (1, datetime.now(TARGET_TZ).date(), r['hour'], r['minute'])
    
    sorted_reminders = sorted(user_reminders, key=sort_key)
    for r in sorted_reminders:
        time_str = f"{r['hour']:02d}:{r['minute']:02d}"
        
        if r.get('is_daily', False):
            when_str = f"每天 {time_str}"
        elif r.get('date'):
            date_obj = datetime.strptime(r['date'], "%Y-%m-%d")
            when_str = f"{date_obj.strftime('%m月%d日')} {time_str}"
        else:
            when_str = f"今天 {time_str}"
        
        location = f"群聊({r['session_id']})中" if r.get('is_group') else "私聊中"
        reply_msg += f"- {when_str}：{r['event']} ({location})\n"
        
    await list_reminders.finish(reply_msg.strip())


@cancel_reminder.handle()
async def handle_cancel_reminder(matcher: Matcher, args: Message = CommandArg()): 
    plain_text = args.extract_plain_text().strip()
    if not plain_text:
        await matcher.send("请告诉我你要取消哪个提醒的【事件】？\n例如：/取消提醒 吃药")
    else:
        matcher.set_arg("event_text", args)

@cancel_reminder.got("event_text")
async def process_cancel_reminder(event: MessageEvent, event_text: str = ArgPlainText("event_text")):
    if not scheduler:
        await cancel_reminder.finish("抱歉，定时提醒功能未准备就绪，无法操作。")
        
    user_id = str(event.user_id)

    event_to_cancel = event_text.strip()
    
    user_reminders = reminders_data.get(user_id, [])
    reminder_to_remove = next((r for r in user_reminders if r.get("event") == event_to_cancel), None)
            
    if not reminder_to_remove:
        await cancel_reminder.finish(f"没有找到名为【{event_to_cancel}】的提醒。")
        return
        
    job_id = reminder_to_remove.get("job_id")
    if job_id:
        try:
            scheduler.remove_job(job_id)
            logger.info(f"已从调度器中移除任务({job_id})")
        except JobLookupError:
            logger.warning(f"尝试从调度器移除任务({job_id})失败: 任务不存在。")
        except (ValueError, TypeError) as e:
            logger.exception(f"移除任务({job_id})时发生错误: {e}")
            # 这里不抛出异常，继续执行删除操作

    user_reminders.remove(reminder_to_remove)
    reminders_data[user_id] = user_reminders

    if not reminders_data[user_id]:
        del reminders_data[user_id]
            
    save_data()
    
    logger.info(f"用户({user_id})取消了提醒: {event_to_cancel}")
    await cancel_reminder.finish(f"好的，我已经取消了【{event_to_cancel}】的提醒。")


def reschedule_jobs(bot: Bot):
    if not scheduler or not TARGET_TZ:
        logger.error("调度器未准备就绪，无法重载提醒任务。")
        return
    
    logger.info("--- 正在从数据文件重载提醒任务 ---")
    now = datetime.now(TARGET_TZ)
    reminders_to_remove = []

    for user_id, reminders in reminders_data.copy().items():
        for reminder in reminders:
            try:
                job_id = reminder.get("job_id")
                event_text = reminder.get("event")
                hour = reminder.get("hour")
                minute = reminder.get("minute")
                is_daily = reminder.get("is_daily", False)
                session_id = reminder.get("session_id")
                is_group = reminder.get("is_group", False)
                date_str = reminder.get("date")
                
                if not all([job_id, event_text, isinstance(hour, int), isinstance(minute, int), session_id is not None]):
                    logger.warning(f"跳过格式错误的提醒: {reminder}")
                    continue

                user_id_int = int(user_id)
                job_args = [bot, session_id, user_id_int, event_text, job_id, is_group]
                
                if is_daily:
                    scheduler.add_job(
                        send_reminder, "cron", hour=hour, minute=minute,
                        id=job_id, args=job_args, timezone=TARGET_TZ, replace_existing=True
                    )
                else:
                    if date_str:
                        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        reminder_time = datetime.combine(target_date, datetime.min.time()).replace(
                            hour=hour, minute=minute, second=0, microsecond=0, tzinfo=TARGET_TZ
                        )
                    else:
                        reminder_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    if reminder_time < now:
                        logger.info(f"一次性提醒 {job_id} ('{event_text}') 已过期，将其移除。")
                        reminders_to_remove.append((user_id, job_id))
                        continue
                    
                    scheduler.add_job(
                        send_reminder, "date", run_date=reminder_time,
                        id=job_id, args=job_args, timezone=TARGET_TZ, replace_existing=True
                    )
            except (ValueError, TypeError, KeyError):
                logger.exception(f"重载提醒任务失败: {reminder}")
    
    if reminders_to_remove:
        for user_id, job_id in reminders_to_remove:
            user_reminders = reminders_data.get(user_id, [])
            reminders_data[user_id] = [r for r in user_reminders if r.get("job_id") != job_id]
            if not reminders_data[user_id]:
                del reminders_data[user_id]
        save_data()
        logger.info(f"清理了 {len(reminders_to_remove)} 个过期的一次性提醒。")

    logger.info("--- 提醒任务重载完毕 ---")



driver = get_driver()
@driver.on_bot_connect
async def on_bot_connect(bot: Bot):
    logger.info(f"Bot {bot.self_id} 已连接，开始加载提醒数据...")
    load_data()
    reschedule_jobs(bot)