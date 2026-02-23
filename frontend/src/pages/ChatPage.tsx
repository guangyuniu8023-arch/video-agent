import { useState, useCallback, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send, X, Video, ImageIcon, Plus, Sparkles, ArrowRight, Upload } from 'lucide-react'
import { startWorkflow, uploadFile } from '@/services/api'
import type { UploadedFile, ChatMessage } from '@/types'

export function ChatPage() {
  const navigate = useNavigate()
  const [input, setInput] = useState('')
  const [pendingFiles, setPendingFiles] = useState<UploadedFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [starting, setStarting] = useState(false)
  const [dragOverType, setDragOverType] = useState<'image' | 'video' | 'global' | null>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const videoInputRef = useRef<HTMLInputElement>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileUpload = useCallback(async (files: FileList | null, filterType?: 'image' | 'video') => {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        if (filterType === 'image' && !file.type.startsWith('image/')) continue
        if (filterType === 'video' && !file.type.startsWith('video/')) continue
        const result = await uploadFile(file)
        setPendingFiles(prev => [...prev, {
          filename: result.filename,
          originalName: result.original_name,
          url: result.url,
          size: result.size,
          contentType: result.content_type,
        }])
      }
    } catch (err) {
      console.error('Upload failed:', err)
    } finally {
      setUploading(false)
    }
  }, [])

  const handleDropOnZone = useCallback((e: React.DragEvent, type: 'image' | 'video') => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverType(null)
    handleFileUpload(e.dataTransfer.files, type)
  }, [handleFileUpload])

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed && pendingFiles.length === 0) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now() / 1000,
      attachments: pendingFiles.length > 0 ? pendingFiles : undefined,
    }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    const files = [...pendingFiles]
    setPendingFiles([])
    setStarting(true)

    try {
      const uploadedAssets = files.map(a => ({
        type: a.contentType?.startsWith('video/') ? 'video' : 'image',
        path: a.filename,
        url: a.url,
      }))
      const res = await startWorkflow(trimmed, undefined, uploadedAssets)
      setMessages(prev => [...prev, {
        id: `sys-${Date.now()}`,
        role: 'system',
        content: '工作流已启动，正在跳转到工作台...',
        timestamp: Date.now() / 1000,
      }])
      setTimeout(() => navigate(`/workspace/${res.project_id}`), 800)
    } catch (err) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'system',
        content: `启动失败: ${err}`,
        timestamp: Date.now() / 1000,
      }])
      setStarting(false)
    }
  }, [input, pendingFiles, navigate])

  const pendingImages = pendingFiles.filter(f => f.contentType?.startsWith('image/'))
  const pendingVideos = pendingFiles.filter(f => f.contentType?.startsWith('video/'))

  return (
    <div
      className="h-screen flex flex-col bg-surface"
      onDragOver={(e) => { e.preventDefault(); if (!dragOverType) setDragOverType('global') }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setDragOverType(null) }}
      onDrop={(e) => { e.preventDefault(); setDragOverType(null); handleFileUpload(e.dataTransfer.files) }}
    >
      {/* 全局拖拽 overlay */}
      {dragOverType === 'global' && (
        <div className="absolute inset-0 bg-primary/10 border-2 border-dashed border-primary/40 rounded-lg z-50 flex items-center justify-center pointer-events-none">
          <div className="flex items-center gap-2 text-primary text-sm font-medium">
            <Upload size={20} />
            释放以上传文件
          </div>
        </div>
      )}

      {/* 顶栏 */}
      <header className="h-12 border-b border-border flex items-center px-4 justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Video size={18} className="text-primary" />
          <span className="text-sm font-semibold text-white">Video Agent</span>
        </div>
        <button
          onClick={() => navigate('/workspace')}
          className="text-xs text-gray-400 hover:text-white flex items-center gap-1 transition-colors"
        >
          工作台 <ArrowRight size={12} />
        </button>
      </header>

      {/* 主体 */}
      <div className="flex-1 flex flex-col items-center justify-center min-h-0 px-4">
        {messages.length === 0 ? (
          <div className="w-full max-w-2xl space-y-8">
            <div className="text-center space-y-3">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 mb-2">
                <Sparkles size={28} className="text-primary" />
              </div>
              <h1 className="text-2xl font-bold text-white">AI 视频创作助手</h1>
              <p className="text-gray-400 text-sm leading-relaxed max-w-md mx-auto">
                描述你想创作的视频，上传角色参考图，AI 会自动策划分镜、生成视频、后期合成
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {[
                '用一个小女孩在花田奔跑的画面，做一段 15 秒治愈系短片',
                '拍一段 30 秒的科幻太空站内部场景，有宇航员漂浮',
                '制作一个中国风水墨动画，展现山水意境',
                '用武打动作拍一段 20 秒的功夫短片',
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="text-left text-xs text-gray-400 border border-border rounded-lg px-3 py-2.5 hover:border-primary/50 hover:text-gray-300 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="w-full max-w-2xl flex-1 overflow-auto py-4 space-y-3">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'system' ? (
                  <div className="text-center text-xs text-gray-500 w-full py-1">{msg.content}</div>
                ) : (
                  <div
                    className={`max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-primary/90 text-white rounded-br-sm'
                        : 'bg-surface-light text-gray-200 border border-border rounded-bl-sm'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                    {msg.attachments && msg.attachments.length > 0 && (
                      <div className="flex gap-1.5 mt-2 flex-wrap">
                        {msg.attachments.map((att, i) =>
                          att.contentType?.startsWith('video/') ? (
                            <video key={i} src={att.url} controls muted className="w-48 rounded border border-white/10" />
                          ) : (
                            <img key={i} src={att.url} alt={att.originalName} className="w-20 h-20 rounded object-cover border border-white/10" />
                          )
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
        )}
      </div>

      {/* 上传区 + 输入区 */}
      <div className="max-w-2xl mx-auto w-full p-4 space-y-3">
        {/* 虚线框上传区 */}
        <div className="flex gap-3">
          <input ref={imageInputRef} type="file" accept="image/*" multiple className="hidden"
            onChange={(e) => handleFileUpload(e.target.files, 'image')} />
          <input ref={videoInputRef} type="file" accept="video/*" multiple className="hidden"
            onChange={(e) => handleFileUpload(e.target.files, 'video')} />

          <button
            type="button"
            onClick={() => imageInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOverType('image') }}
            onDragLeave={(e) => { e.stopPropagation(); setDragOverType(null) }}
            onDrop={(e) => handleDropOnZone(e, 'image')}
            disabled={uploading || starting}
            className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-4 rounded-lg border-2 border-dashed transition-all duration-150 cursor-pointer
              ${dragOverType === 'image'
                ? 'border-primary bg-primary/5 scale-[1.02]'
                : 'border-gray-600 hover:border-primary/50 hover:bg-white/[0.02]'}
              disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <div className="flex items-center gap-1 text-gray-400">
              <ImageIcon size={18} />
              <Plus size={14} />
            </div>
            <span className="text-xs text-gray-500">点击或拖拽添加图片</span>
            {pendingImages.length > 0 && (
              <span className="text-[10px] text-blue-400">{pendingImages.length} 张已选</span>
            )}
          </button>

          <button
            type="button"
            onClick={() => videoInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOverType('video') }}
            onDragLeave={(e) => { e.stopPropagation(); setDragOverType(null) }}
            onDrop={(e) => handleDropOnZone(e, 'video')}
            disabled={uploading || starting}
            className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-4 rounded-lg border-2 border-dashed transition-all duration-150 cursor-pointer
              ${dragOverType === 'video'
                ? 'border-primary bg-primary/5 scale-[1.02]'
                : 'border-gray-600 hover:border-primary/50 hover:bg-white/[0.02]'}
              disabled:opacity-40 disabled:cursor-not-allowed`}
          >
            <div className="flex items-center gap-1 text-gray-400">
              <Video size={18} />
              <Plus size={14} />
            </div>
            <span className="text-xs text-gray-500">点击或拖拽添加视频</span>
            {pendingVideos.length > 0 && (
              <span className="text-[10px] text-blue-400">{pendingVideos.length} 个已选</span>
            )}
          </button>
        </div>

        {/* 已上传文件缩略图 */}
        {pendingFiles.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {pendingFiles.map((f, i) => (
              <div key={i} className="relative group">
                <div className="w-14 h-14 rounded-lg bg-surface-light border border-border overflow-hidden flex items-center justify-center">
                  {f.contentType?.startsWith('image/') ? (
                    <img src={f.url} alt={f.originalName} className="w-full h-full object-cover" />
                  ) : f.contentType?.startsWith('video/') ? (
                    <video src={f.url} className="w-full h-full object-cover" muted />
                  ) : (
                    <Video size={16} className="text-gray-500" />
                  )}
                </div>
                {f.contentType?.startsWith('video/') && (
                  <span className="absolute bottom-0.5 left-0.5 text-[8px] bg-black/60 text-white px-1 rounded">▶</span>
                )}
                <button
                  onClick={() => setPendingFiles(prev => prev.filter((_, idx) => idx !== i))}
                  className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-600 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X size={10} className="text-white" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 输入区 */}
        <form onSubmit={handleSubmit} className="flex items-end gap-2 bg-surface-light border border-border rounded-xl px-3 py-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="描述你想创作的视频..."
            rows={1}
            disabled={starting}
            className="flex-1 bg-transparent text-sm text-white resize-none placeholder:text-gray-500 focus:outline-none min-h-[36px] max-h-[120px] py-1.5"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e)
              }
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement
              target.style.height = 'auto'
              target.style.height = `${Math.min(target.scrollHeight, 120)}px`
            }}
          />
          <button
            type="submit"
            disabled={(!input.trim() && pendingFiles.length === 0) || starting}
            className="p-1.5 rounded-lg bg-primary text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-600 transition-colors shrink-0"
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  )
}
