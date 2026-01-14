import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple
import html

import httpx
from nonebot import on_message, logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message, MessageSegment


BILI_VIDEO_API = "https://api.bilibili.com/x/web-interface/view"
BILI_PLAY_API = "https://api.bilibili.com/x/player/playurl"
BILI_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
BILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"
BILI_TICKET_API = "https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket"
USER_AGENT = "Mozilla/5.0 (compatible; MyBot/1.0; +https://github.com)"

BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
AV_RE = re.compile(r"(?i)(av\d+)")
URL_RE = re.compile(r"https?://[^\s]+")
SHORT_RE = re.compile(r"https?://(b23\.tv|bili2233\.cn)/[^\s]+", re.I)
DESC_RE = re.compile(r'"desc":"([^"]+)"')
TITLE_RE = re.compile(r'"title":"([^"]+)"')
PROMPT_RE = re.compile(r'"prompt":"([^"]+)"')

BILI_SESSDATA = os.getenv("BILI_SESSDATA", "").strip()
BILI_BILI_JCT = os.getenv("BILI_BILI_JCT", "").strip()
BILI_DEDEUSERID = os.getenv("BILI_DEDEUSERID", "").strip()
BILI_PROXY_BASE_URL = os.getenv("BILI_PROXY_BASE_URL", "").strip().rstrip("/")
BILI_PROXY_TTL = int(os.getenv("BILI_PROXY_TTL", "3600"))

WBI_MIXIN_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32,
    15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19,
    29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63,
    57, 62, 11, 36, 20, 34, 44, 52,
]

_wbi_mixin_key: Optional[str] = None
_wbi_key_ts: float = 0.0
WBI_KEY_TTL = 6 * 60 * 60

plugin_dir = Path(__file__).parent
data_dir = Path("/app/data")
if not data_dir.exists():
    data_dir = plugin_dir
proxy_file = data_dir / "bili_proxy.json"


def format_count(value: Optional[int]) -> str:
    if value is None:
        return "0"
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿".rstrip("0").rstrip(".")
    if value >= 10_000:
        return f"{value / 10_000:.1f}万".rstrip("0").rstrip(".")
    return str(value)


def normalize_description(desc: str, limit: int = 120) -> str:
    desc = (desc or "").strip()
    if not desc:
        return "暂无简介"
    if len(desc) > limit:
        return desc[:limit].rstrip() + "..."
    return desc


def build_cookie_dict() -> dict:
    cookies = {}
    if BILI_SESSDATA:
        cookies["SESSDATA"] = BILI_SESSDATA
    if BILI_BILI_JCT:
        cookies["bili_jct"] = BILI_BILI_JCT
    if BILI_DEDEUSERID:
        cookies["DedeUserID"] = BILI_DEDEUSERID
    return cookies


def build_headers() -> dict:
    return {"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com"}


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


def store_proxy_link(play_url: str) -> Optional[str]:
    if not BILI_PROXY_BASE_URL:
        return None
    now = int(time.time())
    cache = load_proxy_cache()
    # 清理过期
    cache = {
        key: value
        for key, value in cache.items()
        if isinstance(value, dict) and value.get("expires_at", 0) > now
    }
    token = secrets.token_urlsafe(12)
    cache[token] = {
        "url": play_url,
        "expires_at": now + BILI_PROXY_TTL,
    }
    save_proxy_cache(cache)
    return f"{BILI_PROXY_BASE_URL}/bili/proxy/{token}"


def mixin_key(img_key: str, sub_key: str) -> str:
    full_key = img_key + sub_key
    mixed = "".join(full_key[i] for i in WBI_MIXIN_TAB)
    return mixed[:32]


def build_wbi_params(params: dict, mixin_key_value: str) -> dict:
    safe_params = {}
    for key, value in params.items():
        if value is None:
            continue
        cleaned = re.sub(r"[!'()*]", "", str(value))
        safe_params[key] = cleaned

    safe_params["wts"] = int(time.time())
    query = urllib.parse.urlencode(sorted(safe_params.items()))
    w_rid = hashlib.md5((query + mixin_key_value).encode("utf-8")).hexdigest()
    safe_params["w_rid"] = w_rid
    return safe_params


