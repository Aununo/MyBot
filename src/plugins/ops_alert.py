from __future__ import annotations

import asyncio
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Optional

from shlex import split as shlex_split

import psutil
from nonebot import get_driver, logger, on_command, require
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg

from ._data_paths import resolve_data_dir

try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
except Exception:
    scheduler = None


HOSTNAME = socket.gethostname()
DATA_DIR = resolve_data_dir()
STATE_FILE = DATA_DIR / "ops_alert_state.json"
WATCHDOG_EVENTS_FILE = Path(
    os.getenv("OPS_ALERT_WATCHDOG_EVENTS_FILE", str(DATA_DIR / "ops_watchdog_events.jsonl"))
)
WATCHDOG_MAINTENANCE_FILE = Path(os.getenv("OPS_ALERT_WATCHDOG_MAINTENANCE_FILE", "/home/ubuntu/watch_dog/maintenance.json"))

OPS_ALERT_ENABLED = os.getenv("OPS_ALERT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
OPS_ALERT_GROUP_ID = int(os.getenv("OPS_ALERT_GROUP_ID", "1063926539") or "1063926539")
OPS_ALERT_AT_USERS_RAW = os.getenv("OPS_ALERT_AT_USERS", "2921712841").strip()
OPS_ALERT_CHECK_INTERVAL_SECONDS = max(30, int(os.getenv("OPS_ALERT_CHECK_INTERVAL_SECONDS", "60") or "60"))
OPS_ALERT_OPENCLAW_CHECK_INTERVAL_SECONDS = max(
    OPS_ALERT_CHECK_INTERVAL_SECONDS,
    int(os.getenv("OPS_ALERT_OPENCLAW_CHECK_INTERVAL_SECONDS", "180") or "180"),
)
OPS_ALERT_CPU_THRESHOLD = float(os.getenv("OPS_ALERT_CPU_THRESHOLD", "95") or "95")
OPS_ALERT_MEMORY_THRESHOLD = float(os.getenv("OPS_ALERT_MEMORY_THRESHOLD", "90") or "90")
OPS_ALERT_DISK_THRESHOLD = float(os.getenv("OPS_ALERT_DISK_THRESHOLD", "90") or "90")
OPS_ALERT_CONSECUTIVE_FAILURES = max(1, int(os.getenv("OPS_ALERT_CONSECUTIVE_FAILURES", "2") or "2"))
OPS_ALERT_OPENCLAW_TIMEOUT_SECONDS = max(5, int(os.getenv("OPS_ALERT_OPENCLAW_TIMEOUT_SECONDS", "20") or "20"))

ops_cmd = on_command("ops", priority=1, block=True)

_active_bot: Optional[Bot] = None
_monitor_lock = asyncio.Lock()
_state_lock = asyncio.Lock()
_alert_state: dict[str, Any] = {
    "checks": {},
    "bot": {
        "connected": False,
        "last_connect_at": 0.0,
        "last_disconnect_at": 0.0,
        "last_disconnect_reason": "",
    },
    "meta": {
        "last_monitor_at": 0.0,
        "last_openclaw_check_at": 0.0,
    },
    "watchdog": {
        "events_offset": 0,
    },
}


psutil.cpu_percent(interval=None)


def _parse_user_ids(raw: str) -> list[int]:
    result: list[int] = []
    for chunk in (raw or "").replace(";", ",").split(","):
        text = chunk.strip()
        if not text:
            continue
        if not text.isdigit():
            continue
        value = int(text)
        if value not in result:
            result.append(value)
    return result


OPS_ALERT_AT_USERS = _parse_user_ids(OPS_ALERT_AT_USERS_RAW)
OPS_ADMIN_USERS = set(OPS_ALERT_AT_USERS)


def _default_check_state() -> dict[str, Any]:
    return {
        "active": False,
        "fail_count": 0,
        "last_problem": "",
        "last_change_at": 0.0,
        "last_fail_at": 0.0,
        "last_ok_at": 0.0,
    }


async def _load_state() -> None:
    global _alert_state
    async with _state_lock:
        if not STATE_FILE.exists():
            return
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"ops_alert 状态文件读取失败: {exc}")
            return
        if not isinstance(data, dict):
            return
        _alert_state["checks"] = data.get("checks") if isinstance(data.get("checks"), dict) else {}
        _alert_state["bot"] = data.get("bot") if isinstance(data.get("bot"), dict) else _alert_state["bot"]
        _alert_state["meta"] = data.get("meta") if isinstance(data.get("meta"), dict) else _alert_state["meta"]
        _alert_state["watchdog"] = data.get("watchdog") if isinstance(data.get("watchdog"), dict) else _alert_state["watchdog"]


