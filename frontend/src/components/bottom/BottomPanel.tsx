import { useRef, useEffect, useState, useCallback } from 'react'
import { Send, X, ImageIcon, Video, Plus, Upload } from 'lucide-react'
import type { LogEntry, ChatMessage, UploadedFile } from '@/types'
import { uploadFile } from '@/services/api'

interface BottomPanelProps {
  logs: LogEntry[]
  chatMessages: ChatMessage[]
  waitingForReply: boolean
  streamingText: { agent: string; content: string } | null
  projectId: string | null
  onSendMessage: (message: string, attachments?: UploadedFile[]) => void
  onReply: (message: string) => void
  connected: boolean
  canSend?: boolean
  sending?: boolean
}

const agentColors: Record<string, string> = {
  system: 'text-gray-400',
  router: 'text-purple-400',
  planner: 'text-blue-400',
  producer: 'text-green-400',
  editor: 'text-orange-400',
  quality_gate: 'text-yellow-400',
  human_feedback: 'text-cyan-400',
}

export function BottomPanel({
  logs,
  chatMessages,
  waitingForReply,
  streamingText,
  projectId,
  onSendMessage,
  onReply,
  connected,
  canSend = true,
  sending = false,
}: BottomPanelProps) {
  const [activeTab, setActiveTab] = useState<'chat' | 'logs'>('chat')
  const [input, setInput] = useState('')
  const [pendingFiles, setPendingFiles] = useState<UploadedFile[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragOverType, setDragOverType] = useState<'image' | 'video' | 'global' | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const videoInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, streamingText])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => {
    if (waitingForReply) setActiveTab('chat')
  }, [waitingForReply])

  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed && pendingFiles.length === 0) return

    if (waitingForReply) {
      onReply(trimmed)
    } else {
      onSendMessage(trimmed, pendingFiles.length > 0 ? pendingFiles : undefined)
    }
    setInput('')
    setPendingFiles([])
  }, [input, pendingFiles, waitingForReply, onSendMessage, onReply])

  const handleFileUpload = useCallback(async (files: FileList | null, filterType?: 'image' | 'video') => {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        if (filterType === 'image' && !file.type.startsWith('image/')) continue
        if (filterType === 'video' && !file.type.startsWith('video/')) continue
        const result = await uploadFile(file, projectId ?? undefined)
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
  }, [projectId])

  const handleDropOnZone = useCallback((e: React.DragEvent, type: 'image' | 'video') => {
    e.preventDefault()
    e.stopPropagation()
    setDragOverType(null)
    handleFileUpload(e.dataTransfer.files, type)
  }, [handleFileUpload])

  const handleGlobalDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOverType(null)
    handleFileUpload(e.dataTransfer.files)
  }, [handleFileUpload])

  const removePendingFile = useCallback((idx: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== idx))
  }, [])

  const pendingImages = pendingFiles.filter(f => f.contentType?.startsWith('image/'))
  const pendingVideos = pendingFiles.filter(f => f.contentType?.startsWith('video/'))

  return (
    <div
      className="h-full flex flex-col border-t border-border bg-surface relative"
      onDragOver={(e) => { e.preventDefault(); if (!dragOverType) setDragOverType('global') }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setDragOverType(null) }}
      onDrop={handleGlobalDrop}
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

      {/* Tab 栏 */}
      <div className="flex border-b border-border shrink-0">
        <button
          onClick={() => setActiveTab('chat')}
          className={`px-4 py-1.5 text-xs font-medium transition-colors relative ${
            activeTab === 'chat' ? 'text-blue-400' : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          对话
          {waitingForReply && (
            <span className="ml-1.5 w-2 h-2 bg-yellow-500 rounded-full inline-block animate-pulse" />
          )}
          {activeTab === 'chat' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400" />
          )}
        </button>
        <button
          onClick={() => setActiveTab('logs')}
          className={`px-4 py-1.5 text-xs font-medium transition-colors relative ${
            activeTab === 'logs' ? 'text-blue-400' : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          日志 ({logs.length})
          {activeTab === 'logs' && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400" />
          )}
        </button>
        <div className="flex-1" />
        <div className="flex items-center gap-1.5 px-3 text-[10px]">
          <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-gray-500">{connected ? '已连接' : '未连接'}</span>
        </div>
      </div>

      {/* 内容区 */}
      <div className="flex-1 min-h-0 flex flex-col">
        {activeTab === 'chat' ? (
          <>
            {/* 对话消息列表 */}
            <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
              {chatMessages.length === 0 ? (
                <div className="h-full flex items-center justify-center text-gray-500 text-sm">
                  输入视频创作需求开始对话
                </div>
              ) : (
                chatMessages.map((msg) => (
                  <ChatBubble key={msg.id} message={msg} />
                ))
              )}
              {streamingText && (
                <StreamingBubble agent={streamingText.agent} content={streamingText.content} />
              )}
              <div ref={chatEndRef} />
            </div>

            {/* 追问提示 */}
            {waitingForReply && (
              <div className="px-4 py-1.5 bg-yellow-900/20 border-t border-yellow-800/30 text-xs text-yellow-400 flex items-center gap-2">
                <span className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse shrink-0" />
                Agent 正在等待你的回复，请在下方输入
              </div>
            )}

            {/* 虚线框上传区 */}
            <div className="px-4 py-2 border-t border-border">
              <input ref={imageInputRef} type="file" accept="image/*" multiple className="hidden"
                onChange={(e) => handleFileUpload(e.target.files, 'image')} />
              <input ref={videoInputRef} type="file" accept="video/*" multiple className="hidden"
                onChange={(e) => handleFileUpload(e.target.files, 'video')} />

              <div className="flex gap-3 mb-2">
                {/* 图片上传区 */}
                <button
                  type="button"
                  onClick={() => imageInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOverType('image') }}
                  onDragLeave={(e) => { e.stopPropagation(); setDragOverType(null) }}
                  onDrop={(e) => handleDropOnZone(e, 'image')}
                  disabled={uploading}
                  className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-all duration-150 cursor-pointer
                    ${dragOverType === 'image'
                      ? 'border-primary bg-primary/5 scale-[1.02]'
                      : 'border-gray-600 hover:border-primary/50 hover:bg-white/[0.02]'}
                    disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <div className="flex items-center gap-1 text-gray-400">
                    <ImageIcon size={16} />
                    <Plus size={12} />
                  </div>
                  <span className="text-[10px] text-gray-500">点击或拖拽添加图片</span>
                  {pendingImages.length > 0 && (
                    <span className="text-[10px] text-blue-400">{pendingImages.length} 张已选</span>
                  )}
                </button>

                {/* 视频上传区 */}
                <button
                  type="button"
                  onClick={() => videoInputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setDragOverType('video') }}
                  onDragLeave={(e) => { e.stopPropagation(); setDragOverType(null) }}
                  onDrop={(e) => handleDropOnZone(e, 'video')}
                  disabled={uploading}
                  className={`flex-1 flex flex-col items-center justify-center gap-1 py-3 rounded-lg border-2 border-dashed transition-all duration-150 cursor-pointer
                    ${dragOverType === 'video'
                      ? 'border-primary bg-primary/5 scale-[1.02]'
                      : 'border-gray-600 hover:border-primary/50 hover:bg-white/[0.02]'}
                    disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <div className="flex items-center gap-1 text-gray-400">
                    <Video size={16} />
                    <Plus size={12} />
                  </div>
                  <span className="text-[10px] text-gray-500">点击或拖拽添加视频</span>
                  {pendingVideos.length > 0 && (
                    <span className="text-[10px] text-blue-400">{pendingVideos.length} 个已选</span>
                  )}
                </button>
              </div>

              {/* 已上传文件缩略图 */}
              {pendingFiles.length > 0 && (
                <div className="flex gap-2 flex-wrap mb-2">
                  {pendingFiles.map((f, i) => (
                    <div key={i} className="relative group">
                      <div className="w-14 h-14 rounded-lg bg-surface-light border border-border overflow-hidden flex items-center justify-center">
                        {f.contentType?.startsWith('image/') ? (
                          <img src={f.url} alt={f.originalName} className="w-full h-full object-cover" />
                        ) : f.contentType?.startsWith('video/') ? (
                          <video src={f.url} className="w-full h-full object-cover" muted />
                        ) : (
                          <ImageIcon size={16} className="text-gray-500" />
                        )}
                      </div>
                      {f.contentType?.startsWith('video/') && (
                        <span className="absolute bottom-0.5 left-0.5 text-[8px] bg-black/60 text-white px-1 rounded">▶</span>
                      )}
                      <button
                        onClick={() => removePendingFile(i)}
                        className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-red-600 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X size={10} className="text-white" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 输入区 */}
            <form onSubmit={handleSubmit} className="px-4 py-2 border-t border-border flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  !canSend ? '工作流运行中...'
                  : waitingForReply ? '输入回复...'
                  : '描述你想创作的视频...'
                }
                rows={1}
                disabled={!canSend}
                className="flex-1 bg-surface-light border border-border rounded-lg px-3 py-2 text-sm text-white resize-none placeholder:text-gray-500 focus:outline-none focus:border-primary transition-colors min-h-[36px] max-h-[100px] disabled:opacity-50"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSubmit(e)
                  }
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = `${Math.min(target.scrollHeight, 100)}px`
                }}
              />
              <button
                type="submit"
                disabled={!canSend || sending || (!input.trim() && pendingFiles.length === 0)}
                className="p-2 rounded-lg bg-primary text-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-600 transition-colors shrink-0"
              >
                {sending ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Send size={16} />
                )}
              </button>
            </form>
          </>
        ) : (
          <div className="flex-1 overflow-auto p-3 font-mono text-xs">
            {logs.length === 0 ? (
              <div className="h-full flex items-center justify-center text-gray-500">
                等待工作流启动...
              </div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="flex gap-2 py-0.5 hover:bg-white/5 px-1 rounded">
                  <span className="text-gray-600 shrink-0">
                    {new Date(log.timestamp * 1000).toLocaleTimeString()}
                  </span>
                  <span className={`shrink-0 w-24 text-right ${agentColors[log.agent] ?? 'text-gray-400'}`}>
                    {log.agent}
                  </span>
                  <span className="text-gray-300">{log.message}</span>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>
    </div>
  )
}

const agentLabels: Record<string, string> = {
  planner: 'Planner',
  producer: 'Producer',
  editor: 'Editor',
  router: 'Router',
}

function StreamingBubble({ agent, content }: { agent: string; content: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed bg-surface-light text-gray-200 border border-blue-500/30 rounded-bl-sm">
        <div className="text-[10px] text-blue-400 mb-1 font-medium flex items-center gap-1.5">
          {agentLabels[agent] ?? agent}
          <span className="inline-block w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
          <span className="text-gray-500">思考中...</span>
        </div>
        {content ? (
          <div className="whitespace-pre-wrap">{content}<span className="inline-block w-0.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-text-bottom" /></div>
        ) : (
          <div className="flex gap-1 py-1">
            <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        )}
      </div>
    </div>
  )
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  if (isSystem) {
    return (
      <div className="text-center text-xs text-gray-500 py-1">
        {message.content}
      </div>
    )
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed ${
          isUser
            ? 'bg-primary/90 text-white rounded-br-sm'
            : 'bg-surface-light text-gray-200 border border-border rounded-bl-sm'
        }`}
      >
        {!isUser && (
          <div className="text-[10px] text-blue-400 mb-1 font-medium">Agent</div>
        )}
        <div className="whitespace-pre-wrap">{message.content}</div>
        {message.attachments && message.attachments.length > 0 && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {message.attachments.map((att, i) =>
              att.contentType?.startsWith('video/') ? (
                <video key={i} src={att.url} controls muted className="w-48 rounded border border-white/10" />
              ) : (
                <img key={i} src={att.url} alt={att.originalName} className="w-20 h-20 rounded object-cover border border-white/10" />
              )
            )}
          </div>
        )}
        <div className={`text-[10px] mt-1 ${isUser ? 'text-blue-200' : 'text-gray-500'}`}>
          {new Date(message.timestamp * 1000).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
