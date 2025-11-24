import { useState, useEffect } from 'react'
import api from '../services/api'
import Modal from '../components/Modal'
import './Todos.css'

function Todos({ showToast }) {
    const [todos, setTodos] = useState({ work: [], play: [] })
    const [isModalOpen, setIsModalOpen] = useState(false)
    const [formData, setFormData] = useState({
        userId: '',
        task: '',
        category: 'work',
    })

    useEffect(() => {
        loadTodos()
    }, [])

    const loadTodos = async () => {
        try {
            const data = await api.getAllTodos()
            const workTodos = []
            const playTodos = []

            Object.entries(data).forEach(([userId, userTodos]) => {
                if (userTodos.work) {
                    userTodos.work.forEach((todo, index) => {
                        workTodos.push({ ...todo, userId, index, category: 'work' })
                    })
                }
                if (userTodos.play) {
                    userTodos.play.forEach((todo, index) => {
                        playTodos.push({ ...todo, userId, index, category: 'play' })
                    })
                }
            })

            setTodos({ work: workTodos, play: playTodos })
        } catch (error) {
            console.error('Failed to load todos:', error)
            showToast('加载待办失败', 'error')
        }
    }

    const handleToggle = async (userId, category, index, done) => {
        try {
            await api.updateTodo(userId, category, index, done)
            loadTodos()
        } catch (error) {
            console.error('Failed to toggle todo:', error)
            showToast('更新失败', 'error')
        }
    }

    const handleDelete = async (userId, category, index) => {
        if (!window.confirm('确定要删除这个待办事项吗？')) return

        try {
            await api.deleteTodo(userId, category, index)
            showToast('待办事项已删除', 'success')
            loadTodos()
        } catch (error) {
            console.error('Failed to delete todo:', error)
            showToast('删除失败', 'error')
        }
    }

    const handleSubmit = async (e) => {
        e.preventDefault()

        if (!formData.userId || !formData.task) {
            showToast('请填写所有必填字段', 'error')
            return
        }

        try {
            await api.createTodo(formData.userId, {
                task: formData.task,
                category: formData.category,
            })

            showToast('待办事项创建成功', 'success')
            setIsModalOpen(false)
            setFormData({ userId: '', task: '', category: 'work' })
            loadTodos()
        } catch (error) {
            console.error('Failed to create todo:', error)
            showToast('创建失败', 'error')
        }
    }

    const workCount = todos.work.filter(t => !t.done).length
    const playCount = todos.play.filter(t => !t.done).length

    return (
        <div className="page active">
            <div className="page-header">
                <div>
                    <h1 className="page-title">✅ 待办事项</h1>
                    <p className="page-subtitle">管理工作和娱乐待办</p>
                </div>
                <button className="btn btn-primary" onClick={() => setIsModalOpen(true)}>
                    <span>➕</span> 添加待办
                </button>
            </div>

            <div className="todos-grid">
                <div className="todo-column">
                    <div className="column-header">
                        <span className="column-icon">💼</span>
                        <span className="column-title">工作</span>
                        <span className="column-count">{workCount}</span>
                    </div>
                    <div className="todos-list">
                        {todos.work.length === 0 ? (
                            <div className="loading">暂无工作待办</div>
                        ) : (
                            todos.work.map((todo, idx) => (
                                <div key={`work-${idx}`} className={`todo-item ${todo.done ? 'done' : ''}`}>
                                    <input
                                        type="checkbox"
                                        className="todo-checkbox"
                                        checked={todo.done}
                                        onChange={(e) => handleToggle(todo.userId, todo.category, todo.index, e.target.checked)}
                                    />
                                    <span className="todo-text">{todo.task}</span>
                                    <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                        用户 {todo.userId}
                                    </small>
                                    <button
                                        className="todo-delete"
                                        onClick={() => handleDelete(todo.userId, todo.category, todo.index)}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                <div className="todo-column">
                    <div className="column-header">
                        <span className="column-icon">🎮</span>
                        <span className="column-title">娱乐</span>
                        <span className="column-count">{playCount}</span>
                    </div>
                    <div className="todos-list">
                        {todos.play.length === 0 ? (
                            <div className="loading">暂无娱乐待办</div>
                        ) : (
                            todos.play.map((todo, idx) => (
                                <div key={`play-${idx}`} className={`todo-item ${todo.done ? 'done' : ''}`}>
                                    <input
                                        type="checkbox"
                                        className="todo-checkbox"
                                        checked={todo.done}
                                        onChange={(e) => handleToggle(todo.userId, todo.category, todo.index, e.target.checked)}
                                    />
                                    <span className="todo-text">{todo.task}</span>
                                    <small style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                                        用户 {todo.userId}
                                    </small>
                                    <button
                                        className="todo-delete"
                                        onClick={() => handleDelete(todo.userId, todo.category, todo.index)}
                                    >
                                        🗑️
                                    </button>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>

            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="添加待办事项">
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
                        <label>待办内容</label>
                        <input
                            type="text"
                            value={formData.task}
                            onChange={(e) => setFormData({ ...formData, task: e.target.value })}
                            placeholder="例如：完成项目报告"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>分类</label>
                        <select
                            value={formData.category}
                            onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                        >
                            <option value="work">💼 工作</option>
                            <option value="play">🎮 娱乐</option>
                        </select>
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

export default Todos
