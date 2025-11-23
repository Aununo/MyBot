// ============= 全局配置 =============
const API_BASE_URL = window.location.origin;

// ============= 工具函数 =============

// 显示 Toast 通知
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => container.removeChild(toast), 300);
    }, 3000);
}

// API 请求封装
async function apiRequest(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast(`请求失败: ${error.message}`, 'error');
        throw error;
    }
}

// 格式化时间差
function formatTimeDelta(targetDate) {
    const now = new Date();
    const target = new Date(targetDate);
    const diff = target - now;

    if (diff < 0) {
        return '已过期';
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (days > 0) {
        return `${days}天${hours}小时`;
    } else if (hours > 0) {
        return `${hours}小时${minutes}分钟`;
    } else {
        return `${minutes}分钟`;
    }
}

// ============= 页面路由 =============

function navigateTo(pageName) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    // 显示目标页面
    const targetPage = document.getElementById(`page-${pageName}`);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    // 更新导航链接状态
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.dataset.page === pageName) {
            link.classList.add('active');
        }
    });

    // 加载对应页面数据
    switch (pageName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'reminders':
            loadReminders();
            break;
        case 'todos':
            loadTodos();
            break;
        case 'countdowns':
            loadCountdowns();
            break;
        case 'usage':
            loadUsageStats();
            break;
        case 'images':
            loadImages();
            break;
        case 'eat':
            loadEatData();
            break;
    }
}

// ==============Eat 吃什么管理页面 =============

async function loadEatData() {
    try {
        const data = await apiRequest('/api/eat');

        // 渲染 Android 列表
        renderEatList('android', data.android || []);

        // 渲染 Apple 列表
        renderEatList('apple', data.apple || []);

    } catch (error) {
        console.error('Failed to load eat data:', error);
    }
}

function renderEatList(listName, foods) {
    const listContainer = document.getElementById(`${listName}-list`);
    const countElement = document.getElementById(`${listName}-count`);

    // 更新计数
    countElement.textContent = foods.length;

    // 清空列表
    listContainer.innerHTML = '';

    if (foods.length === 0) {
        listContainer.innerHTML = '<div class="loading">列表为空</div>';
        return;
    }

    // 渲染食物项
    foods.forEach((food, index) => {
        const item = createEatItem(listName, food, index);
        listContainer.appendChild(item);
    });
}

function createEatItem(listName, food, index) {
    const item = document.createElement('div');
    item.className = 'eat-item';

    item.innerHTML = `
        <span class="eat-food-name">${food}</span>
        <button class="eat-delete-btn" onclick="deleteFood('${listName}', '${food}')">
            🗑️
        </button>
    `;

    return item;
}

async function addFood(listName) {
    const inputElement = document.getElementById(`${listName}-input`);
    const foodName = inputElement.value.trim();

    if (!foodName) {
        showToast('请输入食物名称', 'error');
        return;
    }

    try {
        const params = new URLSearchParams();
        params.append('food', foodName);

        await apiRequest(`/api/eat/${listName}?${params.toString()}`, {
            method: 'POST'
        });

        showToast(`已添加 ${foodName}`, 'success');
        inputElement.value = ''; // 清空输入框
        loadEatData(); // 刷新列表

    } catch (error) {
        console.error('Failed to add food:', error);
        if (error.message.includes('400')) {
            showToast('该食物已存在', 'error');
        }
    }
}

async function deleteFood(listName, foodName) {
    if (!confirm(`确定要删除 "${foodName}" 吗？`)) {
        return;
    }

    try {
        await apiRequest(`/api/eat/${listName}/${encodeURIComponent(foodName)}`, {
            method: 'DELETE'
        });

        showToast(`已删除 ${foodName}`, 'success');
        loadEatData(); // 刷新列表

    } catch (error) {
        console.error('Failed to delete food:', error);
    }
}

// ============= 页面路由 =============

