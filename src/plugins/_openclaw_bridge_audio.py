import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx


AUDIO_EXT_BY_CT = {
    "audio/ogg": ".ogg",
    "audio/opus": ".opus",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/amr": ".amr",
    "audio/aac": ".aac",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "application/ogg": ".ogg",
}


AUDIO_EXT_FALLBACKS = [".ogg", ".opus", ".mp3", ".wav", ".amr", ".aac", ".m4a"]


def extract_audio_entries_from_segments(segments: Any) -> list[Dict[str, str]]:
    out: list[Dict[str, str]] = []
    if not segments:
        return out

    for seg in segments:
        try:
            if getattr(seg, "type", "") != "record":
                continue
            data = getattr(seg, "data", {}) or {}
            file_raw = str(data.get("file", "") or "").strip()
            url_raw = str(data.get("url", "") or "").strip()
            if file_raw or url_raw:
                out.append({"file": file_raw, "url": url_raw})
        except Exception:
            continue

    dedup: list[Dict[str, str]] = []
    seen = set()
    for item in out:
        key = f"{item.get('file', '')}|{item.get('url', '')}"
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def collect_event_audio_entries(event: Any) -> list[Dict[str, str]]:
    entries = extract_audio_entries_from_segments(getattr(event, "message", None))

    rep = getattr(event, "reply", None)
    rep_msg = getattr(rep, "message", None) if rep is not None else None
    if rep_msg:
        entries.extend(extract_audio_entries_from_segments(rep_msg))

    dedup: list[Dict[str, str]] = []
    seen = set()
    for item in entries:
        key = f"{item.get('file', '')}|{item.get('url', '')}"
        if key in seen:
            continue
        seen.add(key)
        dedup.append(item)
    return dedup


def _guess_audio_ext(url: str, content_type: str) -> str:
    ct = (content_type or "").lower().split(";", 1)[0].strip()
    if ct in AUDIO_EXT_BY_CT:
        return AUDIO_EXT_BY_CT[ct]

    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = ""

    for ext in AUDIO_EXT_FALLBACKS:
        if path.endswith(ext):
            return ext
    return ".ogg"


async def download_audio_to_local(url: str, audio_dir: Path, max_bytes: int, logger) -> Optional[str]:
    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        return None

    audio_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(u)
            resp.raise_for_status()
            blob = resp.content
            if not blob:
                return None
            if len(blob) > max_bytes:
                logger.warning(f"audio too large: {len(blob)} bytes > {max_bytes}")
                return None

            ext = _guess_audio_ext(u, resp.headers.get("content-type", ""))
            digest = hashlib.md5(blob[:8192]).hexdigest()[:12]
            ts = int(datetime.utcnow().timestamp() * 1000)
            out = audio_dir / f"qq_audio_{ts}_{digest}{ext}"
            out.write_bytes(blob)
            return str(out)
    except Exception as exc:
        logger.warning(f"download audio failed: {exc}")
        return None


def cleanup_old_bridge_audio(audio_dir: Path, retention_seconds: int, current_paths: Optional[list[str]] = None) -> None:
    if not audio_dir.exists():
        return

    keep = set((current_paths or []))
    now_ts = int(datetime.utcnow().timestamp())

    for f in audio_dir.glob("qq_audio_*.*"):
        try:
            if str(f) in keep:
                continue
            age = now_ts - int(f.stat().st_mtime)
            if age >= retention_seconds:
                f.unlink(missing_ok=True)
        except Exception:
            continue
