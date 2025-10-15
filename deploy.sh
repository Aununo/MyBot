#!/bin/bash

# MyBot 一键部署脚本
# 支持 Linux/MacOS/WSL2

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示欢迎信息
show_banner() {
    echo -e "${GREEN}"
    cat << "EOF"
    __  ___      ____        __ 
   /  |/  /_  __/ __ )____  / /_
  / /|_/ / / / / __  / __ \/ __/
 / /  / / /_/ / /_/ / /_/ / /_  
/_/  /_/\__, /_____/\____/\__/  
       /____/                    
                                   
  MyBot - 一键部署脚本
EOF
    echo -e "${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        return 1
    fi
    return 0
}

# 检查依赖
check_dependencies() {
    print_info "检查依赖环境..."
    
    local missing_deps=()
    
    if ! check_command docker; then
        missing_deps+=("docker")
    fi
    
    if ! check_command docker-compose && ! docker compose version &> /dev/null; then
        missing_deps+=("docker-compose")
    fi
    
    if ! check_command git; then
        missing_deps+=("git")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "缺少以下依赖: ${missing_deps[*]}"
        echo ""
        echo "请先安装缺少的依赖："
        echo "  Docker: https://docs.docker.com/get-docker/"
        echo "  Docker Compose: https://docs.docker.com/compose/install/"
        echo "  Git: https://git-scm.com/downloads"
        exit 1
    fi
    
    print_success "所有依赖已就绪"
}

# 配置环境变量
configure_env() {
    print_info "配置环境变量..."
    
    if [ -f ".env" ]; then
        print_warning ".env 文件已存在"
        read -p "是否覆盖现有配置？(y/N): " overwrite
        if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
            print_info "跳过环境变量配置"
            return
        fi
    fi
    
    cp env.example .env
    
    # 获取用户输入
    echo ""
    echo "📝 基础配置"
    echo ""
    
    # 超级用户 QQ 号（必需）
    while true; do
        read -p "👤 管理员 QQ 号（必填）: " qq_number
        if [ -n "$qq_number" ]; then
            sed -i "s|SUPERUSERS=.*|SUPERUSERS=[\"$qq_number\"]|" .env
            break
        else
            print_warning "QQ 号不能为空，请重新输入"
        fi
    done
    
    echo ""
    # 天气 API Key（可选）
    read -p "OpenWeatherMap API Key（可选，回车跳过）: " weather_key
    if [ -n "$weather_key" ]; then
        sed -i "s|WEATHER_API_KEY=.*|WEATHER_API_KEY=$weather_key|" .env
        print_success "✅ 天气插件配置成功"
    fi
    
    echo ""
    print_success "✅ 环境变量配置完成"
}

# 创建必要的目录
create_directories() {
    print_info "创建数据目录..."
    
    mkdir -p data
    mkdir -p napcat_qq_data
    
    # 检查并修复权限（如果目录由 root 创建）
    if [ ! -w data ] || [ ! -w napcat_qq_data ]; then
        print_warning "检测到权限问题，尝试修复..."
        if sudo chown -R $(id -u):$(id -g) data napcat_qq_data 2>/dev/null; then
            print_success "✅ 权限修复成功"
        else
            print_warning "⚠️  权限修复失败，但会继续部署"
        fi
    fi
    
    # 设置权限
    chmod 755 data 2>/dev/null || true
    chmod 755 napcat_qq_data 2>/dev/null || true
    
    print_success "目录创建完成"
}

# 构建并启动服务
start_services() {
    print_info "构建 Docker 镜像..."
    
    # 设置 NAPCAT UID/GID
    export NAPCAT_UID=$(id -u)
    export NAPCAT_GID=$(id -g)
    
    # 使用 docker compose 或 docker-compose
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
    
    print_info "使用命令: $COMPOSE_CMD"
    
    # 停止旧容器
    $COMPOSE_CMD down 2>/dev/null || true
    
    # 构建并启动
    $COMPOSE_CMD up --build -d
    
    print_success "服务启动成功"
}

# 等待服务就绪
wait_for_services() {
    print_info "等待服务启动..."
    
    sleep 5
    
    # 检查容器状态
    if docker ps | grep -q "nonebot_app"; then
        print_success "NoneBot 服务已启动"
    else
        print_error "NoneBot 服务启动失败"
        return 1
    fi
    
    if docker ps | grep -q "napcat_client"; then
        print_success "NapCat 服务已启动"
    else
        print_error "NapCat 服务启动失败"
        return 1
    fi
}

# 显示登录二维码
show_qrcode() {
    print_info "等待生成登录二维码..."
    
    sleep 3
    
    echo ""
    print_info "登录方式："
    echo ""
    echo "1. 查看终端二维码（推荐）："
    echo "   docker compose logs napcat | grep -A 20 '请扫描'"
    echo ""
    echo "2. 导出二维码图片："
    echo "   docker cp napcat_client:/app/napcat/cache/qrcode.png ./qrcode.png"
    echo ""
    echo "3. 使用 URL 生成二维码："
    echo "   查看日志中的 '二维码解码URL'"
    echo ""
}

# 显示后续步骤
show_next_steps() {
    echo ""
    print_success "🎉 部署完成！"
    echo ""
    echo ""
    echo "📱 下一步操作："
    echo ""
    echo "1. 查看登录二维码："
    echo "   docker compose logs -f napcat"
    echo ""
    echo "2. 扫码登录后，向机器人发送消息测试："
    echo "   /ping       - 快速状态检查"
    echo "   /status     - 详细运行状态"
    echo "   /help       - 查看所有命令"
    echo ""
    echo "3. 查看服务日志："
    echo "   docker compose logs -f"
    echo ""
    echo "4. 管理服务："
    echo "   docker compose restart  - 重启服务"
    echo "   docker compose down     - 停止服务"
    echo "   docker compose ps       - 查看状态"
    echo ""
    echo ""
    print_success "祝你使用愉快！⭐"
    echo ""
}

# 主函数
main() {
    show_banner
    
    # 检查是否在项目根目录
    if [ ! -f "bot.py" ] || [ ! -f "docker-compose.yml" ]; then
        print_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 执行部署步骤
    check_dependencies
    configure_env
    create_directories
    start_services
    
    if wait_for_services; then
        show_qrcode
        show_next_steps
    else
        print_error "服务启动失败，请查看日志："
        echo "  docker compose logs"
        exit 1
    fi
}

# 运行主函数
main "$@"