function navigateTo(pageName) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });

    // 显示目标页面
    const targetPage = document.getElementById(`page-${pageName}`);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    // 更新导航链接状态
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.dataset.page === pageName) {
            link.classList.add('active');
        }
    });

    // 加载对应页面数据
    switch (pageName) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'reminders':
            loadReminders();
            break;
        case 'todos':
            loadTodos();
            break;
        case 'countdowns':
            loadCountdowns();
            break;
        case 'usage':
            loadUsageStats();
            break;
        case 'images':
            loadImages();
            break;
        case 'eat':
            loadEatData();
            break;
    }
}

// 初始化路由
document.addEventListener('DOMContentLoaded', () => {
    // 导航链接点击事件
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            window.location.hash = page;
            navigateTo(page);
        });
    });

    // 根据 URL hash 导航
    const hash = window.location.hash.slice(1) || 'dashboard';
    navigateTo(hash);

    // 定期刷新系统状态
    setInterval(loadSystemStatus, 5000);
});

// ============= Dashboard 页面 =============

async function loadDashboard() {
    await Promise.all([
        updateDashboardStats(),
        loadSystemStatus()
    ]);
}

async function updateDashboardStats() {
    try {
        // 获取提醒数量
        const reminders = await apiRequest('/api/reminders');
        const reminderCount = Object.values(reminders).reduce((sum, arr) => sum + arr.length, 0);
        document.getElementById('stat-reminders').textContent = reminderCount;

        // 获取待办数量
        const todos = await apiRequest('/api/todos');
        let todoCount = 0;
        Object.values(todos).forEach(userTodos => {
            if (userTodos.work) todoCount += userTodos.work.filter(t => !t.done).length;
            if (userTodos.play) todoCount += userTodos.play.filter(t => !t.done).length;
        });
        document.getElementById('stat-todos').textContent = todoCount;

        // 获取倒计时数量
        const countdowns = await apiRequest('/api/countdowns');
        const countdownCount = Object.values(countdowns).reduce((sum, obj) => sum + Object.keys(obj).length, 0);
        document.getElementById('stat-countdowns').textContent = countdownCount;

        // 获取本周消息数
        const usage = await apiRequest('/api/usage/overview');
        document.getElementById('stat-messages').textContent = usage.recent_7days || 0;

    } catch (error) {
        console.error('Failed to load dashboard stats:', error);
    }
}

async function loadSystemStatus() {
    try {
        const status = await apiRequest('/api/status');

        // 更新 CPU
        document.getElementById('cpu-value').textContent = `${status.cpu_percent.toFixed(1)}%`;
        document.getElementById('cpu-progress').style.width = `${status.cpu_percent}%`;

        // 更新内存
        document.getElementById('memory-value').textContent = `${status.memory_percent.toFixed(1)}%`;
        document.getElementById('memory-progress').style.width = `${status.memory_percent}%`;

        // 更新磁盘
        document.getElementById('disk-value').textContent = `${status.disk_percent.toFixed(1)}%`;
        document.getElementById('disk-progress').style.width = `${status.disk_percent}%`;

    } catch (error) {
        console.error('Failed to load system status:', error);
    }
}

// ============= Reminders 页面 =============

async function loadReminders() {
    try {
        const reminders = await apiRequest('/api/reminders');
        const listContainer = document.getElementById('reminders-list');

        // 清空列表
        listContainer.innerHTML = '';

        // 检查是否有数据
        const hasReminders = Object.keys(reminders).length > 0;
        if (!hasReminders) {
            listContainer.innerHTML = '<div class="loading">暂无提醒数据</div>';
            return;
        }

        // 渲染每个用户的提醒
        Object.entries(reminders).forEach(([userId, userReminders]) => {
            userReminders.forEach(reminder => {
                const card = createReminderCard(userId, reminder);
                listContainer.appendChild(card);
            });
        });

    } catch (error) {
        console.error('Failed to load reminders:', error);
    }
}

