import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Bot, Wrench, Server, Users, Search } from 'lucide-react'
import { createAgent, createCanvasNode, fetchAgents } from '@/services/api'

interface NodePickerProps {
  x: number
  y: number
  canvasX: number
  canvasY: number
  parentCanvas?: string
  onClose: () => void
  onNodeCreated: () => void
  onLocateNode?: (nodeId: string) => void
  onDeleteNode?: (nodeId: string) => void
}

type Tab = 'search' | 'agent' | 'skill' | 'mcp'

const TABS: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'search', label: '搜索', icon: <Search size={12} /> },
  { key: 'agent', label: 'Agent', icon: <Bot size={12} /> },
  { key: 'skill', label: 'Skill', icon: <Wrench size={12} /> },
  { key: 'mcp', label: 'MCP', icon: <Server size={12} /> },
]

interface ExistingItem {
  id: string
  name: string
  type: 'agent' | 'sub-agent' | 'skill' | 'mcp'
  description: string
}

export function NodePicker({ x, y, canvasX, canvasY, parentCanvas, onClose, onNodeCreated, onLocateNode, onDeleteNode }: NodePickerProps) {
  const [activeTab, setActiveTab] = useState<Tab>('search')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="fixed z-50 bg-gray-800 border border-gray-600 rounded-xl shadow-2xl w-80 overflow-hidden"
      style={{ left: Math.min(x, window.innerWidth - 340), top: Math.min(y, window.innerHeight - 450) }}
    >
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <span className="text-xs font-medium text-white">添加节点</span>
        <button onClick={onClose} className="text-gray-400 hover:text-white"><X size={14} /></button>
      </div>

      <div className="flex border-b border-gray-700 overflow-x-auto">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center justify-center gap-1 px-2.5 py-1.5 text-[10px] font-medium transition-colors whitespace-nowrap ${
              activeTab === tab.key
                ? 'text-blue-400 border-b-2 border-blue-400 -mb-px'
                : 'text-gray-400 hover:text-gray-300'
            }`}
          >
            {tab.icon}{tab.label}
          </button>
        ))}
      </div>

      <div className="p-3 max-h-72 overflow-auto">
        {activeTab === 'search' && (
          <ExistingSearch
            canvasX={canvasX} canvasY={canvasY}
            onLocate={(nodeId) => { onLocateNode?.(nodeId); onClose() }}
            onDelete={(nodeId) => { onDeleteNode?.(nodeId); onNodeCreated() }}
            onAddToCanvas={(nodeId) => { onNodeCreated() }}
            onClose={onClose}
          />
        )}
        {activeTab === 'agent' && (
          <AgentForm canvasX={canvasX} canvasY={canvasY} parentCanvas={parentCanvas} onCreated={onNodeCreated} onClose={onClose} />
        )}
        {activeTab === 'skill' && (
          <SkillList canvasX={canvasX} canvasY={canvasY} parentCanvas={parentCanvas} onCreated={onNodeCreated} onClose={onClose} />
        )}
        {activeTab === 'mcp' && (
          <McpForm canvasX={canvasX} canvasY={canvasY} parentCanvas={parentCanvas} onCreated={onNodeCreated} onClose={onClose} />
        )}
      </div>
    </div>
  )
}

function ExistingSearch({ canvasX, canvasY, onLocate, onDelete, onAddToCanvas, onClose }: {
  canvasX: number; canvasY: number
  onLocate: (nodeId: string) => void
  onDelete: (nodeId: string) => void
  onAddToCanvas: (nodeId: string) => void
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [items, setItems] = useState<ExistingItem[]>([])
  const [canvasNodeIds, setCanvasNodeIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    const results: ExistingItem[] = []
    try {
      const agentsRes = await fetch('/api/admin/agents')
      const agentsData = await agentsRes.json()
      for (const a of (agentsData.agents || [])) {
        results.push({ id: a.id, name: a.name, type: a.parent_id ? 'sub-agent' : 'agent', description: a.description || '' })
        for (const child of (a.children || [])) {
          results.push({ id: child.id, name: child.name, type: 'sub-agent', description: `${a.name} 的子 Agent` })
        }
      }
    } catch { /* ignore */ }
    try {
      const skillsRes = await fetch('/api/admin/skills')
      const skillsData = await skillsRes.json()
      for (const s of (skillsData.skills || [])) {
        results.push({ id: s.name, name: s.title || s.name, type: 'skill', description: s.description || '' })
      }
    } catch { /* ignore */ }
    try {
      const mcpRes = await fetch('/api/admin/mcp')
      const mcpData = await mcpRes.json()
      for (const m of (mcpData.servers || [])) {
        results.push({ id: m.id, name: m.name, type: 'mcp', description: `${m.transport} | ${m.status}` })
      }
    } catch { /* ignore */ }
    try {
      const canvasRes = await fetch('/api/admin/canvas/nodes')
      const canvasData = await canvasRes.json()
      setCanvasNodeIds(new Set((canvasData.nodes || []).map((n: Record<string, string>) => n.ref_id)))
    } catch { /* ignore */ }
    setItems(results)
    setLoading(false)
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const getCanvasId = (item: ExistingItem) => {
    if (item.type === 'agent' || item.type === 'sub-agent') return `agent:${item.id}`
    if (item.type === 'skill') return `skill:${item.id}`
    if (item.type === 'mcp') return `mcp:${item.id}`
    return item.id
  }

  const handleAddToCanvas = async (item: ExistingItem) => {
    const canvasId = getCanvasId(item)
    const nodeType = item.type === 'sub-agent' ? 'agent' : item.type
    try {
      await createCanvasNode({ id: canvasId, node_type: nodeType, ref_id: item.id, position_x: canvasX, position_y: canvasY })
      setCanvasNodeIds(prev => new Set([...prev, item.id]))
      onAddToCanvas(canvasId)
    } catch { /* ignore */ }
  }

  const handleDelete = async (item: ExistingItem) => {
    if (!confirm(`确定删除 ${item.type} "${item.name}"?`)) return
    const canvasId = getCanvasId(item)
    try {
      if (item.type === 'agent' || item.type === 'sub-agent') {
        await fetch(`/api/admin/agents/${item.id}`, { method: 'DELETE' })
      } else if (item.type === 'skill') {
        await fetch(`/api/admin/skills/${item.id}`, { method: 'DELETE' })
      } else if (item.type === 'mcp') {
        await fetch(`/api/admin/mcp/${item.id}`, { method: 'DELETE' })
      }
      try { await fetch(`/api/admin/canvas/nodes/${encodeURIComponent(canvasId)}`, { method: 'DELETE' }) } catch { /* ok */ }
      onDelete(canvasId)
      loadData()
    } catch { /* ignore */ }
  }

  const filtered = query.trim()
    ? items.filter(i =>
        i.id.toLowerCase().includes(query.toLowerCase()) ||
        i.name.toLowerCase().includes(query.toLowerCase()) ||
        i.description.toLowerCase().includes(query.toLowerCase())
      )
    : items

  const typeColors: Record<string, string> = {
    'agent': 'text-blue-400 bg-blue-900/30',
    'sub-agent': 'text-indigo-400 bg-indigo-900/30',
    'skill': 'text-emerald-400 bg-emerald-900/30',
    'mcp': 'text-orange-400 bg-orange-900/30',
  }

  return (
    <div className="space-y-2">
      <input
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="搜索已有节点 (Skill / Agent / MCP)..."
        autoFocus
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2.5 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500"
      />

      {loading && <div className="text-[10px] text-gray-500">加载中...</div>}

      <div className="space-y-0.5 max-h-52 overflow-auto">
        {filtered.map(item => {
          const onCanvas = canvasNodeIds.has(item.id)
          return (
            <div
              key={`${item.type}:${item.id}`}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded hover:bg-gray-700 group"
            >
              <span className={`text-[9px] px-1.5 py-0.5 rounded shrink-0 ${typeColors[item.type] || ''}`}>
                {item.type}
              </span>
              <div className="flex-1 min-w-0 cursor-pointer" onClick={() => onCanvas ? onLocate(getCanvasId(item)) : undefined}>
                <div className="text-xs text-white truncate">{item.name}</div>
                {item.description && (
                  <div className="text-[9px] text-gray-500 truncate">{item.description}</div>
                )}
              </div>
              <div className="flex gap-1 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                {onCanvas ? (
                  <button onClick={() => onLocate(getCanvasId(item))}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30">
                    定位
                  </button>
                ) : (
                  <button onClick={() => handleAddToCanvas(item)}
                    className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30">
                    添加
                  </button>
                )}
                <button onClick={() => handleDelete(item)}
                  className="text-[9px] px-1.5 py-0.5 rounded bg-red-600/20 text-red-400 hover:bg-red-600/30">
                  删除
                </button>
              </div>
            </div>
          )
        })}
        {!loading && filtered.length === 0 && (
          <div className="text-[10px] text-gray-500 py-2 text-center">
            {query ? '无匹配结果' : '暂无节点'}
          </div>
        )}
      </div>

      {!loading && (
        <div className="text-[9px] text-gray-600 border-t border-gray-700 pt-1.5">
          共 {items.filter(i => i.type === 'agent' || i.type === 'sub-agent').length} Agent, {items.filter(i => i.type === 'skill').length} Skill, {items.filter(i => i.type === 'mcp').length} MCP
        </div>
      )}
    </div>
  )
}

function AgentForm({ canvasX, canvasY, parentCanvas, onCreated, onClose }: {
  canvasX: number; canvasY: number; parentCanvas?: string; onCreated: () => void; onClose: () => void
}) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [agentType, setAgentType] = useState('react')
  const [err, setErr] = useState('')

  const handleSubmit = async () => {
    if (!id.trim() || !name.trim()) return
    setErr('')
    try {
      await createAgent({ id: id.trim(), name: name.trim(), agent_type: agentType })
      await createCanvasNode({ id: `agent:${id.trim()}`, node_type: 'agent', ref_id: id.trim(), position_x: canvasX, position_y: canvasY, parent_canvas: parentCanvas || undefined } as Record<string, unknown>)
      onCreated()
      onClose()
    } catch (e) {
      setErr(String(e).replace('Error: ', ''))
    }
  }

  return (
    <div className="space-y-2">
      <input value={id} onChange={e => setId(e.target.value)} placeholder="Agent ID (如 reviewer)"
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500" />
      <input value={name} onChange={e => setName(e.target.value)} placeholder="名称 (如 审核员)"
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500" />
      <select value={agentType} onChange={e => setAgentType(e.target.value)}
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-500">
        <option value="react">ReAct (有工具)</option>
        <option value="llm">LLM (纯对话)</option>
        <option value="function">Function (代码逻辑)</option>
      </select>
      {err && <div className="text-[10px] text-red-400">{err}</div>}
      <button onClick={handleSubmit} disabled={!id.trim() || !name.trim()}
        className="w-full text-xs py-1.5 rounded bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-40">
        创建 Agent
      </button>
    </div>
  )
}

function SkillList({ canvasX, canvasY, parentCanvas, onCreated, onClose }: {
  canvasX: number; canvasY: number; parentCanvas?: string; onCreated: () => void; onClose: () => void
}) {
  const [skills, setSkills] = useState<Array<{ name: string; title: string }>>([])
  const [existing, setExisting] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch('/api/admin/skills').then(r => r.json()).then(d => setSkills(d.skills || []))
    fetch('/api/admin/canvas/nodes').then(r => r.json()).then(d => {
      const ids = new Set((d.nodes || []).filter((n: Record<string, string>) => n.node_type === 'skill').map((n: Record<string, string>) => n.ref_id))
      setExisting(ids as Set<string>)
    })
  }, [])

  const addSkill = async (skillName: string) => {
    try {
      await createCanvasNode({
        id: `skill:${skillName}${parentCanvas ? ':' + parentCanvas : ''}`, node_type: 'skill', ref_id: skillName,
        position_x: canvasX, position_y: canvasY, parent_canvas: parentCanvas || undefined,
      } as Record<string, unknown>)
      onCreated()
      onClose()
    } catch {
      // already exists
    }
  }

  return (
    <div className="space-y-1">
      {skills.length === 0 && <div className="text-xs text-gray-500">加载中...</div>}
      {skills.map(s => (
        <button
          key={s.name}
          onClick={() => addSkill(s.name)}
          disabled={existing.has(s.name)}
          className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
            existing.has(s.name)
              ? 'text-gray-600 cursor-not-allowed'
              : 'text-gray-200 hover:bg-gray-700'
          }`}
        >
          <span className="font-medium">{s.title || s.name}</span>
          {existing.has(s.name) && <span className="ml-1 text-[9px] text-gray-600">(已在画布)</span>}
        </button>
      ))}
    </div>
  )
}

