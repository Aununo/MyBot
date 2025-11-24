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

- **Docker 部署** - 一键部署，无需手动配置
- **丰富插件** - 若干内置插件，覆盖学习、生活、娱乐
- **数据持久化** - 自动保存数据，重启不丢失
- **Web 管理界面** - 现代化的可视化管理面板，支持远程管理
- **易于扩展** - 模块化设计，轻松添加自定义插件
- **状态监控** - 实时查看 CPU、内存、运行状态

## 📦 插件列表

### 官方插件
- **apscheduler** - 定时任务调度支持
- **status** - 详细系统状态监控（`/status`）

### 自定义插件

- **help** - 查看所有命令帮助 (`/help`)
- **ping** - 快速状态检查 (`/ping`)
- **schedule** - 个人课程表管理 (`/今日课表`)
- **remind** - 灵活的提醒功能 (`/remind`)
- **todo** - 待办事项管理 (`/todo`)
- **countdown** - 事件倒计时管理 (`/time`)
- **eat** - 今天吃什么推荐 (`/android`, `/apple`)
- **weather** - 城市天气查询 (`/天气 北京`)
- **latex** - LaTeX 公式渲染 (`/latex E=mc^2`)
- **pic** - 图片管理 (`/savepic`, `/sendpic`)
- **relay** - 群内接龙（`/接龙`）
- **email_notifier** - 检查邮箱新邮件（`/check_email`）
- **usage** - 查看命令使用情况（`/usage`）


## 🚀 快速开始

### 前置要求

- Git
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

- 安装 Napcat

```bash
curl -o napcat.sh https://nclatest.znin.net/NapNeko/NapCat-Installer/main/script/install.sh && chmod +x napcat.sh

bash napcat.sh # 按照指引安装即可
```

- 安装 Nonebot

```bash
python3 -m venv .venv
source .venv/bin/activate # 新建虚拟环境

pip install nb-cli
nb create 
# 按照指引完成配置
nb run
```

详情请见 [nonebot 官方文档](https://nonebot.dev/docs/quick-start)

- 通信

修改 nonebot 的 `.env.prod`：

```
PORT = 如果 8080 端口被占用，根据你的需要更改
ONEBOT_ACCESS_TOKEN='temp123456'
```

此处为Napcat代理相关配置：

```json
{
  "network": {
    "httpServers": [],
    "httpClients": [],
    "websocketServers": [],
    "websocketClients": [
      {
        "name": "nonebot",
        "enable": true,
        "url": "ws://127.0.0.1:8080/onebot/v11/ws", // 与 nonebot 的 PORT 一致
        "messagePostFormat": "array",
        "reportSelfMessage": true,
        "reconnectInterval": 5000,
        "token": "temp123456", // 与 nonebot 的 ONEBOT_ACCESS_TOKEN 一致
        "debug": false,
        "heartInterval": 30000
      }
    ]
  },
  "musicSignUrl": "",
  "enableLocalFile2Url": false,
  "parseMultMsg": true
}
```

## 🌐 Web 管理界面

全新的现代化 Web 管理面板，让您随时随地管理机器人！

详见 [deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md) 完整测试与部署指南。

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
MyBot/
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
│       ├── eat.py
│       └── ...
├── web/                    # Web 管理界面 (NEW!)
│   ├── web_api.py         # FastAPI 后端
│   ├── static/
│   │   ├── index.html     # 前端页面
│   │   ├── app.js         # JavaScript 逻辑
│   │   └── style.css      # 样式表
│   └── web_server.sh      # 启动脚本
├── deployment/             # 生产部署配置 (NEW!)
│   ├── DEPLOYMENT.md      # 部署文档
│   ├── nginx_bot.conf     # Nginx 配置
│   ├── mybot-web.service  # Systemd 服务
│   └── env.web.example    # 环境变量模板
├── data/                   # 数据持久化目录
│   ├── reminders_data.json
│   ├── todo_data.json
│   ├── eat_data.json
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
