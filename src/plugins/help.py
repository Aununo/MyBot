from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent

help_cmd = on_command("help", aliases={"帮助"}, priority=1, block=True)

HELP_TEXT = """====== 机器人指令帮助 ======

🍔【今天吃啥插件】
管理 android 和 apple 两个独立的食物列表。将指令中的 `android` 替换为 `apple` 即可操作 apple 列表。

- /android
  » 随机推荐一个 android 列表中的食物。
- /android list
  » 查看 android 列表中的所有食物。
- /android add <食物名>
  » 向 android 列表中添加一个新食物。
- /android del <食物名>
  » 从 android 列表中删除一个食物。

⏰【提醒插件】
一个灵活的提醒工具，可用于任何事件。

- /remind <事件> <时间> [日期] [--everyday]
  » 设置提醒。支持指定未来日期，--everyday 可设为每日重复。
  » 例 (今天): /remind 开会 14:30
  » 例 (明天): /remind 开会 14:30 明天
  » 例 (指定日期): /remind 考试 09:00 2025-10-20
  » 例 (相对日期): /remind 复习 19:00 3天后
  » 例 (每日): /remind 上床 23:00 --everyday
  » 支持日期格式: 明天、后天、N天后、YYYY-MM-DD、MM-DD

- /notready <新时间>
  » (在收到提醒后使用) 将提醒推迟到当日指定时间。
  » 例: /notready 23:30

- /listreminders (别名: /我的提醒)
  » 查看你当前设置的所有提醒。

- /cancelremind <事件> (别名: /取消提醒)
  » 取消一个指定的提醒。
  » 例: /cancelremind 开会

📋【待办事项插件】
管理你的个人待办事项列表。

- /todo add <内容>
  » 添加一个新的待办事项。
- /todo (或 /todo list)
  » 查看你所有的待办事项。
- /todo done <编号>
  » 标记一个或多个事项为已完成。
- /todo clear
  » 清除所有已完成的事项。

🌦️【天气查询插件】
查询指定城市的实时天气信息。

- /weather <城市名> (别名: /天气)
  » 获取该城市的天气信息。
  » 例: /weather 北京

📅【我的课表插件】
动态管理和查询你的个人课程表。

查询课表:
- /课表 <星期几>
  » 查询本周指定日期的课程。例: /课表 周一
- /课表 第X周 <星期几>
  » 查询指定周指定日期的课程。例: /课表 第7周 周二
- /本周课表
  » 显示本周所有课程。

管理课程:
- /添加课程 <课程名|教师|地点|星期几|开始节次|结束节次|周数>
  » 添加新课程。例: /添加课程 高等数学|张老师|A101|1|1|2|1-16
- /删除课程 <课程名>
  » 删除指定课程。例: /删除课程 高等数学
- /清空课表
  » 清空所有课程。
- /设置开学日期 <日期>
  » 设置开学日期。例: /设置开学日期 2025-09-01

🖼️【图片管理插件】
说明：大部分指令支持 --eat 参数来操作“食物”图库，不带参数则操作“默认”图- /savepic [--eat] <文件名>
  » (需回复一张图片) 保存图片。
- /sendpic [--eat] <文件名>
  » 发送一张指定的图片。
- /rmpic [--eat] <文件名 | --all>
  » 删除图片或清空指定图库。
- /mvpic [--eat] <旧文件名> <新文件名>
  » 在指定图库中重命名图片。
- /listpic [--eat] [关键词]
  » 列出指定图库中的图片。
- /randpic [--eat] [关键词]
  » 随机发送一张图片 (别名: /随机表情)。

✨【通用指令】
- /help
  » 显示本帮助信息。(别名: /帮助)
- /ping
  » 检测机器人响应时间。
- /latex <LaTeX代码>
  » 渲染 LaTeX 公式为图片。
- /status
  » 获取服务器状态。(别名: 发送"戳一戳")
"""

@help_cmd.handle()
async def send_help_message(event: MessageEvent):
    """
    当用户发送 /help 或 /帮助 时，发送上面定义的帮助文本。
    """
    await help_cmd.finish(HELP_TEXT)