async def _save_state() -> None:
    async with _state_lock:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(_alert_state, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run_command(args: list[str], timeout: int = OPS_ALERT_OPENCLAW_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"timeout after {timeout}s"

    return (
        proc.returncode,
        stdout.decode("utf-8", errors="replace").strip(),
        stderr.decode("utf-8", errors="replace").strip(),
    )


def _load_maintenance_state() -> dict[str, Any]:
    if not WATCHDOG_MAINTENANCE_FILE.exists():
        return {"components": {}}
    try:
        data = json.loads(WATCHDOG_MAINTENANCE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"ops_alert 维护模式文件读取失败: {exc}")
        return {"components": {}}
    if not isinstance(data, dict):
        return {"components": {}}
    if not isinstance(data.get("components"), dict):
        data["components"] = {}
    return data


def _save_maintenance_state(data: dict[str, Any]) -> None:
    WATCHDOG_MAINTENANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHDOG_MAINTENANCE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_maintenance_entry(component: str) -> dict[str, Any] | None:
    data = _load_maintenance_state()
    components = data.get("components") if isinstance(data.get("components"), dict) else {}
    entry = components.get(component)
    if not isinstance(entry, dict):
        return None
    expires_at = entry.get("expires_at")
    if expires_at is not None:
        try:
            if float(expires_at) <= time.time():
                components.pop(component, None)
                _save_maintenance_state(data)
                return None
        except Exception:
            components.pop(component, None)
            _save_maintenance_state(data)
            return None
    return entry


def _set_maintenance_entry(
    component: str,
    mode: str,
    *,
    reason: str,
    operator: str,
    ttl_seconds: int | None,
    extra: dict[str, Any] | None = None,
) -> None:
    data = _load_maintenance_state()
    components = data.setdefault("components", {})
    entry: dict[str, Any] = {
        "mode": mode,
        "reason": reason,
        "operator": operator,
        "updated_at": time.time(),
    }
    if extra:
        entry.update(extra)
    if ttl_seconds is not None:
        entry["expires_at"] = time.time() + max(1, ttl_seconds)
    components[component] = entry
    _save_maintenance_state(data)


def _clear_maintenance_entry(component: str) -> None:
    data = _load_maintenance_state()
    components = data.get("components") if isinstance(data.get("components"), dict) else {}
    if component in components:
        components.pop(component, None)
        _save_maintenance_state(data)


def _format_percent(value: float) -> str:
    return f"{value:.0f}%"


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}秒"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}分{sec}秒"
    hours, minute = divmod(minutes, 60)
    return f"{hours}小时{minute}分"


def _build_alert_message(body: str) -> Message:
    message = Message()
    for user_id in OPS_ALERT_AT_USERS:
        message += MessageSegment.at(user_id)
    if OPS_ALERT_AT_USERS:
        message += Message("\n")
    message += Message(body)
    return message


async def _send_alert(body: str) -> bool:
    if not OPS_ALERT_ENABLED:
        logger.info(f"ops_alert 已禁用，跳过发送: {body}")
        return False
    if _active_bot is None:
        logger.warning(f"ops_alert 没有可用 bot，无法发送告警: {body}")
        return False
    try:
        await _active_bot.send_group_msg(group_id=OPS_ALERT_GROUP_ID, message=_build_alert_message(body))
        logger.info(f"ops_alert 已发送到群 {OPS_ALERT_GROUP_ID}: {body}")
        return True
    except Exception as exc:
        logger.exception(f"ops_alert 发送失败: {exc}")
        return False


async def _update_check_state(key: str, ok: bool, problem: str, recovery: str) -> Optional[str]:
    checks = _alert_state.setdefault("checks", {})
    state = checks.get(key)
    if not isinstance(state, dict):
        state = _default_check_state()
        checks[key] = state

    now = time.time()
    changed = False
    outbound: Optional[str] = None

    if ok:
        was_active = bool(state.get("active"))
        if was_active:
            outbound = recovery
        if was_active or int(state.get("fail_count", 0)) != 0 or state.get("last_problem"):
            changed = True
        state.update(
            {
                "active": False,
                "fail_count": 0,
                "last_problem": "",
                "last_ok_at": now,
                "last_change_at": now if was_active else state.get("last_change_at", 0.0),
            }
        )
    else:
        fail_count = int(state.get("fail_count", 0)) + 1
        was_active = bool(state.get("active"))
        changed = changed or fail_count != int(state.get("fail_count", 0)) or problem != state.get("last_problem", "")
        state.update(
            {
                "fail_count": fail_count,
                "last_problem": problem,
                "last_fail_at": now,
            }
        )
        if (not was_active) and fail_count >= OPS_ALERT_CONSECUTIVE_FAILURES:
            state["active"] = True
            state["last_change_at"] = now
            outbound = problem
            changed = True

    if changed:
        await _save_state()
    return outbound


async def _check_server_metrics() -> list[str]:
    alerts: list[str] = []

    cpu_percent = float(await asyncio.to_thread(psutil.cpu_percent, 0.3))
    mem_percent = float(psutil.virtual_memory().percent)
    disk_percent = float(psutil.disk_usage("/").percent)

    msg = await _update_check_state(
        "server.cpu",
        cpu_percent < OPS_ALERT_CPU_THRESHOLD,
        f"【运维告警 / 服务器 CPU】{HOSTNAME} CPU 连续 {OPS_ALERT_CONSECUTIVE_FAILURES} 次高于阈值，当前 {_format_percent(cpu_percent)}，阈值 {_format_percent(OPS_ALERT_CPU_THRESHOLD)}。",
        f"【运维恢复 / 服务器 CPU】{HOSTNAME} CPU 已恢复正常，当前 {_format_percent(cpu_percent)}。",
    )
    if msg:
        alerts.append(msg)

    msg = await _update_check_state(
        "server.memory",
        mem_percent < OPS_ALERT_MEMORY_THRESHOLD,
        f"【运维告警 / 服务器内存】{HOSTNAME} 内存连续 {OPS_ALERT_CONSECUTIVE_FAILURES} 次高于阈值，当前 {_format_percent(mem_percent)}，阈值 {_format_percent(OPS_ALERT_MEMORY_THRESHOLD)}。",
        f"【运维恢复 / 服务器内存】{HOSTNAME} 内存已恢复正常，当前 {_format_percent(mem_percent)}。",
    )
    if msg:
        alerts.append(msg)

    msg = await _update_check_state(
        "server.disk_root",
        disk_percent < OPS_ALERT_DISK_THRESHOLD,
        f"【运维告警 / 磁盘】{HOSTNAME} 根分区使用率连续 {OPS_ALERT_CONSECUTIVE_FAILURES} 次高于阈值，当前 {_format_percent(disk_percent)}，阈值 {_format_percent(OPS_ALERT_DISK_THRESHOLD)}。",
        f"【运维恢复 / 磁盘】{HOSTNAME} 根分区使用率已恢复正常，当前 {_format_percent(disk_percent)}。",
    )
    if msg:
        alerts.append(msg)

    return alerts


async def _check_openclaw() -> list[str]:
    alerts: list[str] = []

    entry = _get_maintenance_entry("openclaw_gateway")
    if entry and str(entry.get("mode", "") or "").lower() == "disabled":
        await _update_check_state(
            "openclaw.status",
            True,
            "",
            "【运维恢复 / OpenClaw】OpenClaw Gateway 已退出维护停用状态。",
        )
        return alerts

    rc, stdout, stderr = await _run_command(["openclaw", "status", "--json"])
    if rc != 0:
        problem = f"【运维告警 / OpenClaw】openclaw status --json 执行失败，退出码 {rc}。{stderr or stdout or '无额外输出'}"
        msg = await _update_check_state(
            "openclaw.status",
            False,
            problem,
            "【运维恢复 / OpenClaw】openclaw status --json 已恢复正常。",
        )
        if msg:
            alerts.append(msg)
        return alerts

    try:
        payload = json.loads(stdout)
    except Exception as exc:
        msg = await _update_check_state(
            "openclaw.status",
            False,
            f"【运维告警 / OpenClaw】openclaw status --json 输出解析失败：{exc}",
            "【运维恢复 / OpenClaw】openclaw 状态输出已恢复正常。",
        )
        if msg:
            alerts.append(msg)
        return alerts

    gateway_service = payload.get("gatewayService") if isinstance(payload.get("gatewayService"), dict) else {}
    runtime_short = str(gateway_service.get("runtimeShort", "") or "")
    installed = bool(gateway_service.get("installed", False))
    ok = (not installed) or (("running" in runtime_short.lower()) and ("active" in runtime_short.lower()))
    detail = runtime_short or "未拿到 gatewayService.runtimeShort"

    msg = await _update_check_state(
        "openclaw.status",
        ok,
        f"【运维告警 / OpenClaw】{HOSTNAME} 上的 OpenClaw Gateway 状态异常：{detail}。",
        f"【运维恢复 / OpenClaw】{HOSTNAME} 上的 OpenClaw Gateway 已恢复正常：{detail}。",
    )
    if msg:
        alerts.append(msg)

    return alerts


async def _drain_watchdog_events() -> list[str]:
    watchdog_state = _alert_state.setdefault("watchdog", {})
    if not WATCHDOG_EVENTS_FILE.exists():
        return []

    try:
        file_size = WATCHDOG_EVENTS_FILE.stat().st_size
    except Exception:
        return []

    try:
        offset = int(watchdog_state.get("events_offset", 0) or 0)
    except Exception:
        offset = 0

    if offset < 0 or offset > file_size:
        offset = 0

    try:
        with WATCHDOG_EVENTS_FILE.open("r", encoding="utf-8") as f:
            f.seek(offset)
            lines = f.readlines()
            new_offset = f.tell()
    except Exception as exc:
        logger.warning(f"ops_alert 读取 watchdog 事件失败: {exc}")
        return []

    watchdog_state["events_offset"] = new_offset
    messages: list[str] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            logger.warning(f"ops_alert 跳过无法解析的 watchdog 事件: {raw[:120]}")
            continue
        if not isinstance(payload, dict):
            continue
        message = str(payload.get("message", "") or "").strip()
        if message:
            messages.append(message)
    return messages


async def _run_monitor_cycle(trigger: str = "scheduled") -> list[str]:
    async with _monitor_lock:
        _alert_state.setdefault("meta", {})["last_monitor_at"] = time.time()
        messages: list[str] = []

        messages.extend(await _check_server_metrics())

        last_openclaw_check_at = float(_alert_state.get("meta", {}).get("last_openclaw_check_at", 0.0) or 0.0)
        now = time.time()
        if trigger in {"startup", "manual"} or (now - last_openclaw_check_at >= OPS_ALERT_OPENCLAW_CHECK_INTERVAL_SECONDS):
            _alert_state["meta"]["last_openclaw_check_at"] = now
            messages.extend(await _check_openclaw())

        messages.extend(await _drain_watchdog_events())
        await _save_state()

    for item in messages:
        await _send_alert(item)
    return messages


def _is_admin_event(event: MessageEvent) -> bool:
    user_id = int(getattr(event, "user_id", 0) or 0)
    return user_id in OPS_ADMIN_USERS


async def _systemctl_show(unit: str) -> dict[str, str]:
    rc, stdout, stderr = await _run_command(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "--property=ActiveState,SubState,ExecMainPID,Result",
            "--no-pager",
        ],
        timeout=15,
    )
    if rc != 0:
        return {"ActiveState": "unknown", "SubState": "unknown", "ExecMainPID": "0", "Result": stderr or stdout or f"rc={rc}"}
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key] = value
    return result