function createReminderCard(userId, reminder) {
    const card = document.createElement('div');
    card.className = 'item-card';

    const timeStr = `${String(reminder.hour).padStart(2, '0')}:${String(reminder.minute).padStart(2, '0')}`;
    let typeLabel = '一次性';
    if (reminder.is_daily) typeLabel = '每日';
    if (reminder.interval_days) typeLabel = `每${reminder.interval_days}天`;
    if (reminder.weekdays) typeLabel = '周期';

    card.innerHTML = `
        <div class="item-header">
            <div class="item-title">${reminder.event}</div>
            <div class="item-badge">${typeLabel}</div>
        </div>
        <div class="item-details">
            ⏰ ${timeStr} | 👤 用户 ${userId} | 💬 会话 ${reminder.session_id}
            ${reminder.is_group ? ' | 📢 群聊' : ' | 💌 私聊'}
            ${reminder.mention_all ? ' | @全体' : ''}
        </div>
        <div class="item-actions">
            <button class="btn btn-danger btn-small" onclick="deleteReminder('${userId}', '${reminder.job_id}')">
                🗑️ 删除
            </button>
        </div>
    `;

    return card;
}

async function deleteReminder(userId, jobId) {
    if (!confirm('确定要删除这个提醒吗？')) return;

    try {
        await apiRequest(`/api/reminders/${userId}/${jobId}`, { method: 'DELETE' });
        showToast('提醒已删除', 'success');
        loadReminders();
    } catch (error) {
        console.error('Failed to delete reminder:', error);
    }
}

function filterReminders() {
    const searchTerm = document.getElementById('reminder-search').value.toLowerCase();
    const cards = document.querySelectorAll('#reminders-list .item-card');

    cards.forEach(card => {
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(searchTerm) ? 'block' : 'none';
    });
}

// ============= Todos 页面 =============

async function loadTodos() {
    try {
        const todos = await apiRequest('/api/todos');

        let workTodosHTML = '';
        let playTodosHTML = '';
        let workCount = 0;
        let playCount = 0;

        // 渲染所有用户的待办事项
        Object.entries(todos).forEach(([userId, userTodos]) => {
            if (userTodos.work) {
                userTodos.work.forEach((todo, index) => {
                    workTodosHTML += createTodoHTML(userId, 'work', todo, index);
                    if (!todo.done) workCount++;
                });
            }
            if (userTodos.play) {
                userTodos.play.forEach((todo, index) => {
                    playTodosHTML += createTodoHTML(userId, 'play', todo, index);
                    if (!todo.done) playCount++;
                });
            }
        });

        document.getElementById('work-todos').innerHTML = workTodosHTML || '<div class="loading">暂无工作待办</div>';
        document.getElementById('play-todos').innerHTML = playTodosHTML || '<div class="loading">暂无娱乐待办</div>';
        document.getElementById('work-count').textContent = workCount;
        document.getElementById('play-count').textContent = playCount;

    } catch (error) {
        console.error('Failed to load todos:', error);
    }
}

function createTodoHTML(userId, category, todo, index) {
    return `
        <div class="todo-item ${todo.done ? 'done' : ''}">
            <input type="checkbox" class="todo-checkbox" 
                   ${todo.done ? 'checked' : ''} 
                   onchange="toggleTodo('${userId}', '${category}', ${index}, this.checked)">
            <span class="todo-text">${todo.task}</span>
            <small style="color: var(--text-muted); font-size: 0.75rem;">用户 ${userId}</small>
            <button class="todo-delete" onclick="deleteTodo('${userId}', '${category}', ${index})">
                🗑️
            </button>
        </div>
    `;
}

async function toggleTodo(userId, category, index, done) {
    try {
        await apiRequest(`/api/todos/${userId}/${category}/${index}?done=${done}`, { method: 'PUT' });
        loadTodos();
    } catch (error) {
        console.error('Failed to toggle todo:', error);
    }
}

async function deleteTodo(userId, category, index) {
    if (!confirm('确定要删除这个待办事项吗？')) return;

    try {
        await apiRequest(`/api/todos/${userId}/${category}/${index}`, { method: 'DELETE' });
        showToast('待办事项已删除', 'success');
        loadTodos();
    } catch (error) {
        console.error('Failed to delete todo:', error);
    }
}

