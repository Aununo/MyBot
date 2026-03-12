#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response, StreamingResponse

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BILI_PROXY_PORT = int(os.getenv("BILI_PROXY_PORT", "8091"))
BILI_PROXY_HOST = os.getenv("BILI_PROXY_HOST", "127.0.0.1")
UPSTREAM_REFERER = "https://www.bilibili.com"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

plugin_dir = BASE_DIR / "src" / "plugins"
proxy_file = plugin_dir / "bili_proxy.json"

app = FastAPI(title="MyBot Bilibili Proxy", version="2.0.0")


def sanitize_url(url: str) -> str:
    return (url or "").strip()


def load_proxy_cache() -> dict:
    if not proxy_file.exists():
        return {}
    try:
        return json.loads(proxy_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_proxy_cache(cache: dict) -> None:
    proxy_file.parent.mkdir(parents=True, exist_ok=True)
    proxy_file.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def cleanup_proxy_cache(cache: Optional[dict] = None) -> dict:
    now = int(time.time())
    current = cache if cache is not None else load_proxy_cache()
    cleaned = {
        key: value
        for key, value in current.items()
        if isinstance(value, dict) and value.get("expires_at", 0) > now and value.get("url")
    }
    if cleaned != current:
        save_proxy_cache(cleaned)
    return cleaned


def get_proxy_target(token: str) -> Optional[str]:
    cache = cleanup_proxy_cache()
    item = cache.get(token)
    if not isinstance(item, dict):
        return None
    return sanitize_url(str(item.get("url", "") or "")) or None


def build_upstream_headers(request: Request) -> dict:
    headers = {
        "Referer": UPSTREAM_REFERER,
        "User-Agent": DEFAULT_UA,
        "Accept": "*/*",
    }
    for key in ("range", "if-range", "accept-language"):
        value = request.headers.get(key)
        if value:
            headers[key] = value
    return headers


def pick_response_headers(headers: httpx.Headers) -> dict:
    allowed = {
        "content-type",
        "content-length",
        "content-range",
        "accept-ranges",
        "cache-control",
        "etag",
        "last-modified",
        "content-disposition",
    }
    out = {k: v for k, v in headers.items() if k.lower() in allowed}
    out.setdefault("Accept-Ranges", "bytes")
    return out


async def stream_upstream(resp: httpx.Response, client: httpx.AsyncClient) -> AsyncIterator[bytes]:
    try:
        async for chunk in resp.aiter_raw():
            yield chunk
    finally:
        await resp.aclose()
        await client.aclose()


async def proxy_media_request(request: Request, target: str):
    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(connect=15.0, read=None, write=30.0, pool=30.0),
    )
    upstream_req = client.build_request(request.method, target, headers=build_upstream_headers(request))
    upstream_resp = await client.send(upstream_req, stream=True)

    headers = pick_response_headers(upstream_resp.headers)
    media_type = upstream_resp.headers.get("content-type") or "video/mp4"

    if request.method.upper() == "HEAD":
        await upstream_resp.aclose()
        await client.aclose()
        return Response(status_code=upstream_resp.status_code, headers=headers, media_type=media_type)

    return StreamingResponse(
        stream_upstream(upstream_resp, client),
        status_code=upstream_resp.status_code,
        headers=headers,
        media_type=media_type,
    )


@app.get("/health")
async def health():
    cache = cleanup_proxy_cache()
    return JSONResponse(
        {
            "ok": True,
            "host": BILI_PROXY_HOST,
            "port": BILI_PROXY_PORT,
            "cache_file": str(proxy_file),
            "active_tokens": len(cache),
        }
    )


@app.get("/bili/proxy/{token}")
async def legacy_proxy_redirect(token: str):
    return RedirectResponse(url=f"/bili/play/{token}.mp4", status_code=307)


@app.api_route("/bili/play/{token}.mp4", methods=["GET", "HEAD"])
async def bili_play_proxy(token: str, request: Request):
    target = get_proxy_target(token)
    if not target:
        raise HTTPException(status_code=404, detail="proxy token not found or expired")
    return await proxy_media_request(request, target)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=BILI_PROXY_HOST, port=BILI_PROXY_PORT)
