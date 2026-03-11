import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx


def extract_image_urls_from_segments(segments) -> list[str]:
    urls: list[str] = []
    if not segments:
        return urls

    for seg in segments:
        try:
            if getattr(seg, "type", "") != "image":
                continue
            data = getattr(seg, "data", {}) or {}
            u = str(data.get("url", "") or "").strip()
            if u.startswith("http://") or u.startswith("https://"):
                urls.append(u)
        except Exception:
            continue

    # 去重保序
    out: list[str] = []
    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def collect_event_image_urls(event) -> list[str]:
    urls = extract_image_urls_from_segments(event.message)

    rep = getattr(event, "reply", None)
    rep_msg = getattr(rep, "message", None) if rep is not None else None
    if rep_msg:
        urls.extend(extract_image_urls_from_segments(rep_msg))

    # 去重保序
    out: list[str] = []
    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def guess_image_ext(url: str, content_type: str) -> str:
    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "png" in ct:
        return ".png"
    if "webp" in ct:
        return ".webp"
    if "gif" in ct:
        return ".gif"
    if "bmp" in ct:
        return ".bmp"

    try:
        path = urlparse(url).path.lower()
    except Exception:
        path = ""

    for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


async def download_image_to_local(url: str, image_dir: Path, max_bytes: int, logger) -> Optional[str]:
    u = (url or "").strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        return None

    image_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(u)
            resp.raise_for_status()
            blob = resp.content
            if not blob:
                return None
            if len(blob) > max_bytes:
                logger.warning(f"image too large: {len(blob)} bytes > {max_bytes}")
                return None

            ext = guess_image_ext(u, resp.headers.get("content-type", ""))
            digest = hashlib.md5(blob[:8192]).hexdigest()[:12]
            ts = int(datetime.utcnow().timestamp() * 1000)
            out = image_dir / f"qq_{ts}_{digest}{ext}"
            out.write_bytes(blob)
            return str(out)
    except Exception as exc:
        logger.warning(f"download image failed: {exc}")
        return None


def cleanup_old_bridge_images(image_dir: Path, retention_seconds: int, current_paths: Optional[list[str]] = None) -> None:
    if not image_dir.exists():
        return

    keep = set((current_paths or []))
    now_ts = int(datetime.utcnow().timestamp())

    for f in image_dir.glob("qq_*.*"):
        try:
            if str(f) in keep:
                continue
            age = now_ts - int(f.stat().st_mtime)
            if age >= retention_seconds:
                f.unlink(missing_ok=True)
        except Exception:
            continue


def build_attachment_context(local_paths: list[str], remote_urls: list[str], max_count: int) -> str:
    if not local_paths and not remote_urls:
        return ""

    lines = ["你收到了用户附带图片。"]
    if local_paths:
        lines.append("本地图片路径（优先使用 read 工具读取）：")
        for p in local_paths[:max_count]:
            lines.append(f"- {p}")
    if remote_urls:
        lines.append("原始图片 URL（可作为备用）：")
        for u in remote_urls[:max_count]:
            lines.append(f"- {u}")

    lines.append("若任务涉及识图/OCR/提取图中文字，请先读取图片再回答。")
    return "\n".join(lines)
