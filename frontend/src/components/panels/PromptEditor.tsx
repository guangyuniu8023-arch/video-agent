import { useState, useEffect, useCallback, useRef } from 'react'
import Editor, { type OnMount } from '@monaco-editor/react'
import {
  fetchAgentPrompt, updateAgentPrompt, resetAgentPrompt,
  fetchAgentVersions, rollbackAgentPrompt,
} from '@/services/api'

interface PromptEditorProps {
  agentId: string
}

export function PromptEditor({ agentId }: PromptEditorProps) {
  const [prompt, setPrompt] = useState('')
  const [original, setOriginal] = useState('')
  const [isCustom, setIsCustom] = useState(false)
  const [version, setVersion] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [showVersions, setShowVersions] = useState(false)
  const [versions, setVersions] = useState<VersionItem[]>([])
  const editorRef = useRef<ReturnType<OnMount> | null>(null)

  interface VersionItem {
    version: number
    system_prompt: string
    is_active: boolean
    editor: string
    created_at: string
  }

  const loadPrompt = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAgentPrompt(agentId)
      setPrompt(data.prompt)
      setOriginal(data.prompt)
      setIsCustom(data.is_custom)
      setVersion(data.version ?? null)
    } catch {
      setMessage({ text: '加载失败', type: 'error' })
    } finally {
      setLoading(false)
    }
  }, [agentId])

  useEffect(() => { loadPrompt() }, [loadPrompt])

  const hasChanges = prompt !== original

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const res = await updateAgentPrompt(agentId, prompt)
      setOriginal(prompt)
      setIsCustom(true)
      setVersion(res.version ?? version)
      setMessage({ text: '已保存，立即生效', type: 'success' })
      setTimeout(() => setMessage(null), 3000)
    } catch {
      setMessage({ text: '保存失败', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const data = await resetAgentPrompt(agentId)
      setPrompt(data.prompt)
      setOriginal(data.prompt)
      setIsCustom(false)
      setMessage({ text: '已重置为默认 Prompt', type: 'success' })
      setTimeout(() => setMessage(null), 3000)
    } catch {
      setMessage({ text: '重置失败', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleShowVersions = async () => {
    if (showVersions) {
      setShowVersions(false)
      return
    }
    try {
      const data = await fetchAgentVersions(agentId)
      setVersions(data.versions)
      setShowVersions(true)
    } catch {
      setMessage({ text: '获取版本历史失败', type: 'error' })
    }
  }

  const handleRollback = async (targetVersion: number) => {
    setSaving(true)
    try {
      const data = await rollbackAgentPrompt(agentId, targetVersion)
      setPrompt(data.system_prompt)
      setOriginal(data.system_prompt)
      setIsCustom(true)
      setShowVersions(false)
      setMessage({ text: `已回滚到版本 ${targetVersion}`, type: 'success' })
      setTimeout(() => setMessage(null), 3000)
    } catch {
      setMessage({ text: '回滚失败', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleEditorMount: OnMount = (editor) => {
    editorRef.current = editor
  }

  if (loading) {
    return <div className="p-4 text-sm text-gray-500">加载中...</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface-light border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">
            {prompt.length} 字符
          </span>
          {version && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
              v{version}
            </span>
          )}
          {isCustom && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-900/50 text-yellow-400">
              已修改
            </span>
          )}
          {hasChanges && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-900/50 text-blue-400">
              未保存
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleShowVersions}
            className="text-[10px] px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors"
          >
            {showVersions ? '关闭历史' : '版本历史'}
          </button>
          {isCustom && (
            <button
              onClick={handleReset}
              disabled={saving}
              className="text-[10px] px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-40 transition-colors"
            >
              重置默认
            </button>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="text-[10px] px-2 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-40 transition-colors"
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>

      {/* 消息提示 */}
      {message && (
        <div className={`px-3 py-1.5 text-xs shrink-0 ${
          message.type === 'success' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
        }`}>
          {message.text}
        </div>
      )}

      {/* 版本历史面板 */}
      {showVersions && (
        <div className="border-b border-border max-h-48 overflow-auto shrink-0">
          {versions.length === 0 ? (
            <div className="p-3 text-xs text-gray-500">暂无版本历史</div>
          ) : (
            <div className="divide-y divide-border">
              {versions.map((v) => (
                <div key={v.version} className="flex items-center justify-between px-3 py-2 hover:bg-white/5">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-gray-300">v{v.version}</span>
                      {v.is_active && (
                        <span className="text-[10px] px-1 py-0.5 rounded bg-green-900/50 text-green-400">当前</span>
                      )}
                      <span className="text-[10px] text-gray-500">{v.editor}</span>
                    </div>
                    <p className="text-[10px] text-gray-500 truncate mt-0.5">{v.system_prompt}</p>
                  </div>
                  {!v.is_active && (
                    <button
                      onClick={() => handleRollback(v.version)}
                      disabled={saving}
                      className="text-[10px] px-2 py-1 rounded bg-orange-900/50 hover:bg-orange-900/70 text-orange-400 disabled:opacity-40 shrink-0 ml-2"
                    >
                      回滚
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          defaultLanguage="markdown"
          value={prompt}
          onChange={(value) => setPrompt(value ?? '')}
          onMount={handleEditorMount}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: 'off',
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            folding: false,
            glyphMargin: false,
            lineDecorationsWidth: 8,
            lineNumbersMinChars: 0,
            renderLineHighlight: 'none',
            overviewRulerBorder: false,
            hideCursorInOverviewRuler: true,
            overviewRulerLanes: 0,
            scrollbar: {
              verticalScrollbarSize: 6,
              horizontalScrollbarSize: 6,
            },
            padding: { top: 8, bottom: 8 },
          }}
        />
      </div>
    </div>
  )
}
