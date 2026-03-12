from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.plugin import PluginMetadata
from nonebot.params import CommandArg
from typing import List, Dict
from datetime import datetime, timedelta
from pathlib import Path
import pytz
import json
import re

DATA_DIR = Path("data")
SCHEDULE_FILE = DATA_DIR / "schedule_data.json"

DEFAULT_DATA = {
    "semester_start_date": "2025-09-01",
    "courses": []
}

def load_schedule_data() -> Dict:
    if not SCHEDULE_FILE.exists():
        DATA_DIR.mkdir(exist_ok=True)
        save_schedule_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return DEFAULT_DATA.copy()

def save_schedule_data(data: Dict) -> bool:
    try:
        DATA_DIR.mkdir(exist_ok=True)
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except (IOError, OSError):
        return False

def get_semester_start_date() -> datetime:
    data = load_schedule_data()
    date_str = data.get("semester_start_date", "2025-09-01")
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return datetime(2025, 9, 1)

def get_my_schedule() -> List[Dict]:
    data = load_schedule_data()
    return data.get("courses", [])


SECTION_TIMES = {
    1: "08:30-09:15", 2: "09:20-10:05",
    3: "10:20-11:05", 4: "11:10-11:55",
    5: "14:30-15:15", 6: "15:20-16:05",
    7: "16:20-17:05", 8: "17:10-17:55",
    9: "19:30-20:15", 10: "20:20-21:05",
    11: "21:10-21:55", 12: "22:00-22:45"
}
WEEKDAY_MAP = ["一", "二", "三", "四", "五", "六", "日"]
WEEKDAY_NAME_TO_NUM = {"周一": 1, "周二": 2, "周三": 3, "周四": 4, "周五": 5, "周六": 6, "周日": 7}

schedule_day = on_command("课表", priority=10, block=True)
week_schedule = on_command("本周课表", aliases={"这周有什么课", "本周课程"}, priority=10, block=True)
add_course = on_command("添加课程", aliases={"新增课程"}, priority=10, block=True)
delete_course = on_command("删除课程", aliases={"移除课程"}, priority=10, block=True)
clear_schedule = on_command("清空课表", priority=10, block=True)
set_start_date = on_command("设置开学日期", aliases={"开学日期"}, priority=10, block=True)

def get_current_time_info() -> tuple[datetime, int]:
    china_tz = pytz.timezone('Asia/Shanghai')
    now_in_china = datetime.now(china_tz)
    semester_start = get_semester_start_date()
    days_diff = (now_in_china.date() - semester_start.date()).days
    current_week = days_diff // 7 + 1 if days_diff >= 0 else 1
    return now_in_china, current_week

@schedule_day.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    text = args.extract_plain_text().strip()
    
    if not text:
        await schedule_day.finish(
            "📝 查询课表格式：\n"
            "/课表 周一   查看本周周一的课\n"
            "/课表 第7周 周二   查看第7周周二的课\n\n"
            "支持：周一、周二、周三、周四、周五、周六、周日"
        )
    
    target_week = None
    weekday_num = None
    
    week_match = re.match(r'^第(\d+)周\s*(.*)$', text)
    if week_match:
        try:
            target_week = int(week_match.group(1))
            remaining = week_match.group(2).strip()
            
            if target_week < 1 or target_week > 52:
                await schedule_day.finish("❌ 周数必须在 1-52 之间")
            
            if remaining in WEEKDAY_NAME_TO_NUM:
                weekday_num = WEEKDAY_NAME_TO_NUM[remaining]
            else:
                await schedule_day.finish(f"❌ 未识别的星期：{remaining}")
        except ValueError:
            await schedule_day.finish("❌ 周数格式错误")
    else:
        if text in WEEKDAY_NAME_TO_NUM:
            weekday_num = WEEKDAY_NAME_TO_NUM[text]
            _, target_week = get_current_time_info()
        else:
            await schedule_day.finish(f"❌ 格式错误，请使用：/课表 周一 或 /课表 第7周 周二")
    
    reply = await query_schedule_for_day(weekday_num, f"星期{WEEKDAY_MAP[weekday_num-1]}", target_week)
    await schedule_day.finish(reply)

@week_schedule.handle()
async def _(event: MessageEvent):
    _, week = get_current_time_info()
    my_schedule = get_my_schedule()
    
    courses_this_week = [
        c for c in my_schedule if week in c.get("weeks", [])
    ]
    
    if not courses_this_week:
        await week_schedule.finish(f"你本周（第{week}周）没有课哦~")
        return

    reply = f"📅 本周（第{week}周）课表如下：\n"
    
    sorted_courses = sorted(courses_this_week, key=lambda c: (c.get('day', 0), c.get('start_section', 0)))

    current_day = -1
    for course in sorted_courses:
        day_num = course.get("day")
        if day_num != current_day:
            reply += f"\n--- 星期{WEEKDAY_MAP[day_num-1]} ---\n"
            current_day = day_num
        
        reply += format_course_info(course)

    await week_schedule.finish(reply)

