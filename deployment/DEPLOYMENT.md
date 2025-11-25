# MyBot 生产环境部署指南

本文档提供 MyBot React 前端 + FastAPI 后端的单服务器部署方案。

---

## 系统要求

- **OS**: Ubuntu 20.04+ / Debian 10+
- **Python**: 3.8+
- **Node.js**: 16.x+
- **Nginx**: 1.18+（可选但推荐）

---

## 部署步骤

### 1. 准备环境

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3 python3-pip python3-venv nginx git

# 安装 Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 设置 Docker 的官方 APT 仓库
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg

# 添加 Docker 的官方 GPG 密钥
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 设置 Docker 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

sudo systemctl start docker
```

### 2. 克隆项目

```bash
cd /var/www
sudo git clone https://github.com/yourusername/MyBot.git
sudo chown -R $USER:$USER MyBot
cd MyBot
```

### 3. 配置环境变量

项目根目录的 `deploy.sh` 脚本已包含交互式环境变量配置，会自动引导你输入所有必要的配置项：

```bash
# 在项目根目录执行
chmod +x deploy.sh
./deploy.sh
```

脚本会自动：
- 复制 `env.example` 到 `.env`
- 交互式输入管理员 QQ 号、天气 API Key、邮箱配置等
- 验证必填项并设置默认值


### 4. 构建前端

```bash
cd /var/www/MyBot/web/frontend

# 安装依赖
npm install

# 生产构建
npm run build

# 验证构建产物
ls -lh dist/
```

### 5. 配置 Nginx

创建配置文件：

```bash
sudo nano /etc/nginx/sites-available/mybot
```

写入：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 日志
    access_log /var/log/nginx/mybot_access.log;
    error_log /var/log/nginx/mybot_error.log;

    # 前端静态文件
    root /var/www/MyBot/web/frontend/dist;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # API 代理 (必须在静态文件规则之前)
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }

    # 静态资源缓存 (注意：不匹配 /api 路径下的文件)
    location ~* ^/(?!api/).*\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA 路由 (必须在最后)
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/mybot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 6. 配置后端服务

创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

查看 requirements.txt 中的web依赖.

创建 systemd 服务：

```bash
sudo nano /etc/systemd/system/mybot-web.service
```

写入：

```ini
[Unit]
Description=MyBot Web API Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/MyBot/web
Environment="PATH=/var/www/MyBot/.venv/bin"
EnvironmentFile=/var/www/MyBot/.env
ExecStart=/var/www/MyBot/.venv/bin/uvicorn web_api:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start mybot-web
sudo systemctl enable mybot-web
sudo systemctl status mybot-web
```

### 7. 配置 HTTPS（可选但推荐）

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo systemctl status certbot.timer
```

### 8. 验证部署

```bash
# 检查后端
curl http://localhost:8000/health

# 检查前端
curl http://localhost/

# 访问
# http://your-domain.com
```

---

## 安全配置

### 1. 修改默认密码

```bash
nano .env
# 设置强密码
WEB_ADMIN_USERNAME=your_username
WEB_ADMIN_PASSWORD=your_strong_password
```

### 2. 配置防火墙

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. 禁用 API 文档（生产环境）

```python
# web/web_api.py
app = FastAPI(
    docs_url=None if os.getenv("ENVIRONMENT") == "production" else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT") == "production" else "/redoc",
)
```

---

## 维护

### 健康检查

```bash
curl http://localhost:8000/health
# 应返回: {"status":"healthy","timestamp":"..."}
```

### 查看日志

```bash
# Nginx 日志
sudo tail -f /var/log/nginx/mybot_access.log
sudo tail -f /var/log/nginx/mybot_error.log

# 后端日志
sudo journalctl -u mybot-web -f
```

### 更新部署

**更新前端：**
```bash
cd /var/www/MyBot/web/frontend
git pull
npm install
npm run build
sudo systemctl reload nginx
```

**更新后端：**
```bash
cd /var/www/MyBot
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart mybot-web
```

---

## 故障排查

### 前端显示空白

```bash
# 检查构建产物
ls -la /var/www/MyBot/web/frontend/dist/

# 检查 Nginx 配置
sudo nginx -t
```

### API 请求失败

```bash
# 检查后端状态
sudo systemctl status mybot-web

# 查看详细日志
sudo journalctl -u mybot-web -n 100
```

### 502 错误

```bash
# 后端未运行
sudo systemctl start mybot-web

# 测试后端
curl http://localhost:8000/health
```

---

## 性能优化

### 1. Gzip 压缩

Nginx 配置中已启用，可调整级别：
```nginx
gzip_comp_level 6;  # 1-9
```

### 2. CDN 加速

将 `dist/assets/` 上传到 CDN，修改 HTML 引用。

### 3. 后端 workers

根据 CPU 核心数调整：
```bash
# systemd service
ExecStart=... --workers 4
```

---

## 备份

```bash
#!/bin/bash
# 每日备份脚本
BACKUP_DIR="/var/backups/mybot"
DATE=$(date +%Y%m%d)

# 备份数据
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" /var/www/MyBot/data/

# 备份配置
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" /var/www/MyBot/.env

# 保留30天
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +30 -delete
```

添加到 crontab：
```bash
0 2 * * * /usr/local/bin/mybot-backup.sh
```

---

## 总结

部署完成后，您应该有：

- ✅ Nginx 服务前端静态文件
- ✅ FastAPI 后端在 8000 端口
- ✅ Systemd 自动重启服务
- ✅ HTTPS 加密（如果配置）
- ✅ 定期备份机制

访问 `https://your-domain.com` 开始使用！

如有问题，请查看故障排查章节或提交 Issue。
