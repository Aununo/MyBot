"""
MyBot Web Management API
基于 FastAPI 的 RESTful API 服务器
提供对 MyBot 数据的可视化管理接口
"""

import json
import psutil
import os
import secrets
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

# 初始化 FastAPI 应用
app = FastAPI(
    title="MyBot Web API",
    description="MyBot QQ机器人可视化管理接口",
    version="1.0.0"
)

# CORS 配置 - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= HTTP Basic Authentication =============

# 初始化 HTTP Basic Auth
security = HTTPBasic()

# 从环境变量读取认证信息
WEB_ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME", "admin")
WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD", "admin123")

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """
    验证用户凭据
    使用 secrets.compare_digest 防止时序攻击
    """
    is_username_correct = secrets.compare_digest(
        credentials.username.encode("utf8"),
        WEB_ADMIN_USERNAME.encode("utf8")
    )
    is_password_correct = secrets.compare_digest(
        credentials.password.encode("utf8"),
        WEB_ADMIN_PASSWORD.encode("utf8")
    )
    
    if not (is_username_correct and is_password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Basic realm=\"MyBot Web Management\""},
        )
    
    return credentials.username

# 数据文件路径配置
DATA_DIR = Path("/app/data")
if not DATA_DIR.exists():
    DATA_DIR = Path(__file__).parent.parent / "data"

REMINDERS_FILE = DATA_DIR / "reminders_data.json"
TODO_FILE = DATA_DIR / "todo_data.json"
COUNTDOWN_FILE = DATA_DIR / "countdown_data.json"
USAGE_FILE = DATA_DIR / "usage_data.json"

# ============= Pydantic Models =============

class ReminderCreate(BaseModel):
    event: str = Field(..., description="提醒事件名称")
    hour: int = Field(..., ge=0, le=23, description="小时")
    minute: int = Field(..., ge=0, le=59, description="分钟")
    is_daily: bool = Field(default=False, description="是否每日提醒")
    interval_days: Optional[int] = Field(None, description="间隔天数")
    date: Optional[str] = Field(None, description="日期 (YYYY-MM-DD)")
    weekdays: Optional[List[int]] = Field(None, description="周几提醒 (0-6)")
    session_id: str = Field(..., description="会话ID")
    is_group: bool = Field(default=False, description="是否群聊")
    mention_all: bool = Field(default=False, description="是否@全体成员")

class TodoCreate(BaseModel):
    task: str = Field(..., description="待办事项内容")
    category: str = Field(..., description="分类: work 或 play")

class CountdownCreate(BaseModel):
    event_name: str = Field(..., description="倒计时事件名称")
    time: str = Field(..., description="截止时间 (ISO格式)")

# ============= 数据读写工具函数 =============

def read_json_file(file_path: Path) -> Dict:
    """读取 JSON 文件"""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def write_json_file(file_path: Path, data: Dict):
    """写入 JSON 文件"""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ============= 提醒 API =============

@app.get("/api/reminders", response_model=Dict[str, List[Dict]])
async def get_all_reminders(username: str = Depends(verify_credentials)):
    """获取所有用户的提醒列表"""
    data = read_json_file(REMINDERS_FILE)
    return data

@app.get("/api/reminders/{user_id}", response_model=List[Dict])
async def get_user_reminders(user_id: str, username: str = Depends(verify_credentials)):
    """获取指定用户的提醒"""
    data = read_json_file(REMINDERS_FILE)
    return data.get(user_id, [])

@app.post("/api/reminders/{user_id}", status_code=status.HTTP_201_CREATED)
async def create_reminder(user_id: str, reminder: ReminderCreate, username: str = Depends(verify_credentials)):
    """创建新提醒"""
    data = read_json_file(REMINDERS_FILE)
    
    if user_id not in data:
        data[user_id] = []
    
    # 生成唯一的 job_id
    import uuid
    job_id = f"reminder_{user_id}_{uuid.uuid4()}"
    
    new_reminder = {
        "event": reminder.event,
        "hour": reminder.hour,
        "minute": reminder.minute,
        "job_id": job_id,
        "is_daily": reminder.is_daily,
        "session_id": reminder.session_id,
        "is_group": reminder.is_group
    }
    
    if reminder.date:
        new_reminder["date"] = reminder.date
    if reminder.interval_days:
        new_reminder["interval_days"] = reminder.interval_days
    if reminder.weekdays:
        new_reminder["weekdays"] = reminder.weekdays
    if reminder.mention_all:
        new_reminder["mention_all"] = reminder.mention_all
    
    data[user_id].append(new_reminder)
    write_json_file(REMINDERS_FILE, data)
    
    return {"message": "提醒创建成功", "reminder": new_reminder}

