<div align="center">

# 🤖 MyBot

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![NoneBot](https://img.shields.io/badge/NoneBot-2.4.3-green.svg)](https://nonebot.dev/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-brightgreen.svg)](docker-compose.yml)

基于 NoneBot2 和 NapCat 的功能丰富的 QQ 机器人，支持提醒、待办事项、天气查询等多种实用功能。

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [插件列表](#-插件列表) • [常用命令](#-常用命令)

</div>



## ✨ 功能特性

- 🚀 **开箱即用** - Docker Compose 一键部署，无需复杂配置
- 📦 **丰富插件** - 若干内置插件，覆盖学习、生活、娱乐
- 💾 **数据持久化** - 自动保存数据，重启不丢失
- 🔧 **易于扩展** - 模块化设计，轻松添加自定义插件
- 📊 **状态监控** - 实时查看 CPU、内存、运行状态
- 🐳 **容器化部署** - Docker 隔离环境，稳定可靠

## 📦 插件列表

### 官方插件
- ✅ **apscheduler** - 定时任务调度支持
- ✅ **status** - 详细系统状态监控（`/status`）

### 自定义插件

- 🔔 **help** - 查看所有命令帮助 (`/help`)
- 📶 **ping** - 快速状态检查 (`/ping`)
- 📅 **schedule** - 个人课程表管理 (`/今日课表`)
- ⏰ **remind** - 灵活的提醒功能 (`/remind`)
- ✅ **todo** - 待办事项管理 (`/todo`)
- ⏳ **countdown** - 事件倒计时管理 (`/time`)
- 🍔 **eat** - 今天吃什么推荐 (`/android`, `/apple`)
- 🌤️ **weather** - 城市天气查询 (`/天气 北京`)
- 🔬 **latex** - LaTeX 公式渲染 (`/latex E=mc^2`)
- 🖼️ **pic** - 图片管理 (`/savepic`, `/sendpic`)
- 📝 **relay** - 群内接龙（`/接龙`）
- 📧 **email_notifier** - 检查邮箱新邮件（`/check_email`）
- 📊 **usage** - 查看命令使用情况（`/usage`）

## 🚀 快速开始

### 前置要求

- Git
- Docker & Docker Compose
- Linux/MacOS 或 Windows WSL2

### 一键部署

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/MyBot.git
cd MyBot

# 2. 运行一键部署脚本
chmod +x deploy.sh
./deploy.sh

# 3. 按提示完成配置，扫码登录即可使用
```

### 手动部署

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/MyBot.git
cd MyBot

# 2. 复制并编辑环境变量
cp env.example .env
nano .env  # 修改配置（可选）

# 3. 启动服务
NAPCAT_UID=$(id -u) NAPCAT_GID=$(id -g) docker compose up --build -d

# 4. 查看日志获取登录二维码
docker compose logs -f napcat

# 5. 扫码登录后测试
```


## 🔧 常用命令

```bash
# 查看实时日志 [最近100行]
docker compose logs -f [--tail 100]

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 重新构建
docker compose up --build -d

# 备份数据
cp -r data ~/backup_$(date +%Y%m%d)
```

## 📁 项目结构

```
mybot/
├── bot.py                  # NoneBot 入口文件
├── pyproject.toml          # 项目配置
├── requirements.txt        # Python 依赖
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # Docker 镜像构建
├── env.example             # 环境变量模板
├── LICENSE                 # MIT 许可证
├── README.md               # 项目说明
├── src/
│   └── plugins/           # 自定义插件目录
│       ├── help.py
│       ├── remind.py
│       └── ...
├── data/                   # 数据持久化目录（不上传 Git）
│   ├── reminders_data.json
│   ├── todo_data.json
│   └── ...              
└── deploy.sh              # 一键部署脚本
```


## 🙏 致谢

- [NoneBot2](https://nonebot.dev/) - 优秀的 Python 异步机器人框架
- [NapCat](https://github.com/NapNeko/NapCatQQ) - QQ 协议端
- [OneBot](https://onebot.dev/) - 聊天机器人应用接口标准

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证。



<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！⭐**

Made with ❤️ by [Aununo]

</div>
