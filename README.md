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
- **状态监控** - 支持基础状态查询与运行情况检查
- **OpenClaw Bridge** - 可将 QQ 消息桥接到 OpenClaw，支持更强的 Agent / LLM 对话能力

## 📦 插件列表

### 官方插件
- **apscheduler** - 定时任务调度支持
- **status** - 系统状态监控（`/status`）

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
- **summary** - 群聊内容总结 (`/总结`)
- **copywriting** - 文案生成 (`/文案`)
- **quote** - 消息截图 (`/save`)
- **bilibili** - B 站视频解析（群聊自动触发）
- **relay** - 群内接龙（`/接龙`）
- **email_notifier** - 检查邮箱新邮件（`/check_email`）
- **usage** - 查看命令使用情况（`/usage`）
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
- `ONEBOT_WS_URLS` / 反向 WebSocket 对接配置

如果要启用 OpenClaw Bridge，建议同时关注：
- `OPENCLAW_AGENT_ID`
- `OPENCLAW_BRIDGE_USE_LOCAL`
- `OPENCLAW_BRIDGE_TIMEOUT`
- `OPENCLAW_AUDIO_MODE`
- `OPENCLAW_IMAGE_MODE`

### 4. 配置 NapCat / OneBot 反向 WebSocket

NoneBot 侧监听地址示例：

```env
PORT=8080
ONEBOT_ACCESS_TOKEN='temp123456'
```

NapCat 侧示例配置：

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
        "url": "ws://127.0.0.1:8080/onebot/v11/ws",
        "messagePostFormat": "array",
        "reportSelfMessage": true,
        "reconnectInterval": 5000,
        "token": "temp123456",
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

### 5. 启动机器人

```bash
source .venv/bin/activate
python bot.py
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
```

## 📁 项目结构

```text
MyBot/
├── bot.py                  # NoneBot 入口文件
├── pyproject.toml          # 项目配置
├── requirements.txt        # Python 依赖
├── env.example             # 环境变量模板
├── README.md               # 项目说明
├── LICENSE                 # 许可证
├── src/
│   └── plugins/
│       ├── openclaw_bridge.py
│       ├── remind.py
│       ├── todo.py
│       ├── weather.py
│       └── ...
├── data/                   # 数据持久化目录
└── napcat_qq_data/         # NapCat 数据目录
```

## 🙏 致谢

- [NoneBot2](https://nonebot.dev/) - Python 异步机器人框架
- [NapCat](https://github.com/NapNeko/NapCatQQ) - QQ 协议端
- [OneBot](https://onebot.dev/) - 聊天机器人接口标准
- [OpenClaw](https://github.com/openclaw/openclaw) - Agent / LLM 系统能力支持

## 📄 许可证

本项目基于 **MIT License** 开源，详见 [LICENSE](LICENSE) 文件。
