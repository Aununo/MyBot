import asyncio
import hashlib
import json
import os
import random
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from ._data_paths import resolve_data_dir
from typing import Optional, Dict, Tuple, Any

import httpx
from nonebot import logger, on_message, require, get_driver
from nonebot.message import handle_event
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, Message, MessageSegment

from ._openclaw_bridge_images import (
    build_attachment_context as _build_attachment_context_impl,
    cleanup_old_bridge_images as _cleanup_old_bridge_images_impl,
    collect_event_image_urls as _collect_event_image_urls,
    download_image_to_local as _download_image_to_local_impl,
)
from ._openclaw_bridge_audio import (
    cleanup_old_bridge_audio as _cleanup_old_bridge_audio_impl,
    collect_event_audio_entries as _collect_event_audio_entries,
    download_audio_to_local as _download_audio_to_local_impl,
)
from ._openclaw_bridge_text import (
    clean_user_text as _clean_user_text,
    coerce_to_message as _coerce_to_message,
    flatten_forward_nodes as _flatten_forward_nodes,
    looks_like_incomplete_progress_reply as _looks_like_incomplete_progress_reply,
    merge_captured_messages as _merge_captured_messages,
    message_has_media as _message_has_media,
    message_to_plain_text as _message_to_plain_text,
    parse_tool_call as _parse_tool_call,
    strip_markdown as _strip_markdown,
    strip_native_network_marker as _strip_native_network_marker,
)
from ._openclaw_bridge_prompts import (
    build_exec_prompt as _build_exec_prompt,
    build_no_placeholder_prompt as _build_no_placeholder_prompt,
    build_plugin_rewrite_prompt as _build_plugin_rewrite_prompt,
    build_tool_followup_prompt as _build_tool_followup_prompt,
    build_tool_retry_prompt as _build_tool_retry_prompt,
)
from ._openclaw_bridge_registry import (
    is_supported_plugin_command,
    normalize_plugin_command,
    render_plugin_catalog_for_prompt,
)

bridge = on_message(priority=20, block=True)

OPENCLAW_AGENT_ID = os.getenv("OPENCLAW_AGENT_ID", "main")
OPENCLAW_BRIDGE_USE_LOCAL = os.getenv("OPENCLAW_BRIDGE_USE_LOCAL", "false").strip().lower() in {"1", "true", "yes", "on"}
OPENCLAW_TIMEOUT = int(os.getenv("OPENCLAW_BRIDGE_TIMEOUT", "180"))
OPENCLAW_THINKING = os.getenv("OPENCLAW_BRIDGE_THINKING", "medium")
OPENCLAW_NODE_OPTIONS = os.getenv("OPENCLAW_BRIDGE_NODE_OPTIONS", "").strip()
try:
    OPENCLAW_NODE_MAX_OLD_SPACE_MB = max(256, int(os.getenv("OPENCLAW_BRIDGE_NODE_MAX_OLD_SPACE_MB", "768")))
except Exception:
    OPENCLAW_NODE_MAX_OLD_SPACE_MB = 768
OPENCLAW_TOOL_TRACE = os.getenv("OPENCLAW_TOOL_TRACE", "true").strip().lower() in {"1", "true", "yes", "on"}
OPENCLAW_FAST_SINGLE_STEP = os.getenv("OPENCLAW_FAST_SINGLE_STEP", "true").strip().lower() in {"1", "true", "yes", "on"}
try:
    OPENCLAW_SESSION_SLICE_HOURS = int(os.getenv("OPENCLAW_SESSION_SLICE_HOURS", "6"))
except Exception:
    OPENCLAW_SESSION_SLICE_HOURS = 6

OPENCLAW_SESSION_MODE = os.getenv("OPENCLAW_SESSION_MODE", "ephemeral").strip().lower()  # ephemeral | slice | sticky

try:
    _tool_rounds_raw = int(os.getenv("OPENCLAW_TOOL_MAX_ROUNDS", "0"))
except Exception:
    _tool_rounds_raw = 0

# <=0 视为“不设轮次上限”（实践中用超大值实现）
if _tool_rounds_raw <= 0:
    OPENCLAW_TOOL_MAX_ROUNDS = 10 ** 9
else:
    OPENCLAW_TOOL_MAX_ROUNDS = min(10000, _tool_rounds_raw)

GEOCODE_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"

ROLEPLAY_BASE_PROMPT = (
    "你在QQ群里聊天，像真人，不像客服。"
    "口语化、短句、自然一点；优先 1-2 句说清楚。"
    "可用少量语气词（呀/呢/啦），但别堆砌。"
    "避免过度煽情、模板化夸赞和尴尬土味情话。"
    "不要使用括号动作描写（如（深深地）/（抱抱）），不要舞台腔。"
)

OPENCLAW_DAD_QQ = os.getenv("OPENCLAW_DAD_QQ", "").strip()
OPENCLAW_MOM_QQ = os.getenv("OPENCLAW_MOM_QQ", "").strip()
# 可选：按群绑定角色（强烈推荐）
# 例：{"123456789":{"dad":"111111","mom":"222222"}}
OPENCLAW_GROUP_ROLE_BINDINGS_JSON = os.getenv("OPENCLAW_GROUP_ROLE_BINDINGS_JSON", "").strip()

# 直接绑定 user_id（按群）
GROUP_ROLE_BINDINGS: Dict[str, Dict[str, str]] = {
    "1063926539": {"dad": "2921712841", "mom": "3244180869"},
    # "群号": {"dad": "爸爸QQ号", "mom": "妈妈QQ号"},
}

if OPENCLAW_GROUP_ROLE_BINDINGS_JSON:
    try:
        parsed = json.loads(OPENCLAW_GROUP_ROLE_BINDINGS_JSON)
        if isinstance(parsed, dict):
            for gid, item in parsed.items():
                if isinstance(item, dict):
                    dad = str(item.get("dad", "") or "").strip()
                    mom = str(item.get("mom", "") or "").strip()
                    GROUP_ROLE_BINDINGS[str(gid)] = {"dad": dad, "mom": mom}
    except Exception as exc:
        logger.warning(f"invalid OPENCLAW_GROUP_ROLE_BINDINGS_JSON: {exc}")

try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler  # type: ignore
except Exception:
    scheduler = None

try:
    SH_TZ = __import__("zoneinfo").ZoneInfo("Asia/Shanghai")
except Exception:
    SH_TZ = None