function SubAgentForm({ canvasX, canvasY, onCreated, onClose }: {
  canvasX: number; canvasY: number; onCreated: () => void; onClose: () => void
}) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [parentId, setParentId] = useState('')
  const [parents, setParents] = useState<Array<{ id: string; name: string }>>([])
  const [err, setErr] = useState('')

  useEffect(() => {
    fetchAgents().then(d => {
      const agents = d.agents || []
      setParents(agents.filter(a => ['react'].includes(a.agent_type || '')))
      if (agents.length > 0 && !parentId) setParentId(agents[0].id)
    })
  }, [])

  const handleSubmit = async () => {
    if (!id.trim() || !name.trim() || !parentId) return
    setErr('')
    try {
      await createAgent({ id: id.trim(), name: name.trim(), parent_id: parentId, agent_type: 'react' })
      await createCanvasNode({ id: `agent:${id.trim()}`, node_type: 'agent', ref_id: id.trim(), position_x: canvasX, position_y: canvasY })
      onCreated()
      onClose()
    } catch (e) {
      setErr(String(e).replace('Error: ', ''))
    }
  }

  return (
    <div className="space-y-2">
      <select value={parentId} onChange={e => setParentId(e.target.value)}
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white focus:outline-none focus:border-indigo-500">
        <option value="">选择父 Agent</option>
        {parents.map(p => <option key={p.id} value={p.id}>{p.name} ({p.id})</option>)}
      </select>
      <input value={id} onChange={e => setId(e.target.value)} placeholder="Sub-Agent ID (如 image_agent)"
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500" />
      <input value={name} onChange={e => setName(e.target.value)} placeholder="名称 (如 图像处理)"
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-indigo-500" />
      {err && <div className="text-[10px] text-red-400">{err}</div>}
      <button onClick={handleSubmit} disabled={!id.trim() || !name.trim() || !parentId}
        className="w-full text-xs py-1.5 rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-40">
        创建 Sub-Agent
      </button>
    </div>
  )
}

