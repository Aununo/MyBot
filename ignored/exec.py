import subprocess
import os
import re
import shlex
import shutil
import pwd
import sys
from pathlib import Path
from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException

# CTF Flag (隐藏在环境变量和文件中)
FLAG_ENV_NAME = "flag"
FLAG_VALUE = "nailong{c0mm@nd_eX3cut1on_bypa5s_filte7}"

# 设置环境变量（如果还没有设置）
if FLAG_ENV_NAME not in os.environ:
    os.environ[FLAG_ENV_NAME] = FLAG_VALUE

# 同时将flag写入隐藏文件
FLAG_FILE_PATH = "/tmp/nailong.txt"
FLAG_FILE_ALLOWED = "/tmp/nailong.txt"
try:
    with open(FLAG_FILE_PATH, 'w') as f:
        f.write(FLAG_VALUE)
    os.chmod(FLAG_FILE_PATH, 0o644)  # 允许其他用户读取
except Exception as e:
    logger.warning(f"无法创建flag文件: {e}")

# ========== 安全配置 ==========

# 1. 严格的命令白名单（只允许这些命令）
ALLOWED_COMMANDS = {
    "ls": {
        "max_args": 5,
        "allowed_flags": ["-l", "-a", "-h", "-d"],
        "value_flags": [],
        "path_restriction": True,  # 限制路径访问
    },
    "pwd": {
        "max_args": 0,
        "allowed_flags": [],
        "value_flags": [],
        "path_restriction": False,
    },
    "whoami": {
        "max_args": 0,
        "allowed_flags": [],
        "value_flags": [],
        "path_restriction": False,
    },
    "id": {
        "max_args": 2,
        "allowed_flags": ["-u", "-g"],
        "value_flags": [],
        "path_restriction": False,
    },
    "date": {
        "max_args": 0,
        "allowed_flags": [],
        "value_flags": [],
        "path_restriction": False,
    },
    "echo": {
        "max_args": 10,
        "allowed_flags": ["-n", "-e"],
        "value_flags": [],
        "path_restriction": False,
    },
    "cat": {
        "max_args": 3,
        "allowed_flags": [],
        "value_flags": [],
        "path_restriction": True,  # 严格限制文件路径
    },
    "head": {
        "max_args": 4,
        "allowed_flags": ["-n", "-c"],
        "value_flags": ["-n", "-c"],
        "path_restriction": True,
    },
    "tail": {
        "max_args": 4,
        "allowed_flags": ["-n", "-c"],
        "value_flags": ["-n", "-c"],
        "path_restriction": True,
    },
    "wc": {
        "max_args": 3,
        "allowed_flags": ["-l", "-w", "-c"],
        "value_flags": [],
        "path_restriction": True,
    },
}

# 2. 允许访问的目录白名单（绝对路径）
ALLOWED_PATHS = [
    "/var/tmp",
    "/home",
    "/dev/shm",
    "/run/shm",
    "/run/user",
    "/tmp"
]

# 3. 禁止访问的路径（黑名单，优先级更高）
BLOCKED_PATHS = [
    "/etc",
    "/root",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/sys",
    "/proc",
    "/dev",
    "/boot",
    "/opt",
    "/srv",
    "/var/log",
    "/var/lib",
]

# 4. 禁止的关键词（额外安全层）
BLOCKED_KEYWORDS = [
    "flag", "FLAG",
    "rm", "delete", "del",
    "wget", "curl", "nc", "netcat",
    "python", "python3", "bash", "sh", "zsh",
    "sudo", "su",
    "exec", "eval",
    "env", "export", "printenv",
]

# 5. 禁止的字符（防止命令注入）
FORBIDDEN_CHARS = [
    ">", ">>", "<", "&", ";", "|", "`", "$", "(", ")", "{", "}", "[", "]",
    "*", "?", "~", "!", "@", "#", "%", "^", "\\", "\"", "'",
]

# 6. 安全执行用户（使用非root用户执行命令）
# 优先级：nobody > daemon > www-data > www

def is_path_allowed(file_path: str) -> bool:
    """
    检查文件路径是否在允许列表中
    返回: (是否允许, 原因)
    """
    # 规范化路径
    try:
        abs_path = os.path.abspath(os.path.expanduser(file_path))
    except Exception:
        return False, "路径解析失败"
    
    # 检查是否在禁止列表中
    for blocked in BLOCKED_PATHS:
        if abs_path.startswith(blocked):
            return False, f"路径在禁止列表中: {blocked}"
    
    # 检查是否在允许列表中
    for allowed in ALLOWED_PATHS:
        if abs_path.startswith(allowed):
            return True, "路径在允许列表中"
    
    # 默认拒绝
    return False, "路径不在允许列表中"


def parse_command(cmd_str: str) -> tuple[str, list[str]]:
    """
    安全地解析命令字符串
    返回: (命令名, 参数列表)
    """
    try:
        # 使用shlex安全解析，防止命令注入
        parts = shlex.split(cmd_str)
        if not parts:
            return "", []
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        return command, args
    except ValueError as e:
        raise ValueError(f"命令解析失败: {e}")


