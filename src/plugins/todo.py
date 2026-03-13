import json
from pathlib import Path
from typing import Dict, List, Literal, TypedDict, cast

from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.params import CommandArg

from ._data_paths import resolve_data_dir

plugin_dir = Path(__file__).parent
data_dir = resolve_data_dir()

data_file = data_dir / "todo_data.json"


class TodoItem(TypedDict):
    task: str
    done: bool


CategoryName = Literal["work", "play"]
UserTodoData = Dict[CategoryName, List[TodoItem]]
TodoDataType = Dict[str, UserTodoData]


todo_data: TodoDataType = {}

CATEGORIES: tuple[CategoryName, ...] = ("work", "play")


def create_empty_user_data() -> UserTodoData:
    return {category: [] for category in CATEGORIES}


def save_data():
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(todo_data, f, ensure_ascii=False, indent=4)

def load_data():
    global todo_data
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            try:
                todo_data = json.load(f)
            except json.JSONDecodeError:
                todo_data = {}
    else:
        todo_data = {}

def init_user_data(user_id: str):
    """初始化用户数据结构，并处理旧格式数据迁移"""
    if user_id not in todo_data:
        todo_data[user_id] = create_empty_user_data()
    elif isinstance(todo_data[user_id], list):
        old_todos = cast(List[TodoItem], todo_data[user_id])
        todo_data[user_id] = {
            "work": old_todos,
            "play": []
        }
        save_data()

load_data()


todo_matcher = on_command("todo", priority=5, block=True)


