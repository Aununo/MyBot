# MyBot

基于 **NoneBot2 + NapCat(OneBot V11) + OpenClaw Bridge** 的 QQ 机器人。

- 群聊/私聊命令插件（提醒、待办、课表、天气、图片等）
- Bilibili 链接自动解析（合并转发样式）
- 可桥接到 OpenClaw 做 Agent/LLM 对话

---

## 1. 快速开始

### 1) 环境要求

- Linux / macOS / WSL2
- Python 3.10+
- 可用的 NapCat（OneBot V11）

### 2) 安装

```bash
git clone https://github.com/Aununo/MyBot.git
cd MyBot
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp env.example .env
```

### 3) 启动

```bash
# 启动主 bot
./start_mybot.sh

# （可选）启动 B 站代理服务
./start_bilibili_server.sh
```

---

## 2. NapCat 连接配置（关键）

NoneBot 默认监听：`ws://127.0.0.1:8080/onebot/v11/ws`

NapCat 侧建议：

```json
{
  "network": {
    "websocketClients": [
      {
        "name": "nonebot",
        "enable": true,
        "url": "ws://127.0.0.1:8080/onebot/v11/ws",
        "messagePostFormat": "array",
        "reportSelfMessage": true,
        "reconnectInterval": 5000,
        "token": "<ONEBOT_ACCESS_TOKEN>",
        "debug": false,
        "heartInterval": 30000
      }
    ]
  },
  "parseMultMsg": true
}
```

---

## 3. Bilibili 解析说明

### 功能

群聊出现 B 站链接时自动触发，默认发送 **合并转发消息**：

1. 标题 / UP 主 / 数据
2. 封面图
3. 简介 + 原视频链接
4. 代理播放链接（含有效期）

若平台对图片节点兼容异常，会自动降级为纯文本合并转发，再降级为普通文本。

### 需要的环境变量（`.env`）

- `BILI_SESSDATA`
- `BILI_BILI_JCT`
- `BILI_DEDEUSERID`
- `BILI_PROXY_BASE_URL`（例如 `https://aununo.xyz`）
- `BILI_PROXY_HOST`（默认 `127.0.0.1`）
- `BILI_PROXY_PORT`（默认 `8091`）
- `BILI_PROXY_TTL`（默认 `3600`）

> 如果你用 HTTPS 域名做直链，证书必须覆盖你配置的域名。

---

## 4. OpenClaw Bridge

桥接插件：`src/plugins/openclaw_bridge.py`

常用变量：

- `OPENCLAW_AGENT_ID=main`
- `OPENCLAW_BRIDGE_USE_LOCAL=true`
- `OPENCLAW_BRIDGE_TIMEOUT=180`
- `OPENCLAW_IMAGE_MODE=true`
- `OPENCLAW_AUDIO_MODE=true`

---

## 5. 常用维护命令

```bash
# 语法检查
python -m py_compile bot.py bilibili_server.py src/plugins/*.py

# 查看日志
tail -f logs/mybot.log
tail -f logs/bilibili_server.log
```

---

## 6. 项目结构

```text
MyBot/
├── bot.py
├── bilibili_server.py
├── start_mybot.sh
├── start_bilibili_server.sh
├── env.example
├── requirements.txt
├── pyproject.toml
└── src/plugins/
    ├── openclaw_bridge.py
    ├── bilibili.py
    ├── remind.py
    ├── todo.py
    ├── schedule.py
    └── ...
```

---

## License

MIT