def _describe_maintenance(component: str) -> str:
    entry = _get_maintenance_entry(component)
    if not entry:
        return "无"
    mode = str(entry.get("mode", "") or "")
    reason = str(entry.get("reason", "") or "")
    operator = str(entry.get("operator", "") or "")
    expires_at = entry.get("expires_at")
    ttl_text = "长期"
    if expires_at is not None:
        try:
            ttl_text = f"剩余 {_format_duration(float(expires_at) - time.time())}"
        except Exception:
            ttl_text = "剩余时间未知"
    details = ", ".join(part for part in [mode, reason, operator, ttl_text] if part)
    return details or "无"


async def _build_ops_status_text() -> str:
    mybot = await _systemctl_show("mybot.service")
    openclaw_rc, openclaw_stdout, openclaw_stderr = await _run_command(["openclaw", "gateway", "status"], timeout=20)
    openclaw_status = (openclaw_stdout or openclaw_stderr or f"rc={openclaw_rc}").strip().splitlines()
    openclaw_line = openclaw_status[0] if openclaw_status else f"rc={openclaw_rc}"
    control_lines = [
        "运维控制状态：",
        f"- mybot: {mybot.get('ActiveState', 'unknown')}/{mybot.get('SubState', 'unknown')} (pid {mybot.get('ExecMainPID', '0')})",
        f"- mybot 维护: {_describe_maintenance('mybot')}",
        f"- openclaw: {openclaw_line}",
        f"- openclaw 维护: {_describe_maintenance('openclaw_gateway')}",
    ]
    return "\n".join(control_lines + [""] + _build_status_text().splitlines())