async def query_schedule_for_day(weekday: int, day_str: str, current_week: int) -> str:
    my_schedule = get_my_schedule()
    
    courses_on_day = [
        c for c in my_schedule 
        if c.get("day") == weekday and current_week in c.get("weeks", [])
    ]
    
    if not courses_on_day:
        return f"你{day_str}（第{current_week}周）没有课哦，好好休息一下吧！"

    sorted_courses = sorted(courses_on_day, key=lambda c: c.get("start_section", 0))

    reply = f"📅 {day_str}（第{current_week}周）的课表：\n--------------------\n"
    for course in sorted_courses:
        reply += format_course_info(course)
    
    return reply

def format_course_info(course: Dict) -> str:
    start = course.get("start_section", "?")
    end = course.get("end_section", "?")
    
    start_time = SECTION_TIMES.get(start, '')
    end_time_full = SECTION_TIMES.get(end, '')
    end_time = end_time_full.split('-')[-1] if end_time_full else ''
    time_str = f"{start_time}-{end_time}" if start_time and end_time else ""

    weeks = sorted(set(course.get('weeks', [])))
    
    if not weeks:
        weeks_str = "无"
    else:
        ranges = []
        range_start = weeks[0]
        prev = weeks[0]
        for w in weeks[1:]:
            if w == prev + 1:
                prev = w
                continue
            ranges.append(f"{range_start}-{prev}" if range_start != prev else str(range_start))
            range_start = prev = w
        ranges.append(f"{range_start}-{prev}" if range_start != prev else str(range_start))
        weeks_str = ",".join(ranges)

    return (
        f"📕 {course.get('name', '未知课程')}\n"
        f"🕒 第{start}-{end}节 ({time_str})\n"
        f"📍 {course.get('location', '未知地点')}\n"
        f"👨‍🏫 {course.get('teacher', '未知老师')}\n"
        f"🗓️ 第{weeks_str}周\n"
        "--------------------\n"
    )


def parse_weeks(weeks_str: str) -> List[int]:
    weeks: List[int] = []
    for part in [p.strip() for p in weeks_str.split(',') if p.strip()]:
        if '-' in part:
            start_s, end_s = [x.strip() for x in part.split('-', 1)]
            start_w = int(start_s)
            end_w = int(end_s)
            if start_w > end_w:
                raise ValueError("周数范围起始不能大于结束")
            weeks.extend(range(start_w, end_w + 1))
        else:
            weeks.append(int(part))

    weeks = sorted(set(weeks))
    if not weeks:
        raise ValueError("周数不能为空")
    if weeks[0] < 1 or weeks[-1] > 52:
        raise ValueError("周数必须在 1-52 之间")
    return weeks


def parse_course_line(text: str) -> Dict:
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 7:
        raise ValueError("格式错误！请使用：课程名|教师|地点|星期几|开始节次|结束节次|周数")

    name, teacher, location, day_str, start_str, end_str, weeks_str = parts

    try:
        day = int(day_str)
    except ValueError:
        raise ValueError(f"星期几必须是数字，当前值：{day_str}")

    if day < 1 or day > 7:
        raise ValueError("星期几必须在 1-7 之间")

    try:
        start_section = int(start_str)
        end_section = int(end_str)
    except ValueError:
        raise ValueError(f"节次必须是数字，当前值：{start_str}, {end_str}")

    if start_section < 1 or end_section > 12 or start_section > end_section:
        raise ValueError("节次必须在 1-12 之间，且开始节次不能大于结束节次")

    try:
        weeks = parse_weeks(weeks_str)
    except ValueError as exc:
        raise ValueError(f"周数格式错误，请使用范围(1-16)、列表(1,3,5)或混合格式(1-5,7-16)，当前值：{weeks_str}；{exc}")

    return {
        "name": name,
        "teacher": teacher,
        "location": location,
        "day": day,
        "start_section": start_section,
        "end_section": end_section,
        "weeks": weeks,
    }