@todo_matcher.handle()
async def handle_todo(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = str(event.user_id)
    plain_text = args.extract_plain_text().strip()

    parts = plain_text.split()
    
    init_user_data(user_id)
    
    category = None
    sub_command = "list"
    command_parts = []
    
    if parts:
        if parts[0].lower() in CATEGORIES:
            category = parts[0].lower()
            if len(parts) > 1:
                sub_command = parts[1].lower()
                command_parts = parts[2:]
            else:
                sub_command = "list"
        else:
            sub_command = parts[0].lower()
            command_parts = parts[1:]
    
    if category is None and sub_command not in ["list", "help"]:
        await matcher.finish(
            "🤔 请指定分类！\n\n"
            "📋 /todo 指令用法：\n"
            "- /todo work add <内容>  (添加工作事项)\n"
            "- /todo play add <内容>  (添加娱乐事项)\n"
            "- /todo work [list]      (查看工作列表)\n"
            "- /todo play [list]      (查看娱乐列表)\n"
            "- /todo list             (查看所有列表)\n"
            "- /todo work done <编号> (完成工作事项)\n"
            "- /todo play done <编号> (完成娱乐事项)\n"
            "- /todo work clear       (清除已完成的工作事项)\n"
            "- /todo play clear       (清除已完成的娱乐事项)"
        )
    
    if sub_command == "add":
        if category is None:
            await matcher.finish("请指定分类！\n用法: /todo work add <内容> 或 /todo play add <内容>")
            return
            
        task_content = " ".join(command_parts)
        if not task_content:
            await matcher.finish(f"要添加的待办事项内容不能为空哦！\n用法: /todo {category} add <内容>")
            return
        
        category_icon = "💼" if category == "work" else "🎮"
        todo_data[user_id][category].append({"task": task_content, "done": False})
        save_data()
        await matcher.finish(f"{category_icon} 已添加{category == 'work' and '工作' or '娱乐'}待办事项：\n- {task_content}")

    elif sub_command == "list":
        if category is None:
            reply_msg = "📋 你的待办事项：\n\n"
            has_todos = False
            
            for cat in CATEGORIES:
                cat_icon = "💼" if cat == "work" else "🎮"
                cat_name = "工作" if cat == "work" else "娱乐"
                user_todos = todo_data[user_id].get(cat, [])
                
                if user_todos:
                    has_todos = True
                    pending_count = sum(1 for item in user_todos if not item["done"])
                    reply_msg += f"{cat_icon} {cat_name} ({pending_count}/{len(user_todos)} 未完成)\n"
                    
                    for i, item in enumerate(user_todos, 1):
                        status_icon = "✅" if item["done"] else "⬜️"
                        task_text = item["task"]
                        if item["done"]:
                            task_text = f"~{task_text}~"
                        reply_msg += f"  {i}. {status_icon} {task_text}\n"
                    reply_msg += "\n"
            
            if not has_todos:
                await matcher.finish("你还没有任何待办事项哦！\n使用 /todo work add <内容> 或 /todo play add <内容> 来添加吧。")
            else:
                await matcher.finish(reply_msg.strip())
        else:
            user_todos = todo_data[user_id][category]
            cat_icon = "💼" if category == "work" else "🎮"
            cat_name = "工作" if category == "work" else "娱乐"
            
            if not user_todos:
                await matcher.finish(f"你还没有任何{cat_name}待办事项哦！\n使用 /todo {category} add <内容> 来添加一个吧。")
                return
            
            reply_msg = f"{cat_icon} 你的{cat_name}待办事项列表：\n"
            pending_count = 0
            for i, item in enumerate(user_todos, 1):
                status_icon = "✅" if item["done"] else "⬜️"
                task_text = item["task"]
                if item["done"]:
                    task_text = f"~{task_text}~"
                
                reply_msg += f"{i}. {status_icon} {task_text}\n"
                if not item["done"]:
                    pending_count += 1
            
            reply_msg += f"\n总计 {len(user_todos)} 项，还有 {pending_count} 项未完成。"
            await matcher.finish(reply_msg.strip())

    elif sub_command == "done":
        if category is None:
            await matcher.finish("请指定分类！\n用法: /todo work done <编号> 或 /todo play done <编号>")
            return
            
        if len(command_parts) < 1:
            await matcher.finish(f"请指定要完成的事项编号。\n用法: /todo {category} done <编号1> [编号2] ...")
            return

        user_todos = todo_data[user_id][category]
        if not user_todos:
            await matcher.finish(f"你还没有任何{category == 'work' and '工作' or '娱乐'}待办事项可以完成。")
            return

        done_tasks = []
        error_msgs = []
        
        for part in command_parts:
            try:
                task_num = int(part)
                if 1 <= task_num <= len(user_todos):
                    if not user_todos[task_num - 1]["done"]:
                        user_todos[task_num - 1]["done"] = True
                        done_tasks.append(user_todos[task_num - 1]["task"])
                    else:
                        error_msgs.append(f"第 {task_num} 项已经是完成状态了。")
                else:
                    error_msgs.append(f"编号 {task_num} 无效，请输入 1 到 {len(user_todos)} 之间的数字。")
            except ValueError:
                error_msgs.append(f'"{part}" 不是一个有效的数字编号。')

        if done_tasks:
            save_data()
            reply = f"🎉 已完成 {len(done_tasks)} 项任务！"
            if error_msgs:
                reply += "\n\n但出现了一些小问题：\n" + "\n".join(error_msgs)
            await matcher.finish(reply)
        else:
            await matcher.finish("没有任何任务被标记为完成。\n" + "\n".join(error_msgs))

    elif sub_command == "clear":
        if category is None:
            await matcher.finish("请指定分类！\n用法: /todo work clear 或 /todo play clear")
            return
            
        user_todos = todo_data[user_id][category]
        pending_todos = [item for item in user_todos if not item["done"]]
        
        cleared_count = len(user_todos) - len(pending_todos)
        if cleared_count == 0:
            cat_name = "工作" if category == "work" else "娱乐"
            await matcher.finish(f"你没有已完成的{cat_name}事项可以清除。")
            return
            
        todo_data[user_id][category] = pending_todos
        save_data()
        await matcher.finish(f"✨ 已为你清除 {cleared_count} 项已完成的待办事项！")
        
    else:
        await matcher.finish(
            "🤔 /todo 指令用法：\n"
            "- /todo work add <内容>  (添加工作事项)\n"
            "- /todo play add <内容>  (添加娱乐事项)\n"
            "- /todo work [list]      (查看工作列表)\n"
            "- /todo play [list]      (查看娱乐列表)\n"
            "- /todo list             (查看所有列表)\n"
            "- /todo work done <编号> (完成工作事项)\n"
            "- /todo play done <编号> (完成娱乐事项)\n"
            "- /todo work clear       (清除已完成的工作事项)\n"
            "- /todo play clear       (清除已完成的娱乐事项)"
        )