// ============= Countdowns 页面 =============

async function loadCountdowns() {
    try {
        const countdowns = await apiRequest('/api/countdowns');
        const listContainer = document.getElementById('countdowns-list');

        listContainer.innerHTML = '';

        const hasCountdowns = Object.keys(countdowns).some(userId => Object.keys(countdowns[userId]).length > 0);
        if (!hasCountdowns) {
            listContainer.innerHTML = '<div class="loading">暂无倒计时数据</div>';
            return;
        }

        Object.entries(countdowns).forEach(([userId, userCountdowns]) => {
            Object.entries(userCountdowns).forEach(([eventName, data]) => {
                const card = createCountdownCard(userId, eventName, data);
                listContainer.appendChild(card);
            });
        });

        // 定时更新倒计时
        setTimeout(updateCountdownTimers, 1000);

    } catch (error) {
        console.error('Failed to load countdowns:', error);
    }
}

function createCountdownCard(userId, eventName, data) {
    const card = document.createElement('div');
    card.className = 'countdown-card';
    card.dataset.targetTime = data.time;

    const timeLeft = formatTimeDelta(data.time);
    const dateStr = new Date(data.time).toLocaleString('zh-CN');

    card.innerHTML = `
        <div class="countdown-name">${eventName}</div>
        <div class="countdown-time">${timeLeft}</div>
        <div class="countdown-date">📅 ${dateStr}</div>
        <div class="item-details">👤 用户 ${userId}</div>
        <div class="item-actions">
            <button class="btn btn-danger btn-small" onclick="deleteCountdown('${userId}', '${eventName}')">
                🗑️ 删除
            </button>
        </div>
    `;

    return card;
}

function updateCountdownTimers() {
    document.querySelectorAll('.countdown-card').forEach(card => {
        const targetTime = card.dataset.targetTime;
        if (targetTime) {
            const timeLeftElement = card.querySelector('.countdown-time');
            if (timeLeftElement) {
                timeLeftElement.textContent = formatTimeDelta(targetTime);
            }
        }
    });

    // 每秒更新一次
    if (document.getElementById('page-countdowns').classList.contains('active')) {
        setTimeout(updateCountdownTimers, 1000);
    }
}

async function deleteCountdown(userId, eventName) {
    if (!confirm('确定要删除这个倒计时吗？')) return;

    try {
        await apiRequest(`/api/countdowns/${userId}/${encodeURIComponent(eventName)}`, { method: 'DELETE' });
        showToast('倒计时已删除', 'success');
        loadCountdowns();
    } catch (error) {
        console.error('Failed to delete countdown:', error);
    }
}

// ============= Usage 统计页面 =============

let hourlyChart, weekdayChart, dailyChart;

async function loadUsageStats() {
    try {
        const [hourlyData, weekdayData, dailyData] = await Promise.all([
            apiRequest('/api/usage/hourly'),
            apiRequest('/api/usage/weekday'),
            apiRequest('/api/usage/daily')
        ]);

        renderHourlyChart(hourlyData.hourly_stats);
        renderWeekdayChart(weekdayData.weekday_stats);
        renderDailyChart(dailyData.daily_stats);

    } catch (error) {
        console.error('Failed to load usage stats:', error);
    }
}

