from __future__ import annotations

import time

import psutil
from nonebot import on_command, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, NotifyEvent


status_cmd = on_command("status", priority=1, block=True)
status_poke = on_notice(priority=1, block=False)

_BOOT_TIME = psutil.boot_time()


def _format_runtime(seconds: float) -> str:
    seconds = max(0, seconds)
    hours = int(seconds // 3600)
    minutes = (seconds % 3600) / 60
    hour_label = "hour" if hours == 1 else "hours"
    return f"{hours} {hour_label} and {minutes:05.2f} minutes"


def _cpu_percent() -> float:
    return psutil.cpu_percent(interval=0.25)


def _format_percent(value: float) -> str:
    return f"{int(round(value)):02d}%"


def _build_status_text() -> str:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    sys_cpu = _cpu_percent()
    disk_lines: list[str] = []
    seen_mounts: set[str] = set()
    for part in psutil.disk_partitions(all=False):
        if part.mountpoint in seen_mounts:
            continue
        seen_mounts.add(part.mountpoint)
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        disk_lines.append(f"  {part.mountpoint}: {_format_percent(usage.percent)}")

    if not disk_lines:
        try:
            disk = psutil.disk_usage("/")
            disk_lines.append(f"  /: {_format_percent(disk.percent)}")
        except Exception:
            disk_lines.append("  /: --")

    lines = [
        f"CPU: {_format_percent(sys_cpu)}",
        f"Memory: {_format_percent(vm.percent)}",
        f"Runtime: {_format_runtime(time.time() - _BOOT_TIME)}",
        f"Swap: {_format_percent(swap.percent)}",
        "Disk:",
    ]
    lines.extend(disk_lines)
    return "\n".join(lines)


@status_cmd.handle()
async def handle_status(bot: Bot, event: MessageEvent):
    await status_cmd.finish(_build_status_text())


@status_poke.handle()
async def handle_poke(bot: Bot, event: NotifyEvent):
    if getattr(event, "sub_type", None) != "poke":
        return
    target_id = str(getattr(event, "target_id", ""))
    if target_id != str(bot.self_id):
        return
    await bot.send(event, _build_status_text())