def validate_command(command: str, args: list[str]) -> tuple[bool, str]:
    """
    验证命令和参数是否安全
    返回: (是否安全, 错误信息)
    """
    command_lower = command.lower()
    
    # 1. 检查命令是否在白名单中
    if command_lower not in ALLOWED_COMMANDS:
        return False, f"命令不在白名单中: {command}"
    
    cmd_config = ALLOWED_COMMANDS[command_lower]
    
    # 2. 检查参数数量
    if len(args) > cmd_config["max_args"]:
        return False, f"参数过多，最多允许 {cmd_config['max_args']} 个参数"
    
    # 3. 检查是否包含禁止的关键词
    full_cmd = f"{command} {' '.join(args)}"
    for keyword in BLOCKED_KEYWORDS:
        if keyword in full_cmd:
            return False, f"命令包含禁止的关键词: {keyword}"
    
    # 4. 检查是否包含禁止的字符
    for char in FORBIDDEN_CHARS:
        if char in full_cmd:
            return False, f"命令包含禁止的字符: {char}"
    
    # 5. 检查路径限制/参数类型
    allowed_flags = set(cmd_config.get("allowed_flags", []))
    value_flags = set(cmd_config.get("value_flags", []))
    expect_flag_value = False
    
    if cmd_config["path_restriction"]:
        for arg in args:
            if expect_flag_value:
                expect_flag_value = False
                # 参数作为 flag 的值，不当作路径
                continue
            
            if arg.startswith("-"):
                if arg not in allowed_flags:
                    return False, f"不允许的参数: {arg}"
                if arg in value_flags:
                    expect_flag_value = True
                continue
            
            # 检查文件路径
            is_allowed, reason = is_path_allowed(arg)
            if not is_allowed:
                return False, f"路径访问被拒绝: {reason}"
    else:
        for arg in args:
            if expect_flag_value:
                expect_flag_value = False
                continue
            if arg.startswith("-"):
                if arg not in allowed_flags:
                    return False, f"不允许的参数: {arg}"
                if arg in value_flags:
                    expect_flag_value = True
                continue
    
    # 6. 验证参数格式（防止特殊构造）
    for arg in args:
        # 禁止包含路径遍历
        if ".." in arg:
            return False, "禁止路径遍历 (..)"
        # 禁止绝对路径（除非在允许列表中）
        if arg.startswith("/") and not cmd_config["path_restriction"]:
            return False, "该命令不允许使用绝对路径"
    
    return True, ""


def sanitize_output(output: str, max_length: int = 100, max_lines: int = 40) -> str:
    """
    清理输出，移除敏感信息
    """
    # 检测到 nailong{ 立即截断
    match = re.search(r"nailong\{", output, flags=re.IGNORECASE)
    if match:
        output = output[: match.start()] + "***FILTERED***"

    # 其他 flag 相关内容兜底过滤
    output = re.sub(r"flag[=:]\s*[^\s]+", "flag=***FILTERED***", output, flags=re.IGNORECASE)
    
    # 限制输出行数
    lines = output.splitlines()
    if len(lines) > max_lines:
        output = "\n".join(lines[:max_lines]) + f"\n... (输出超过{max_lines}行，已截断)"
    else:
        output = "\n".join(lines)

    # 限制输出长度
    if len(output) > max_length:
        output = output[:max_length] + "\n... (输出过长，已截断)"
    
    return output


def get_safe_user() -> str | None:
    """
    获取安全的非root用户
    返回: 用户名或None（如果无法获取）
    """
    # 尝试的用户列表（按优先级）
    candidate_users = ["nobody", "daemon", "www-data", "www"]
    
    for username in candidate_users:
        try:
            user_info = pwd.getpwnam(username)
            # 确保不是root用户
            if user_info.pw_uid != 0:
                return username
        except KeyError:
            continue
    
    # 如果都不可用，返回None
    return None


