import json
from pathlib import Path
from typing import List, Dict

from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.params import CommandArg


plugin_dir = Path(__file__).parent

data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir

data_file = data_dir / "todo_data.json"


TodoDataType = Dict[str, List[Dict[str, any]]]
todo_data: TodoDataType = {}

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

# 插件加载时读取数据
load_data()


todo_matcher = on_command("todo", priority=5, block=True)


@todo_matcher.handle()
async def handle_todo(event: MessageEvent, matcher: Matcher, args: Message = CommandArg()):
    user_id = str(event.user_id)
    plain_text = args.extract_plain_text().strip()

    parts = plain_text.split()
    sub_command = parts[0].lower() if parts else "list"
    
    if user_id not in todo_data:
        todo_data[user_id] = []

    if sub_command == "add":
        task_content = " ".join(parts[1:])
        if not task_content:
            await matcher.finish("要添加的待办事项内容不能为空哦！\n用法: /todo add <内容>")
            return
        
        todo_data[user_id].append({"task": task_content, "done": False})
        save_data()
        await matcher.finish(f"已添加待办事项：\n- {task_content}")

    elif sub_command == "list":
        user_todos = todo_data.get(user_id, [])
        if not user_todos:
            await matcher.finish("你还没有任何待办事项哦！\n使用 /todo add <内容> 来添加一个吧。")
            return
        
        reply_msg = "📋 你的待办事项列表：\n"
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
        if len(parts) < 2:
            await matcher.finish("请指定要完成的事项编号。\n用法: /todo done <编号1> [编号2] ...")
            return

        user_todos = todo_data.get(user_id, [])
        if not user_todos:
            await matcher.finish("你还没有任何待办事项可以完成。")
            return

        done_tasks = []
        error_msgs = []
        
        for part in parts[1:]:
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
                error_msgs.append(f"“{part}”不是一个有效的数字编号。")

        if done_tasks:
            save_data()
            reply = f"🎉 已完成 {len(done_tasks)} 项任务！"
            if error_msgs:
                reply += "\n\n但出现了一些小问题：\n" + "\n".join(error_msgs)
            await matcher.finish(reply)
        else:
            await matcher.finish("没有任何任务被标记为完成。\n" + "\n".join(error_msgs))

    elif sub_command == "clear":
        user_todos = todo_data.get(user_id, [])
        pending_todos = [item for item in user_todos if not item["done"]]
        
        cleared_count = len(user_todos) - len(pending_todos)
        if cleared_count == 0:
            await matcher.finish("你没有已完成的事项可以清除。")
            return
            
        todo_data[user_id] = pending_todos
        save_data()
        await matcher.finish(f"✨ 已为你清除 {cleared_count} 项已完成的待办事项！")
        
    else:
        await matcher.finish(
            "🤔 /todo 指令用法：\n"
            "- /todo add <内容>  (添加事项)\n"
            "- /todo (或 /todo list) (查看列表)\n"
            "- /todo done <编号>  (完成事项)\n"
            "- /todo clear        (清除已完成)"
        )