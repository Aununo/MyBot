import { NavLink } from 'react-router-dom'
import './Navbar.css'

function Navbar() {
    const navItems = [
        { path: '/dashboard', icon: '📊', label: '仪表盘' },
        { path: '/reminders', icon: '⏰', label: '提醒' },
        { path: '/todos', icon: '✅', label: '待办' },
        { path: '/countdowns', icon: '⏳', label: '倒计时' },
        { path: '/usage', icon: '📈', label: '统计' },
        { path: '/images', icon: '🖼️', label: '图片' },
        { path: '/eat', icon: '🍔', label: '吃什么' },
    ]

    return (
        <nav className="navbar">
            <div className="nav-container">
                <div className="nav-brand">
                    <span className="brand-icon">🤖</span>
                    <span className="brand-text">MyBot</span>
                    <span className="brand-subtitle">管理面板</span>
                </div>
                <div className="nav-links">
                    {navItems.map(item => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                        >
                            <span>{item.icon}</span>
                            <span>{item.label}</span>
                        </NavLink>
                    ))}
                </div>
            </div>
        </nav>
    )
}

export default Navbar