@app.delete("/api/reminders/{user_id}/{job_id}")
async def delete_reminder(user_id: str, job_id: str, username: str = Depends(verify_credentials)):
    """删除指定提醒"""
    data = read_json_file(REMINDERS_FILE)
    
    if user_id not in data:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    user_reminders = data[user_id]
    reminder_to_delete = None
    
    for i, reminder in enumerate(user_reminders):
        if reminder.get("job_id") == job_id:
            reminder_to_delete = user_reminders.pop(i)
            break
    
    if not reminder_to_delete:
        raise HTTPException(status_code=404, detail="提醒不存在")
    
    if not data[user_id]:
        del data[user_id]
    
    write_json_file(REMINDERS_FILE, data)
    return {"message": "提醒已删除", "reminder": reminder_to_delete}

# ============= 待办事项 API =============

@app.get("/api/todos", response_model=Dict)
async def get_all_todos(username: str = Depends(verify_credentials)):
    """获取所有待办事项"""
    data = read_json_file(TODO_FILE)
    return data

@app.get("/api/todos/{user_id}", response_model=Dict[str, List[Dict]])
async def get_user_todos(user_id: str, username: str = Depends(verify_credentials)):
    """获取指定用户的待办事项"""
    data = read_json_file(TODO_FILE)
    return data.get(user_id, {"work": [], "play": []})

@app.post("/api/todos/{user_id}", status_code=status.HTTP_201_CREATED)
async def create_todo(user_id: str, todo: TodoCreate, username: str = Depends(verify_credentials)):
    """创建待办事项"""
    data = read_json_file(TODO_FILE)
    
    if user_id not in data:
        data[user_id] = {"work": [], "play": []}
    
    if todo.category not in ["work", "play"]:
        raise HTTPException(status_code=400, detail="分类必须是 work 或 play")
    
    new_todo = {"task": todo.task, "done": False}
    data[user_id][todo.category].append(new_todo)
    
    write_json_file(TODO_FILE, data)
    return {"message": "待办事项创建成功", "todo": new_todo}

@app.put("/api/todos/{user_id}/{category}/{index}")
async def update_todo(user_id: str, category: str, index: int, done: bool, username: str = Depends(verify_credentials)):
    """更新待办事项状态"""
    data = read_json_file(TODO_FILE)
    
    if user_id not in data:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if category not in ["work", "play"]:
        raise HTTPException(status_code=400, detail="分类必须是 work 或 play")
    
    if index < 0 or index >= len(data[user_id][category]):
        raise HTTPException(status_code=404, detail="待办事项不存在")
    
    data[user_id][category][index]["done"] = done
    write_json_file(TODO_FILE, data)
    
    return {"message": "待办事项已更新", "todo": data[user_id][category][index]}

@app.delete("/api/todos/{user_id}/{category}/{index}")
async def delete_todo(user_id: str, category: str, index: int, username: str = Depends(verify_credentials)):
    """删除待办事项"""
    data = read_json_file(TODO_FILE)
    
    if user_id not in data:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if category not in ["work", "play"]:
        raise HTTPException(status_code=400, detail="分类必须是 work 或 play")
    
    if index < 0 or index >= len(data[user_id][category]):
        raise HTTPException(status_code=404, detail="待办事项不存在")
    
    deleted_todo = data[user_id][category].pop(index)
    write_json_file(TODO_FILE, data)
    
    return {"message": "待办事项已删除", "todo": deleted_todo}

# ============= 倒计时 API =============

@app.get("/api/countdowns", response_model=Dict)
async def get_all_countdowns(username: str = Depends(verify_credentials)):
    """获取所有倒计时"""
    data = read_json_file(COUNTDOWN_FILE)
    return data

@app.get("/api/countdowns/{user_id}", response_model=Dict[str, Dict])
async def get_user_countdowns(user_id: str, username: str = Depends(verify_credentials)):
    """获取指定用户的倒计时"""
    data = read_json_file(COUNTDOWN_FILE)
    return data.get(user_id, {})

@app.post("/api/countdowns/{user_id}", status_code=status.HTTP_201_CREATED)
async def create_countdown(user_id: str, countdown: CountdownCreate, username: str = Depends(verify_credentials)):
    """创建倒计时"""
    data = read_json_file(COUNTDOWN_FILE)
    
    if user_id not in data:
        data[user_id] = {}
    
    new_countdown = {
        "time": countdown.time,
        "created_at": datetime.now().isoformat()
    }
    
    data[user_id][countdown.event_name] = new_countdown
    write_json_file(COUNTDOWN_FILE, data)
    
    return {"message": "倒计时创建成功", "countdown": new_countdown}

