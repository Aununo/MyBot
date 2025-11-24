import { useState, useEffect } from 'react'
import api from '../services/api'
import './Eat.css'

function Eat({ showToast }) {
    const [eatData, setEatData] = useState({ android: [], apple: [] })
    const [inputs, setInputs] = useState({ android: '', apple: '' })

    useEffect(() => {
        loadEatData()
    }, [])

    const loadEatData = async () => {
        try {
            const data = await api.getEatData()
            setEatData({
                android: data.android || [],
                apple: data.apple || [],
            })
        } catch (error) {
            console.error('Failed to load eat data:', error)
            showToast('加载数据失败', 'error')
        }
    }

    const handleAddFood = async (listName) => {
        const foodName = inputs[listName].trim()

        if (!foodName) {
            showToast('请输入食物名称', 'error')
            return
        }

        try {
            await api.addFood(listName, foodName)
            showToast(`已添加 ${foodName}`, 'success')
            setInputs({ ...inputs, [listName]: '' })
            loadEatData()
        } catch (error) {
            console.error('Failed to add food:', error)
            if (error.message.includes('400')) {
                showToast('该食物已存在', 'error')
            } else {
                showToast('添加失败', 'error')
            }
        }
    }

    const handleDeleteFood = async (listName, foodName) => {
        if (!window.confirm(`确定要删除 "${foodName}" 吗？`)) return

        try {
            await api.deleteFood(listName, foodName)
            showToast(`已删除 ${foodName}`, 'success')
            loadEatData()
        } catch (error) {
            console.error('Failed to delete food:', error)
            showToast('删除失败', 'error')
        }
    }

    const handleKeyPress = (e, listName) => {
        if (e.key === 'Enter') {
            handleAddFood(listName)
        }
    }

    return (
        <div className="page active">
            <div className="page-header">
                <div>
                    <h1 className="page-title">🍔 吃什么管理</h1>
                    <p className="page-subtitle">管理上学和假期的美食列表</p>
                </div>
            </div>

            <div className="eat-grid">
                <div className="eat-column">
                    <div className="column-header">
                        <span className="column-icon">📱</span>
                        <span className="column-title">上学吃什么 (Android)</span>
                        <span className="column-count">{eatData.android.length}</span>
                    </div>
                    <div className="eat-actions">
                        <input
                            type="text"
                            className="eat-input"
                            placeholder="输入食物名称..."
                            value={inputs.android}
                            onChange={(e) => setInputs({ ...inputs, android: e.target.value })}
                            onKeyPress={(e) => handleKeyPress(e, 'android')}
                        />
                        <button
                            className="btn btn-primary btn-small"
                            onClick={() => handleAddFood('android')}
                        >
                            ➕ 添加
                        </button>
                    </div>
                    <div className="eat-list">
                        {eatData.android.length === 0 ? (
                            <div className="loading">列表为空</div>
                        ) : (
                            eatData.android.map((food, index) => (
                                <div key={index} className="eat-item">
                                    <span className="eat-food-name">{food}</span>
                                    <button
                                        className="eat-delete-btn"
                                        onClick={() => handleDeleteFood('android', food)}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="eat-column">
                    <div className="column-header">
                        <span className="column-icon">🍎</span>
                        <span className="column-title">假期吃什么 (Apple)</span>
                        <span className="column-count">{eatData.apple.length}</span>
                    </div>
                    <div className="eat-actions">
                        <input
                            type="text"
                            className="eat-input"
                            placeholder="输入食物名称..."
                            value={inputs.apple}
                            onChange={(e) => setInputs({ ...inputs, apple: e.target.value })}
                            onKeyPress={(e) => handleKeyPress(e, 'apple')}
                        />
                        <button
                            className="btn btn-primary btn-small"
                            onClick={() => handleAddFood('apple')}
                        >
                            ➕ 添加
                        </button>
                    </div>
                    <div className="eat-list">
                        {eatData.apple.length === 0 ? (
                            <div className="loading">列表为空</div>
                        ) : (
                            eatData.apple.map((food, index) => (
                                <div key={index} className="eat-item">
                                    <span className="eat-food-name">{food}</span>
                                    <button
                                        className="eat-delete-btn"
                                        onClick={() => handleDeleteFood('apple', food)}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Eat
