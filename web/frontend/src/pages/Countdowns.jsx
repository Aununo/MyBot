import { useState, useEffect } from 'react'
import api from '../services/api'
import Modal from '../components/Modal'
import { formatTimeDelta } from '../utils/helpers'
import './Countdowns.css'

function Countdowns({ showToast }) {
    const [countdowns, setCountdowns] = useState([])
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [formData, setFormData] = useState({
        userId: '',
        eventName: '',
        time: '',
    })

    useEffect(() => {
        loadCountdowns()
        const interval = setInterval(updateTimers, 1000)
        return () => clearInterval(interval)
    }, [])

    const loadCountdowns = async () => {
        try {
            const data = await api.getAllCountdowns()
            const countdownList = []

            Object.entries(data).forEach(([userId, userCountdowns]) => {
                Object.entries(userCountdowns).forEach(([eventName, countdownData]) => {
                    countdownList.push({ userId, eventName, ...countdownData })
                })
            })

            setCountdowns(countdownList)
        } catch (error) {
            console.error('Failed to load countdowns:', error)
            showToast('加载倒计时失败', 'error')
        }
    }

    const updateTimers = () => {
        setCountdowns(prev => [...prev])
    }

    const handleDelete = async (userId, eventName) => {
        if (!window.confirm('确定要删除这个倒计时吗？')) return

        try {
            await api.deleteCountdown(userId, eventName)
            showToast('倒计时已删除', 'success')
            loadCountdowns()
        } catch (error) {
            console.error('Failed to delete countdown:', error)
            showToast('删除失败', 'error')
        }
    }

    const handleSubmit = async (e) => {
        e.preventDefault()

        if (!formData.userId || !formData.eventName || !formData.time) {
            showToast('请填写所有必填字段', 'error')
            return
        }

        try {
            await api.createCountdown(formData.userId, {
                event_name: formData.eventName,
                time: new Date(formData.time).toISOString(),
            })

            showToast('倒计时创建成功', 'success')
            setIsModalOpen(false)
            setFormData({ userId: '', eventName: '', time: '' })
            loadCountdowns()
        } catch (error) {
            console.error('Failed to create countdown:', error)
            showToast('创建失败', 'error')
        }
    }

    return (
        <div className="page active">
            <div className="page-header">
                <div>
                    <h1 className="page-title">⏳ 倒计时</h1>
                    <p className="page-subtitle">追踪重要事件倒计时</p>
                </div>
                <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
                    <span>➕</span> 添加倒计时
                </button>
            </div>

            <div className="countdowns-grid">
                {countdowns.length === 0 ? (
                    <div className="loading">暂无倒计时数据</div>
                ) : (
                    countdowns.map((countdown, index) => {
                        const dateStr = new Date(countdown.time).toLocaleString('zh-CN')
                        const timeLeft = formatTimeDelta(countdown.time)

                        return (
                            <div key={index} className="countdown-card">
                                <div className="countdown-name">{countdown.eventName}</div>
                                <div className="countdown-time">{timeLeft}</div>
                                <div className="countdown-date">📅 {dateStr}</div>
                                <div className="item-details">👤 用户 {countdown.userId}</div>
                                <div className="item-actions">
                                    <button
                                        className="btn btn-danger btn-small"
                                        onClick={() => handleDelete(countdown.userId, countdown.eventName)}
                                    >
                                        🗑️ 删除
                                    </button>
                                </div>
                            </div>
                        )
                    })
                )}
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="添加倒计时">
                <form onSubmit={handleSubmit}>
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
                            value={formData.eventName}
                            onChange={(e) => setFormData({ ...formData, eventName: e.target.value })}
                            placeholder="例如：考试"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>截止时间</label>
                        <input
                            type="datetime-local"
                            value={formData.time}
                            onChange={(e) => setFormData({ ...formData, time: e.target.value })}
                            required
                        />
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

export default Countdowns
