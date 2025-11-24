import { useState, useEffect } from 'react'
import api from '../services/api'
import './Dashboard.css'

function Dashboard({ showToast }) {
    const [stats, setStats] = useState({
        reminders: '-',
        todos: '-',
        countdowns: '-',
        messages: '-',
    })

    const [systemStatus, setSystemStatus] = useState({
        cpu: { value: 0, label: '-' },
        memory: { value: 0, label: '-' },
        disk: { value: 0, label: '-' },
    })

    useEffect(() => {
        loadDashboard()
        const interval = setInterval(loadSystemStatus, 5000)
        return () => clearInterval(interval)
    }, [])

    const loadDashboard = async () => {
        await Promise.all([updateStats(), loadSystemStatus()])
    }

    const updateStats = async () => {
        try {
            const [reminders, todos, countdowns, usage] = await Promise.all([
                api.getAllReminders(),
                api.getAllTodos(),
                api.getAllCountdowns(),
                api.getUsageOverview(),
            ])

            const reminderCount = Object.values(reminders).reduce((sum, arr) => sum + arr.length, 0)

            let todoCount = 0
            Object.values(todos).forEach(userTodos => {
                if (userTodos.work) todoCount += userTodos.work.filter(t => !t.done).length
                if (userTodos.play) todoCount += userTodos.play.filter(t => !t.done).length
            })

            const countdownCount = Object.values(countdowns).reduce(
                (sum, obj) => sum + Object.keys(obj).length, 0
            )

            setStats({
                reminders: reminderCount,
                todos: todoCount,
                countdowns: countdownCount,
                messages: usage.recent_7days || 0,
            })
        } catch (error) {
            console.error('Failed to load stats:', error)
            showToast('加载统计数据失败', 'error')
        }
    }

    const loadSystemStatus = async () => {
        try {
            const status = await api.getSystemStatus()
            setSystemStatus({
                cpu: {
                    value: status.cpu_percent,
                    label: `${status.cpu_percent.toFixed(1)}%`,
                },
                memory: {
                    value: status.memory_percent,
                    label: `${status.memory_percent.toFixed(1)}%`,
                },
                disk: {
                    value: status.disk_percent,
                    label: `${status.disk_percent.toFixed(1)}%`,
                },
            })
        } catch (error) {
            console.error('Failed to load system status:', error)
        }
    }

    return (
        <div className="page active">
            <div className="page-header">
                <h1 className="page-title">📊 仪表盘</h1>
                <p className="page-subtitle">快速概览和系统状态</p>
            </div>

            <div className="stats-grid">
                <div className="stat-card">
                    <div className="stat-icon">⏰</div>
                    <div className="stat-content">
                        <div className="stat-label">活跃提醒</div>
                        <div className="stat-value">{stats.reminders}</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">✅</div>
                    <div className="stat-content">
                        <div className="stat-label">待办事项</div>
                        <div className="stat-value">{stats.todos}</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">⏳</div>
                    <div className="stat-content">
                        <div className="stat-label">倒计时</div>
                        <div className="stat-value">{stats.countdowns}</div>
                    </div>
                </div>
                <div className="stat-card">
                    <div className="stat-icon">📈</div>
                    <div className="stat-content">
                        <div className="stat-label">本周消息</div>
                        <div className="stat-value">{stats.messages}</div>
                    </div>
                </div>
            </div>

            <div className="status-section">
                <h2 className="section-title">系统状态</h2>
                <div className="status-grid">
                    <div className="status-card">
                        <div className="status-header">
                            <span className="status-label">CPU 使用率</span>
                            <span className="status-value">{systemStatus.cpu.label}</span>
                        </div>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${systemStatus.cpu.value}%` }}></div>
                        </div>
                    </div>
                    <div className="status-card">
                        <div className="status-header">
                            <span className="status-label">内存使用</span>
                            <span className="status-value">{systemStatus.memory.label}</span>
                        </div>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${systemStatus.memory.value}%` }}></div>
                        </div>
                    </div>
                    <div className="status-card">
                        <div className="status-header">
                            <span className="status-label">磁盘使用</span>
                            <span className="status-value">{systemStatus.disk.label}</span>
                        </div>
                        <div className="progress-bar">
                            <div className="progress-fill" style={{ width: `${systemStatus.disk.value}%` }}></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Dashboard
