# MyBot 生产环境部署指南

## 📋 前置要求

- Ubuntu/Debian 服务器
- 域名 DNS 已指向服务器 IP
- sudo 权限
- Python 3.8+

## 🚀 部署步骤

### 1. 服务器准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必需软件
sudo apt install -y nginx python3-pip python3-venv certbot python3-certbot-nginx git

# 安装 Python 依赖
sudo pip3 install fastapi uvicorn[standard] python-multipart psutil
```

### 2. 克隆项目

```bash
# 克隆到服务器
cd /home/aununo
git clone https://github.com/your_username/MyBot.git
cd MyBot

# 创建数据目录
mkdir -p data
chmod 755 data
```

### 3. 配置环境变量

```bash
# 复制环境变量模板
cp deployment/env.web.example .env.web

# 编辑配置，设置强密码
nano .env.web

# 内容示例:
# WEB_ADMIN_USERNAME=your_admin_name
# WEB_ADMIN_PASSWORD=YourVerySecurePassword123!@#

# 加载环境变量到 systemd 服务
# (已在 mybot-web.service 中配置)
```

### 4. 配置 Systemd 服务

```bash
# 复制服务文件
sudo cp deployment/mybot-web.service /etc/systemd/system/

# **重要**: 编辑服务文件，修改环境变量
sudo nano /etc/systemd/system/mybot-web.service
# 修改:
# Environment="WEB_ADMIN_USERNAME=你的用户名"
# Environment="WEB_ADMIN_PASSWORD=你的强密码"

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start mybot-web

# 设置开机自启
sudo systemctl enable mybot-web

# 检查状态
sudo systemctl status mybot-web
```

### 5. DNS 配置

在您的 DNS 提供商添加 A 记录:

```
类型: A
主机: bot
值: 您的服务器IP
TTL: 自动/300
```

等待 DNS 传播 (通常 5-10 分钟)

### 6. 配置 Nginx

```bash
# 复制 Nginx 配置
sudo cp deployment/nginx_bot.conf /etc/nginx/sites-available/bot.aununo.xyz

# 创建软链接
sudo ln -s /etc/nginx/sites-available/bot.aununo.xyz /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 如果测试通过，重启 Nginx
sudo systemctl restart nginx
```

### 7. 申请SSL证书 (Let's Encrypt)

```bash
# 使用 Certbot 自动申请并配置
sudo certbot --nginx -d bot.aununo.xyz

# 按提示操作:
# 1. 输入邮箱
# 2. 同意服务条款
#  3. 选择是否重定向HTTP到HTTPS (建议选择是)

# 测试自动续期
sudo certbot renew --dry-run

# Certbot 会自动添加 cron job 来续期证书
```

### 8. 验证部署

访问 `https://bot.aununo.xyz`

应该看到:
1. ✅ 浏览器显示安全锁图标 (HTTPS)
2. ✅ 弹出登录框要求输入用户名密码
3. ✅ 登录后显示管理界面

## 🔧 故障排查

### 服务无法启动

```bash
# 查看服务日志
sudo journalctl -u mybot-web -f

# 查看详细错误
sudo journalctl -u mybot-web --since "10 minutes ago"

# 手动测试
cd /home/aununo/MyBot/web
python3 -m uvicorn web_api:app --host 127.0.0.1 --port 8000
```

### Nginx 错误

```bash
# 查看错误日志
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/bot.aununo.xyz.error.log

# 测试配置文件
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### SSL 证书问题

```bash
# 查看证书状态
sudo certbot certificates

# 手动续期
sudo certbot renew

# 如果失败，检查防火墙
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### 无法访问

```bash
# 检查服务是否运行
sudo systemctl status mybot-web
sudo systemctl status nginx

# 检查端口监听
sudo netstat -tlnp | grep 8000
sudo netstat -tlnp | grep 80

# 检查防火墙
sudo ufw status
sudo ufw allow 'Nginx Full'
```

## 🔐 安全建议

1. **强密码**: 使用至少 16 位的强密码
2. **定期更换**: 每 3-6 个月更换密码
3. **防火墙**: 只开放必要端口 (80, 443)
4. **日志监控**: 定期检查访问日志
5. **系统更新**: 定期更新系统和依赖

```bash
# 定期更新
sudo apt update && sudo apt upgrade -y

# 查看访问日志
sudo tail -f /var/log/nginx/bot.aununo.xyz.access.log
```

## 📊 日常维护

### 重启服务

```bash
sudo systemctl restart mybot-web
```

### 查看日志

```bash
# Web 服务日志
sudo journalctl -u mybot-web -f

# Nginx 访问日志
sudo tail -f /var/log/nginx/bot.aununo.xyz.access.log

# Nginx 错误日志
sudo tail -f /var/log/nginx/bot.aununo.xyz.error.log
```

### 更新代码

```bash
cd /home/aununo/MyBot
git pull origin main
sudo systemctl restart mybot-web
```

## 🎯 可选增强

### IP 白名单

在 Nginx 配置中添加:

```nginx
location / {
    allow 你的IP;
    deny all;
    proxy_pass http://127.0.0.1:8000;
}
```

### 监控告警

使用 UptimeRobot 或类似服务监控:
- URL: https://bot.aununo.xyz/health
- 间隔: 5分钟
- 告警: 邮件/Telegram

## 📞 支持

如遇到问题，请检查:
1. 服务日志: `journalctl -u mybot-web`
2. Nginx日志: `/var/log/nginx/`
3. 系统日志: `dmesg`