async def get_wbi_mixin_key(client: httpx.AsyncClient) -> Optional[str]:
    global _wbi_mixin_key, _wbi_key_ts
    now = time.time()
    if _wbi_mixin_key and (now - _wbi_key_ts) < WBI_KEY_TTL:
        return _wbi_mixin_key

    cookies = build_cookie_dict()
    if not cookies:
        return None

    try:
        resp = await client.get(BILI_NAV_API, headers=build_headers(), cookies=cookies, timeout=10.0)
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(f"获取 B 站 WBI Key 失败: {exc}")
        return None
    except ValueError as exc:
        logger.warning(f"解析 B 站 WBI Key 失败: {exc}")
        return None

    if payload.get("code") != 0:
        logger.warning(f"B 站 WBI Key 接口返回错误: {payload.get('code')} {payload.get('message')}")
        return None

    wbi_img = payload.get("data", {}).get("wbi_img", {})
    img_url = wbi_img.get("img_url", "")
    sub_url = wbi_img.get("sub_url", "")
    if not img_url or not sub_url:
        return None

    img_key = img_url.rsplit("/", 1)[-1].split(".", 1)[0]
    sub_key = sub_url.rsplit("/", 1)[-1].split(".", 1)[0]
    _wbi_mixin_key = mixin_key(img_key, sub_key)
    _wbi_key_ts = now
    return _wbi_mixin_key


