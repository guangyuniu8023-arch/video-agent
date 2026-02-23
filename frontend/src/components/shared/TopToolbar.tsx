import { useState, useCallback, useEffect } from 'react'
import { Play, Square, RotateCcw, Rocket, Copy, Check, History, Save } from 'lucide-react'

interface TopToolbarProps {
  projectId: string | null
  running: boolean
  onStart: () => void
  onStop: () => void
  onReset: () => void
  onVersionLoaded?: () => void
}

export function TopToolbar({ projectId, running, onStart, onStop, onReset, onVersionLoaded }: TopToolbarProps) {
  const [publishing, setPublishing] = useState(false)
  const [showPublish, setShowPublish] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [showGuide, setShowGuide] = useState<{ version: string; nodes: number; edges: number; agents: number } | null>(null)
  const [version, setVersion] = useState('')
  const [desc, setDesc] = useState('')
  const [copied, setCopied] = useState('')
  const [versions, setVersions] = useState<Array<{ id: number; version: string; description: string; is_published: boolean; created_at: string; nodes: number; edges: number; agents: number }>>([])
  const [currentVersion, setCurrentVersion] = useState<string | null>(null)

  const loadVersions = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/versions')
      const data = await res.json()
      setVersions(data.versions || [])
      const published = (data.versions || []).find((v: Record<string, unknown>) => v.is_published)
      setCurrentVersion(published?.version || null)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadVersions() }, [loadVersions])

  const handlePublish = useCallback(async () => {
    if (!version.trim()) return
    setPublishing(true)
    try {
      const res = await fetch('/api/v1/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ version: version.trim(), description: desc.trim() }),
      })
      const data = await res.json()
      if (res.ok) {
        setShowPublish(false)
        setShowGuide({ version: version.trim(), nodes: data.nodes, edges: data.edges, agents: data.agents })
        setVersion('')
        setDesc('')
        loadVersions()
      } else {
        alert(`发布失败: ${data.detail || '未知错误'}`)
      }
    } catch (e) {
      alert(`发布失败: ${e}`)
    } finally {
      setPublishing(false)
    }
  }, [version, desc])

  const copyText = useCallback((text: string, label: string) => {
    navigator.clipboard.writeText(text)
    setCopied(label)
    setTimeout(() => setCopied(''), 2000)
  }, [])

  return (
    <div className="h-12 bg-surface border-b border-border flex items-center px-4 gap-3 shrink-0 relative">
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
          <span className="text-white text-xs font-bold">VA</span>
        </div>
        <span className="font-semibold text-sm text-white">Video Agent</span>
      </div>

      <div className="h-5 w-px bg-border mx-1" />

      {projectId && (
        <span className="text-xs text-gray-500 font-mono">
          {projectId.slice(0, 8)}...
        </span>
      )}

      <div className="flex-1" />

      <div className="flex items-center gap-1.5">
        {!running ? (
          <button onClick={onStart}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-500 text-white text-xs rounded-md transition-colors">
            <Play size={12} />运行
          </button>
        ) : (
          <button onClick={onStop}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs rounded-md transition-colors">
            <Square size={12} />停止
          </button>
        )}
        <button onClick={onReset}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-md transition-colors">
          <RotateCcw size={12} />重置
        </button>

        <div className="h-5 w-px bg-border mx-1" />

        <button
          onClick={async () => {
            const res = await fetch('/api/v1/save', { method: 'POST' })
            const data = await res.json()
            if (res.ok) {
              setCopied('saved')
              setTimeout(() => setCopied(''), 2000)
              loadVersions()
            }
          }}
          className="flex items-center gap-1.5 px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-md transition-colors"
          title={currentVersion ? `保存到 ${currentVersion}` : '保存草稿'}
        >
          {copied === 'saved' ? <Check size={12} className="text-green-400" /> : <Save size={12} />}
          {copied === 'saved' ? '已保存' : '保存'}
        </button>

        {currentVersion && (
          <span className="text-[10px] text-purple-400 bg-purple-900/30 px-2 py-0.5 rounded">
            {currentVersion}
          </span>
        )}

        <button onClick={() => { setShowVersions(!showVersions); setShowPublish(false) }}
          className="flex items-center gap-1.5 px-2 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-md transition-colors"
          title="版本历史">
          <History size={12} />
        </button>

        <button onClick={() => { setShowPublish(!showPublish); setShowVersions(false) }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs rounded-md transition-colors">
          <Rocket size={12} />发布
        </button>
      </div>

      {showVersions && (
        <div className="absolute right-4 top-12 z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl w-72 max-h-80 overflow-auto">
          <div className="px-3 py-2 border-b border-gray-700 flex items-center justify-between sticky top-0 bg-gray-800">
            <span className="text-xs font-medium text-white">版本历史</span>
            <button onClick={() => setShowVersions(false)} className="text-gray-400 hover:text-white text-sm">×</button>
          </div>
          {versions.filter(v => v.version !== '_draft').length === 0 ? (
            <div className="p-3 text-[10px] text-gray-500 text-center">暂无发布版本</div>
          ) : (
            <div className="p-2 space-y-1">
              {versions.filter(v => v.version !== '_draft').map(v => (
                <div key={v.id} className={`px-3 py-2 rounded-lg group ${v.is_published ? 'bg-purple-900/20 border border-purple-500/30' : 'bg-gray-900/50 hover:bg-gray-700'}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-white">{v.version}</span>
                    <div className="flex items-center gap-1">
                      {v.is_published && <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-600/30 text-purple-300">当前</span>}
                      <button
                        onClick={async () => {
                          if (!confirm(`加载版本 ${v.version} 到画布？当前未保存的修改将丢失。`)) return
                          const res = await fetch(`/api/v1/versions/${v.id}/load`, { method: 'POST' })
                          if (res.ok) {
                            await loadVersions()
                            setShowVersions(false)
                            await new Promise(r => setTimeout(r, 300))
                            onVersionLoaded?.()
                          }
                        }}
                        className="text-[9px] px-1.5 py-0.5 rounded text-blue-400 hover:bg-blue-600/20 opacity-0 group-hover:opacity-100 transition-opacity"
                      >加载</button>
                      <button
                        onClick={async () => {
                          if (!confirm(`确定删除版本 ${v.version}?`)) return
                          await fetch(`/api/v1/versions/${v.id}`, { method: 'DELETE' })
                          loadVersions()
                        }}
                        className="text-[9px] px-1.5 py-0.5 rounded text-red-400 hover:bg-red-600/20 opacity-0 group-hover:opacity-100 transition-opacity"
                      >删除</button>
                    </div>
                  </div>
                  {v.description && <div className="text-[10px] text-gray-400 mt-0.5">{v.description}</div>}
                  <div className="text-[9px] text-gray-600 mt-1">
                    {v.nodes} 节点 · {v.edges} 边 · {v.agents} Agent · {new Date(v.created_at).toLocaleString('zh-CN')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {showPublish && (
        <div className="absolute right-4 top-12 z-50 bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-3 w-64 space-y-2">
          <div className="text-xs font-medium text-white">发布当前配置为版本</div>
          <input value={version} onChange={e => setVersion(e.target.value)} placeholder="版本号 (如 v1.0)"
            className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-purple-500" />
          <input value={desc} onChange={e => setDesc(e.target.value)} placeholder="描述 (可选)"
            className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-purple-500" />
          <div className="flex gap-1.5">
            <button onClick={handlePublish} disabled={!version.trim() || publishing}
              className="flex-1 text-xs py-1.5 rounded bg-purple-600 text-white hover:bg-purple-500 disabled:opacity-40">
              {publishing ? '发布中...' : '确认发布'}
            </button>
            <button onClick={() => setShowPublish(false)}
              className="text-xs px-3 py-1.5 rounded bg-gray-700 text-gray-300">取消</button>
          </div>
          <div className="text-[9px] text-gray-500">发布后可通过 /api/v1/video/ 外部调用</div>
        </div>
      )}

      {showGuide && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowGuide(null)}>
          <div className="bg-gray-800 border border-gray-600 rounded-xl shadow-2xl w-[560px] max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="px-5 py-4 border-b border-gray-700">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-white">版本 {showGuide.version} 发布成功</h2>
                  <div className="text-[10px] text-gray-400 mt-0.5">{showGuide.nodes} 节点, {showGuide.edges} 边, {showGuide.agents} Agent</div>
                </div>
                <button onClick={() => setShowGuide(null)} className="text-gray-400 hover:text-white text-lg">×</button>
              </div>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <h3 className="text-xs font-medium text-blue-400 mb-2">方式 1: REST API</h3>
                <div className="bg-gray-900 rounded-lg p-3 relative group">
                  <pre className="text-[10px] text-gray-300 whitespace-pre-wrap">{`# 启动生成
curl -X POST http://localhost:8000/api/v1/video/generate \\
  -H 'Content-Type: application/json' \\
  -d '{"prompt": "你的视频描述"}'

# 查询结果
curl http://localhost:8000/api/v1/video/{project_id}/result`}</pre>
                  <button onClick={() => copyText(`curl -X POST http://localhost:8000/api/v1/video/generate -H 'Content-Type: application/json' -d '{"prompt": "你的视频描述"}'`, 'rest')}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-white transition-opacity">
                    {copied === 'rest' ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                </div>
              </div>

              <div>
                <h3 className="text-xs font-medium text-orange-400 mb-2">方式 2: MCP Server (供 Claude / Cursor 等 Agent 调用)</h3>
                <div className="bg-gray-900 rounded-lg p-3 relative group">
                  <pre className="text-[10px] text-gray-300 whitespace-pre-wrap">{`# 启动 MCP 服务
python mcp_server.py                    # stdio 模式
python mcp_server.py --transport sse    # SSE 模式

# Claude Desktop 配置 (claude_desktop_config.json):
{
  "mcpServers": {
    "video-agent": {
      "command": "python",
      "args": ["${window.location.origin.replace(':5173', '')}/backend/mcp_server.py"]
    }
  }
}`}</pre>
                  <button onClick={() => copyText('python mcp_server.py --transport sse --port 3100', 'mcp')}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-white transition-opacity">
                    {copied === 'mcp' ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                </div>
                <div className="text-[10px] text-gray-500 mt-1">
                  提供两个工具: generate_video (启动生成) + get_video_status (查询结果)
                </div>
              </div>

              <div>
                <h3 className="text-xs font-medium text-purple-400 mb-2">方式 3: Python SDK 调用</h3>
                <div className="bg-gray-900 rounded-lg p-3 relative group">
                  <pre className="text-[10px] text-gray-300 whitespace-pre-wrap">{`import httpx, time

API = "http://localhost:8000/api/v1/video"

# 启动
resp = httpx.post(f"{API}/generate", json={"prompt": "拍一个日落延时"})
pid = resp.json()["project_id"]

# 轮询等待
while True:
    r = httpx.get(f"{API}/{pid}/result").json()
    if r["status"] in ("complete", "error"):
        break
    time.sleep(5)

print(r["final_video_url"])  # 视频地址`}</pre>
                  <button onClick={() => copyText(`import httpx, time\nAPI = "http://localhost:8000/api/v1/video"\nresp = httpx.post(f"{API}/generate", json={"prompt": "拍一个日落延时"})\npid = resp.json()["project_id"]\nwhile True:\n    r = httpx.get(f"{API}/{pid}/result").json()\n    if r["status"] in ("complete", "error"): break\n    time.sleep(5)\nprint(r["final_video_url"])`, 'python')}
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-white transition-opacity">
                    {copied === 'python' ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
