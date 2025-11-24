const API_BASE_URL = window.location.origin

class ApiService {
    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
            })

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`)
            }

            return await response.json()
        } catch (error) {
            console.error('API Error:', error)
            throw error
        }
    }

    // Reminders
    async getAllReminders() {
        return this.request('/api/reminders')
    }

    async getUserReminders(userId) {
        return this.request(`/api/reminders/${userId}`)
    }

    async createReminder(userId, data) {
        return this.request(`/api/reminders/${userId}`, {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async deleteReminder(userId, jobId) {
        return this.request(`/api/reminders/${userId}/${jobId}`, {
            method: 'DELETE',
        })
    }

    // Todos
    async getAllTodos() {
        return this.request('/api/todos')
    }

    async getUserTodos(userId) {
        return this.request(`/api/todos/${userId}`)
    }

    async createTodo(userId, data) {
        return this.request(`/api/todos/${userId}`, {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async updateTodo(userId, category, index, done) {
        return this.request(`/api/todos/${userId}/${category}/${index}?done=${done}`, {
            method: 'PUT',
        })
    }

    async deleteTodo(userId, category, index) {
        return this.request(`/api/todos/${userId}/${category}/${index}`, {
            method: 'DELETE',
        })
    }

    // Countdowns
    async getAllCountdowns() {
        return this.request('/api/countdowns')
    }

    async getUserCountdowns(userId) {
        return this.request(`/api/countdowns/${userId}`)
    }

    async createCountdown(userId, data) {
        return this.request(`/api/countdowns/${userId}`, {
            method: 'POST',
            body: JSON.stringify(data),
        })
    }

    async deleteCountdown(userId, eventName) {
        return this.request(`/api/countdowns/${userId}/${encodeURIComponent(eventName)}`, {
            method: 'DELETE',
        })
    }

    // Usage Stats
    async getUsageOverview() {
        return this.request('/api/usage/overview')
    }

    async getUsageHourly() {
        return this.request('/api/usage/hourly')
    }

    async getUsageDaily() {
        return this.request('/api/usage/daily')
    }

    async getUsageWeekday() {
        return this.request('/api/usage/weekday')
    }

    // System Status
    async getSystemStatus() {
        return this.request('/api/status')
    }

    // Images
    async getAllImages() {
        return this.request('/api/images')
    }

    async getFolderImages(folder) {
        return this.request(`/api/images/${folder}`)
    }

    async uploadImage(folder, file) {
        const formData = new FormData()
        formData.append('file', file)

        const response = await fetch(`${API_BASE_URL}/api/images/${folder}/upload`, {
            method: 'POST',
            body: formData,
        })

        if (!response.ok) {
            const error = await response.json()
            throw new Error(error.detail || '上传失败')
        }

        return await response.json()
    }

    async deleteImage(folder, filename) {
        return this.request(`/api/images/${folder}/${filename}`, {
            method: 'DELETE',
        })
    }

    // Eat (吃什么)
    async getEatData() {
        return this.request('/api/eat')
    }

    async getEatList(listName) {
        return this.request(`/api/eat/${listName}`)
    }

    async addFood(listName, food) {
        return this.request(`/api/eat/${listName}?food=${encodeURIComponent(food)}`, {
            method: 'POST',
        })
    }

    async deleteFood(listName, food) {
        return this.request(`/api/eat/${listName}/${encodeURIComponent(food)}`, {
            method: 'DELETE',
        })
    }
}

export default new ApiService()
