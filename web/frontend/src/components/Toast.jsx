import './Toast.css'

function Toast({ toasts }) {
    return (
        <div className="toast-container">
            {toasts.map(toast => (
                <div key={toast.id} className={`toast ${toast.type}`}>
                    {toast.message}
                </div>
            ))}
        </div>
    )
}

export default Toast
