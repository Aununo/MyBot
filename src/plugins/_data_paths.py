from pathlib import Path


PLUGIN_DIR = Path(__file__).parent
PROJECT_ROOT = PLUGIN_DIR.parent.parent
APP_ROOT = Path("/app")
APP_DATA_DIR = APP_ROOT / "data"


def resolve_data_dir() -> Path:
    """Resolve the shared data directory for local and container environments."""
    if APP_ROOT.exists():
        data_dir = APP_DATA_DIR
    else:
        data_dir = PROJECT_ROOT / "data"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