@app.delete("/api/countdowns/{user_id}/{event_name}")
async def delete_countdown(user_id: str, event_name: str, username: str = Depends(verify_credentials)):
    """删除倒计时"""
    data = read_json_file(COUNTDOWN_FILE)
    
    if user_id not in data:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if event_name not in data[user_id]:
        raise HTTPException(status_code=404, detail="倒计时不存在")
    
    deleted_countdown = data[user_id].pop(event_name)
    
    if not data[user_id]:
        del data[user_id]
    
    write_json_file(COUNTDOWN_FILE, data)
    return {"message": "倒计时已删除", "countdown": deleted_countdown}

# ============= 使用统计 API =============

@app.get("/api/usage/overview")
async def get_usage_overview(username: str = Depends(verify_credentials)):
    """获取总体统计"""
    data = read_json_file(USAGE_FILE)
    records = data.get("sent_messages", [])
    
    total_calls = len(records)
    
    # 最近7天统计
    from datetime import timedelta
    now = datetime.now()
    cutoff_time = int((now - timedelta(days=7)).timestamp())
    recent_calls = sum(1 for r in records if r.get("timestamp", 0) >= cutoff_time)
    
    return {
        "total_calls": total_calls,
        "recent_7days": recent_calls,
        "total_records": len(records)
    }

@app.get("/api/usage/hourly")
async def get_usage_hourly(username: str = Depends(verify_credentials)):
    """按小时统计"""
    data = read_json_file(USAGE_FILE)
    records = data.get("sent_messages", [])
    
    hour_counts = {}
    for i in range(24):
        hour_counts[i] = 0
    
    for record in records:
        hour = record.get("hour", 0)
        hour_counts[hour] = hour_counts.get(hour, 0) + 1
    
    return {"hourly_stats": hour_counts}

@app.get("/api/usage/daily")
async def get_usage_daily(username: str = Depends(verify_credentials)):
    """按日期统计"""
    data = read_json_file(USAGE_FILE)
    records = data.get("sent_messages", [])
    
    date_counts = {}
    for record in records:
        date = record.get("date", "")
        if date:
            date_counts[date] = date_counts.get(date, 0) + 1
    
    # 按日期排序
    sorted_dates = sorted(date_counts.items(), key=lambda x: x[0], reverse=True)
    
    return {"daily_stats": dict(sorted_dates[:30])}  # 最近30天

@app.get("/api/usage/weekday")
async def get_usage_weekday(username: str = Depends(verify_credentials)):
    """按星期统计"""
    data = read_json_file(USAGE_FILE)
    records = data.get("sent_messages", [])
    
    weekday_counts = {
        "Monday": 0, "Tuesday": 0, "Wednesday": 0, "Thursday": 0,
        "Friday": 0, "Saturday": 0, "Sunday": 0
    }
    
    for record in records:
        weekday = record.get("weekday", "")
        if weekday in weekday_counts:
            weekday_counts[weekday] += 1
    
    return {"weekday_stats": weekday_counts}

# ============= 系统状态 API =============

