<div align="center">

# 🦀MyBot

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![NoneBot](https://img.shields.io/badge/NoneBot-2.4.3-green.svg)](https://nonebot.dev/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Bridge-orange.svg)](https://github.com/openclaw/openclaw)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

基于 NoneBot2、NapCat 与 OpenClaw Bridge 的 QQ 机器人，支持丰富功能插件以及 Agent 对话能力。

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [插件列表](#-插件列表) • [项目结构](#-项目结构)

</div>

## ✨ 功能特性

- **丰富插件** - 内置提醒、待办、课表、天气、图片、B站解析等功能
- **数据持久化** - 自动保存数据，重启不丢失
- **易于扩展** - 模块化设计，便于继续添加自定义插件
- **OpenClaw Bridge** - 可将 QQ 消息桥接到 OpenClaw，支持更强的 Agent / LLM 对话能力

## 📦 插件列表

### 官方插件
- **apscheduler** - 定时任务调度支持

### 自定义插件
- **help** - 查看所有命令帮助 (`/help`)
- **ping** - 快速连通性检查 (`/ping`)
- **status** - 服务器状态查询 (`/status`，支持戳一戳触发)
- **schedule** - 个人课程表管理 (`/今日课表`)
- **remind** - 灵活的提醒功能 (`/remind`)
- **todo** - 待办事项管理 (`/todo`)
- **countdown** - 事件倒计时管理 (`/countdown`, `/倒计时`)
- **eat** - 今天吃什么推荐 (`/android`, `/apple`)
- **weather** - 城市天气查询 (`/天气 北京`)
- **latex** - LaTeX 公式渲染 (`/latex E=mc^2`)
- **pic** - 图片管理 (`/savepic`, `/sendpic`)
- **quote** - 消息截图 (`/save`)
- **bilibili** - B 站视频解析（群聊自动触发）
- **email_notifier** - 检查邮箱新邮件（`/check_email`）
- **openclaw_bridge** - OpenClaw 对话桥接（群聊 @机器人 / 私聊可触发）

## 🚀 快速开始

### 前置要求

- Linux / WSL2 / macOS
- Python 3.10+
- Git
- 已安装并可使用的 QQ 协议端（如 NapCat）
- 本机可直接调用 `openclaw` 命令

### 1. 克隆项目

```bash
git clone https://github.com/Aununo/MyBot.git
cd MyBot
```

### 2. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp env.example .env
```

至少需要根据你的实际环境修改：
- `SUPERUSERS`
- `PORT`

如果要启用 OpenClaw Bridge，建议同时关注：
- `OPENCLAW_AGENT_ID`
- `OPENCLAW_BRIDGE_USE_LOCAL`
- `OPENCLAW_BRIDGE_TIMEOUT`
- `OPENCLAW_AUDIO_MODE`
- `OPENCLAW_IMAGE_MODE`

### 4. 配置 NapCat / OneBot 反向 WebSocket

NoneBot 侧 `.env` 示例：

```env
HOST=0.0.0.0
PORT=8080
ONEBOT_WS_URLS=[]
```

推荐由 **NapCat 主动反向连接** 到 NoneBot：
- 反向 WebSocket 地址：`ws://127.0.0.1:8080/onebot/v11/ws`
- 如果部署在同一台机器，通常 **不需要 token**

NapCat 侧示例配置：

```json
{
  "network": {
    "httpServers": [],
    "httpClients": [],
    "httpSseServers": [],
    "websocketServers": [],
    "websocketClients": [
      {
        "name": "mybot-reverse-ws",
        "enable": true,
        "url": "ws://127.0.0.1:8080/onebot/v11/ws",
        "reportSelfMessage": false,
        "messagePostFormat": "array",
        "token": "",
        "debug": false,
        "heartInterval": 30000,
        "reconnectInterval": 5000
      }
    ]
  }
}
```

如果是无桌面服务器，可配合 `screen + xvfb-run -a qq --no-sandbox` 启动 NapCat/QQ；登录时扫码即可。

### 5. 启动机器人

```bash
source .venv/bin/activate
python bot.py
```

项目内也提供了两个直接启动脚本：

```bash
# 启动 NoneBot 本体
bash start_mybot.sh

# 启动 B 站代理服务（给 bilibili 插件生成可访问代理链接）
bash start_bilibili_server.sh
```

如果你使用 `screen` 管理进程，可参考：

```bash
# MyBot
screen -S mybot
cd /path/to/MyBot
bash start_mybot.sh

# Bilibili 代理服务
screen -S bilibili
cd /path/to/MyBot
bash start_bilibili_server.sh

# NapCat / QQ
screen -S napcat
# 然后在该会话中启动 NapCat/QQ
```

## 🔧 常用命令

```bash
# 启动
source .venv/bin/activate
python bot.py

# 重新安装依赖
pip install -r requirements.txt

# 语法检查
python -m compileall src bot.py

# 查看日志（如果你用了 screen / 重定向）
tail -f logs/mybot.log
```

## 📁 项目结构

```text
MyBot/
├── bot.py                  # NoneBot 入口文件
├── pyproject.toml          # 项目配置
├── data/                   # 数据持久化目录
├── README.md               # 项目说明
├── LICENSE                 # 许可证
├── src/
│   └── plugins/
│       ├── openclaw_bridge.py
│       ├── status.py
│       ├── remind.py
│       ├── todo.py
│       ├── weather.py
│       └── ...
├── env.example             # 环境变量模板
└── requirements.txt        # Python 依赖
```

## 🙏 致谢

- [NoneBot2](https://nonebot.dev/) - Python 异步机器人框架
- [NapCat](https://github.com/NapNeko/NapCatQQ) - QQ 协议端
- [OneBot](https://onebot.dev/) - 聊天机器人接口标准
- [OpenClaw](https://github.com/openclaw/openclaw) - Agent / LLM 系统能力支持

## 📄 许可证

本项目基于 **MIT License** 开源，详见 [LICENSE](LICENSE) 文件。
