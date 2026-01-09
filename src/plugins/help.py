from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

help_cmd = on_command("help", aliases={"帮助"}, priority=1, block=True)

# 帮助信息字典，每个插件有独立的详细说明
HELP_DETAILS = {
    "android": """🍔【今天吃啥插件 - android】
管理 android 独立的食物列表。
- /android
  » 随机推荐一个 android 列表中的食物。
- /android list
  » 查看 android 列表中的所有食物。
- /android add <食物名>
  » 向 android 列表中添加一个新食物。
- /android del <食物名>
  » 从 android 列表中删除一个食物。""",
    
    "apple": """🍎【今天吃啥插件 - apple】
管理 apple 独立的食物列表。
- /apple
  » 随机推荐一个 apple 列表中的食物。
- /apple list
  » 查看 apple 列表中的所有食物。
- /apple add <食物名>
  » 向 apple 列表中添加一个新食物。
- /apple del <食物名>
  » 从 apple 列表中删除一个食物。""",
    
    "remind": """⏰【提醒插件】
一个灵活的提醒工具，可用于任何事件。
- /remind <事件> <时间> [日期] [--everyday | --everyNdays | 周几]
  » 设置提醒。支持指定未来日期，--everyday 每日重复，--everyNdays 每隔N天重复，周几重复。
  » 日期和重复参数可叠加使用（从指定日期开始重复）。
  » 例 (今天): /remind 开会 14:30
  » 例 (明天): /remind 开会 14:30 明天
  » 例 (指定日期): /remind 考试 09:00 2025-10-20
  » 例 (相对日期): /remind 复习 19:00 3天后
  » 例 (每日): /remind 上床 23:00 --everyday
  » 例 (每隔3天): /remind 换水 08:00 --every3days
  » 例 (从明天起每日): /remind 开会 08:00 明天 --everyday
  » 例 (从指定日期起每3天): /remind 吃药 12:00 2025-11-01 --every3days
  » 例 (周几提醒): /remind 吃药 13:00 周二 周四
  » 例 (多个周几): /remind 开会 09:30 周一 周三 周五
  » 支持日期格式: 明天、后天、N天后、YYYY-MM-DD、MM-DD
  » 支持周几格式: 周一~周日、星期一~星期日
- /notready <新时间>
  » (在收到提醒后使用) 将提醒推迟到当日指定时间。
  » 例: /notready 23:30
- /listreminders (别名: /我的提醒)
  » 查看你当前设置的所有提醒。
- /cancelremind <事件> (别名: /取消提醒)
  » 取消一个指定的提醒。
  » 例: /cancelremind 开会""",
    
    "todo": """📋【待办事项插件】
管理你的个人待办事项列表，支持工作(work)和娱乐(play)分类。
- /todo work add <内容>
  » 添加一个工作待办事项。
- /todo play add <内容>
  » 添加一个娱乐待办事项。
- /todo work [list]
  » 查看工作待办列表。
- /todo play [list]
  » 查看娱乐待办列表。
- /todo list (或直接 /todo)
  » 查看所有分类的待办事项。
- /todo work done <编号>
  » 标记工作事项为已完成。
- /todo play done <编号>
  » 标记娱乐事项为已完成。
- /todo work clear
  » 清除已完成的工作事项。
- /todo play clear
  » 清除已完成的娱乐事项。""",
    
    "time": """⏰【倒计时插件】
管理你的重要事件倒计时，随时查看距离事件还有多久。
- /time add <事件名> <截止时间>
  » 添加一个倒计时事件。
  » 例: /time add 考试 2025-12-31 18:00
  » 支持格式: 2025-12-31、2025-12-31 23:59、2025/12/31 23:59:59
- /time <事件名>
  » 查看指定事件的倒计时。
  » 例: /time 考试
- /time list (或直接 /time)
  » 查看所有倒计时事件。
- /time del <事件名>
  » 删除一个倒计时事件。
  » 例: /time del 考试""",
    
    "weather": """🌦️【天气查询插件】
查询指定城市的实时天气信息。
- /weather <城市名> (别名: /天气)
  » 获取该城市的天气信息。
  » 例: /weather 北京""",
    
    "课表": """📅【我的课表插件】
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
  » 设置开学日期。例: /设置开学日期 2025-09-01""",
    
    "pic": """🖼️【图片管理插件】
说明：大部分指令支持 --eat 参数来操作"食物"图库，不带参数则操作"默认"图库。
- /savepic [--eat] <文件名>
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
  » 随机发送一张图片 (别名: /随机表情)。""",
    
    "接龙": """📝【接龙插件】
在群聊中创建和管理接龙活动，自动记录参与人员并编号。
- /接龙 <事件名>
  » 创建新的接龙或参与现有接龙。
  » 例: /接龙 周末聚餐
  » 例: /接龙 (参与当前接龙)
  » 如果群内已有接龙，发送 /接龙 会自动加入；发送 /接龙 新事件名 会创建新接龙。
  » 每个群有独立的接龙，已参与的用户会显示其位置。
- /接龙 查看 (别名: /接龙 view/list/显示)
  » 查看当前群的接龙列表。
- /接龙 删除 (别名: /接龙 del/delete/clear)
  » 删除当前群的接龙任务。""",
    
    "check_email": """📧【邮件通知插件】
检查当前邮件有没有新邮件。
- /check_email
  » 检查是否有新邮件。""",
    
    "usage": """📊【使用统计插件】
统计 Bot 命令调用的活跃时间段和次数，自动记录所有命令使用情况。
- /usage (别名: /使用统计 /统计)
  » 显示总体统计信息（总命令数、总调用次数、最近 7 天调用）。
- /usage hour (别名: /usage 小时)
  » 按小时统计活跃时间段，显示 24 小时分布图。
- /usage day (别名: /usage 天 /usage 日期)
  » 按日期统计，显示最近 30 天的调用情况。
- /usage weekday (别名: /usage 星期)
  » 按星期统计，显示周一到周日的使用分布。""",
    
    "ping": """✨【通用指令 - PING】
- /ping
  » 检测机器人响应时间。""",
    
    "latex": """✨【通用指令 - LaTeX】
- /latex <LaTeX代码>
  » 渲染 LaTeX 公式为图片，支持多行/环境及行内模式。""",
    
    "文案": """✨【通用指令 - 文案生成】
- /文案 <主题1> <主题2> (别名: /copywriting)
  » 使用 AI 根据提供的主题词进行创意文案仿写。
  » 例: /文案 冰激凌 火锅
  » 会按照特定句式为你创作有趣的文案。
  » 需要配置 GEMINI_API_KEY 才能使用。""",
    
    "status": """✨【通用指令 - 状态】
- /status
  » 获取服务器状态。(别名: 发送"戳一戳")""",
    
    "总结": """📋【群聊总结插件】
使用 AI 自动总结群聊内容，实时获取历史消息。

基础用法:
- /总结 (别名: /summary, /群聊总结)
  » 总结最近 50 条群聊消息。
- /总结 <数量>
  » 总结最近指定数量的消息（最大 200 条）。
  » 例: /总结 100

高级功能:
- /总结 话题 [数量]
  » 分析群聊中讨论的主要话题。
- /总结 活跃 [数量]
  » 分析群聊活跃度和参与情况。
- /总结 帮助
  » 查看使用帮助。

说明:
• 实时获取历史消息，无需缓存
• 最大可总结 200 条消息
• 需要配置 GEMINI_API_KEY""",

    "save": """📸【消息截图插件】
将消息转换为带头像的精美卡片图片。

使用方法:
- 回复一条消息，然后发送 /save 
  » 将被回复的消息渲染成带头像的卡片截图。

说明:
• 自动获取发送者头像（圆形显示）
• 显示发送者昵称/群名片
• 群聊中会显示用户等级
• 仅支持文本消息"""
}