plugin_dir = Path(__file__).parent
data_dir = resolve_data_dir()
weather_job_file = data_dir / "openclaw_bridge_weather_jobs.json"
weather_jobs: Dict[str, Dict] = {}
eat_data_file = data_dir / "eat_data.json"
pic_index_file = data_dir / "pic_index.json"
OPENCLAW_IMAGE_MODE = os.getenv("OPENCLAW_IMAGE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
OPENCLAW_IMAGE_MAX_COUNT = max(1, min(6, int(os.getenv("OPENCLAW_IMAGE_MAX_COUNT", "3"))))
OPENCLAW_IMAGE_MAX_BYTES = max(512 * 1024, int(os.getenv("OPENCLAW_IMAGE_MAX_BYTES", str(12 * 1024 * 1024))))
OPENCLAW_IMAGE_DIR = Path(os.getenv("OPENCLAW_BRIDGE_IMAGE_DIR", "/home/aununo/.openclaw/workspace/bridge_images"))
try:
    OPENCLAW_IMAGE_RETENTION_SECONDS = max(0, int(os.getenv("OPENCLAW_IMAGE_RETENTION_SECONDS", "600")))
except Exception:
    OPENCLAW_IMAGE_RETENTION_SECONDS = 600

OPENCLAW_AUDIO_MODE = os.getenv("OPENCLAW_AUDIO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
OPENCLAW_AUDIO_MAX_COUNT = max(1, min(3, int(os.getenv("OPENCLAW_AUDIO_MAX_COUNT", "1"))))
OPENCLAW_AUDIO_MAX_BYTES = max(512 * 1024, int(os.getenv("OPENCLAW_AUDIO_MAX_BYTES", str(24 * 1024 * 1024))))
OPENCLAW_AUDIO_DIR = Path(os.getenv("OPENCLAW_BRIDGE_AUDIO_DIR", "/home/aununo/.openclaw/workspace/bridge_audio"))
OPENCLAW_AUDIO_MODEL = os.getenv("OPENCLAW_AUDIO_MODEL", "small").strip() or "small"
try:
    OPENCLAW_AUDIO_RETENTION_SECONDS = max(0, int(os.getenv("OPENCLAW_AUDIO_RETENTION_SECONDS", "1800")))
except Exception:
    OPENCLAW_AUDIO_RETENTION_SECONDS = 1800
try:
    OPENCLAW_AUDIO_TRANSCRIBE_TIMEOUT = max(20, int(os.getenv("OPENCLAW_AUDIO_TRANSCRIBE_TIMEOUT", "180")))
except Exception:
    OPENCLAW_AUDIO_TRANSCRIBE_TIMEOUT = 180

_PLUGIN_CAPTURE_LOCK = asyncio.Lock()

_PLUGIN_HELP_CACHE: Dict[str, str] = {}

PLACEHOLDER_PATTERNS = [
    r"我来查",
    r"我帮你查",
    r"正在查询",
    r"请等我一下",
    r"稍等",
    r"等下",
    r"马上告诉你",
    r"查不到",
    r"我马上开始",
    r"我这就",
    r"我先去",
    r"整理好就",
    r"第一时间发",
    r"稍后发",
]

def _load_weather_jobs() -> None:
    global weather_jobs
    if weather_job_file.exists():
        try:
            weather_jobs = json.loads(weather_job_file.read_text(encoding="utf-8"))
        except Exception:
            weather_jobs = {}
    else:
        weather_jobs = {}


def _save_weather_jobs() -> None:
    weather_job_file.parent.mkdir(parents=True, exist_ok=True)
    weather_job_file.write_text(
        json.dumps(weather_jobs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _resolve_sender_role(event: GroupMessageEvent) -> Tuple[str, str]:
    """
    返回 (role, display_name)
    role: dad | mom | other
    只使用 user_id 直接绑定，不做昵称猜测/自动学习。
    """
    gid = str(event.group_id)
    uid = str(event.user_id)
    card = str(getattr(getattr(event, "sender", None), "card", "") or "")
    nick = str(getattr(getattr(event, "sender", None), "nickname", "") or "")
    display = card.strip() or nick.strip() or uid

    group_bind = GROUP_ROLE_BINDINGS.get(gid, {})
    dad = str(group_bind.get("dad", "") or "").strip()
    mom = str(group_bind.get("mom", "") or "").strip()

    # 全局兜底（当群内映射没填时）
    if not dad and OPENCLAW_DAD_QQ:
        dad = OPENCLAW_DAD_QQ
    if not mom and OPENCLAW_MOM_QQ:
        mom = OPENCLAW_MOM_QQ

    if uid == dad:
        return "dad", display
    if uid == mom:
        return "mom", display

    return "other", display


def _get_group_family_ids(event: GroupMessageEvent) -> Tuple[str, str]:
    gid = str(event.group_id)
    group_bind = GROUP_ROLE_BINDINGS.get(gid, {})
    dad = str(group_bind.get("dad", "") or "").strip() or OPENCLAW_DAD_QQ
    mom = str(group_bind.get("mom", "") or "").strip() or OPENCLAW_MOM_QQ
    return dad.strip(), mom.strip()


def _infer_kinship_target_user_id(event: GroupMessageEvent, text: str) -> str:
    """从语义中推断提醒对象（你妈妈/你爸爸），用于提醒类命令兜底。"""
    t = _clean_user_text(text)
    if not t:
        return ""

    dad, mom = _get_group_family_ids(event)
    sender_uid = str(event.user_id)

    if ("你妈妈" in t) and mom:
        return mom
    if ("你爸爸" in t) and dad:
        return dad

    # 轻量兜底：父母双方互提时自动识别
    if ("妈妈" in t) and (sender_uid == dad) and mom:
        return mom
    if ("爸爸" in t) and (sender_uid == mom) and dad:
        return dad

    return ""


def _inject_kinship_target_into_tool_call(tool: str, args: Dict[str, Any], event: GroupMessageEvent, user_text: str) -> Dict[str, Any]:
    if not isinstance(args, dict):
        return args

    cmd = _clean_user_text(str(args.get("command", "")).lstrip("/")).lower()
    remind_like = {"remind", "listreminders", "我的提醒", "cancelremind", "取消提醒"}

    inferred = _infer_kinship_target_user_id(event, user_text)
    if not inferred:
        return args

    out = dict(args)

    if tool == "plugin_call" and cmd in remind_like:
        has_target = any(str(out.get(k, "")).strip() for k in ("target_user_id", "target_qq", "user_id"))
        if not has_target:
            out["target_user_id"] = inferred
        return out

    if tool == "plugin_command":
        command = _clean_user_text(str(out.get("command", ""))).strip()
        if not command:
            return out
        low = command.lower()
        if low.startswith("/remind") or low.startswith("/listreminders") or low.startswith("/我的提醒") or low.startswith("/cancelremind") or low.startswith("/取消提醒"):
            if "[CQ:at,qq=" not in command:
                parts = command.split(maxsplit=1)
                head = parts[0]
                tail = parts[1] if len(parts) > 1 else ""
                out["command"] = f"{head} [CQ:at,qq={inferred}] {tail}".strip()
        return out

    return out


def _rewrite_family_mentions_in_reply(event: GroupMessageEvent, user_text: str, reply: str) -> str:
    """将“@妈妈/@爸爸”等口语称呼尽量改写为 OneBot @ 提及。"""
    if not reply:
        return reply

    out = str(reply)
    dad, mom = _get_group_family_ids(event)
    sender_uid = str(event.user_id)

    # 1) 显式“@妈妈/@爸爸”写法 -> CQ at
    if mom:
        out = re.sub(r"@\s*妈妈", f"[CQ:at,qq={mom}]", out)
    if dad:
        out = re.sub(r"@\s*爸爸", f"[CQ:at,qq={dad}]", out)

    # 2) 若用户明确说“给妈妈/跟妈妈说...”且回复里提到妈妈但未@，补一个@
    if "[CQ:at,qq=" not in out:
        if mom and sender_uid == dad and re.search(r"(给|跟|和)?妈妈说", user_text) and ("妈妈" in out):
            out = f"[CQ:at,qq={mom}] {out}".strip()
        elif dad and sender_uid == mom and re.search(r"(给|跟|和)?爸爸说", user_text) and ("爸爸" in out):
            out = f"[CQ:at,qq={dad}] {out}".strip()

    return out


def _render_reply_message(reply: str) -> Message:
    """把文本中的 [CQ:at,qq=xxxx] 转成真正的 MessageSegment.at，避免原样显示。"""
    txt = str(reply or "")
    msg = Message()
    pos = 0
    has_seg = False

    for m in re.finditer(r"\[CQ:at,qq=(\d+)\]", txt):
        if m.start() > pos:
            msg.append(MessageSegment.text(txt[pos:m.start()]))
        qq = m.group(1)
        try:
            msg.append(MessageSegment.at(int(qq)))
        except Exception:
            msg.append(MessageSegment.text(m.group(0)))
        has_seg = True
        pos = m.end()

    if pos < len(txt):
        msg.append(MessageSegment.text(txt[pos:]))

    if not has_seg:
        return Message(txt)
    return msg


def _extract_text_without_at(event: GroupMessageEvent) -> str:
    chunks: list[str] = []
    self_id = str(event.self_id)
    for seg in event.message:
        if seg.type == "at" and str(seg.data.get("qq", "")) == self_id:
            continue
        if seg.type == "text":
            chunks.append(seg.data.get("text", ""))
    return "".join(chunks)


def _is_at_bot(event: GroupMessageEvent) -> bool:
    self_id = str(event.self_id)
    return any(
        seg.type == "at" and str(seg.data.get("qq", "")) == self_id
        for seg in event.message
    )


async def _download_image_to_local(url: str) -> Optional[str]:
    return await _download_image_to_local_impl(
        url=url,
        image_dir=OPENCLAW_IMAGE_DIR,
        max_bytes=OPENCLAW_IMAGE_MAX_BYTES,
        logger=logger,
    )


async def _download_audio_to_local(url: str) -> Optional[str]:
    return await _download_audio_to_local_impl(
        url=url,
        audio_dir=OPENCLAW_AUDIO_DIR,
        max_bytes=OPENCLAW_AUDIO_MAX_BYTES,
        logger=logger,
    )


def _cleanup_old_bridge_images(current_paths: Optional[list[str]] = None) -> None:
    _cleanup_old_bridge_images_impl(
        image_dir=OPENCLAW_IMAGE_DIR,
        retention_seconds=OPENCLAW_IMAGE_RETENTION_SECONDS,
        current_paths=current_paths,
    )


def _cleanup_old_bridge_audio(current_paths: Optional[list[str]] = None) -> None:
    _cleanup_old_bridge_audio_impl(
        audio_dir=OPENCLAW_AUDIO_DIR,
        retention_seconds=OPENCLAW_AUDIO_RETENTION_SECONDS,
        current_paths=current_paths,
    )


def _normalize_local_file_path(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return ""
    if t.startswith("file://"):
        t = unquote(t[len("file://"):])
    return t


async def _resolve_record_to_local(bot: Bot, entry: Dict[str, str]) -> Optional[str]:
    raw_url = str(entry.get("url", "") or "").strip()
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        p = await _download_audio_to_local(raw_url)
        if p:
            return p

    raw_file = str(entry.get("file", "") or "").strip()
    if not raw_file:
        return None

    if raw_file.startswith("http://") or raw_file.startswith("https://"):
        p = await _download_audio_to_local(raw_file)
        if p:
            return p

    local_file = _normalize_local_file_path(raw_file)
    if local_file and Path(local_file).exists():
        return local_file

    try:
        api_result = await bot.call_api("get_record", file=raw_file, out_format="wav")
    except Exception as exc:
        logger.warning(f"get_record failed: {exc}")
        return None

    candidates: list[str] = []
    if isinstance(api_result, str):
        candidates.append(api_result)
    elif isinstance(api_result, dict):
        for k in ("file", "path", "url"):
            v = api_result.get(k)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())

    for c in candidates:
        if c.startswith("http://") or c.startswith("https://"):
            p = await _download_audio_to_local(c)
            if p:
                return p
            continue

        pth = _normalize_local_file_path(c)
        if pth and Path(pth).exists():
            return pth

    return None


def _transcribe_audio_to_text(local_path: str) -> Tuple[str, str, float]:
    script = r'''
import json
import sys

path = sys.argv[1]
model_name = sys.argv[2]

try:
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(path, beam_size=5)
    text = "".join(seg.text for seg in segments).strip()
    out = {
        "ok": True,
        "text": text,
        "language": getattr(info, "language", "") or "",
        "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
    }
    print(json.dumps(out, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
'''

    try:
        proc = subprocess.run(
            ["/usr/bin/python3", "-c", script, str(local_path), OPENCLAW_AUDIO_MODEL],
            capture_output=True,
            text=True,
            timeout=OPENCLAW_AUDIO_TRANSCRIBE_TIMEOUT,
            check=False,
        )
    except Exception as exc:
        logger.warning(f"voice asr subprocess failed: {exc}")
        return "", "", 0.0

    raw = (proc.stdout or "").strip()
    if not raw:
        logger.warning(f"voice asr empty output, stderr={proc.stderr[:300] if proc.stderr else ''}")
        return "", "", 0.0

    start = raw.find("{")
    end = raw.rfind("}")
    payload_text = raw[start:end + 1] if (start != -1 and end != -1 and end > start) else raw

    try:
        payload = json.loads(payload_text)
    except Exception as exc:
        logger.warning(f"voice asr invalid json: {exc}; raw={raw[:300]}")
        return "", "", 0.0

    if not isinstance(payload, dict) or not payload.get("ok"):
        logger.warning(f"voice asr failed payload: {payload}")
        return "", "", 0.0

    text = _clean_user_text(str(payload.get("text", "") or ""))
    lang = str(payload.get("language", "") or "")
    try:
        prob = float(payload.get("language_probability", 0.0) or 0.0)
    except Exception:
        prob = 0.0

    return text, lang, prob


def _build_attachment_context(local_paths: list[str], remote_urls: list[str]) -> str:
    return _build_attachment_context_impl(
        local_paths=local_paths,
        remote_urls=remote_urls,
        max_count=OPENCLAW_IMAGE_MAX_COUNT,
    )


def _build_session_id(event: GroupMessageEvent) -> str:
    """会话策略：
    - ephemeral: 每条消息独立会话（最快，几乎无历史记忆）
    - slice: 按时间分片（折中）
    - sticky: 单群固定会话（历史最长）
    """
    mode = OPENCLAW_SESSION_MODE

    if mode == "sticky":
        return f"qq-group-{event.group_id}"

    if mode == "slice":
        if OPENCLAW_SESSION_SLICE_HOURS <= 0:
            return f"qq-group-{event.group_id}"
        now = datetime.now(SH_TZ) if SH_TZ else datetime.utcnow()
        slice_hours = max(1, min(24, OPENCLAW_SESSION_SLICE_HOURS))
        bucket = now.hour // slice_hours
        day = now.strftime("%Y%m%d")
        return f"qq-group-{event.group_id}:{day}:h{slice_hours}:b{bucket}"

    # 默认 ephemeral（每条消息独立会话）
    msg_id = str(getattr(event, "message_id", "0") or "0")
    now = datetime.now(SH_TZ) if SH_TZ else datetime.utcnow()
    return f"qq-group-{event.group_id}:ep:{now.strftime('%Y%m%d%H%M%S')}:{msg_id}"


def _looks_like_multi_step_request(text: str) -> bool:
    t = _clean_user_text(text)
    if not t:
        return False

    multi_markers = ["然后", "并且", "再", "顺便", "另外", "同时", "接着", "最后", ";", "；", "，再", "并"]
    return any(m in t for m in multi_markers)


def _is_current_time_query(text: str) -> bool:
    t = _clean_user_text(text)
    if not t:
        return False

    if t.startswith("/"):
        return False

    time_ask_patterns = [
        r"现在几点", r"现在几点了", r"几点了", r"当前时间", r"现在时间", r"北京时间", r"time\??$",
    ]
    if not any(re.search(p, t, re.I) for p in time_ask_patterns):
        return False

    # 避免与倒计时/提醒语义冲突
    conflict = ["倒计时", "countdown", "ddl", "提醒", "remind", "明天", "后天", "周"]
    return not any(k in t.lower() for k in [c.lower() for c in conflict])


def _is_placeholder_reply(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    return any(re.search(p, t) for p in PLACEHOLDER_PATTERNS)


def _is_likely_city_name(city: str) -> bool:
    c = _clean_user_text(city)
    if not c:
        return False
    if not re.fullmatch(r"[一-龥A-Za-z]{2,12}", c):
        return False
    bad_subs = ["提醒", "然后", "并且", "帮我", "告诉", "群里", "明天", "后天", "今天", "早上", "上午", "下午", "晚上", "现在"]
    return not any(x in c for x in bad_subs)


def _parse_date_token(date_str: str, now: datetime):
    if date_str == "明天":
        return (now + timedelta(days=1)).date()
    if date_str == "后天":
        return (now + timedelta(days=2)).date()
    if date_str == "大后天":
        return (now + timedelta(days=3)).date()

    m = re.match(r"^(\d+)天后$", date_str)
    if m:
        return (now + timedelta(days=int(m.group(1)))).date()

    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return None

    if re.match(r"^\d{1,2}-\d{1,2}$", date_str):
        try:
            mm, dd = map(int, date_str.split("-"))
            y = now.year
            d = datetime(y, mm, dd).date()
            if d < now.date():
                d = datetime(y + 1, mm, dd).date()
            return d
        except Exception:
            return None

    return None


async def _fetch_weather_reply(city: str) -> Optional[str]:
    city = _clean_user_text(city)
    if not city:
        return None

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            geo = await client.get(
                GEOCODE_API,
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
            )
            g = geo.json()
            results = g.get("results") or []

            if not results:
                geo2 = await client.get(
                    GEOCODE_API,
                    params={"name": city, "count": 1, "language": "en", "format": "json"},
                )
                g2 = geo2.json()
                results = g2.get("results") or []

            if not results:
                return None

            r0 = results[0]
            lat, lon = r0.get("latitude"), r0.get("longitude")
            real_name = r0.get("name", city)
            tz = r0.get("timezone", "Asia/Shanghai")

            fc = await client.get(
                FORECAST_API,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m",
                    "daily": "precipitation_probability_max",
                    "timezone": tz,
                    "forecast_days": 1,
                },
            )
            data = fc.json()
            cur = data.get("current", {})
            daily = data.get("daily", {})

            temp = cur.get("temperature_2m")
            app = cur.get("apparent_temperature")
            rh = cur.get("relative_humidity_2m")
            pr = cur.get("precipitation")
            pops = daily.get("precipitation_probability_max") or []
            pop = pops[0] if isinstance(pops, list) and pops else None

            if temp is None:
                return None

            parts = [f"爸爸，{real_name}现在 {temp}°C"]
            if app is not None:
                parts.append(f"体感 {app}°C")
            if rh is not None:
                parts.append(f"湿度 {rh}%")
            if pr is not None:
                parts.append(f"降水 {pr}mm")
            if pop is not None:
                parts.append(f"今天降雨概率最高约 {pop}%")
            return "，".join(parts) + "。"

    except Exception as exc:
        logger.warning(f"weather fetch failed: {exc}")
        return None


async def _scheduled_weather_push(bot: Bot, group_id: int, user_id: int, city: str, job_key: str = ""):
    reply = await _fetch_weather_reply(city)
    if not reply:
        reply = f"爸爸，{city}这次天气没查到，我下一次再继续帮你查。"

    msg = MessageSegment.at(user_id) + Message(f" {reply}")
    await bot.send_group_msg(group_id=int(group_id), message=msg)

    # 一次性任务执行后清理持久化记录
    if job_key and job_key in weather_jobs:
        item = weather_jobs.get(job_key, {})
        if isinstance(item, dict) and item.get("kind") == "date":
            weather_jobs.pop(job_key, None)
            _save_weather_jobs()


def _upsert_daily_weather_job(bot: Bot, group_id: int, user_id: int, city: str, hour: int, minute: int) -> Tuple[bool, str]:
    if scheduler is None or SH_TZ is None:
        return False, "爸爸，定时器模块现在不可用，暂时没法创建自动天气提醒。"

    key = f"{group_id}:{user_id}:daily_weather"
    job_hash = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    job_id = f"ocw_{job_hash}"

    try:
        scheduler.add_job(
            _scheduled_weather_push,
            "cron",
            hour=hour,
            minute=minute,
            id=job_id,
            args=[bot, int(group_id), int(user_id), city],
            timezone=SH_TZ,
            replace_existing=True,
        )
    except Exception as exc:
        logger.exception(f"create daily weather job failed: {exc}")
        return False, "爸爸，创建定时任务失败了，我这边再检查一下。"

    weather_jobs[key] = {
        "kind": "cron",
        "job_id": job_id,
        "group_id": int(group_id),
        "user_id": int(user_id),
        "city": city,
        "hour": hour,
        "minute": minute,
    }
    _save_weather_jobs()

    return True, f"好的爸爸，安排好了：每天 {hour:02d}:{minute:02d} 我会在群里报 {city}天气给你。"


def _upsert_once_weather_job(bot: Bot, group_id: int, user_id: int, city: str, run_dt: datetime) -> Tuple[bool, str]:
    if scheduler is None or SH_TZ is None:
        return False, "爸爸，定时器模块现在不可用，暂时没法创建自动天气提醒。"

    key = f"{group_id}:{user_id}:once_weather:{run_dt.isoformat()}"
    job_hash = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    job_id = f"ocw_once_{job_hash}"

    try:
        scheduler.add_job(
            _scheduled_weather_push,
            "date",
            run_date=run_dt,
            id=job_id,
            args=[bot, int(group_id), int(user_id), city, key],
            timezone=SH_TZ,
            replace_existing=True,
        )
    except Exception as exc:
        logger.exception(f"create once weather job failed: {exc}")
        return False, "爸爸，创建一次性天气任务失败了，我这边再检查一下。"

    weather_jobs[key] = {
        "kind": "date",
        "job_id": job_id,
        "group_id": int(group_id),
        "user_id": int(user_id),
        "city": city,
        "run_at": run_dt.isoformat(),
    }
    _save_weather_jobs()

    return True, f"好的爸爸，安排好了：{run_dt.strftime('%m-%d %H:%M')} 我会在群里报 {city}天气提醒你。"


def _restore_weather_jobs(bot: Bot) -> None:
    if scheduler is None or SH_TZ is None:
        return

    now = datetime.now(SH_TZ)
    changed = False

    for key, item in list(weather_jobs.items()):
        try:
            kind = str(item.get("kind", "cron"))
            city_raw = str(item.get("city", "")).strip()
            if not _is_likely_city_name(city_raw):
                weather_jobs.pop(key, None)
                changed = True
                continue
            if kind == "date":
                run_at_raw = str(item.get("run_at", ""))
                run_at = datetime.fromisoformat(run_at_raw) if run_at_raw else None
                if (run_at is None) or (run_at <= now):
                    weather_jobs.pop(key, None)
                    changed = True
                    continue

                scheduler.add_job(
                    _scheduled_weather_push,
                    "date",
                    run_date=run_at,
                    id=str(item.get("job_id")),
                    args=[
                        bot,
                        int(item.get("group_id")),
                        int(item.get("user_id")),
                        str(item.get("city", "成都")),
                        key,
                    ],
                    timezone=SH_TZ,
                    replace_existing=True,
                )
            else:
                scheduler.add_job(
                    _scheduled_weather_push,
                    "cron",
                    hour=int(item.get("hour", 7)),
                    minute=int(item.get("minute", 0)),
                    id=str(item.get("job_id")),
                    args=[
                        bot,
                        int(item.get("group_id")),
                        int(item.get("user_id")),
                        str(item.get("city", "成都")),
                    ],
                    timezone=SH_TZ,
                    replace_existing=True,
                )
        except Exception as exc:
            logger.warning(f"restore weather job failed: {exc}")

    if changed:
        _save_weather_jobs()


def _load_json_dict(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _pic_entry_url(entry: Any) -> Optional[str]:
    if isinstance(entry, str) and entry.strip():
        return entry.strip()
    if isinstance(entry, dict):
        url = entry.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _find_food_image_url(food_name: str) -> Optional[str]:
    idx = _load_json_dict(pic_index_file)
    bucket = idx.get("food_images", {})
    if not isinstance(bucket, dict):
        return None

    for filename, entry in bucket.items():
        stem = Path(str(filename)).stem
        if stem == food_name:
            u = _pic_entry_url(entry)
            if u:
                return u
    return None


TOOL_ERROR_PATTERNS = [
    r"未找到",
    r"缺少",
    r"无效",
    r"失败",
    r"异常",
    r"不存在",
    r"空的",
    r"不支持",
    r"超范围",
    r"请指定",
    r"过去了",
    r"没查到",
]


def _looks_like_tool_error(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    return any(re.search(p, t) for p in TOOL_ERROR_PATTERNS)


def _normalize_batch_commands(args: Dict[str, Any]) -> list[str]:
    out: list[str] = []
    raw = args.get("commands", [])
    if not isinstance(raw, list):
        return out

    for item in raw[:40]:
        cmd = ""
        if isinstance(item, str):
            cmd = _clean_user_text(item)
            if cmd and not cmd.startswith("/"):
                cmd = "/" + cmd
        elif isinstance(item, dict):
            # 结构化调用（优先按 plugin_call 组装）
            if any(k in item for k in ["argv", "raw", "filename", "category"]):
                cmd = _build_plugin_call_command(item) or ""
            else:
                c0 = _clean_user_text(str(item.get("command", "")))
                if c0:
                    cmd = c0 if c0.startswith("/") else "/" + c0

        cmd = _clean_user_text(cmd)
        if cmd:
            out.append(cmd)

    return out


def _is_network_cmd_text(cmd: str) -> bool:
    c = _clean_user_text(cmd).strip().lower()
    if not c:
        return False
    if not c.startswith("/"):
        c = "/" + c
    head = c.split()[0]
    return head in {"/weather", "/天气", "/check_email", "/检查邮件"}


def _is_network_tool_call(tname: str, targs: Dict[str, Any]) -> bool:
    t = (tname or "").strip()
    if t in {"weather_now", "weather_schedule_daily", "weather_schedule_once"}:
        return True

    if t == "plugin_command":
        cmd = _clean_user_text(str(targs.get("command", "")))
        return _is_network_cmd_text(cmd)

    if t == "plugin_call":
        cmd = _build_plugin_call_command(targs) or ""
        return _is_network_cmd_text(cmd)

    if t == "plugin_batch":
        cmds = _normalize_batch_commands(targs)
        return any(_is_network_cmd_text(c) for c in cmds[:20])

    return False


def _build_trace_text(tname: str, targs: Dict[str, Any]) -> str:
    t = (tname or "").strip()

    if t == "plugin_command":
        cmd = _clean_user_text(str(targs.get("command", "")))
        if _is_network_tool_call(t, targs):
            return f"🌐 已执行联网查询：{cmd or '(空命令)'}"
        return f"🛠️ 已执行插件命令：{cmd or '(空命令)'}"

    if t == "plugin_call":
        cmd = _build_plugin_call_command(targs) or "(空命令)"
        if _is_network_tool_call(t, targs):
            return f"🌐 已执行联网查询：{cmd}"
        return f"🛠️ 已执行插件命令：{cmd}"

    if t == "plugin_batch":
        cmds = _normalize_batch_commands(targs)
        count = len(cmds)
        if count <= 0:
            if _is_network_tool_call(t, targs):
                return "🌐 已执行联网批量任务：0 条"
            return "🛠️ 已执行批量命令：0 条"

        preview = [f"{i}. {c}" for i, c in enumerate(cmds[:8], 1)]
        if count > 8:
            preview.append(f"... 其余 {count - 8} 条略")

        if _is_network_tool_call(t, targs):
            head = f"🌐 已执行联网批量任务：{count} 条"
        else:
            head = f"🛠️ 已执行批量命令：{count} 条"
        return head + "\n" + "\n".join(preview)

    if _is_network_tool_call(t, targs):
        return f"🌐 已执行联网查询：{t}"
    return f"🛠️ 已执行工具：{t}"


async def _rewrite_plugin_output(
    role_prompt: str,
    user_text: str,
    plugin_command: str,
    plugin_output_text: str,
    session_id: str,
) -> Optional[str]:
    if not plugin_output_text.strip():
        return None

    prompt = _build_plugin_rewrite_prompt(
        role_prompt=role_prompt,
        user_text=user_text,
        plugin_command=plugin_command,
        plugin_output_text=plugin_output_text,
    )
    # 用独立 rewrite 会话，避免沿用执行模式上下文导致继续吐工具 JSON
    rewrite_session_id = f"{session_id}:rewrite"
    out = await _call_openclaw(prompt, rewrite_session_id)
    out = _strip_markdown(out or "")
    if not out:
        return None
    # 避免误返回工具 JSON
    if _parse_tool_call(out):
        return None
    return out


async def _dispatch_plugin_command(
    bot: Bot,
    event: GroupMessageEvent,
    command_text: str,
    capture_output: bool = False,
) -> list[Message]:
    cmd = _clean_user_text(command_text)
    if not cmd:
        raise ValueError("空命令")
    if not cmd.startswith("/"):
        cmd = "/" + cmd
    cmd = _normalize_help_style_command(cmd)

    synthetic = event.model_copy(
        update={
            "message": Message(cmd),
            "raw_message": cmd,
            "original_message": Message(cmd),
            "to_me": False,
            "reply": None,
        }
    )

    if not capture_output:
        await handle_event(bot, synthetic)
        return []

    captured: list[Message] = []

    orig_send = getattr(bot, "send", None)
    orig_send_group_msg = getattr(bot, "send_group_msg", None)
    orig_send_private_msg = getattr(bot, "send_private_msg", None)
    orig_call_api = getattr(bot, "call_api", None)

    async def _fake_send(*args, **kwargs):
        msg_payload = kwargs.get("message")
        if msg_payload is None:
            if len(args) >= 2:
                msg_payload = args[1]
            elif len(args) >= 1:
                msg_payload = args[0]
        msg = _coerce_to_message(msg_payload)
        if msg is not None:
            captured.append(msg)
        return {"message_id": 0}

    async def _fake_send_group_msg(*args, **kwargs):
        msg_payload = kwargs.get("message")
        if msg_payload is None and len(args) >= 2:
            msg_payload = args[1]
        msg = _coerce_to_message(msg_payload)
        if msg is not None:
            captured.append(msg)
        return {"message_id": 0}

    async def _fake_send_private_msg(*args, **kwargs):
        msg_payload = kwargs.get("message")
        if msg_payload is None and len(args) >= 2:
            msg_payload = args[1]
        msg = _coerce_to_message(msg_payload)
        if msg is not None:
            captured.append(msg)
        return {"message_id": 0}

    async def _fake_call_api(api: str, *args, **kwargs):
        api_name = str(api)

        if api_name in {"send_msg", "send_group_msg", "send_private_msg"}:
            msg_payload = kwargs.get("message")
            if msg_payload is None and len(args) >= 1:
                msg_payload = args[-1]
            msg = _coerce_to_message(msg_payload)
            if msg is not None:
                captured.append(msg)
            return {"message_id": 0, "retcode": 0, "status": "ok"}

        if api_name in {"send_group_forward_msg", "send_private_forward_msg"}:
            nodes = kwargs.get("messages")
            if nodes is None and len(args) >= 1:
                nodes = args[-1]
            forward_text = _flatten_forward_nodes(nodes)
            if forward_text:
                captured.append(Message(forward_text))
            return {"message_id": 0, "retcode": 0, "status": "ok"}

        if callable(orig_call_api):
            return await orig_call_api(api, *args, **kwargs)

        return {"retcode": 0, "status": "ok"}

    async with _PLUGIN_CAPTURE_LOCK:
        try:
            if callable(orig_send):
                setattr(bot, "send", _fake_send)
            if callable(orig_send_group_msg):
                setattr(bot, "send_group_msg", _fake_send_group_msg)
            if callable(orig_send_private_msg):
                setattr(bot, "send_private_msg", _fake_send_private_msg)
            if callable(orig_call_api):
                setattr(bot, "call_api", _fake_call_api)

            await handle_event(bot, synthetic)
        finally:
            if callable(orig_send):
                setattr(bot, "send", orig_send)
            if callable(orig_send_group_msg):
                setattr(bot, "send_group_msg", orig_send_group_msg)
            if callable(orig_send_private_msg):
                setattr(bot, "send_private_msg", orig_send_private_msg)
            if callable(orig_call_api):
                setattr(bot, "call_api", orig_call_api)

    return captured


def _build_plugin_call_command(args: Dict[str, Any]) -> Optional[str]:
    command = normalize_plugin_command(_clean_user_text(str(args.get("command", ""))).lstrip("/"))
    if not command:
        return None

    cmd_lower = command.lower()

    # 提醒类命令支持结构化目标用户参数，自动转为 CQ at（便于插件识别）
    target_user = _clean_user_text(str(
        args.get("target_user_id", args.get("target_qq", args.get("user_id", "")))
    )).strip()
    at_prefix = ""
    if cmd_lower in {"remind", "listreminders", "我的提醒", "cancelremind", "取消提醒"}:
        if target_user.isdigit() and len(target_user) >= 5:
            at_prefix = f"[CQ:at,qq={target_user}] "
    cat = _clean_user_text(str(args.get("category", ""))).strip().lower()
    category_flag = ""
    if cmd_lower in {"savepic", "sendpic", "rmpic", "mvpic", "listpic", "randpic"}:
        if cat in {"food_images", "food", "eat", "--eat"}:
            category_flag = "--eat"
        elif cat in {"latex", "--latex"}:
            category_flag = "--latex"

    # 如果未显式给分类，且是按文件名操作的图片命令，则按索引自动推断 --eat/--latex
    if not category_flag and cmd_lower in {"sendpic", "rmpic", "mvpic", "savepic"}:
        probe_name = _clean_user_text(str(args.get("filename", ""))).strip()
        if not probe_name:
            argv_probe = args.get("argv", [])
            if isinstance(argv_probe, list):
                for x in argv_probe:
                    xs = _clean_user_text(str(x)).strip()
                    if xs and (not xs.startswith("--")):
                        probe_name = xs
                        break
        if probe_name:
            idx = _load_json_dict(pic_index_file)
            food_bucket = idx.get("food_images", {})
            latex_bucket = idx.get("latex", {})
            if isinstance(food_bucket, dict) and probe_name in food_bucket:
                category_flag = "--eat"
            elif isinstance(latex_bucket, dict) and probe_name in latex_bucket:
                category_flag = "--latex"


    # 结构化参数支持：添加课程
    structured_args_for_add_course = cmd_lower in {"添加课程", "新增课程", "add_course"}
    if structured_args_for_add_course and (not args.get("raw")):
        name = _clean_user_text(str(args.get("name", args.get("course_name", "")))).strip()
        teacher = _clean_user_text(str(args.get("teacher", ""))).strip()
        location = _clean_user_text(str(args.get("location", ""))).strip()
        day = args.get("day", args.get("weekday", ""))
        start_section = args.get("start_section", args.get("start", ""))
        end_section = args.get("end_section", args.get("end", ""))
        weeks = args.get("weeks", args.get("week_range", ""))

        if isinstance(weeks, list):
            weeks = ",".join(str(x).strip() for x in weeks if str(x).strip())

        if all(str(x).strip() for x in [name, teacher, location, day, start_section, end_section, weeks]):
            raw = f"{name}|{teacher}|{location}|{day}|{start_section}|{end_section}|{weeks}"
            return f"/{command} {raw}"
    # raw 优先：适合带空格/复杂参数
    raw = args.get("raw")
    if isinstance(raw, str) and raw.strip():
        raw_text = raw.strip()
        if category_flag and ("--eat" not in raw_text) and ("--latex" not in raw_text):
            raw_text = f"{category_flag} {raw_text}".strip()
        if at_prefix and "[CQ:at,qq=" not in raw_text:
            raw_text = f"{at_prefix}{raw_text}".strip()
        return f"/{command} {raw_text}".strip()

    argv = args.get("argv", [])
    parts = []
    if isinstance(argv, list):
        for x in argv:
            xs = _clean_user_text(str(x)).strip()
            if xs:
                parts.append(xs)

    # 允许结构化 filename 参数
    if not parts:
        filename = _clean_user_text(str(args.get("filename", ""))).strip()
        if filename:
            parts.append(filename)

    if category_flag and ("--eat" not in parts) and ("--latex" not in parts):
        parts.insert(0, category_flag)

    suffix = " ".join(parts).strip()
    if suffix:
        if at_prefix and "[CQ:at,qq=" not in suffix:
            suffix = f"{at_prefix}{suffix}".strip()
        return f"/{command} {suffix}"
    if at_prefix:
        return f"/{command} {at_prefix}".strip()
    return f"/{command}"


def _normalize_help_style_command(cmd: str) -> str:
    c = _clean_user_text(cmd).strip()
    if not c:
        return c

    # /删除课程 help  -> /help 删除课程
    m = re.match(r"^/([^\s]+)\s+(help|--help|帮助)$", c, flags=re.IGNORECASE)
    if m:
        topic = m.group(1)
        if topic not in {"help", "帮助"}:
            return f"/help {topic}"

    # /删除课程 ?  -> /help 删除课程
    m2 = re.match(r"^/([^\s]+)\s*\?$", c)
    if m2:
        topic = m2.group(1)
        if topic not in {"help", "帮助"}:
            return f"/help {topic}"

    return c


def _extract_plugin_topic_from_command(cmd: str) -> str:
    c = _clean_user_text(cmd).strip()
    if not c:
        return ""
    if not c.startswith("/"):
        c = "/" + c
    return c.split()[0].lstrip("/").strip()


async def _get_plugin_help_text(bot: Bot, event: GroupMessageEvent, topic: str) -> str:
    t = _clean_user_text(topic).strip().lstrip("/")
    if not t or t in {"help", "帮助"}:
        return ""

    if t in _PLUGIN_HELP_CACHE:
        return _PLUGIN_HELP_CACHE[t]

    try:
        msgs = await _dispatch_plugin_command(bot, event, f"/help {t}", capture_output=True)
        merged = _merge_captured_messages(msgs)
        txt = _message_to_plain_text(merged)
        txt = _clean_user_text(txt)
        if not txt:
            return ""

        # 无命中帮助时不缓存错误提示
        if "未找到命令" in txt and "可用关键词" in txt:
            return ""

        _PLUGIN_HELP_CACHE[t] = txt[:3000]
        return _PLUGIN_HELP_CACHE[t]
    except Exception:
        return ""


async def _execute_tool_call(tool_call: Dict[str, Any], bot: Bot, event: GroupMessageEvent, user_text: str = "") -> Tuple[Optional[Message], bool]:
    """
    返回 (msg, consumed)
    - consumed=True: 已处理（msg 可为 None，表示由插件命令自行发消息）
    - consumed=False: 未识别工具，回退普通文本
    """
    tool = str(tool_call.get("tool", "")).strip()
    args = tool_call.get("args", {})
    if not isinstance(args, dict):
        args = {}

    # 关系代词兜底：如“提醒你妈妈...”自动注入 target_user_id
    args = _inject_kinship_target_into_tool_call(tool, args, event, user_text)

    if tool == "plugin_call":
        command_name = normalize_plugin_command(str(args.get("command", "")))
        if command_name and (not is_supported_plugin_command(command_name)):
            return Message(f"不支持的插件命令：{command_name}"), True

        cmd = _build_plugin_call_command(args)
        if not cmd:
            return Message("plugin_call 缺少 command（或参数非法）。"), True
        try:
            topic = _extract_plugin_topic_from_command(cmd)
            help_text = await _get_plugin_help_text(bot, event, topic)

            msgs = await _dispatch_plugin_command(bot, event, cmd, capture_output=True)
            merged = _merge_captured_messages(msgs)
            if merged is None:
                return Message("插件已执行，但没有返回内容。"), True

            if help_text:
                txt = _message_to_plain_text(merged)
                if _looks_like_tool_error(txt):
                    merged = Message(f"{txt}\n\n【/{topic} 用法参考】\n{help_text[:1200]}")

            return merged, True
        except Exception as exc:
            return Message(f"插件命令执行失败：{exc}"), True

    if tool == "plugin_batch":
        cmds = _normalize_batch_commands(args)
        if not cmds:
            return Message("plugin_batch 缺少 commands。"), True

        lines: list[str] = [f"🛠️ 批量命令执行完成：{len(cmds)} 条"]

        for idx, cmd in enumerate(cmds, 1):
            try:
                topic = _extract_plugin_topic_from_command(cmd)
                help_text = await _get_plugin_help_text(bot, event, topic)

                msgs = await _dispatch_plugin_command(bot, event, cmd, capture_output=True)
                merged = _merge_captured_messages(msgs)

                if merged is None:
                    lines.append(f"⚠️ {idx}. {cmd}")
                    lines.append("   ↳ 无返回内容")
                    continue

                if _message_has_media(merged):
                    lines.append(f"✅ {idx}. {cmd}")
                    lines.append("   ↳ 返回媒体消息")
                    continue

                txt = _clean_user_text(_message_to_plain_text(merged))
                if help_text and _looks_like_tool_error(txt):
                    txt = f"{txt}\n\n【/{topic} 用法参考】\n{help_text[:600]}"

                if not txt:
                    lines.append(f"✅ {idx}. {cmd}")
                    lines.append("   ↳ 执行成功")
                    continue

                compact = txt.replace("\n", " / ").strip()
                if len(compact) > 220:
                    compact = compact[:220].rstrip() + "..."
                lines.append(f"✅ {idx}. {cmd}")
                lines.append(f"   ↳ {compact}")
            except Exception as exc:
                lines.append(f"❌ {idx}. {cmd}")
                lines.append(f"   ↳ 执行失败：{exc}")

        return Message("\n".join(lines)), True

    if tool == "plugin_command":
        cmd = _clean_user_text(str(args.get("command", "")))
        if not cmd:
            return Message("缺少 command 参数。"), True
        try:
            topic = _extract_plugin_topic_from_command(cmd)
            help_text = await _get_plugin_help_text(bot, event, topic)

            msgs = await _dispatch_plugin_command(bot, event, cmd, capture_output=True)
            merged = _merge_captured_messages(msgs)
            if merged is None:
                return Message("插件已执行，但没有返回内容。"), True

            if help_text:
                txt = _message_to_plain_text(merged)
                if _looks_like_tool_error(txt):
                    merged = Message(f"{txt}\n\n【/{topic} 用法参考】\n{help_text[:1200]}")

            return merged, True
        except Exception as exc:
            return Message(f"插件命令执行失败：{exc}"), True

    if tool == "weather_now":
        city = _clean_user_text(str(args.get("city", "")))
        if (not city) or (not _is_likely_city_name(city)):
            return Message("缺少或无效城市参数（city）。"), True
        rep = await _fetch_weather_reply(city)
        return Message(rep or f"我这次没查到 {city} 的天气。"), True

    if tool == "weather_schedule_daily":
        city = _clean_user_text(str(args.get("city", "")))
        try:
            hour = int(args.get("hour", 7))
            minute = int(args.get("minute", 0))
        except Exception:
            return Message("时间参数不合法，hour/minute 需要是数字。"), True

        if (not city) or (not _is_likely_city_name(city)):
            return Message("缺少或无效城市参数（city）。"), True
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return Message("时间参数超范围，hour 需 0-23，minute 需 0-59。"), True

        ok, msg = _upsert_daily_weather_job(bot, int(event.group_id), int(event.user_id), city, hour, minute)
        return Message(msg), True

    if tool == "weather_schedule_once":
        city = _clean_user_text(str(args.get("city", "")))
        date_str = _clean_user_text(str(args.get("date", "明天")))
        try:
            hour = int(args.get("hour", 7))
            minute = int(args.get("minute", 0))
        except Exception:
            return Message("时间参数不合法，hour/minute 需要是数字。"), True

        if (not city) or (not _is_likely_city_name(city)):
            return Message("缺少或无效城市参数（city）。"), True
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return Message("时间参数超范围，hour 需 0-23，minute 需 0-59。"), True

        now = datetime.now(SH_TZ) if SH_TZ else datetime.now()
        d = _parse_date_token(date_str, now)
        if d is None:
            return Message("date 参数格式不支持，可用：明天/后天/3天后/YYYY-MM-DD/MM-DD"), True

        run_dt = now.replace(year=d.year, month=d.month, day=d.day, hour=hour, minute=minute, second=0, microsecond=0)
        if run_dt <= now:
            return Message("这个时间已经过去了，请换一个未来时间。"), True

        ok, msg = _upsert_once_weather_job(bot, int(event.group_id), int(event.user_id), city, run_dt)
        return Message(msg), True

    if tool == "eat_random":
        list_name = str(args.get("list", "android")).strip().lower()
        if list_name not in {"android", "apple"}:
            list_name = "android"

        data = _load_json_dict(eat_data_file)
        arr = data.get(list_name, [])
        if not isinstance(arr, list) or not arr:
            return Message(f"[{list_name}] 列表是空的。"), True

        food = str(random.choice(arr)).strip()
        greeting = "上学辛苦了！" if list_name == "android" else "假期要好好休息哦！"
        text = f"{greeting}浅浅推荐你吃：{food}"

        img_url = _find_food_image_url(food)
        if img_url:
            return Message(text + "\n") + MessageSegment.image(file=img_url), True
        return Message(text + "（没有找到图片）"), True

    if tool == "eat_list":
        list_name = str(args.get("list", "android")).strip().lower()
        if list_name not in {"android", "apple"}:
            list_name = "android"
        data = _load_json_dict(eat_data_file)
        arr = data.get(list_name, [])
        if not isinstance(arr, list) or not arr:
            return Message(f"[{list_name}] 列表是空的。"), True
        lines = [f"[{list_name}] 共 {len(arr)} 项："] + [f"- {x}" for x in arr[:60]]
        if len(arr) > 60:
            lines.append("... 仅显示前 60 项")
        return Message("\n".join(lines)), True

    if tool == "pic_send":
        category = str(args.get("category", "pics")).strip() or "pics"
        filename = os.path.basename(str(args.get("filename", "")).strip())
        if not filename:
            return Message("缺少 filename 参数。"), True

        idx = _load_json_dict(pic_index_file)
        bucket = idx.get(category, {})
        if not isinstance(bucket, dict):
            return Message(f"分类不存在：{category}"), True

        entry = bucket.get(filename)
        url = _pic_entry_url(entry)
        if not url:
            return Message(f"未找到文件：{filename}"), True

        ext = Path(filename).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            return MessageSegment.image(file=url), True
        if ext in {".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm"}:
            return MessageSegment.video(file=url), True
        return Message(url), True

    return None, False


def _build_role_prompt(sender_role: str, sender_name: str) -> str:
    if sender_role == "dad":
        who = "当前发言人是爸爸，可称呼\"爸爸\"，但不必每句都叫。"
    elif sender_role == "mom":
        who = "当前发言人是妈妈，可称呼\"妈妈\"，但不必每句都叫。"
    else:
        who = f"当前发言人是群成员\"{sender_name}\"，用自然称呼，不要叫爸爸/妈妈。"

    return (
        f"{ROLEPLAY_BASE_PROMPT}\n"
        f"{who}\n"
        "不要误认他人身份；只基于当前发言人身份称呼。"
    )


async def _call_openclaw(prompt: str, session_id: str) -> Optional[str]:
    cmd = [
        "openclaw",
        "agent",
        "--agent",
        OPENCLAW_AGENT_ID,
        "--session-id",
        session_id,
        "--message",
        prompt,
        "--thinking",
        OPENCLAW_THINKING,
        "--json",
    ]

    env = os.environ.copy()
    desired_node_opt = f"--max-old-space-size={OPENCLAW_NODE_MAX_OLD_SPACE_MB}"
    if OPENCLAW_NODE_OPTIONS:
        env["NODE_OPTIONS"] = OPENCLAW_NODE_OPTIONS
    else:
        current_opts = str(env.get("NODE_OPTIONS", "") or "").strip()
        if desired_node_opt not in current_opts:
            env["NODE_OPTIONS"] = f"{current_opts} {desired_node_opt}".strip()

    if OPENCLAW_BRIDGE_USE_LOCAL:
        cmd.insert(2, "--local")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except Exception as e:
        logger.exception(f"openclaw subprocess start failed: {e}")
        return "启动 OpenClaw 命令失败，请检查环境。"

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=OPENCLAW_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        return "我这边有点慢，超时了，等下再试一次。"

    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="ignore").strip()
        err_l = err.lower()
        if ("heap out of memory" in err_l) or ("allocation failed" in err_l) or ("last few gcs" in err_l):
            logger.error("openclaw subprocess OOM: %s", err[:500])
            return (
                f"转 OpenClaw 失败：进程内存不足（Node OOM）。"
                f"已启用 NODE_OPTIONS=--max-old-space-size={OPENCLAW_NODE_MAX_OLD_SPACE_MB}，请重试。"
            )
        return f"转 OpenClaw 失败：{err[:180]}" if err else "转 OpenClaw 失败了，稍后再试。"

    out = stdout.decode("utf-8", errors="ignore").strip()
    if not out:
        return "OpenClaw 没返回内容。"

    json_text = out
    start = json_text.find("{")
    end = json_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_text = json_text[start:end + 1]

    try:
        payload = json.loads(json_text)
        payloads = []
        if isinstance(payload, dict):
            if isinstance(payload.get("payloads"), list):
                payloads = payload.get("payloads", [])
            elif isinstance(payload.get("result"), dict):
                payloads = payload.get("result", {}).get("payloads", []) or []

        texts = [item.get("text", "") for item in payloads if isinstance(item, dict) and item.get("text")]
        answer = "\n".join(texts).strip()
        return answer or "OpenClaw 没返回文本内容。"
    except Exception:
        return out[:500]


@bridge.handle()
async def handle_bridge(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        return

    raw_text = event.get_plaintext().strip()
    raw_msg = str(event.message)
    self_id = str(event.self_id)

    at_bot = _is_at_bot(event) or (f"qq={self_id}" in raw_msg) or bool(getattr(event, "to_me", False))
    if not at_bot and not (raw_text.startswith("浅浅ovo") or raw_text.startswith("浅浅")):
        return

    if str(event.user_id) == str(event.self_id):
        return

    user_text = _extract_text_without_at(event) if at_bot else raw_text
    user_text = _clean_user_text(user_text)
    if not user_text:
        user_text = _clean_user_text(raw_text)

    logger.info(
        f"openclaw_bridge trigger gid={event.group_id} uid={event.user_id} text={user_text[:120]!r}"
    )

    # 其余走模型理解（执行模式 + 文本模式）
    sender_role, sender_name = _resolve_sender_role(event)
    role_prompt = _build_role_prompt(sender_role, sender_name)
    plugin_catalog = render_plugin_catalog_for_prompt()

    session_id = _build_session_id(event)

    attachment_context = ""
    attachment_parts: list[str] = []

    image_urls: list[str] = []
    image_paths: list[str] = []
    if OPENCLAW_IMAGE_MODE:
        image_urls = _collect_event_image_urls(event)[:OPENCLAW_IMAGE_MAX_COUNT]
        if image_urls:
            dl_results = await asyncio.gather(
                *[_download_image_to_local(u) for u in image_urls],
                return_exceptions=True,
            )
            for r in dl_results:
                if isinstance(r, str) and r:
                    image_paths.append(r)
        _cleanup_old_bridge_images(current_paths=image_paths)
        img_ctx = _build_attachment_context(image_paths, image_urls)
        if img_ctx:
            attachment_parts.append(img_ctx)

    audio_entries: list[Dict[str, str]] = []
    audio_paths: list[str] = []
    if OPENCLAW_AUDIO_MODE:
        audio_entries = _collect_event_audio_entries(event)[:OPENCLAW_AUDIO_MAX_COUNT]
        if audio_entries:
            for item in audio_entries:
                p = await _resolve_record_to_local(bot, item)
                if p:
                    audio_paths.append(p)
            _cleanup_old_bridge_audio(current_paths=audio_paths)

            if audio_paths:
                audio_text, audio_lang, audio_prob = _transcribe_audio_to_text(audio_paths[0])
                if audio_text:
                    logger.info(
                        "openclaw_bridge asr ok gid=%s uid=%s lang=%s prob=%.3f text=%r",
                        event.group_id,
                        event.user_id,
                        audio_lang,
                        audio_prob,
                        audio_text[:120],
                    )
                    if user_text:
                        user_text = _clean_user_text(f"{user_text}\n\n语音补充：{audio_text}")
                    else:
                        user_text = audio_text

                    asr_ctx = f"用户还发送了语音，已转写如下：\n{audio_text[:1200]}"
                    if audio_lang:
                        asr_ctx += f"\n（识别语言: {audio_lang}）"
                    attachment_parts.append(asr_ctx)
                else:
                    logger.warning(
                        "openclaw_bridge asr empty gid=%s uid=%s path=%s",
                        event.group_id,
                        event.user_id,
                        audio_paths[0],
                    )

    if (not user_text) and image_paths:
        user_text = "请帮我阅读这张图片内容并提取关键信息。"

    attachment_context = "\n\n".join([p for p in attachment_parts if p]).strip()

    if not user_text:
        if audio_entries:
            await bot.send(event, "这条语音我没听清，能再发一次或者转成文字吗？")
        else:
            await bot.send(event, "在呢，你直接说需求就行～")
        await bridge.finish()
        return

    # 本地插件命令优先：像 /status /help /ping 这类已有命令，
    # 不应被 bridge 抢占，直接交给对应插件处理。
    if user_text.startswith("/"):
        slash_cmd = normalize_plugin_command(_clean_user_text(user_text).split()[0].lstrip("/"))
        if slash_cmd and is_supported_plugin_command(slash_cmd):
            logger.info(
                f"openclaw_bridge skip local plugin command gid={event.group_id} uid={event.user_id} cmd={slash_cmd}"
            )
            return

    if _is_current_time_query(user_text):
        now = datetime.now(SH_TZ) if SH_TZ else datetime.utcnow()
        await bot.send(event, f"现在是 {now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间）")
        await bridge.finish()
        return

    current_prompt = _build_exec_prompt(role_prompt, user_text, attachment_context=attachment_context, plugin_catalog=plugin_catalog)
    reply = ""
    last_tool_text = ""
    last_tool_name = ""
    last_tool_args: Dict[str, Any] = {}
    execution_log: list[dict] = []
    native_network_traced = False

    for round_idx in range(OPENCLAW_TOOL_MAX_ROUNDS):
        model_reply = await _call_openclaw(current_prompt, session_id)
        model_reply = _strip_markdown(model_reply or "我这边没拿到结果，稍后再试。")

        tool_call = _parse_tool_call(model_reply)
        if not tool_call:
            clean_reply, native_net_used = _strip_native_network_marker(model_reply)
            if native_net_used and OPENCLAW_TOOL_TRACE and (not native_network_traced):
                await bot.send(event, "🌐 已执行联网查询")
                native_network_traced = True
            model_reply = clean_reply or model_reply

            if execution_log and _looks_like_incomplete_progress_reply(model_reply) and (round_idx < OPENCLAW_TOOL_MAX_ROUNDS - 1):
                current_prompt = _build_tool_followup_prompt(
                    role_prompt=role_prompt,
                    user_text=user_text,
                    execution_log=execution_log + [{"assistant": model_reply}],
                    round_idx=round_idx + 1,
                    max_rounds=OPENCLAW_TOOL_MAX_ROUNDS,
                    attachment_context=attachment_context,
                    plugin_catalog=plugin_catalog,
                )
                continue
            reply = model_reply
            break

        tname = str(tool_call.get("tool", ""))
        targs = tool_call.get("args", {}) if isinstance(tool_call.get("args", {}), dict) else {}

        pre_trace: Optional[str] = None
        if OPENCLAW_TOOL_TRACE and tname in {"plugin_command", "plugin_call"}:
            pre_trace = _build_trace_text(tname, targs)

        # 对插件命令，先回显再执行，保证顺序在前
        if pre_trace:
            await bot.send(event, pre_trace)

        tool_msg, consumed = await _execute_tool_call(tool_call, bot, event, user_text=user_text)
        if not consumed:
            reply = model_reply
            break

        logger.info(
            f"openclaw_bridge tool executed gid={event.group_id} tool={tool_call.get('tool')} round={round_idx + 1}"
        )

        # 非 plugin_call/plugin_command 的工具也要显式回显执行情况
        if OPENCLAW_TOOL_TRACE and (not pre_trace):
            await bot.send(event, _build_trace_text(tname, targs))

        if tool_msg is None:
            execution_log.append({"tool": tool_call, "result": "(no output)"})
            if round_idx < OPENCLAW_TOOL_MAX_ROUNDS - 1:
                current_prompt = _build_tool_followup_prompt(
                    role_prompt=role_prompt,
                    user_text=user_text,
                    execution_log=execution_log,
                    round_idx=round_idx + 1,
                    max_rounds=OPENCLAW_TOOL_MAX_ROUNDS,
                    attachment_context=attachment_context,
                    plugin_catalog=plugin_catalog,
                )
                continue
            reply = "任务已执行，但没有返回可展示内容。"
            break

        tool_text = _message_to_plain_text(tool_msg)
        last_tool_text = tool_text or last_tool_text
        last_tool_name = tname
        last_tool_args = targs
        execution_log.append({
            "tool": tool_call,
            "result": (tool_text[:1200] if tool_text else "(media/non-text)"),
        })

        # 失败时进入下一轮，让 OpenClaw 自主调整参数/换工具
        if _looks_like_tool_error(tool_text) and (round_idx < OPENCLAW_TOOL_MAX_ROUNDS - 1):
            current_prompt = _build_tool_retry_prompt(
                role_prompt=role_prompt,
                user_text=user_text,
                previous_tool_call=tool_call,
                tool_result_text=tool_text,
                round_idx=round_idx + 1,
                max_rounds=OPENCLAW_TOOL_MAX_ROUNDS,
                attachment_context=attachment_context,
                plugin_catalog=plugin_catalog,
            )
            continue

        # 媒体结果直接发送，避免重写破坏
        if _message_has_media(tool_msg):
            await bot.send(event, tool_msg)
            await bridge.finish()
            return

        # 非媒体结果：单步请求优先快返回，减少额外一轮模型调用
        if round_idx < OPENCLAW_TOOL_MAX_ROUNDS - 1:
            if OPENCLAW_FAST_SINGLE_STEP and (not _looks_like_multi_step_request(user_text)):
                if last_tool_name in {"plugin_call", "plugin_command", "plugin_batch"} and last_tool_text:
                    plugin_cmd = (
                        _build_plugin_call_command(last_tool_args)
                        if last_tool_name == "plugin_call"
                        else _clean_user_text(str(last_tool_args.get("command", "")))
                    )
                    rewritten = await _rewrite_plugin_output(
                        role_prompt=role_prompt,
                        user_text=user_text,
                        plugin_command=plugin_cmd or "(unknown)",
                        plugin_output_text=last_tool_text,
                        session_id=session_id,
                    )
                    reply = rewritten or last_tool_text
                    break
                if last_tool_text:
                    reply = last_tool_text
                    break

            current_prompt = _build_tool_followup_prompt(
                role_prompt=role_prompt,
                user_text=user_text,
                execution_log=execution_log,
                round_idx=round_idx + 1,
                max_rounds=OPENCLAW_TOOL_MAX_ROUNDS,
                attachment_context=attachment_context,
                plugin_catalog=plugin_catalog,
            )
            continue

        # 达到最大轮次：尝试重写最后一次插件结果
        if last_tool_name in {"plugin_call", "plugin_command"} and last_tool_text:
            plugin_cmd = (
                _build_plugin_call_command(last_tool_args)
                if last_tool_name == "plugin_call"
                else _clean_user_text(str(last_tool_args.get("command", "")))
            )
            rewritten = await _rewrite_plugin_output(
                role_prompt=role_prompt,
                user_text=user_text,
                plugin_command=plugin_cmd or "(unknown)",
                plugin_output_text=last_tool_text,
                session_id=session_id,
            )
            if rewritten:
                reply = rewritten
            else:
                reply = last_tool_text or "我这边没拿到结果，稍后再试。"
        else:
            reply = last_tool_text or "我这边没拿到结果，稍后再试。"
        break
    else:
        # 达到最大轮次仍未产出文本回复时，退回最后一条工具结果
        if last_tool_name in {"plugin_call", "plugin_command"} and last_tool_text:
            plugin_cmd = (
                _build_plugin_call_command(last_tool_args)
                if last_tool_name == "plugin_call"
                else _clean_user_text(str(last_tool_args.get("command", "")))
            )
            rewritten = await _rewrite_plugin_output(
                role_prompt=role_prompt,
                user_text=user_text,
                plugin_command=plugin_cmd or "(unknown)",
                plugin_output_text=last_tool_text,
                session_id=session_id,
            )
            reply = rewritten or last_tool_text or "我这边没拿到结果，稍后再试。"
        else:
            reply = last_tool_text or "我这边没拿到结果，稍后再试。"

    if not reply:
        if last_tool_name in {"plugin_call", "plugin_command"} and last_tool_text:
            plugin_cmd = (
                _build_plugin_call_command(last_tool_args)
                if last_tool_name == "plugin_call"
                else _clean_user_text(str(last_tool_args.get("command", "")))
            )
            rewritten = await _rewrite_plugin_output(
                role_prompt=role_prompt,
                user_text=user_text,
                plugin_command=plugin_cmd or "(unknown)",
                plugin_output_text=last_tool_text,
                session_id=session_id,
            )
            reply = rewritten or last_tool_text or "我这边没拿到结果，稍后再试。"
        else:
            reply = last_tool_text or "我这边没拿到结果，稍后再试。"
    # 先做最多两次“反占位”重试：避免“我这就去整理/稍等”后没下文
    if _is_placeholder_reply(reply):
        for _ in range(2):
            retry_prompt = _build_no_placeholder_prompt(role_prompt, user_text, reply)
            retry_reply = await _call_openclaw(retry_prompt, session_id)
            retry_reply = _strip_markdown(retry_reply or "")
            if retry_reply and (not _is_placeholder_reply(retry_reply)):
                reply = retry_reply
                break
            if retry_reply:
                reply = retry_reply

    reply = _rewrite_family_mentions_in_reply(event, user_text, reply)

    logger.info(f"openclaw_bridge reply gid={event.group_id} len={len(reply)} preview={reply[:80]!r}")

    try:
        await bot.send(event, _render_reply_message(reply))
    except Exception as e:
        logger.exception(f"openclaw_bridge send failed: {e}")

    await bridge.finish()


_load_weather_jobs()


driver = get_driver()


@driver.on_bot_connect
async def _on_bot_connect(bot: Bot):
    _restore_weather_jobs(bot)