@app.get("/api/status")
async def get_system_status(username: str = Depends(verify_credentials)):
    """获取系统状态"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_gb": round(memory.used / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {str(e)}")

# ============= 图片管理 API =============

# 图片资源目录配置
ASSETS_DIR = Path(__file__).parent.parent / "src" / "plugins" / "assets"
IMAGE_FOLDERS = {
    "pics": ASSETS_DIR / "pics",
    "food_images": ASSETS_DIR / "food_images",
    "latex": ASSETS_DIR / "latex"
}

# 确保目录存在
for folder_path in IMAGE_FOLDERS.values():
    folder_path.mkdir(parents=True, exist_ok=True)

# 支持的图片格式
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

@app.get("/api/images")
async def get_all_images(username: str = Depends(verify_credentials)):
    """获取所有文件夹的图片列表"""
    result = {}
    
    for folder_name, folder_path in IMAGE_FOLDERS.items():
        try:
            images = []
            if folder_path.exists():
                for file in folder_path.iterdir():
                    if file.is_file() and file.suffix.lower() in ALLOWED_EXTENSIONS:
                        stat = file.stat()
                        images.append({
                            "name": file.name,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "url": f"/api/images/{folder_name}/{file.name}"
                        })
            result[folder_name] = images
        except Exception as e:
            result[folder_name] = {"error": str(e)}
    
    return result

@app.get("/api/images/{folder}")
async def get_folder_images(folder: str, username: str = Depends(verify_credentials)):
    """获取指定文件夹的图片列表"""
    if folder not in IMAGE_FOLDERS:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    
    folder_path = IMAGE_FOLDERS[folder]
    images = []
    
    try:
        if folder_path.exists():
            for file in folder_path.iterdir():
                if file.is_file() and file.suffix.lower() in ALLOWED_EXTENSIONS:
                    stat = file.stat()
                    images.append({
                        "name": file.name,
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "url": f"/api/images/{folder}/{file.name}"
                    })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件夹失败: {str(e)}")
    
    return {"folder": folder, "images": images}

@app.get("/api/images/{folder}/{filename}")
async def get_image(folder: str, filename: str, username: str = Depends(verify_credentials)):
    """下载/查看图片"""
    if folder not in IMAGE_FOLDERS:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    
    file_path = IMAGE_FOLDERS[folder] / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    
    from fastapi.responses import FileResponse
    return FileResponse(file_path)

@app.post("/api/images/{folder}/upload", status_code=status.HTTP_201_CREATED)
async def upload_image(folder: str, file: UploadFile = File(...), username: str = Depends(verify_credentials)):
    """上传图片到指定文件夹"""
    
    if folder not in IMAGE_FOLDERS:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    
    # 检查文件扩展名
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件格式。允许的格式: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # 保存文件
    folder_path = IMAGE_FOLDERS[folder]
    file_path = folder_path / file.filename
    
    # 如果文件已存在，添加序号
    if file_path.exists():
        base_name = Path(file.filename).stem
        counter = 1
        while file_path.exists():
            new_filename = f"{base_name}_{counter}{file_ext}"
            file_path = folder_path / new_filename
            counter += 1
    
    try:
        # 读取并保存文件
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # 返回文件信息
        stat = file_path.stat()
        return {
            "message": "上传成功",
            "file": {
                "name": file_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "url": f"/api/images/{folder}/{file_path.name}"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@app.delete("/api/images/{folder}/{filename}")
async def delete_image(folder: str, filename: str, username: str = Depends(verify_credentials)):
    """删除图片"""
    if folder not in IMAGE_FOLDERS:
        raise HTTPException(status_code=404, detail="文件夹不存在")
    
    file_path = IMAGE_FOLDERS[folder] / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="图片不存在")
    
    try:
        file_path.unlink()
        return {"message": f"图片 {filename} 已删除", "folder": folder, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

# ============= 吃什么管理 API =============

# 吃什么数据文件配置
EAT_DATA_FILE = DATA_DIR / "eat_data.json"

def read_eat_data() -> Dict:
    """读取吃什么数据"""
    if not EAT_DATA_FILE.exists():
        return {"android": [], "apple": []}
    try:
        with open(EAT_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"android": [], "apple": []}

def write_eat_data(data: Dict):
    """写入吃什么数据"""
    with open(EAT_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@app.get("/api/eat")
async def get_eat_data(username: str = Depends(verify_credentials)):
    """获取所有吃什么数据"""
    data = read_eat_data()
    return {
        "android": data.get("android", []),
        "apple": data.get("apple", [])
    }

@app.get("/api/eat/{list_name}")
async def get_eat_list(list_name: str, username: str = Depends(verify_credentials)):
    """获取指定列表的食物"""
    if list_name not in ["android", "apple"]:
        raise HTTPException(status_code=404, detail="列表不存在")
    
    data = read_eat_data()
    return {"list_name": list_name, "foods": data.get(list_name, [])}

@app.post("/api/eat/{list_name}", status_code=status.HTTP_201_CREATED)
async def add_food(list_name: str, food: str, username: str = Depends(verify_credentials)):
    """添加食物到列表"""
    if list_name not in ["android", "apple"]:
        raise HTTPException(status_code=404, detail="列表不存在")
    
    data = read_eat_data()
    
    if food in data[list_name]:
        raise HTTPException(status_code=400, detail="该食物已存在")
    
    data[list_name].append(food)
    write_eat_data(data)
    
    return {"message": f"已添加 {food} 到 {list_name} 列表", "food": food}

@app.delete("/api/eat/{list_name}/{food}")
async def delete_food(list_name: str, food: str, username: str = Depends(verify_credentials)):
    """从列表删除食物"""
    if list_name not in ["android", "apple"]:
        raise HTTPException(status_code=404, detail="列表不存在")
    
    data = read_eat_data()
    
    if food not in data[list_name]:
        raise HTTPException(status_code=404, detail="食物不存在")
    
    data[list_name].remove(food)
    write_eat_data(data)
    
    return {"message": f"已从 {list_name} 列表删除 {food}", "food": food}

# ============= 静态文件服务 =============

# 挂载静态文件目录
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def read_root(username: str = Depends(verify_credentials)):
    """返回主页 (需要认证)"""
    index_file = Path(__file__).parent / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "MyBot Web API is running!", "docs": "/docs"}

# ============= 健康检查 =============

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
