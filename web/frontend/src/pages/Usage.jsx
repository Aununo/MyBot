import { useState, useEffect } from 'react'
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, PointElement, LineElement, ArcElement, Title, Tooltip, Legend, Filler } from 'chart.js'
import { Bar, Doughnut, Line } from 'react-chartjs-2'
import api from '../services/api'
import './Usage.css'

ChartJS.register(CategoryScale, LinearScale, BarElement, PointElement, LineElement, ArcElement, Title, Tooltip, Legend, Filler)

function Usage({ showToast }) {
    const [hourlyData, setHourlyData] = useState(null)
    const [weekdayData, setWeekdayData] = useState(null)
    const [dailyData, setDailyData] = useState(null)

    useEffect(() => {
        loadUsageStats()
    }, [])

    const loadUsageStats = async () => {
        try {
            const [hourly, weekday, daily] = await Promise.all([
                api.getUsageHourly(),
                api.getUsageWeekday(),
                api.getUsageDaily(),
            ])

            // Hourly chart data
            const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
            const hourlyValues = Array.from({ length: 24 }, (_, i) => hourly.hourly_stats[i] || 0)

            setHourlyData({
                labels: hours,
                datasets: [{
                    label: '消息数量',
                    data: hourlyValues,
                    backgroundColor: 'rgba(102, 126, 234, 0.6)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1,
                }],
            })

            // Weekday chart data
            const weekdayLabels = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            const weekdayKeys = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            const weekdayValues = weekdayKeys.map(key => weekday.weekday_stats[key] || 0)

            setWeekdayData({
                labels: weekdayLabels,
                datasets: [{
                    data: weekdayValues,
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(118, 75, 162, 0.8)',
                        'rgba(79, 172, 254, 0.8)',
                        'rgba(0, 212, 170, 0.8)',
                        'rgba(255, 140, 66, 0.8)',
                        'rgba(245, 87, 108, 0.8)',
                        'rgba(240, 147, 251, 0.8)',
                    ],
                    borderWidth: 0,
                }],
            })

            // Daily chart data
            const dates = Object.keys(daily.daily_stats).reverse()
            const dailyValues = dates.map(date => daily.daily_stats[date])

            setDailyData({
                labels: dates,
                datasets: [{
                    label: '消息数量',
                    data: dailyValues,
                    borderColor: 'rgba(79, 172, 254, 1)',
                    backgroundColor: 'rgba(79, 172, 254, 0.2)',
                    tension: 0.4,
                    fill: true,
                }],
            })

        } catch (error) {
            console.error('Failed to load usage stats:', error)
            showToast('加载统计数据失败', 'error')
        }
    }

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { display: false },
        },
        scales: {
            y: {
                beginAtZero: true,
                ticks: { color: '#b4b4c5' },
                grid: { color: 'rgba(255, 255, 255, 0.1)' },
            },
            x: {
                ticks: { color: '#b4b4c5' },
                grid: { display: false },
            },
        },
    }

    const doughnutOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                position: 'right',
                labels: { color: '#b4b4c5' },
            },
        },
    }

    const lineOptions = {
        ...chartOptions,
        scales: {
            ...chartOptions.scales,
            x: {
                ticks: { color: '#b4b4c5', maxRotation: 45 },
                grid: { display: false },
            },
        },
    }

    return (
        <div className="page active">
            <div className="page-header">
                <h1 className="page-title">📈 使用统计</h1>
                <p className="page-subtitle">数据分析与可视化</p>
            </div>

            <div className="usage-section">
                <div className="chart-card">
                    <h3 className="chart-title">📊 24小时活跃时段</h3>
                    {hourlyData && <Bar data={hourlyData} options={chartOptions} />}
                </div>
                <div className="chart-card">
                    <h3 className="chart-title">📆 星期分布</h3>
                    {weekdayData && <Doughnut data={weekdayData} options={doughnutOptions} />}
                </div>
            </div>

            <div className="usage-section">
                <div className="chart-card full-width">
                    <h3 className="chart-title">📅 最近30天趋势</h3>
                    {dailyData && <Line data={dailyData} options={lineOptions} />}
                </div>
            </div>
        </div>
    )
}

export default Usage
