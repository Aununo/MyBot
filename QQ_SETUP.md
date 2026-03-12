# QQ 机器人部署说明

## 已完成
- MyBot Python 环境已准备到 `.venv`
- `.env` 已写入最小配置
- 反向 WebSocket 目标为 `ws://127.0.0.1:8080/onebot/v11/ws`
- OneBot Access Token 已生成

## 当前阻塞点
NapCat 安装脚本需要 `sudo` 安装系统依赖，本会话无法代输 sudo 密码。

## 你需要手动执行的命令

### 1) 安装 NapCat（rootless + CLI）
```bash
cd /home/aununo
bash ./napcat.sh --docker n --cli y --proxy 0
```

如果它提示 sudo 密码，输入服务器用户 `aununo` 的 sudo 密码即可。

### 2) 启动 MyBot
```bash
cd /home/aununo/MyBot
./start_mybot.sh
```

### 3) 在另一个终端启动 NapCat / QQ
安装完成后，按 NapCat CLI/TUI 的引导：
- 登录 QQ（扫码）
- 新建一个 `reverse_ws` 或 `websocketClients` 连接
- 地址填：`ws://127.0.0.1:8080/onebot/v11/ws`
- Token 填：`JXBZ9_qD6gkKqMnAgJ4-FcMtyp9L2ZWG`

## 验证
连接成功后：
- MyBot 终端应看到 OneBot 连接日志
- 在 QQ 里给机器人发 `/ping`
- 正常应回复 `pong` 或类似在线响应

## 说明
- 当前 `.env` 里未填天气 / Gemini / 邮箱 / B站凭据，这些功能会显示未配置，但不会影响基础 QQ 对话与大部分命令。
- OpenClaw Bridge 已设为本地调用：`OPENCLAW_BRIDGE_USE_LOCAL=true`
