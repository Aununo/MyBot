import json
from typing import Any, Dict


def build_plugin_rewrite_prompt(
    role_prompt: str,
    user_text: str,
    plugin_command: str,
    plugin_output_text: str,
) -> str:
    return (
        f"{role_prompt}\n\n"
        "你现在不是执行模式，不允许调用任何工具。\n"
        "你刚刚拿到一段插件原始输出，请整理成自然口语再回复用户。\n"
        "要求：\n"
        "- 先读懂再转述，保留关键信息与结论。\n"
        "- 输出成 1 段自然中文（除非用户明确要列表）。\n"
        "- 语气简洁清楚，避免机械模板。\n"
        "- 不要提到‘插件/命令/调用’等内部实现。\n"
        "- 不要输出 JSON。\n\n"
        f"用户原始消息：{user_text}\n"
        f"插件命令：{plugin_command}\n"
        f"插件原始输出：{plugin_output_text}"
    )


def build_tool_retry_prompt(
    role_prompt: str,
    user_text: str,
    previous_tool_call: Dict[str, Any],
    tool_result_text: str,
    round_idx: int,
    max_rounds: int,
    attachment_context: str = "",
    plugin_catalog: str = "",
) -> str:
    return (
        f"{role_prompt}\n\n"
        "你正在执行多轮工具调用。请基于上轮执行结果继续决策。\n"
        f"用户原始消息：{user_text}\n"
        f"上一轮工具调用：{json.dumps(previous_tool_call, ensure_ascii=False)}\n"
        f"执行结果：{tool_result_text}\n"
        f"当前轮次：{round_idx}/{max_rounds}\n"
        f"{attachment_context + chr(10) if attachment_context else ''}\n"
        f"{plugin_catalog + chr(10) if plugin_catalog else ''}"
        "规则：\n"
        "- 如果上一轮是本地插件且报格式/参数错误：先用该命令的 /help 学习格式，再重试同插件。\n"
        "- 如果需要继续调用本地插件，请输出一行 JSON 工具调用；若改用原生工具更合适可直接改用。\n"
        "- 如果改用原生联网工具能完成任务，可直接联网并给最终自然回复。\n"
        "- 若使用原生联网工具并直接回复，首行加 [NATIVE_NETWORK_USED]。\n"
        "- 如果已经无法继续，请直接给用户最终回复（自然语言，简短明确）。\n"
        "- 不要输出解释过程。"
    )


def build_tool_followup_prompt(
    role_prompt: str,
    user_text: str,
    execution_log: list[dict],
    round_idx: int,
    max_rounds: int,
    attachment_context: str = "",
    plugin_catalog: str = "",
) -> str:
    compact_log = execution_log[-8:]
    return (
        f"{role_prompt}\n\n"
        "你正在进行多步工具执行。请根据已执行结果决定下一步。\n"
        f"用户原始消息：{user_text}\n"
        f"已执行步骤：{json.dumps(compact_log, ensure_ascii=False)}\n"
        f"当前轮次：{round_idx}/{max_rounds}\n"
        f"{attachment_context + chr(10) if attachment_context else ''}\n"
        f"{plugin_catalog + chr(10) if plugin_catalog else ''}"
        "规则：\n"
        "- 若上一轮插件报格式/参数错误：优先 /help 同命令后重试，不要直接跳到无关工具。\n"
        "- 若任务尚未完成：可继续输出下一步插件 JSON 调用；也可改用任意原生工具补齐信息。\n"
        "- 若你改用原生联网工具并直接回复，首行加 [NATIVE_NETWORK_USED]。\n"
        "- 若任务已完成：直接输出给用户的最终自然回复（不要 JSON）。\n"
        "- 不要重复执行已经成功完成且无必要重复的步骤。\n"
        "- 不要输出解释过程。"
    )


def build_exec_prompt(role_prompt: str, user_text: str, attachment_context: str = "", plugin_catalog: str = "") -> str:
    return (
        f"{role_prompt}\n\n"
        "你现在处于执行模式。目标是：先判断是否需要工具，再给最终结果。\n"
        "你有两类能力：\n"
        "A) OpenClaw 原生全工具（含联网、浏览器、文件、命令执行、会话、记忆、消息等）——可直接调用并给最终自然回复。\n"
        "B) QQ 本地插件接口（需要你输出 JSON）：plugin_call / plugin_command / plugin_batch。\n\n"
        "插件接口示例（仅插件调用时输出 JSON）：\n"
        "1) plugin_call（推荐）:\n"
        "   {\"tool\":\"plugin_call\",\"args\":{\"command\":\"todo\",\"argv\":[\"list\"]}}\n"
        "   {\"tool\":\"plugin_call\",\"args\":{\"command\":\"课表\",\"argv\":[\"周一\"]}}\n"
        "   {\"tool\":\"plugin_call\",\"args\":{\"command\":\"sendpic\",\"category\":\"food_images\",\"filename\":\"美蛙鱼.jpg\"}}\n"
        "   复杂参数可用 raw：\n"
        "   {\"tool\":\"plugin_call\",\"args\":{\"command\":\"remind\",\"raw\":\"吃药 23:30 --everyday\"}}\n"
        "2) plugin_command（兼容旧接口）:\n"
        "   {\"tool\":\"plugin_command\",\"args\":{\"command\":\"/todo list\"}}\n"
        "3) plugin_batch（批量命令）:\n"
        "   {\"tool\":\"plugin_batch\",\"args\":{\"commands\":[\"/添加课程 课程A|老师|地点|1|1|2|1-16\",\"/添加课程 课程B|老师|地点|2|3|4|1-16\"]}}\n\n"
        f"{plugin_catalog + chr(10) if plugin_catalog else ""}"
        "输出规则：\n"
        "- 若需要本地插件：输出一行 JSON（不要 markdown，不要解释）。\n"
        "- 若只需 OpenClaw 原生工具即可完成任务（不限于联网），直接调用并返回最终答案，不要说‘没有接口’。\n"
        "- 如果你使用了原生联网工具并直接给最终自然回复（非插件JSON），请在首行加标记：[NATIVE_NETWORK_USED]。\n"
        "- 图片命令请显式带分类参数：food_images 对应 --eat，latex 对应 --latex。\n"
        "- 工具失败时先自我修正（改参数/换工具）再重试。\n"
        "- 当插件提示格式要求时，先调用 /help <命令名> 确认格式再重试。\n"
        "- “countdown/倒计时/ddl”仅用于倒计时管理，不要把普通时间问句误判成倒计时命令。\n"
        "- 批量任务优先 plugin_batch，避免只做一条就停。\n"
        "- 插件执行成功后，先理解插件输出，再用自然话术整理回复，不要原样粘贴。\n"
        "- 如果不需要任何工具，直接自然回复。\n"
        f"{attachment_context + chr(10) if attachment_context else ''}"
        f"用户消息：{user_text}"
    )


def build_no_placeholder_prompt(role_prompt: str, user_text: str, last_reply: str) -> str:
    return (
        f"{role_prompt}\n\n"
        f"用户消息：{user_text}\n"
        f"你刚才的回复：{last_reply}\n\n"
        "请直接给可用结论，不要先说‘我去查一下/稍等’这类过渡句。"
        "如果信息不足，就只补问一句关键问题；不要长篇解释流程。"
    )
