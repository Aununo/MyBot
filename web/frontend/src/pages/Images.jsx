import { useState, useEffect, useRef } from 'react'
import api from '../services/api'
import Modal from '../components/Modal'
import { formatFileSize, formatDateTime } from '../utils/helpers'
import './Images.css'

function Images({ showToast }) {
    const [currentFolder, setCurrentFolder] = useState('pics')
    const [images, setImages] = useState([])
    const [previewImage, setPreviewImage] = useState(null)
    const [uploading, setUploading] = useState(false)
    const fileInputRef = useRef(null)

    useEffect(() => {
        loadImages()
    }, [currentFolder])

    const loadImages = async () => {
        try {
            const data = await api.getFolderImages(currentFolder)
            setImages(data.images || [])
        } catch (error) {
            console.error('Failed to load images:', error)
            showToast('加载图片失败', 'error')
        }
    }

    const switchFolder = (folder) => {
        setCurrentFolder(folder)
    }

    const handleImageClick = (image) => {
        setPreviewImage(image)
    }

    const handleDeleteImage = async () => {
        if (!previewImage) return
        if (!window.confirm(`确定要删除 "${previewImage.name}" 吗？`)) return

        try {
            await api.deleteImage(currentFolder, previewImage.name)
            showToast(`图片 ${previewImage.name} 已删除`, 'success')
            setPreviewImage(null)
            loadImages()
        } catch (error) {
            console.error('Failed to delete image:', error)
            showToast('删除失败', 'error')
        }
    }

    const handleUploadClick = () => {
        fileInputRef.current?.click()
    }

    const handleFileSelect = async (event) => {
        const files = event.target.files
        if (!files || files.length === 0) return

        const file = files[0]

        // 验证文件类型
        const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp']
        if (!allowedTypes.includes(file.type)) {
            showToast('只支持 JPG, PNG, GIF, WebP, BMP 格式的图片', 'error')
            return
        }

        // 验证文件大小 (最大 10MB)
        const maxSize = 10 * 1024 * 1024
        if (file.size > maxSize) {
            showToast('图片大小不能超过 10MB', 'error')
            return
        }

        setUploading(true)
        try {
            await api.uploadImage(currentFolder, file)
            showToast(`图片 ${file.name} 上传成功`, 'success')
            loadImages()
        } catch (error) {
            console.error('Failed to upload image:', error)
            showToast(error.message || '上传失败', 'error')
        } finally {
            setUploading(false)
            // 清空 input，允许重复上传同一文件
            event.target.value = ''
        }
    }

    const folders = [
        { key: 'pics', label: '📁 默认表情' },
        { key: 'food_images', label: '🍔 美食图片' },
        { key: 'latex', label: '🔬 LaTeX 公式' },
    ]

    return (
        <div className="page active">
            <div className="page-header">
                <div>
                    <h1 className="page-title">🖼️ 图片管理</h1>
                    <p className="page-subtitle">管理 assets 文件夹中的图片资源</p>
                </div>
            </div>

            <div className="folder-tabs">
                {folders.map(folder => (
                    <button
                        key={folder.key}
                        className={`folder-tab ${currentFolder === folder.key ? 'active' : ''}`}
                        onClick={() => switchFolder(folder.key)}
                    >
                        {folder.label}
                    </button>
                ))}
            </div>

            <div className="images-toolbar">
                <div className="images-count">
                    共 <span>{images.length}</span> 张图片
                </div>
                <div className="images-actions">
                    <input
                        type="file"
                        ref={fileInputRef}
                        style={{ display: 'none' }}
                        accept="image/jpeg,image/png,image/gif,image/webp,image/bmp"
                        onChange={handleFileSelect}
                    />
                    <button
                        className="btn btn-primary btn-small"
                        onClick={handleUploadClick}
                        disabled={uploading}
                        style={{ marginRight: '8px' }}
                    >
                        {uploading ? '⏳ 上传中...' : '📤 上传图片'}
                    </button>
                    <button className="btn btn-secondary btn-small" onClick={loadImages}>
                        🔄 刷新
                    </button>
                </div>
            </div>

            <div className="images-grid">
                {images.length === 0 ? (
                    <div className="loading">暂无图片</div>
                ) : (
                    images.map((image, index) => (
                        <div
                            key={index}
                            className="image-item"
                            onClick={() => handleImageClick(image)}
                        >
                            <img src={image.url} alt={image.name} />
                            <div className="image-name">{image.name}</div>
                            <div className="image-size">{formatFileSize(image.size)}</div>
                        </div>
                    ))
                )}
            </div>

            {previewImage && (
                <Modal
                    isOpen={!!previewImage}
                    onClose={() => setPreviewImage(null)}
                    title={previewImage.name}
                >
                    <img
                        src={previewImage.url}
                        alt={previewImage.name}
                        style={{ width: '100%', borderRadius: '12px' }}
                    />
                    <div style={{ marginTop: '16px', color: 'var(--text-secondary)' }}>
                        <div>文件大小: {formatFileSize(previewImage.size)}</div>
                        <div>修改时间: {formatDateTime(previewImage.modified)}</div>
                    </div>
                    <div className="modal-footer">
                        <button className="btn btn-danger" onClick={handleDeleteImage}>
                            🗑️ 删除图片
                        </button>
                        <button className="btn btn-secondary" onClick={() => setPreviewImage(null)}>
                            关闭
                        </button>
                    </div>
                </Modal>
            )}
        </div>
    )
}

export default Images
