import { useState, useCallback, useRef, useEffect } from 'react'
import { Send, Check, RotateCcw, FileText, Code } from 'lucide-react'

interface SkillCreatorProps {
  agentId: string
  onCreated: () => void
  onClose: () => void
}

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  skillDef?: { name: string; files: Record<string, string> } | null
}

export function SkillCreator({ agentId, onCreated, onClose }: SkillCreatorProps) {
  const [messages, setMessages] = useState<ChatMsg[]>([{
    role: 'assistant',
    content: '你好！我是 Skill 创建助手。请描述你想创建什么样的 Skill，我会帮你生成完整的 Skill 定义。\n\n例如:\n- "我需要一个搜索 Google 的工具"\n- "帮我创建一个图片压缩的 Skill"\n- "我想要一个读取 CSV 文件并分析数据的工具"',
  }])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [savedSkillDef, setSavedSkillDef] = useState<{ name: string; files: Record<string, string> } | null>(null)
  const [saving, setSaving] = useState(false)
  const [previewFile, setPreviewFile] = useState<string | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async () => {
    if (!input.trim() || sending) return
    const userMsg = input.trim()
    setInput('')

    const history = messages.map(m => ({ role: m.role, content: m.content }))
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setSending(true)

    try {
      const res = await fetch('/api/admin/skills/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, history }),
      })
      const data = await res.json()

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.reply,
        skillDef: data.skill_definition || null,
      }])

      if (data.skill_definition) {
        setSavedSkillDef(data.skill_definition)
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `生成失败: ${err}`,
      }])
    } finally {
      setSending(false)
    }
  }, [input, sending, messages])

  const handleSave = useCallback(async () => {
    if (!savedSkillDef || saving) return
    setSaving(true)
    try {
      await fetch('/api/admin/skills/save-generated', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(savedSkillDef),
      })

      const currentTools = await fetch(`/api/admin/agents/${agentId}/tools`).then(r => r.json())
      const toolNames = (currentTools.tools || []).map((t: Record<string, string>) => t.name)
      if (!toolNames.includes(savedSkillDef.name)) {
        await fetch(`/api/admin/agents/${agentId}/tools`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ tools: [...toolNames, savedSkillDef.name] }),
        })
      }

      onCreated()
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `保存失败: ${err}` }])
    } finally {
      setSaving(false)
    }
  }, [savedSkillDef, saving, agentId, onCreated])

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
            <h3 className="font-semibold text-white">Skill 创建器</h3>
            <span className="text-[10px] text-emerald-400 bg-emerald-900/30 px-1.5 py-0.5 rounded">AI</span>
          </div>
          <button onClick={onClose} className="text-xs text-gray-400 hover:text-white">关闭</button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-3">
        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[90%] rounded-lg px-3 py-2 text-xs ${
                msg.role === 'user'
                  ? 'bg-blue-600/30 text-blue-100'
                  : 'bg-gray-800 text-gray-200'
              }`}>
                <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
              </div>
            </div>

            {msg.skillDef && (
              <div className="mt-2 border border-emerald-500/30 rounded-lg bg-emerald-950/10 overflow-hidden">
                <div className="px-3 py-2 border-b border-emerald-500/20 flex items-center justify-between">
                  <span className="text-xs font-medium text-emerald-300">
                    生成的 Skill: {msg.skillDef.name}
                  </span>
                  <span className="text-[9px] text-gray-500">{Object.keys(msg.skillDef.files).length} 个文件</span>
                </div>

                <div className="p-2 space-y-1">
                  {Object.entries(msg.skillDef.files).map(([fileName]) => (
                    <button
                      key={fileName}
                      onClick={() => setPreviewFile(previewFile === fileName ? null : fileName)}
                      className="w-full flex items-center gap-1.5 px-2 py-1 rounded text-xs hover:bg-gray-800 text-gray-300"
                    >
                      {fileName.endsWith('.py') ? <Code size={10} className="text-yellow-400" /> : <FileText size={10} className="text-emerald-400" />}
                      {fileName}
                      <span className="text-[9px] text-gray-600 ml-auto">{previewFile === fileName ? '▼' : '▸'}</span>
                    </button>
                  ))}
                </div>

                {previewFile && msg.skillDef.files[previewFile] && (
                  <div className="px-3 py-2 border-t border-emerald-500/20">
                    <pre className="text-[10px] text-gray-400 whitespace-pre-wrap max-h-40 overflow-auto font-mono bg-gray-900 rounded p-2">
                      {msg.skillDef.files[previewFile]}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="bg-gray-800 rounded-lg px-3 py-2 text-xs text-gray-400">
              <span className="animate-pulse">思考中...</span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {savedSkillDef && (
        <div className="px-3 py-2 border-t border-emerald-500/30 bg-emerald-950/10 flex items-center gap-2 shrink-0">
          <Check size={12} className="text-emerald-400" />
          <span className="text-xs text-emerald-300 flex-1">
            Skill "{savedSkillDef.name}" 已就绪
          </span>
          <button onClick={handleSave} disabled={saving}
            className="text-[10px] px-3 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40">
            {saving ? '保存中...' : '确认创建'}
          </button>
        </div>
      )}

      <div className="px-3 py-2 border-t border-border shrink-0 flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="描述你想要的 Skill..."
          disabled={sending}
          className="flex-1 text-xs bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500 disabled:opacity-50"
        />
        <button onClick={handleSend} disabled={sending || !input.trim()}
          className="px-2 py-1.5 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-40">
          <Send size={12} />
        </button>
      </div>
    </div>
  )
}
