from __future__ import annotations

import os
import platform
import socket
import time
from datetime import datetime

import psutil
from nonebot import on_command, on_notice
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, NotifyEvent


status_cmd = on_command("status", priority=1, block=True)
status_poke = on_notice(priority=1, block=False)

_PROCESS = psutil.Process(os.getpid())
_BOOT_TIME = psutil.boot_time()


def _format_bytes(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{value:.1f}B"


def _format_seconds(seconds: float) -> str:
    seconds = int(max(0, seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if secs or not parts:
        parts.append(f"{secs}秒")
    return "".join(parts)


def _cpu_percent() -> tuple[float, float]:
    proc_cpu = _PROCESS.cpu_percent(interval=0.25)
    sys_cpu = psutil.cpu_percent(interval=0.25)
    return proc_cpu, sys_cpu


def _build_status_text(bot: Bot | None = None) -> str:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    proc_mem = _PROCESS.memory_info()
    proc_cpu, sys_cpu = _cpu_percent()
    loadavg = None
    try:
        loadavg = os.getloadavg()
    except Exception:
        pass

    lines = [
        "📊 服务器状态",
        f"主机: {socket.gethostname()}",
        f"系统: {platform.system()} {platform.release()}",
        f"Python: {platform.python_version()}",
        f"Bot进程运行: {_format_seconds(time.time() - _PROCESS.create_time())}",
        f"服务器运行: {_format_seconds(time.time() - _BOOT_TIME)}",
        "",
        "🧠 资源使用",
        f"CPU: 系统 {sys_cpu:.1f}% / Bot进程 {proc_cpu:.1f}%",
        f"内存: 系统 {_format_bytes(vm.used)} / {_format_bytes(vm.total)} ({vm.percent:.1f}%)",
        f"Bot内存: RSS {_format_bytes(proc_mem.rss)} / VMS {_format_bytes(proc_mem.vms)}",
        f"磁盘(/): {_format_bytes(disk.used)} / {_format_bytes(disk.total)} ({disk.percent:.1f}%)",
    ]

    if loadavg:
        lines.append(f"负载: {loadavg[0]:.2f} / {loadavg[1]:.2f} / {loadavg[2]:.2f}")

    lines.extend([
        "",
        "🌐 网络",
        f"上行: {_format_bytes(net.bytes_sent)}  下行: {_format_bytes(net.bytes_recv)}",
    ])

    if bot is not None:
        try:
            login = bot.self_id
            lines.append(f"Bot QQ: {login}")
        except Exception:
            pass

    lines.extend([
        "",
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ])
    return "\n".join(lines)


@status_cmd.handle()
async def handle_status(bot: Bot, event: MessageEvent):
    await status_cmd.finish(_build_status_text(bot))


@status_poke.handle()
async def handle_poke(bot: Bot, event: NotifyEvent):
    if getattr(event, "sub_type", None) != "poke":
        return
    target_id = str(getattr(event, "target_id", ""))
    if target_id != str(bot.self_id):
        return
    await bot.send(event, _build_status_text(bot))
