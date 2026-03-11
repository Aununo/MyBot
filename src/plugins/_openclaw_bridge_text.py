import json
import re
from typing import Any, Dict, Optional, Tuple

from nonebot.adapters.onebot.v11 import Message, MessageSegment


def clean_user_text(text: str) -> str:
    t = text or ""
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t)
    t = re.sub(r"^\s*(浅浅ovo|浅浅)[:：,，\s]+", "", t, flags=re.I)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def strip_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", "").strip(), text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    t = (text or "").strip()
    if not t:
        return None

    m = re.search(r"\{[\s\S]*\}", t)
    if not m:
        return None

    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None

    if not isinstance(obj, dict):
        return None

    tool = obj.get("tool")
    args = obj.get("args", {})
    if not isinstance(tool, str) or not tool.strip() or not isinstance(args, dict):
        return None

    return {"tool": tool.strip(), "args": args}


def message_to_plain_text(msg: Optional[Message]) -> str:
    if msg is None:
        return ""
    try:
        if isinstance(msg, MessageSegment):
            if msg.type == "text":
                return str(msg.data.get("text", "")).strip()
            return ""
        if isinstance(msg, Message):
            return msg.extract_plain_text().strip()
        return str(msg).strip()
    except Exception:
        return str(msg).strip()


def coerce_to_message(payload: Any) -> Optional[Message]:
    if payload is None:
        return None
    try:
        if isinstance(payload, Message):
            return payload
        if isinstance(payload, MessageSegment):
            return Message(payload)
        if isinstance(payload, str):
            return Message(payload)
        if isinstance(payload, list):
            # OneBot array message
            return Message(payload)
        return Message(str(payload))
    except Exception:
        try:
            return Message(str(payload))
        except Exception:
            return None


def flatten_forward_nodes(nodes: Any) -> str:
    if not isinstance(nodes, list):
        return ""

    parts: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data", {}) if isinstance(node.get("data", {}), dict) else {}
        content = data.get("content", "")

        if isinstance(content, str):
            t = content.strip()
            if t:
                parts.append(t)
        elif isinstance(content, list):
            # onebot array message
            seg_texts = []
            for seg in content:
                if isinstance(seg, dict):
                    st = str((seg.get("data") or {}).get("text", "")).strip()
                    if st:
                        seg_texts.append(st)
            if seg_texts:
                parts.append("".join(seg_texts))

    return "\n\n".join(parts).strip()


def merge_captured_messages(msgs: list[Message]) -> Optional[Message]:
    if not msgs:
        return None
    if len(msgs) == 1:
        return msgs[0]

    merged = Message()
    for i, m in enumerate(msgs[:8]):
        if i > 0:
            merged += Message("\n")
        merged += m
    return merged


def message_has_media(msg: Optional[Message]) -> bool:
    if msg is None:
        return False
    try:
        for seg in msg:
            if seg.type in {"image", "video", "record", "file", "music", "share", "json", "xml"}:
                return True
    except Exception:
        return False
    return False


def strip_native_network_marker(text: str) -> Tuple[str, bool]:
    t = (text or "").strip()
    if not t:
        return "", False

    used = False
    lines = t.splitlines()
    cleaned = []
    for i, ln in enumerate(lines):
        line = ln.strip()
        if i == 0 and line == "[NATIVE_NETWORK_USED]":
            used = True
            continue
        cleaned.append(ln)

    out = "\n".join(cleaned).strip()
    return out, used


def looks_like_incomplete_progress_reply(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False

    done_markers = ["全部完成", "都已完成", "已完成", "已经完成", "导入完成", "都加好了", "已全部导入", "处理完了"]
    if any(k in t for k in done_markers):
        return False

    progress_markers = ["继续", "接着", "往后", "后面", "下一条", "下一步", "我再", "我会继续", "正在", "处理中", "先把", "先加"]
    return any(k in t for k in progress_markers)
