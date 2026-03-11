import os
from pathlib import Path


PLUGIN_DIR = Path(__file__).parent
PROJECT_ROOT = PLUGIN_DIR.parent.parent


def resolve_data_dir() -> Path:
    """统一数据目录：
    1) QQ_DATA_DIR 环境变量（最高优先级）
    2) /app/data（容器环境）
    3) <repo>/data（本地开发）
    """
    custom = os.getenv("QQ_DATA_DIR", "").strip()
    if custom:
        p = Path(custom).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    app_data = Path("/app/data")
    if app_data.exists():
        app_data.mkdir(parents=True, exist_ok=True)
        return app_data

    local_data = PROJECT_ROOT / "data"
    local_data.mkdir(parents=True, exist_ok=True)
    return local_data
