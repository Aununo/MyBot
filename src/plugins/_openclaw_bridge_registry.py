import importlib
import time
from typing import Dict, Tuple

# 静态兜底目录（help 插件异常时使用）
FALLBACK_PLUGIN_COMMANDS: Dict[str, str] = {
    "todo": "待办事项管理",
    "remind": "提醒（支持代设）",
    "remindall": "群内@全体提醒",
    "notready": "提醒延后到当天新时间",
    "listreminders": "查看提醒列表",
    "cancelremind": "取消提醒",
    "countdown": "倒计时管理",
    "weather": "天气查询",
    "课表": "课表查询",
    "本周课表": "本周课表",
    "添加课程": "新增/合并课程",
    "删除课程": "删除课程",
    "清空课表": "清空课表",
    "设置开学日期": "设置开学日期",
    "接龙": "接龙",
    "check_email": "检查邮件",
    "usage": "使用统计",
    "latex": "LaTeX 渲染",
    "save": "消息截图",
    "savepic": "保存到图床索引",
    "sendpic": "发送图床媒体",
    "rmpic": "删除图床媒体",
    "mvpic": "重命名索引项",
    "listpic": "列出图片索引",
    "randpic": "随机图片",
    "android": "今天吃啥（android）",
    "apple": "今天吃啥（apple）",
    "ping": "连通性检测",
    "status": "状态查询",
    "help": "插件帮助",
}

FALLBACK_PLUGIN_ALIASES: Dict[str, str] = {
    "我的提醒": "listreminders",
    "取消提醒": "cancelremind",
    "倒计时": "countdown",
    "ddl": "countdown",
    "天气": "weather",
    "tex": "latex",
    "随机表情": "randpic",
    "帮助": "help",
}

# 运行时缓存（避免每次都 import + 解析 help）
_CACHE_TTL_SECONDS = 300
_cache_at: float = 0.0
_cache_commands: Dict[str, str] = dict(FALLBACK_PLUGIN_COMMANDS)
_cache_aliases: Dict[str, str] = dict(FALLBACK_PLUGIN_ALIASES)


def _extract_help_summary(help_text: str) -> str:
    txt = (help_text or "").strip()
    if not txt:
        return ""
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        return ""

    # 取第一行标题或第一条命令作为摘要
    first = lines[0]
    if first.startswith("-") and len(lines) > 1:
        return lines[1][:30]
    return first[:30]


def _load_from_help_module() -> Tuple[Dict[str, str], Dict[str, str]]:
    mod = importlib.import_module("src.plugins.help")
    help_details = getattr(mod, "HELP_DETAILS", {})
    aliases = getattr(mod, "ALIASES", {})

    commands: Dict[str, str] = {}
    if isinstance(help_details, dict):
        for key, val in help_details.items():
            k = str(key).strip().lstrip("/")
            if not k:
                continue
            # ai 是 bridge 对话入口，不算本地插件命令
            if k in {"ai"}:
                continue
            summary = _extract_help_summary(str(val))
            commands[k] = summary or f"{k} 命令"

    alias_map: Dict[str, str] = {}
    if isinstance(aliases, dict):
        for a, canon in aliases.items():
            ak = str(a).strip().lstrip("/")
            ck = str(canon).strip().lstrip("/")
            if ak and ck:
                alias_map[ak] = ck

    if not commands:
        commands = dict(FALLBACK_PLUGIN_COMMANDS)
    if not alias_map:
        alias_map = dict(FALLBACK_PLUGIN_ALIASES)

    return commands, alias_map


def _refresh_cache_if_needed(force: bool = False) -> None:
    global _cache_at, _cache_commands, _cache_aliases
    now = time.time()
    if (not force) and (now - _cache_at < _CACHE_TTL_SECONDS):
        return

    try:
        cmds, aliases = _load_from_help_module()
        _cache_commands = cmds
        _cache_aliases = aliases
    except Exception:
        _cache_commands = dict(FALLBACK_PLUGIN_COMMANDS)
        _cache_aliases = dict(FALLBACK_PLUGIN_ALIASES)
    finally:
        _cache_at = now


def normalize_plugin_command(command: str) -> str:
    _refresh_cache_if_needed()
    c = (command or "").strip().lstrip("/")
    if not c:
        return ""
    return _cache_aliases.get(c, c)


def is_supported_plugin_command(command: str) -> bool:
    _refresh_cache_if_needed()
    return normalize_plugin_command(command) in _cache_commands


def render_plugin_catalog_for_prompt() -> str:
    _refresh_cache_if_needed()
    lines = ["本地插件命令目录（canonical）："]
    for k, v in _cache_commands.items():
        lines.append(f"- {k}: {v}")
    if _cache_aliases:
        lines.append("别名：" + "，".join(f"{a}->{b}" for a, b in _cache_aliases.items()))
    return "\n".join(lines)