# 简短的命令列表
COMMAND_LIST = """====== 机器人指令列表 ======

💡 提示：使用 /help <命令名> 查看具体命令的详细用法

📋 可用命令：
- /android, /apple       - 今天吃啥
- /remind                - 提醒功能
- /todo                  - 待办事项
- /time                  - 倒计时
- /weather               - 天气查询
- /课表                  - 课程表管理
- /pic                   - 图片管理
- /接龙                  - 接龙活动
- /check_email             - 邮件检查
- /usage                 - 使用统计
- /ping                  - 响应测试
- /latex                 - LaTeX 渲染
- /文案                  - AI文案生成
- /总结                  - AI群聊总结
- /save                  - 消息截图
- /status                - 服务器状态

例如：/help apple. 使用 /help <命令名> 查看详细帮助信息！
"""


@help_cmd.handle()
async def send_help_message(event: MessageEvent, args: Message = CommandArg()):
    """
    当用户发送 /help 或 /帮助 时，根据参数返回相应的帮助信息。
    - /help: 显示命令列表
    - /help <命令名>: 显示具体命令的详细信息
    """
    # 获取用户输入的参数
    arg_text = args.extract_plain_text().strip()
    
    if not arg_text:
        # 没有参数，显示命令列表
        await help_cmd.finish(COMMAND_LIST)
    else:
        # 有参数，查找对应的详细帮助
        command = arg_text.lower()
        
        if command in HELP_DETAILS:
            await help_cmd.finish(HELP_DETAILS[command])
        else:
            # 命令不存在，提示用户
            error_msg = f"❌ 未找到命令 '{arg_text}' 的帮助信息。\n\n使用 /help 查看所有可用命令。"
            await help_cmd.finish(error_msg)
