// 格式化时间差
export function formatTimeDelta(targetDate) {
    const now = new Date()
    const target = new Date(targetDate)
    const diff = target - now

    if (diff < 0) {
        return '已过期'
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    if (days > 0) {
        return `${days}天${hours}小时`
    } else if (hours > 0) {
        return `${hours}小时${minutes}分钟`
    } else {
        return `${minutes}分钟`
    }
}

// 格式化文件大小
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

// 格式化日期时间
export function formatDateTime(dateString) {
    return new Date(dateString).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}
