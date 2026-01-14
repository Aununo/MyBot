import hashlib
import os
import re
import time
import urllib.parse
from typing import Optional, Tuple

import httpx
from nonebot import on_message, logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message, MessageSegment


BILI_VIDEO_API = "https://api.bilibili.com/x/web-interface/view"
BILI_PLAY_API = "https://api.bilibili.com/x/player/playurl"
BILI_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
USER_AGENT = "Mozilla/5.0 (compatible; MyBot/1.0; +https://github.com)"

BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")
AV_RE = re.compile(r"(?i)(av\d+)")
URL_RE = re.compile(r"https?://[^\s]+")
SHORT_RE = re.compile(r"https?://(b23\.tv|bili2233\.cn)/[^\s]+", re.I)

BILI_SESSDATA = os.getenv("BILI_SESSDATA", "").strip()
BILI_BILI_JCT = os.getenv("BILI_BILI_JCT", "").strip()
BILI_DEDEUSERID = os.getenv("BILI_DEDEUSERID", "").strip()

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
    return durl[0].get("url")


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

    if play_url:
        nodes.append(
            {
                "type": "node",
                "data": {
                    "uin": str(bot.self_id),
                    "content": play_url,
                },
            }
        )

    fallback_lines = [header_text, "", desc_text]
    if play_url:
        fallback_lines.append(play_url)
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
        return

    if plain.startswith("/") or plain.startswith("!") or plain.startswith("！"):
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        bvid, aid, video_url = await extract_bili_id(client, plain)
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
