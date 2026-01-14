#!/bin/bash

# MyBot Web 管理界面启动脚本

echo "🚀 启动 MyBot Web 管理界面..."
echo "================================"

# 检查是否在项目根目录
if [ ! -d "web" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本！"
    exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检查 Python 依赖（使用独立虚拟环境，避免系统环境限制）
echo "📦 检查依赖..."
VENV_DIR="$ROOT_DIR/.venv-web"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR" 2>/dev/null
fi

PY_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"

if [ ! -x "$PY_BIN" ]; then
    echo "❌ 未能创建虚拟环境，请先安装 venv 组件："
    echo "   sudo apt install -y python3-venv"
    exit 1
fi

$PY_BIN -c "import fastapi, uvicorn, psutil, httpx" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  检测到缺少依赖，正在安装..."
    $PIP_BIN install fastapi uvicorn[standard] python-multipart psutil httpx
fi

# 切换到 web 目录
cd "$ROOT_DIR/web"

# 启动服务
echo ""
echo "✅ 依赖检查完成！"
echo "🌐 启动 Web 服务器..."
echo "📍 访问地址: http://localhost:8000"
echo "📚 API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "================================"
echo ""

# 使用 uvicorn 启动
$PY_BIN -m uvicorn web_api:app --host 0.0.0.0 --port 8000 --reload
