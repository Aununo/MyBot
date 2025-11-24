import { useState } from 'react'
import { HashRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import Reminders from './pages/Reminders'
import Todos from './pages/Todos'
import Countdowns from './pages/Countdowns'
import Usage from './pages/Usage'
import Images from './pages/Images'
import Eat from './pages/Eat'
import Toast from './components/Toast'
import './styles/App.css'

function App() {
    const [toasts, setToasts] = useState([])

    const showToast = (message, type = 'info') => {
        const id = Date.now()
        setToasts(prev => [...prev, { id, message, type }])
        setTimeout(() => {
            setToasts(prev => prev.filter(toast => toast.id !== id))
        }, 3000)
    }

    return (
        <Router>
            <div className="app">
                <Navbar />
                <main className="main-content">
                    <div className="container">
                        <Routes>
                            <Route path="/" element={<Navigate to="/dashboard" replace />} />
                            <Route path="/dashboard" element={<Dashboard showToast={showToast} />} />
                            <Route path="/reminders" element={<Reminders showToast={showToast} />} />
                            <Route path="/todos" element={<Todos showToast={showToast} />} />
                            <Route path="/countdowns" element={<Countdowns showToast={showToast} />} />
                            <Route path="/usage" element={<Usage showToast={showToast} />} />
                            <Route path="/images" element={<Images showToast={showToast} />} />
                            <Route path="/eat" element={<Eat showToast={showToast} />} />
                        </Routes>
                    </div>
                </main>
                <Toast toasts={toasts} />
            </div>
        </Router>
    )
}

export default App
