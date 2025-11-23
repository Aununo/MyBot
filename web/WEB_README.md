# MyBot Web 管理界面

🎨 **现代化的 Web 可视化管理面板，让机器人管理更简单、更高效！**

## ✨ 功能特性

- 📊 **仪表盘** - 数据概览、系统状态实时监控
- ⏰ **提醒管理** - 查看、添加、删除提醒任务
- ✅ **待办事项** - 工作/娱乐分类管理
- ⏳ **倒计时** - 可视化事件倒计时追踪
- 📈 **使用统计** - 数据可视化图表分析

## 🎨 设计亮点

- 🌙 **深色主题** - 舒适的暗色调配色
- 🔮 **毛玻璃效果** - 现代化的视觉体验
- 🎭 **渐变配色** - 精心设计的色彩系统
- ✨ **微动画** - 流畅的交互反馈
- 📱 **响应式设计** - 完美支持桌面和移动设备

## 🚀 快速开始

### 方式一：使用启动脚本（推荐）

```bash
# 给脚本执行权限
chmod +x web_server.sh

# 启动服务
./web_server.sh
```

### 方式二：手动启动

```bash
# 1. 安装依赖（如果还没安装）
pip install fastapi uvicorn[standard] python-multipart psutil

# 2. 进入 web 目录
cd web

# 3. 启动服务
python -m uvicorn web_api:app --host 0.0.0.0 --port 8000 --reload
```

### 访问界面

- 🌐 **Web 界面**: http://localhost:8000
- 📚 **API 文档**: http://localhost:8000/docs
- 🔍 **健康检查**: http://localhost:8000/health

## 📁 项目结构

```
web/
├── web_api.py              # FastAPI 后端服务
└── static/
    ├── index.html          # 主页面
    ├── style.css           # 样式文件
    └── app.js              # 前端逻辑
```

## 🔌 API 端点

### 提醒管理
- `GET /api/reminders` - 获取所有提醒
- `GET /api/reminders/{user_id}` - 获取用户提醒
- `POST /api/reminders/{user_id}` - 创建提醒
- `DELETE /api/reminders/{user_id}/{job_id}` - 删除提醒

### 待办事项
- `GET /api/todos` - 获取所有待办
- `GET /api/todos/{user_id}` - 获取用户待办
- `POST /api/todos/{user_id}` - 创建待办
- `PUT /api/todos/{user_id}/{category}/{index}` - 更新待办
- `DELETE /api/todos/{user_id}/{category}/{index}` - 删除待办

### 倒计时
- `GET /api/countdowns` - 获取所有倒计时
- `GET /api/countdowns/{user_id}` - 获取用户倒计时
- `POST /api/countdowns/{user_id}` - 创建倒计时
- `DELETE /api/countdowns/{user_id}/{event_name}` - 删除倒计时

### 统计数据
- `GET /api/usage/overview` - 总体统计
- `GET /api/usage/hourly` - 按小时统计
- `GET /api/usage/daily` - 按日期统计
- `GET /api/usage/weekday` - 按星期统计

### 系统状态
- `GET /api/status` - 获取系统状态（CPU、内存、磁盘）

## ⚙️ 配置说明

### 数据文件路径

Web API 默认读取 `/app/data` 目录下的数据文件：
- `reminders_data.json` - 提醒数据
- `todo_data.json` - 待办事项数据
- `countdown_data.json` - 倒计时数据
- `usage_data.json` - 使用统计数据

如果 `/app/data` 不存在，会自动回退到 `MyBot/data` 目录。

### 端口配置

默认端口为 `8000`，可在启动时修改：

```bash
uvicorn web_api:app --host 0.0.0.0 --port 8080
```

## ⚠️ 重要提示

1. **数据同步**: Web 界面直接读写 JSON 数据文件，与机器人共享数据
2. **提醒生效**: 通过 Web 添加的提醒需要**重启机器人**才能注册到调度器
3. **安全性**: 建议在**内网环境**使用，或添加身份验证机制
4. **并发安全**: 机器人运行时修改数据可能存在竞争条件

## 🎯 使用技巧

### 快速查找
- 在提醒页面使用搜索框快速筛选
- 支持按事件名、用户ID、会话ID 搜索

### 待办管理
- 直接点击复选框完成/取消完成
- 鼠标悬停显示删除按钮
- 分类计数实时更新

### 倒计时
- 自动计算剩余时间
- 过期事件特殊标记
- 支持实时刷新

### 数据可视化
- 24小时活跃时段柱状图
- 星期分布环形图
- 30天趋势折线图

## 🛠️ 故障排查

### 启动失败
```bash
# 检查依赖是否安装
pip list | grep -E "fastapi|uvicorn|psutil"

# 重新安装
pip install -r requirements.txt
```

### 数据不显示
- 检查数据文件是否存在：`ls data/`
- 查看浏览器控制台错误信息
- 检查 API 响应：访问 `/docs` 测试端点

### 端口被占用
```bash
# 查找占用端口的进程
lsof -i:8000

# 更换端口启动
uvicorn web_api:app --port 8001
```

## 🔮 未来计划

- [ ] 用户认证与权限管理
- [ ] WebSocket 实时数据推送
- [ ] 机器人日志查看
- [ ] 插件配置界面
- [ ] 多语言支持
- [ ] 黑暗/明亮主题切换
- [ ] 导出数据功能

## 📝 开发说明

### 技术栈
- **Backend**: FastAPI + Uvicorn
- **Frontend**: 原生 HTML/CSS/JavaScript
- **Charts**: Chart.js
- **Fonts**: Google Fonts (Inter, Outfit)

### 本地开发
```bash
# 开发模式（自动重载）
uvicorn web_api:app --reload

# 查看 API 文档
open http://localhost:8000/docs
```

## 📄 许可证

本项目采用 [MIT](../LICENSE) 许可证。

---

💡 **提示**: 首次使用建议先查看 [API 文档](http://localhost:8000/docs) 了解所有功能！
