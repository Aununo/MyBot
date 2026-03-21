from __future__ import annotations

import time

import psutil
from nonebot import on_command, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, NotifyEvent


status_cmd = on_command("status", priority=1, block=True)
status_poke = on_notice(priority=1, block=False)

_BOOT_TIME = psutil.boot_time()
_CURRENT_PID = psutil.Process().pid
_PROCESS_LIMIT = 8


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


def _format_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    size = float(max(0, value))
    unit = units[0]
    for next_unit in units[1:]:
        if size < 1024:
            break
        size /= 1024
        unit = next_unit
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def _get_cached_bytes() -> int:
    vm = psutil.virtual_memory()
    cached = int(getattr(vm, "cached", 0) or 0)
    buffers = int(getattr(vm, "buffers", 0) or 0)
    return max(0, cached + buffers)


def _collect_process_memory_lines(limit: int = _PROCESS_LIMIT) -> list[str]:
    processes: list[tuple[int, int, str, float]] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "memory_info", "memory_percent"]):
        try:
            info = proc.info
            memory_info = info.get("memory_info")
            rss = int(getattr(memory_info, "rss", 0) or 0)
            if rss <= 0:
                continue
            pid = int(info.get("pid") or proc.pid)
            name = str(info.get("name") or proc.name() or "unknown")
            mem_percent = float(info.get("memory_percent") or proc.memory_percent())
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        processes.append((rss, pid, name, mem_percent))

    processes.sort(key=lambda item: item[0], reverse=True)
    lines: list[str] = []
    displayed_pids: set[int] = set()
    for rss, pid, name, mem_percent in processes[:limit]:
        marker = "*" if pid == _CURRENT_PID else "-"
        displayed_pids.add(pid)
        lines.append(
            f"  {marker} {name} (pid {pid}): {_format_bytes(rss)} ({_format_percent(mem_percent)})"
        )

    if _CURRENT_PID not in displayed_pids:
        try:
            current = psutil.Process(_CURRENT_PID)
            rss = current.memory_info().rss
            mem_percent = current.memory_percent()
            name = current.name()
            lines.insert(
                0,
                f"  * {name} (pid {_CURRENT_PID}): {_format_bytes(rss)} ({_format_percent(mem_percent)})",
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not lines:
        lines.append("  --")

    return lines


def _build_status_text() -> str:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    sys_cpu = _cpu_percent()
    cache_bytes = _get_cached_bytes()
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
        f"Memory: {_format_bytes(vm.used)} / {_format_bytes(vm.total)} ({_format_percent(vm.percent)})",
        f"Available: {_format_bytes(vm.available)}",
        f"Cache/Buffers: {_format_bytes(cache_bytes)}",
        f"Runtime: {_format_runtime(time.time() - _BOOT_TIME)}",
        f"Swap: {_format_bytes(swap.used)} / {_format_bytes(swap.total)} ({_format_percent(swap.percent)})",
        f"Top Processes by RSS (partial list, top {_PROCESS_LIMIT}):",
    ]
    lines.extend(_collect_process_memory_lines())
    lines.append("Disk:")
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
