import { useState, useEffect } from 'react'
import api from '../services/api'
import Modal from '../components/Modal'
import './Reminders.css'

function Reminders({ showToast }) {
    const [reminders, setReminders] = useState([])
    const [searchTerm, setSearchTerm] = useState('')
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [formData, setFormData] = useState({
        userId: '',
        event: '',
        hour: '',
        minute: '',
        sessionId: '',
        isGroup: false,
        isDaily: false,
    })

    useEffect(() => {
        loadReminders()
    }, [])

    const loadReminders = async () => {
        try {
            const data = await api.getAllReminders()
            const reminderList = []
            Object.entries(data).forEach(([userId, userReminders]) => {
                userReminders.forEach(reminder => {
                    reminderList.push({ ...reminder, userId })
                })
            })
            setReminders(reminderList)
        } catch (error) {
            console.error('Failed to load reminders:', error)
            showToast('加载提醒失败', 'error')
        }
    }

    const handleDelete = async (userId, jobId) => {
        if (!window.confirm('确定要删除这个提醒吗？')) return

        try {
            await api.deleteReminder(userId, jobId)
            showToast('提醒已删除', 'success')
            loadReminders()
        } catch (error) {
            console.error('Failed to delete reminder:', error)
            showToast('删除失败', 'error')
        }
    }

    const handleSubmit = async (e) => {
        e.preventDefault()

        if (!formData.userId || !formData.event || !formData.hour || !formData.minute || !formData.sessionId) {
            showToast('请填写所有必填字段', 'error')
            return
        }

        try {
            await api.createReminder(formData.userId, {
                event: formData.event,
                hour: parseInt(formData.hour),
                minute: parseInt(formData.minute),
                session_id: formData.sessionId,
                is_group: formData.isGroup,
                is_daily: formData.isDaily,
                mention_all: false,
            })

            showToast('提醒创建成功！重启机器人后生效', 'success')
            setIsModalOpen(false)
            setFormData({
                userId: '',
                event: '',
                hour: '',
                minute: '',
                sessionId: '',
                isGroup: false,
                isDaily: false,
            })
            loadReminders()
        } catch (error) {
            console.error('Failed to create reminder:', error)
            showToast('创建失败', 'error')
        }
    }

    const filteredReminders = reminders.filter(reminder => {
        const searchLower = searchTerm.toLowerCase()
        return (
            reminder.event.toLowerCase().includes(searchLower) ||
            reminder.userId.toString().includes(searchLower) ||
            reminder.session_id.toString().includes(searchLower)
        )
    })

    return (
        <div className="page active">
            <div className="page-header">
                <div>
                    <h1 className="page-title">⏰ 提醒管理</h1>
                    <p className="page-subtitle">查看和管理所有提醒</p>
                </div>
                <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
                    <span>➕</span> 添加提醒
                </button>
            </div>

            <div className="search-box">
                <input
                    type="text"
                    placeholder="🔍 搜索提醒..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            <div className="items-list">
                {filteredReminders.length === 0 ? (
                    <div className="loading">暂无提醒数据</div>
                ) : (
                    filteredReminders.map(reminder => {
                        const timeStr = `${String(reminder.hour).padStart(2, '0')}:${String(reminder.minute).padStart(2, '0')}`
                        let typeLabel = '一次性'
                        if (reminder.is_daily) typeLabel = '每日'
                        if (reminder.interval_days) typeLabel = `每${reminder.interval_days}天`
                        if (reminder.weekdays) typeLabel = '周期'

                        return (
                            <div key={reminder.job_id} className="item-card">
                                <div className="item-header">
                                    <div className="item-title">{reminder.event}</div>
                                    <div className="item-badge">{typeLabel}</div>
                                </div>
                                <div className="item-details">
                                    ⏰ {timeStr} | 👤 用户 {reminder.userId} | 💬 会话 {reminder.session_id}
                                    {reminder.is_group ? ' | 📢 群聊' : ' | 💌 私聊'}
                                    {reminder.mention_all ? ' | @全体' : ''}
                                </div>
                                <div className="item-actions">
                                    <button
                                        className="btn btn-danger btn-small"
                                        onClick={() => handleDelete(reminder.userId, reminder.job_id)}
                                    >
                                        🗑️ 删除
                                    </button>
                                </div>
                            </div>
                        )
                    })
                )}
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="添加提醒">
                <form onSubmit={handleSubmit}>
                    <p className="modal-note">⚠️ 注意：通过 Web 界面添加的提醒不会自动注册到调度器，需重启机器人才能生效。</p>

                    <div className="form-group">
                        <label>用户 ID</label>
                        <input
                            type="text"
                            value={formData.userId}
                            onChange={(e) => setFormData({ ...formData, userId: e.target.value })}
                            placeholder="请输入用户 ID"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>事件名称</label>
                        <input
                            type="text"
                            value={formData.event}
                            onChange={(e) => setFormData({ ...formData, event: e.target.value })}
                            placeholder="例如：吃药"
                            required
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>小时 (0-23)</label>
                            <input
                                type="number"
                                min="0"
                                max="23"
                                value={formData.hour}
                                onChange={(e) => setFormData({ ...formData, hour: e.target.value })}
                                placeholder="14"
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>分钟 (0-59)</label>
                            <input
                                type="number"
                                min="0"
                                max="59"
                                value={formData.minute}
                                onChange={(e) => setFormData({ ...formData, minute: e.target.value })}
                                placeholder="30"
                                required
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>会话 ID (群号或用户号)</label>
                        <input
                            type="text"
                            value={formData.sessionId}
                            onChange={(e) => setFormData({ ...formData, sessionId: e.target.value })}
                            placeholder="请输入会话 ID"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={formData.isGroup}
                                onChange={(e) => setFormData({ ...formData, isGroup: e.target.checked })}
                            />
                            <span>是否为群聊</span>
                        </label>
                    </div>

                    <div className="form-group">
                        <label className="checkbox-label">
                            <input
                                type="checkbox"
                                checked={formData.isDaily}
                                onChange={(e) => setFormData({ ...formData, isDaily: e.target.checked })}
                            />
                            <span>每日重复</span>
                        </label>
                    </div>

                    <div className="modal-footer">
                        <button type="button" className="btn btn-secondary" onClick={() => setIsModalOpen(false)}>
                            取消
                        </button>
                        <button type="submit" className="btn btn-primary">
                            确定
                        </button>
                    </div>
                </form>
            </Modal>
        </div>
    )
}

export default Reminders