def execute_command_safely(command: str, args: list[str]) -> tuple[str, str, int]:
    """
    安全地执行命令（在非root用户下）
    返回: (stdout, stderr, returncode)
    """
    # 构建命令列表（不使用shell=True）
    # 使用绝对路径，防止PATH劫持
    command_path = shutil.which(command)
    if not command_path:
        raise ValueError(f"命令未找到: {command}")
    
    # 验证命令路径是否在系统目录中（防止使用自定义脚本）
    allowed_command_dirs = ["/bin", "/usr/bin", "/usr/local/bin"]
    if not any(command_path.startswith(dir) for dir in allowed_command_dirs):
        raise ValueError(f"命令路径不在允许的目录中: {command_path}")
    
    # 注意：这里直接使用args，没有再次验证路径
    # 在validate_command和execute_command_safely之间存在时间窗口
    # 如果路径是符号链接，在验证时可能指向安全路径，但在执行时可能被替换为危险路径
    # 这是一个TOCTOU漏洞
    cmd_list = [command_path] + args
    
    # 准备环境变量（移除敏感信息）
    safe_env = os.environ.copy()
    # 移除flag环境变量
    if FLAG_ENV_NAME in safe_env:
        del safe_env[FLAG_ENV_NAME]
    # 限制PATH，只包含系统目录
    safe_env["PATH"] = "/bin:/usr/bin:/usr/local/bin"
    # 移除其他可能危险的环境变量
    dangerous_env_vars = ["LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH"]
    for var in dangerous_env_vars:
        safe_env.pop(var, None)
    
    # 获取安全的非root用户
    safe_user = get_safe_user()
    
    # 检查当前是否为root用户
    is_root = os.geteuid() == 0 if hasattr(os, 'geteuid') else False
    
    # 准备subprocess参数
    subprocess_kwargs = {
        "args": cmd_list,
        "shell": False,  # 关键：不使用shell
        "capture_output": True,
        "text": True,
        "timeout": 5,  # 5秒超时
        "cwd": "/home",  # 限制工作目录
        "env": safe_env,  # 使用清理后的环境变量
    }
    
    # 如果当前是root用户，尝试使用非root用户执行
    if is_root and safe_user:
        try:
            # Python 3.9+ 支持 user 参数
            if sys.version_info >= (3, 9):
                subprocess_kwargs["user"] = safe_user
                logger.info(f"使用非root用户执行命令: {safe_user}")
            else:
                logger.warning("Python版本 < 3.9，无法使用user参数，将使用当前用户")
        except Exception as e:
            logger.warning(f"无法切换到非root用户 {safe_user}: {e}")
    elif is_root and not safe_user:
        logger.warning("当前是root用户，但未找到可用的非root用户，命令将以root权限执行")
    else:
        logger.info(f"当前不是root用户（UID: {os.geteuid() if hasattr(os, 'geteuid') else 'unknown'}），直接执行")
    
    try:
        # 使用subprocess.run执行命令
        result = subprocess.run(**subprocess_kwargs)
        
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        raise TimeoutError("命令执行超时")
    except FileNotFoundError:
        raise ValueError(f"命令未找到: {command}")
    except PermissionError:
        raise RuntimeError("权限不足，无法执行命令")
    except TypeError as e:
        # 如果user参数不被支持（Python < 3.9），回退到不使用user参数
        if "user" in str(e) and sys.version_info < (3, 9):
            logger.warning("Python版本不支持user参数，回退到当前用户执行")
            subprocess_kwargs.pop("user", None)
            result = subprocess.run(**subprocess_kwargs)
            return result.stdout, result.stderr, result.returncode
        raise RuntimeError(f"执行失败: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"执行失败: {str(e)}")


exec_cmd = on_command("exec", aliases={"执行", "cmd"}, priority=1, block=True)

@exec_cmd.handle()
async def handle_exec(event: MessageEvent, args: Message = CommandArg()):
    """
    执行命令处理器 - 安全版本
    """
    cmd_str = args.extract_plain_text().strip()
    
    if not cmd_str:
        allowed_cmds = ", ".join(sorted(ALLOWED_COMMANDS.keys()))
        await exec_cmd.finish(
            "用法: /exec <命令> [参数]\n\n"
            f"flag格式:nailong{{xxx}}"
        )
        return
    
    try:
        # 1. 解析命令
        command, cmd_args = parse_command(cmd_str)
        
        if not command:
            await exec_cmd.finish("❌ 命令不能为空")
            return
        
        # 2. 验证命令
        is_safe, error_msg = validate_command(command, cmd_args)
        if not is_safe:
            await exec_cmd.finish(f"❌ 命令被拒绝: {error_msg}")
            return
        
        # 3. 执行命令
        stdout, stderr, returncode = execute_command_safely(command, cmd_args)
        
        # 4. 组合输出
        output_parts = []
        if stdout:
            output_parts.append(f"📤 标准输出:\n{stdout}")
        if stderr:
            output_parts.append(f"⚠️ 错误输出:\n{stderr}")
        if returncode != 0:
            output_parts.append(f"退出码: {returncode}")
        
        if not output_parts:
            output_parts.append("命令执行完成，无输出")
        
        output = "\n\n".join(output_parts)
        
        # 5. 清理输出
        output = sanitize_output(output)
        
        await exec_cmd.finish(f"✅ 命令执行完成\n{output}")
        
    except FinishedException:
        # NoneBot 用于结束流程的异常，直接抛出避免被误判为错误
        raise
    except ValueError as e:
        await exec_cmd.finish(f"❌ 命令解析错误: {str(e)}")
    except TimeoutError:
        await exec_cmd.finish("⏱️ 命令执行超时（超过5秒）")
    except Exception as e:
        logger.error(f"命令执行错误: {e}")
        await exec_cmd.finish(f"❌ 执行失败: {str(e)}")