async def resolve_short_url(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        return str(resp.url)
    except httpx.HTTPError as exc:
        logger.warning(f"解析 B 站短链接失败: {exc}")
        return url


async def extract_bili_id(client: httpx.AsyncClient, text: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    bvid_match = BV_RE.search(text)
    if bvid_match:
        bvid = bvid_match.group(1)
        return bvid, None, f"https://www.bilibili.com/video/{bvid}"

    av_match = AV_RE.search(text)
    if av_match:
        aid = int(av_match.group(1).lower().replace("av", ""))
        return None, aid, f"https://www.bilibili.com/video/av{aid}"

    urls = URL_RE.findall(text)
    for url in urls:
        if "bilibili.com" in url or SHORT_RE.match(url):
            final_url = url
            if SHORT_RE.match(url):
                final_url = await resolve_short_url(client, url)
            bvid_match = BV_RE.search(final_url)
            if bvid_match:
                bvid = bvid_match.group(1)
                return bvid, None, f"https://www.bilibili.com/video/{bvid}"
            av_match = AV_RE.search(final_url)
            if av_match:
                aid = int(av_match.group(1).lower().replace("av", ""))
                return None, aid, f"https://www.bilibili.com/video/av{aid}"

    return None, None, None


def sanitize_url(url: str) -> str:
    if not url:
        return url
    url = url.strip()
    url = html.unescape(url)
    url = url.replace("\\u0026", "&").replace("\\u003d", "=").replace("\\/", "/")
    return url


def normalize_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        return ""
    title = title.replace("[QQ小程序]", "").strip()
    title = title.replace("哔哩哔哩", "").strip()
    return title


def extract_title_from_raw_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    cleaned = html.unescape(raw_text)
    for regex in (DESC_RE, PROMPT_RE, TITLE_RE):
        match = regex.search(cleaned)
        if not match:
            continue
        title = normalize_title(match.group(1))
        if title and "哔哩" not in title:
            return title
    return ""


def extract_candidates_from_event(event: MessageEvent) -> Tuple[str, list, list]:
    raw_parts = []
    urls = []
    titles = []

    def record_text(value: str) -> None:
        if not value:
            return
        raw_parts.append(value)
        if "bilibili.com" in value or "b23.tv" in value or "bili2233.cn" in value:
            urls.append(value)

    def walk_json(obj) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    walk_json(value)
                elif isinstance(value, str):
                    record_text(value)
                    lower_key = key.lower()
                    if lower_key in {"desc", "title", "prompt", "summary", "name"}:
                        titles.append(value)
                    if lower_key in {"url", "jumpurl", "jump_url", "targeturl", "qqdocurl", "preview"}:
                        urls.append(value)
        elif isinstance(obj, list):
            for item in obj:
                walk_json(item)

    for seg in event.message:
        if seg.type == "text":
            record_text(seg.data.get("text", ""))
        elif seg.type == "json":
            data = seg.data.get("data", "")
            record_text(data)
            try:
                payload = json.loads(data)
                walk_json(payload)
            except Exception:
                continue
        elif seg.type == "xml":
            data = seg.data.get("data", "")
            record_text(data)
            xml_text = html.unescape(data)
            for url in URL_RE.findall(xml_text):
                urls.append(url)
            title_match = DESC_RE.search(xml_text) or TITLE_RE.search(xml_text)
            if title_match:
                titles.append(title_match.group(1))

    urls = [sanitize_url(u) for u in urls if u]
    titles = [normalize_title(t) for t in titles if t]
    raw_text = "\n".join(raw_parts)
    return raw_text, urls, titles


def hmac_sha256(key: str, message: str) -> str:
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


async def get_bili_ticket(client: httpx.AsyncClient) -> Optional[str]:
    ts = int(time.time())
    hexsign = hmac_sha256("XgwSnGZ1p", f"ts{ts}")
    params = {
        "key_id": "ec02",
        "hexsign": hexsign,
        "context[ts]": str(ts),
        "csrf": "",
    }
    try:
        resp = await client.post(BILI_TICKET_API, params=params, headers=build_headers(), timeout=10.0)
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(f"获取 B 站 ticket 失败: {exc}")
        return None
    except ValueError as exc:
        logger.warning(f"解析 B 站 ticket 失败: {exc}")
        return None

    if payload.get("code") != 0:
        logger.info(f"B 站 ticket 接口返回错误: {payload.get('code')} {payload.get('message')}")
        return None
    return payload.get("data", {}).get("ticket")


async def search_bili_by_title(client: httpx.AsyncClient, title: str) -> Optional[str]:
    mixin_key_value = await get_wbi_mixin_key(client)
    if not mixin_key_value:
        return None

    params = build_wbi_params({"keyword": title}, mixin_key_value)
    cookies = build_cookie_dict()
    ticket = await get_bili_ticket(client)
    if ticket:
        cookies["bili_ticket"] = ticket

    try:
        resp = await client.get(BILI_SEARCH_API, params=params, headers=build_headers(), cookies=cookies, timeout=10.0)
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(f"搜索 B 站视频失败: {exc}")
        return None
    except ValueError as exc:
        logger.warning(f"解析 B 站搜索结果失败: {exc}")
        return None

    if payload.get("code") != 0:
        logger.info(f"B 站搜索接口返回错误: {payload.get('code')} {payload.get('message')}")
        return None

    for item in payload.get("data", {}).get("result", []):
        if item.get("result_type") != "video":
            continue
        data_list = item.get("data") or []
        if not data_list:
            continue
        return data_list[0].get("arcurl")
    return None


async def fetch_video_info(
    client: httpx.AsyncClient,
    bvid: Optional[str],
    aid: Optional[int],
) -> Optional[dict]:
    params = {"bvid": bvid} if bvid else {"aid": aid}
    headers = build_headers()
    cookies = build_cookie_dict()
    mixin_key_value = await get_wbi_mixin_key(client)
    if mixin_key_value:
        params = build_wbi_params(params, mixin_key_value)
    try:
        resp = await client.get(
            BILI_VIDEO_API, params=params, headers=headers, cookies=cookies, timeout=10.0
        )
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(f"获取 B 站视频信息失败: {exc}")
        return None
    except ValueError as exc:
        logger.warning(f"解析 B 站视频信息失败: {exc}")
        return None

    if payload.get("code") != 0:
        logger.warning(f"B 站视频接口返回错误: {payload.get('code')} {payload.get('message')}")
        return None
    return payload.get("data")


async def fetch_play_url(
    client: httpx.AsyncClient,
    bvid: str,
    cid: int,
) -> Optional[str]:
    params = {
        "bvid": bvid,
        "cid": cid,
        "qn": 16,
        "fnver": 0,
        "fnval": 1,
        "platform": "html5",
    }
    headers = {"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com"}
    cookies = build_cookie_dict()
    mixin_key_value = await get_wbi_mixin_key(client)
    if mixin_key_value:
        params = build_wbi_params(params, mixin_key_value)
    try:
        resp = await client.get(
            BILI_PLAY_API, params=params, headers=headers, cookies=cookies, timeout=10.0
        )
        payload = resp.json()
    except httpx.HTTPError as exc:
        logger.warning(f"获取 B 站播放链接失败: {exc}")
        return None
    except ValueError as exc:
        logger.warning(f"解析 B 站播放链接失败: {exc}")
        return None

    if payload.get("code") != 0:
        logger.info(f"B 站播放链接接口返回错误: {payload.get('code')} {payload.get('message')}")
        return None

    data = payload.get("data") or {}
    durl = data.get("durl") or []
    if not durl:
        return None
    return sanitize_url(durl[0].get("url"))


def build_forward_nodes(
    bot: Bot,
    info: dict,
    video_url: str,
    play_url: Optional[str],
) -> Tuple[list, str]:
    title = info.get("title", "")
    owner = info.get("owner", {}) or {}
    stat = info.get("stat", {}) or {}
    desc = normalize_description(info.get("desc", ""))

    header_lines = [
        f"标题: {title}",
        f"UP主: {owner.get('name', '未知')}",
        f"点赞: {format_count(stat.get('like'))}  投币: {format_count(stat.get('coin'))}",
        f"收藏: {format_count(stat.get('favorite'))}  转发: {format_count(stat.get('share'))}",
        f"观看: {format_count(stat.get('view'))}  弹幕: {format_count(stat.get('danmaku'))}",
    ]
    header_text = "\n".join(header_lines)

    cover_url = info.get("pic")
    nodes = [
        {
            "type": "node",
            "data": {
                "uin": str(bot.self_id),
                "content": header_text,
            },
        }
    ]

    if cover_url:
        nodes.append(
            {
                "type": "node",
                "data": {
                    "uin": str(bot.self_id),
                    "content": Message(MessageSegment.image(cover_url)),
                },
            }
        )

    desc_text = f"简介: {desc}\n{video_url}"
    nodes.append(
        {
            "type": "node",
            "data": {
                "uin": str(bot.self_id),
                "content": desc_text,
            },
        }
    )

    proxy_url = None
    if play_url:
        proxy_url = store_proxy_link(play_url)

    if proxy_url or play_url:
        nodes.append(
            {
                "type": "node",
                "data": {
                    "uin": str(bot.self_id),
                    "content": proxy_url or play_url,
                },
            }
        )

    fallback_lines = [header_text, "", desc_text]
    if proxy_url or play_url:
        fallback_lines.append(proxy_url or play_url)
    fallback_text = "\n".join(fallback_lines)

    return nodes, fallback_text


bilibili = on_message(priority=20, block=False)


@bilibili.handle()
async def handle_bilibili(bot: Bot, event: MessageEvent):
    if event.message_type != "group":
        return

    if event.user_id == int(bot.self_id):
        return

    plain = event.get_plaintext().strip()
    if not plain:
        plain = ""

    if plain.startswith("/") or plain.startswith("!") or plain.startswith("！"):
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        raw_text, urls, titles = extract_candidates_from_event(event)
        combined = "\n".join([plain, raw_text]).strip()
        bvid, aid, video_url = await extract_bili_id(client, combined)
        if not bvid and not aid:
            for url in urls:
                bvid, aid, video_url = await extract_bili_id(client, url)
                if bvid or aid:
                    break
        if not bvid and not aid:
            raw_title = extract_title_from_raw_text(raw_text)
            if raw_title:
                titles.insert(0, raw_title)
            for title in titles:
                if not title:
                    continue
                search_url = await search_bili_by_title(client, title)
                if search_url:
                    bvid, aid, video_url = await extract_bili_id(client, search_url)
                    if bvid or aid:
                        break
        if not bvid and not aid:
            return

        info = await fetch_video_info(client, bvid, aid)
        if not info:
            return

        resolved_bvid = info.get("bvid") or bvid
        resolved_cid = info.get("cid")
        play_url = None
        if resolved_bvid and resolved_cid:
            play_url = await fetch_play_url(client, resolved_bvid, resolved_cid)

        nodes, fallback_text = build_forward_nodes(bot, info, video_url, play_url)
        try:
            await bot.call_api("send_group_forward_msg", group_id=event.group_id, messages=nodes)
        except Exception as exc:
            logger.error(f"发送合并转发消息失败: {exc}")
            await bilibili.finish(fallback_text)