function renderHourlyChart(data) {
    const ctx = document.getElementById('hourly-chart');

    if (hourlyChart) {
        hourlyChart.destroy();
    }

    const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`);
    const values = Array.from({ length: 24 }, (_, i) => data[i] || 0);

    hourlyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hours,
            datasets: [{
                label: '消息数量',
                data: values,
                backgroundColor: 'rgba(102, 126, 234, 0.6)',
                borderColor: 'rgba(102, 126, 234, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#b4b4c5' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                x: {
                    ticks: { color: '#b4b4c5' },
                    grid: { display: false }
                }
            }
        }
    });
}

function renderWeekdayChart(data) {
    const ctx = document.getElementById('weekday-chart');

    if (weekdayChart) {
        weekdayChart.destroy();
    }

    const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    const weekdayKeys = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const values = weekdayKeys.map(key => data[key] || 0);

    weekdayChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: weekdayLabels,
            datasets: [{
                data: values,
                backgroundColor: [
                    'rgba(102, 126, 234, 0.8)',
                    'rgba(118, 75, 162, 0.8)',
                    'rgba(79, 172, 254, 0.8)',
                    'rgba(0, 212, 170, 0.8)',
                    'rgba(255, 140, 66, 0.8)',
                    'rgba(245, 87, 108, 0.8)',
                    'rgba(240, 147, 251, 0.8)'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#b4b4c5' }
                }
            }
        }
    });
}

function renderDailyChart(data) {
    const ctx = document.getElementById('daily-chart');

    if (dailyChart) {
        dailyChart.destroy();
    }

    const dates = Object.keys(data).reverse();
    const values = dates.map(date => data[date]);

    dailyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [{
                label: '消息数量',
                data: values,
                borderColor: 'rgba(79, 172, 254, 1)',
                backgroundColor: 'rgba(79, 172, 254, 0.2)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#b4b4c5' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' }
                },
                x: {
                    ticks: { color: '#b4b4c5', maxRotation: 45 },
                    grid: { display: false }
                }
            }
        }
    });
}

// ============= 模态框管理 =============

function openAddReminderModal() {
    document.getElementById('add-reminder-modal').classList.add('active');
}

function openAddTodoModal() {
    document.getElementById('add-todo-modal').classList.add('active');
}

function openAddCountdownModal() {
    document.getElementById('add-countdown-modal').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// 点击模态框外部关闭
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});

// ============= 表单提交 =============

async function submitReminder() {
    const userId = document.getElementById('reminder-user-id').value;
    const event = document.getElementById('reminder-event').value;
    const hour = parseInt(document.getElementById('reminder-hour').value);
    const minute = parseInt(document.getElementById('reminder-minute').value);
    const sessionId = document.getElementById('reminder-session-id').value;
    const isGroup = document.getElementById('reminder-is-group').checked;
    const isDaily = document.getElementById('reminder-is-daily').checked;

    if (!userId || !event || isNaN(hour) || isNaN(minute) || !sessionId) {
        showToast('请填写所有必填字段', 'error');
        return;
    }

    try {
        await apiRequest(`/api/reminders/${userId}`, {
            method: 'POST',
            body: JSON.stringify({
                event,
                hour,
                minute,
                session_id: sessionId,
                is_group: isGroup,
                is_daily: isDaily,
                mention_all: false
            })
        });

        showToast('提醒创建成功！重启机器人后生效', 'success');
        closeModal('add-reminder-modal');
        loadReminders();

        // 清空表单
        document.getElementById('reminder-user-id').value = '';
        document.getElementById('reminder-event').value = '';
        document.getElementById('reminder-hour').value = '';
        document.getElementById('reminder-minute').value = '';
        document.getElementById('reminder-session-id').value = '';
        document.getElementById('reminder-is-group').checked = false;
        document.getElementById('reminder-is-daily').checked = false;

    } catch (error) {
        console.error('Failed to create reminder:', error);
    }
}

async function submitTodo() {
    const userId = document.getElementById('todo-user-id').value;
    const task = document.getElementById('todo-task').value;
    const category = document.getElementById('todo-category').value;

    if (!userId || !task) {
        showToast('请填写所有必填字段', 'error');
        return;
    }

    try {
        await apiRequest(`/api/todos/${userId}`, {
            method: 'POST',
            body: JSON.stringify({ task, category })
        });

        showToast('待办事项创建成功', 'success');
        closeModal('add-todo-modal');
        loadTodos();

        // 清空表单
        document.getElementById('todo-user-id').value = '';
        document.getElementById('todo-task').value = '';

    } catch (error) {
        console.error('Failed to create todo:', error);
    }
}

async function submitCountdown() {
    const userId = document.getElementById('countdown-user-id').value;
    const eventName = document.getElementById('countdown-event').value;
    const time = document.getElementById('countdown-time').value;

    if (!userId || !eventName || !time) {
        showToast('请填写所有必填字段', 'error');
        return;
    }

    // 转换为 ISO 格式
    const isoTime = new Date(time).toISOString();

    try {
        await apiRequest(`/api/countdowns/${userId}`, {
            method: 'POST',
            body: JSON.stringify({ event_name: eventName, time: isoTime })
        });

        showToast('倒计时创建成功', 'success');
        closeModal('add-countdown-modal');
        loadCountdowns();

        // 清空表单
        document.getElementById('countdown-user-id').value = '';
        document.getElementById('countdown-event').value = '';
        document.getElementById('countdown-time').value = '';

    } catch (error) {
        console.error('Failed to create countdown:', error);
    }
}

// ============= Images 图片管理页面 =============

let currentImageFolder = 'pics';
let currentFolderImages = [];

async function loadImages() {
    try {
        const data = await apiRequest(`/api/images/${currentImageFolder}`);
        currentFolderImages = data.images || [];

        const gridContainer = document.getElementById('images-grid');
        const countElement = document.getElementById('current-folder-count');

        // 更新计数
        countElement.textContent = currentFolderImages.length;

        // 清空网格
        gridContainer.innerHTML = '';

        if (currentFolderImages.length === 0) {
            gridContainer.innerHTML = '<div class="loading">该文件夹暂无图片</div>';
            return;
        }

        // 渲染图片卡片
        currentFolderImages.forEach(image => {
            const card = createImageCard(image);
            gridContainer.appendChild(card);
        });

    } catch (error) {
        console.error('Failed to load images:', error);
    }
}

function createImageCard(image) {
    const card = document.createElement('div');
    card.className = 'image-card';

    const sizeKB = (image.size / 1024).toFixed(1);
    const modifiedDate = new Date(image.modified).toLocaleDateString('zh-CN');

    card.innerHTML = `
        <img src="${image.url}" alt="${image.name}" class="image-preview" loading="lazy">
        <div class="image-info">
            <div class="image-name">${image.name}</div>
            <div class="image-meta">
                <span>${sizeKB} KB</span>
                <span>${modifiedDate}</span>
            </div>
        </div>
    `;

    // 点击打开预览
    card.addEventListener('click', () => openImagePreview(image));

    return card;
}

function switchImageFolder(folder) {
    currentImageFolder = folder;

    // 更新选项卡状态
    document.querySelectorAll('.folder-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.folder === folder) {
            tab.classList.add('active');
        }
    });

    // 加载图片
    loadImages();
}

function refreshImages() {
    loadImages();
    showToast('图片列表已刷新', 'success');
}

function openImagePreview(image) {
    // 设置预览内容
    document.getElementById('preview-image-name').textContent = image.name;
    document.getElementById('preview-image').src = image.url;
    document.getElementById('preview-image-size').textContent = (image.size / 1024).toFixed(2) + ' KB';
    document.getElementById('preview-image-modified').textContent = new Date(image.modified).toLocaleString('zh-CN');

    // 设置删除按钮
    const deleteBtn = document.getElementById('delete-preview-image-btn');
    deleteBtn.onclick = () => deleteImage(currentImageFolder, image.name);

    // 打开模态框
    document.getElementById('image-preview-modal').classList.add('active');
}

async function deleteImage(folder, filename) {
    if (!confirm(`确定要删除图片 "${filename}" 吗？`)) {
        return;
    }

    try {
        await apiRequest(`/api/images/${folder}/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });

        showToast('图片已删除', 'success');
        closeModal('image-preview-modal');
        loadImages();  // 刷新列表

    } catch (error) {
        console.error('Failed to delete image:', error);
        showToast('删除失败', 'error');
    }
}