function McpForm({ canvasX, canvasY, parentCanvas, onCreated, onClose }: {
  canvasX: number; canvasY: number; parentCanvas?: string; onCreated: () => void; onClose: () => void
}) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [transport, setTransport] = useState('sse')
  const [url, setUrl] = useState('')

  const handleSubmit = async () => {
    if (!id.trim() || !name.trim()) return
    try {
      await fetch('/api/admin/mcp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id.trim(), name: name.trim(), transport, url: url.trim() }),
      })
      await createCanvasNode({ id: `mcp:${id.trim()}`, node_type: 'mcp', ref_id: id.trim(), position_x: canvasX, position_y: canvasY, parent_canvas: parentCanvas || undefined } as Record<string, unknown>)
      onCreated()
      onClose()
    } catch {
      // handle error
    }
  }

  return (
    <div className="space-y-2">
      <input value={id} onChange={e => setId(e.target.value)} placeholder="MCP ID (如 figma)"
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-orange-500" />
      <input value={name} onChange={e => setName(e.target.value)} placeholder="名称 (如 Figma Design)"
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-orange-500" />
      <select value={transport} onChange={e => setTransport(e.target.value)}
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white focus:outline-none focus:border-orange-500">
        <option value="sse">SSE (HTTP)</option>
        <option value="stdio">stdio (命令行)</option>
      </select>
      <input value={url} onChange={e => setUrl(e.target.value)}
        placeholder={transport === 'sse' ? 'http://localhost:3001/sse' : 'npx @mcp/server-xxx'}
        className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1.5 text-white placeholder:text-gray-500 focus:outline-none focus:border-orange-500" />
      <button onClick={handleSubmit} disabled={!id.trim() || !name.trim()}
        className="w-full text-xs py-1.5 rounded bg-orange-600 text-white hover:bg-orange-500 disabled:opacity-40">
        创建 MCP 服务
      </button>
      <div className="text-[9px] text-gray-500">完整 MCP 连接功能将在 Phase 5 实现</div>
    </div>
  )
}