@add_course.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    text = args.extract_plain_text().strip()
    
    if not text:
        help_msg = (
            "📝 添加课程格式：\n"
            "/添加课程 课程名|教师|地点|星期几|开始节次|结束节次|周数\n\n"
            "示例：\n"
            "/添加课程 高等数学|张老师|A101|1|1|2|1-16\n"
            "/添加课程 大学英语|李老师|B202|3|5|6|1,3,5,7,9\n"
            "/添加课程 商务沟通英语|杜佳洋|第二教学楼215|1|3|4|1-5,7-16\n\n"
            "说明：\n"
            "- 星期几：1-7（1=周一，7=周日）\n"
            "- 节次：1-12\n"
            "- 周数：支持范围(1-16)、列表(1,3,5)和混合格式(1-5,7-16)\n"
            "- 支持批量导入：一次发送多行 /添加课程 ..."
        )
        await add_course.finish(help_msg)

    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_lines = []
    for line in raw_lines:
        if line.startswith("/添加课程"):
            line = line[len("/添加课程"):].strip()
        elif line.startswith("添加课程"):
            line = line[len("添加课程"):].strip()
        normalized_lines.append(line)

    if not normalized_lines:
        await add_course.finish("❌ 没有检测到可导入的课程内容")

    data = load_schedule_data()
    added_courses = []
    errors = []

    for idx, line in enumerate(normalized_lines, start=1):
        try:
            course = parse_course_line(line)
            data["courses"].append(course)
            added_courses.append(course)
        except ValueError as exc:
            errors.append(f"第{idx}行：{exc}")

    if added_courses and save_schedule_data(data):
        if len(added_courses) == 1 and not errors:
            await add_course.finish(
                f"✅ 课程添加成功！\n\n"
                f"{format_course_info(added_courses[0])}"
            )
            return

        preview = "\n".join(
            f"- {c['name']}｜周{WEEKDAY_MAP[c['day']-1]} 第{c['start_section']}-{c['end_section']}节｜第{format_course_info(c).split('🗓️ 第',1)[1].split('周',1)[0]}周"
            for c in added_courses[:8]
        )
        more = ""
        if len(added_courses) > 8:
            more = f"\n- 其余 {len(added_courses) - 8} 门已省略显示"

        msg = f"✅ 成功导入 {len(added_courses)} 门课程"
        if preview:
            msg += f"\n\n{preview}{more}"
        if errors:
            msg += f"\n\n⚠️ 以下课程导入失败：\n" + "\n".join(errors[:10])
            if len(errors) > 10:
                msg += f"\n... 还有 {len(errors) - 10} 条错误未显示"
        await add_course.finish(msg)
    elif added_courses:
        await add_course.finish("❌ 保存失败，请稍后重试")
    else:
        await add_course.finish("❌ 导入失败：\n" + "\n".join(errors[:10]))

@delete_course.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    course_name = args.extract_plain_text().strip()
    
    if not course_name:
        await delete_course.finish("请指定要删除的课程名，例如：/删除课程 高等数学")
    
    data = load_schedule_data()
    courses = data.get("courses", [])
    
    original_count = len(courses)
    data["courses"] = [c for c in courses if c.get("name") != course_name]
    
    deleted_count = original_count - len(data["courses"])
    
    if deleted_count == 0:
        await delete_course.finish(f"❌ 未找到课程：{course_name}")
    
    if save_schedule_data(data):
        await delete_course.finish(f"✅ 已删除 {deleted_count} 门课程：{course_name}")
    else:
        await delete_course.finish("❌ 删除失败，请稍后重试")

@clear_schedule.handle()
async def _(event: MessageEvent):
    data = load_schedule_data()
    course_count = len(data.get("courses", []))
    
    if course_count == 0:
        await clear_schedule.finish("课表已经是空的了~")
    
    data["courses"] = []
    if save_schedule_data(data):
        await clear_schedule.finish(f"✅ 已清空 {course_count} 门课程")
    else:
        await clear_schedule.finish("❌ 清空失败，请稍后重试")

@set_start_date.handle()
async def _(event: MessageEvent, args: Message = CommandArg()):
    date_str = args.extract_plain_text().strip()
    
    if not date_str:
        current_date = get_semester_start_date().strftime("%Y-%m-%d")
        await set_start_date.finish(
            f"📅 当前开学日期：{current_date}\n\n"
            f"修改格式：/设置开学日期 YYYY-MM-DD\n"
            f"例如：/设置开学日期 2025-09-01"
        )
    
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await set_start_date.finish("❌ 日期格式错误，请使用：YYYY-MM-DD（例如：2025-09-01）")
        return
    
    data = load_schedule_data()
    data["semester_start_date"] = date_str
    
    if save_schedule_data(data):
        await set_start_date.finish(f"✅ 开学日期已设置为：{date_str}")
    else:
        await set_start_date.finish("❌ 保存失败，请稍后重试")