async def _execute_ops_action(target: str, operator: str, event: MessageEvent | None = None) -> tuple[bool, str]:
    if target == "restart mybot":
        notify_user_id = int(getattr(event, "user_id", 0) or 0) if event is not None else 0
        message_type = str(getattr(event, "message_type", "") or "") if event is not None else ""
        group_id = int(getattr(event, "group_id", 0) or 0) if event is not None else 0
        _set_maintenance_entry(
            "mybot",
            "maintenance",
            reason="manual restart from bot command",
            operator=operator,
            ttl_seconds=120,
            extra={
                "notify_user_id": notify_user_id,
                "notify_group_id": group_id,
                "notify_message_type": message_type,
                "notify_message": "mybot 已成功重启。",
            },
        )
        rc, stdout, stderr = await _run_command(
            [
                "bash",
                "-lc",
                "sleep 1; systemctl --user restart mybot.service >/dev/null 2>&1 &",
            ],
            timeout=10,
        )
        if rc != 0:
            _clear_maintenance_entry("mybot")
            return False, f"重启 mybot 失败：{stderr or stdout or f'rc={rc}'}"
        return True, "已接受重启 mybot，预计 5~10 秒内恢复；watchdog 已静默此次计划内重启。"

    if target == "start openclaw":
        _clear_maintenance_entry("openclaw_gateway")
        rc, stdout, stderr = await _run_command(["openclaw", "gateway", "start"], timeout=60)
        if rc != 0:
            return False, f"启动 OpenClaw 失败：{stderr or stdout or f'rc={rc}'}"
        return True, f"OpenClaw 已启动。{stdout or stderr or ''}".strip()

    if target == "stop openclaw":
        _set_maintenance_entry("openclaw_gateway", "disabled", reason="stopped intentionally from bot command", operator=operator, ttl_seconds=None)
        rc, stdout, stderr = await _run_command(["openclaw", "gateway", "stop"], timeout=60)
        if rc != 0:
            _clear_maintenance_entry("openclaw_gateway")
            return False, f"停止 OpenClaw 失败：{stderr or stdout or f'rc={rc}'}"
        return True, f"OpenClaw 已停止；watchdog 将保持静默，直到你执行启动命令。{stdout or stderr or ''}".strip()

    return False, "不支持的操作。"


async def _ensure_monitor_job() -> None:
    if scheduler is None:
        logger.error("ops_alert 无法启动：nonebot_plugin_apscheduler 未就绪")
        return
    scheduler.add_job(
        _run_monitor_cycle,
        "interval",
        seconds=OPS_ALERT_CHECK_INTERVAL_SECONDS,
        id="ops_alert_monitor",
        kwargs={"trigger": "scheduled"},
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("ops_alert 监控任务已启动")


def _build_status_text() -> str:
    bot_state = _alert_state.get("bot", {}) if isinstance(_alert_state.get("bot"), dict) else {}
    checks = _alert_state.get("checks", {}) if isinstance(_alert_state.get("checks"), dict) else {}
    watchdog_state = _alert_state.get("watchdog", {}) if isinstance(_alert_state.get("watchdog"), dict) else {}
    active_keys = [key for key, value in checks.items() if isinstance(value, dict) and value.get("active")]
    lines = [
        "运维告警状态：",
        f"- 已启用: {'是' if OPS_ALERT_ENABLED else '否'}",
        f"- 告警群: {OPS_ALERT_GROUP_ID}",
        f"- 艾特对象: {', '.join(str(x) for x in OPS_ALERT_AT_USERS) if OPS_ALERT_AT_USERS else '未配置'}",
        f"- 巡检间隔: {OPS_ALERT_CHECK_INTERVAL_SECONDS}s",
        f"- OpenClaw 巡检间隔: {OPS_ALERT_OPENCLAW_CHECK_INTERVAL_SECONDS}s",
        f"- Bot 当前连接: {'是' if bot_state.get('connected') else '否'}",
        f"- 当前活跃告警: {len(active_keys)}",
        f"- 外部 Watchdog 事件偏移: {int(watchdog_state.get('events_offset', 0) or 0)}",
    ]
    for key in active_keys:
        info = checks.get(key, {})
        problem = str(info.get("last_problem", "") or "")
        if problem:
            lines.append(f"  - {key}: {problem}")
        else:
            lines.append(f"  - {key}")
    lines.append(f"- mybot 维护模式: {_describe_maintenance('mybot')}")
    lines.append(f"- openclaw 维护模式: {_describe_maintenance('openclaw_gateway')}")
    lines.append("- 说明: 外部 watchdog 会负责拉起进程；计划内重启/停用会通过维护模式静默。")
    return "\n".join(lines)


driver = get_driver()


@driver.on_startup
async def _opsalert_startup() -> None:
    await _load_state()
    await _ensure_monitor_job()
    logger.info("ops_alert 插件已加载")


@driver.on_bot_connect
async def _opsalert_on_connect(bot: Bot) -> None:
    global _active_bot
    _active_bot = bot

    bot_state = _alert_state.setdefault("bot", {})
    was_connected = bool(bot_state.get("connected", False))
    last_disconnect_at = float(bot_state.get("last_disconnect_at", 0.0) or 0.0)

    bot_state.update(
        {
            "connected": True,
            "last_connect_at": time.time(),
        }
    )
    await _save_state()

    mybot_maintenance = _get_maintenance_entry("mybot")
    if (not was_connected) and last_disconnect_at > 0:
        downtime = time.time() - last_disconnect_at
        if mybot_maintenance and str(mybot_maintenance.get("mode", "") or "").lower() == "maintenance":
            logger.info("ops_alert 检测到 mybot 计划内重启，跳过 QQ 机器人恢复通知")
            notify_user_id = int(mybot_maintenance.get("notify_user_id", 0) or 0)
            notify_group_id = int(mybot_maintenance.get("notify_group_id", 0) or 0)
            notify_message_type = str(mybot_maintenance.get("notify_message_type", "") or "").strip().lower()
            notify_message = str(mybot_maintenance.get("notify_message", "") or "").strip()
            if notify_message:
                try:
                    if notify_message_type == "group" and notify_group_id > 0:
                        await bot.send_group_msg(group_id=notify_group_id, message=notify_message)
                    elif notify_user_id > 0:
                        await bot.send_private_msg(user_id=notify_user_id, message=notify_message)
                except Exception as exc:
                    logger.warning(f"ops_alert 发送 mybot 重启完成通知失败: {exc}")
            _clear_maintenance_entry("mybot")
        else:
            await _send_alert(f"【运维恢复 / QQ机器人】QQ 机器人已恢复连接，最近一次断连持续约 {_format_duration(downtime)}。")

    await _run_monitor_cycle(trigger="startup")


@driver.on_bot_disconnect
async def _opsalert_on_disconnect(bot: Bot) -> None:
    bot_state = _alert_state.setdefault("bot", {})
    bot_state.update(
        {
            "connected": False,
            "last_disconnect_at": time.time(),
        }
    )
    await _save_state()
    logger.warning("ops_alert 检测到 QQ 机器人连接断开；如果外部 watchdog 将其拉起，恢复后会补发通知。")


@ops_cmd.handle()
async def _handle_ops(event: MessageEvent, args: Message = CommandArg()) -> None:
    action = " ".join(args.extract_plain_text().strip().lower().split())
    operator = str(getattr(event, "user_id", "unknown") or "unknown")

    if action in {"", "status"}:
        await ops_cmd.finish(await _build_ops_status_text())
        return

    if action == "test":
        ok = await _send_alert(f"【运维告警测试】{HOSTNAME} 的运维告警插件测试成功。")
        if ok:
            await ops_cmd.finish("测试告警已发到目标群。")
        await ops_cmd.finish("测试告警发送失败，去日志里看下具体错误。")
        return

    if action == "check":
        messages = await _run_monitor_cycle(trigger="manual")
        if messages:
            await ops_cmd.finish("已执行一次即时巡检，并把新告警/恢复通知发到目标群。")
        await ops_cmd.finish("已执行一次即时巡检，当前没有新的告警状态变化。")
        return

    if not _is_admin_event(event):
        await ops_cmd.finish("你没有这个命令的权限。")
        return

    if action == "restart mybot":
        await ops_cmd.send("收到，开始计划内重启 mybot，预计 5~10 秒内恢复。")
        ok, message = await _execute_ops_action(action, operator, event)
        await ops_cmd.finish(message)
        return

    if action in {"start openclaw", "stop openclaw"}:
        ok, message = await _execute_ops_action(action, operator)
        await ops_cmd.finish(message)
        return

    await ops_cmd.finish("支持的命令：/ops status、/ops check、/ops test、/ops restart mybot、/ops start openclaw、/ops stop openclaw")
