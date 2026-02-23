import { useState, useCallback, useEffect } from 'react'
import type { Node } from '@xyflow/react'
import type { AgentNodeData, LogEntry } from '@/types'
import { PromptEditor } from './PromptEditor'
import { ToolCheckboxList } from './ToolCheckboxList'
import { RoutingRulesManager } from './RoutingRulesManager'
import { AgentRunLog } from './AgentRunLog'
import { createAgent, updateAgent, fetchAgents } from '@/services/api'
import { SkillCreator } from './SkillCreator'
import { Plus } from 'lucide-react'

interface NodeDetailPanelProps {
  selectedNodeId: string | null
  nodes: Node[]
  logs: LogEntry[]
  onSubAgentCreated?: () => void
}

function parseCanvasId(canvasId: string): { type: string; refId: string } {
  const idx = canvasId.indexOf(':')
  if (idx === -1) return { type: 'agent', refId: canvasId }
  return { type: canvasId.slice(0, idx), refId: canvasId.slice(idx + 1) }
}

export function NodeDetailPanel({ selectedNodeId, nodes, logs, onSubAgentCreated }: NodeDetailPanelProps) {
  if (!selectedNodeId) {
    return <ProjectOverview nodes={nodes} />
  }

  const node = nodes.find(n => n.id === selectedNodeId)
  const { type: nodeType, refId } = parseCanvasId(selectedNodeId)

  if (nodeType === 'trigger') {
    return (
      <div className="h-full flex flex-col">
        <div className="px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-500 shrink-0" />
            <h3 className="font-semibold text-white">Chat Trigger</h3>
            <span className="text-xs px-1.5 py-0.5 rounded bg-teal-900/30 text-teal-400">Trigger</span>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-4 space-y-3">
          <div className="text-xs text-gray-400">
            聊天触发器节点。用户输入和追问回复都从这里进入工作流。
          </div>
          <div className="bg-surface-light rounded-lg p-3">
            <h4 className="text-xs font-medium text-gray-300 mb-1">功能</h4>
            <ul className="text-[10px] text-gray-400 space-y-1">
              <li>接收用户消息，启动工作流</li>
              <li>Agent 追问时，用户回复从此节点重新进入</li>
              <li>支持文件上传（图片/视频）</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  if (nodeType === 'skillgroup') {
    return <SkillGroupPanel containerId={selectedNodeId} refId={refId} onChanged={onSubAgentCreated} />
  }

  if (nodeType === 'subagentgroup') {
    return <SubAgentGroupPanel agentId={refId} onChanged={onSubAgentCreated} />
  }

  if (nodeType === 'mcpgroup') {
    return <McpDetailView mcpId={refId} />
  }

  if (nodeType === 'skill') {
    return (
      <SkillDetailView
        skillName={refId}
        nodeData={node?.data as Record<string, unknown> | undefined}
      />
    )
  }

  if (nodeType === 'mcp') {
    return <McpDetailView mcpId={refId} />
  }

  if (!node) {
    return <ProjectOverview nodes={nodes} />
  }

  const nodeData = node.data as unknown as AgentNodeData

  if (refId === 'router') {
    return <RouterDetailView nodeData={nodeData} logs={logs} />
  }
  if (refId === 'quality_gate') {
    return <QualityGateDetail nodeData={nodeData} logs={logs} />
  }
  if (refId === 'human_feedback') {
    return <HumanFeedbackDetail nodeData={nodeData} logs={logs} />
  }

  return (
    <AgentDetailView
      nodeId={refId}
      nodeData={nodeData}
      logs={logs}
      onSubAgentCreated={onSubAgentCreated}
    />
  )
}

// ── Router 面板: Prompt + 路由规则 + 日志 ──

function RouterDetailView({ nodeData, logs }: {
  nodeData: AgentNodeData
  logs: LogEntry[]
}) {
  const [activeTab, setActiveTab] = useState<'prompt' | 'rules' | 'logs'>('rules')

  return (
    <div className="h-full flex flex-col">
      <NodeHeader nodeData={nodeData} />
      <TabBar
        tabs={[
          { key: 'prompt', label: 'Prompt' },
          { key: 'rules', label: '路由规则' },
          { key: 'logs', label: `日志 (${logs.filter(l => l.agent === 'router').length})` },
        ]}
        active={activeTab}
        onChange={(t) => setActiveTab(t as 'prompt' | 'rules' | 'logs')}
      />
      <div className="flex-1 overflow-hidden">
        {activeTab === 'prompt' && <PromptEditor agentId="router" />}
        {activeTab === 'rules' && <RoutingRulesManager />}
        {activeTab === 'logs' && <AgentRunLog agentId="router" logs={logs} />}
      </div>
    </div>
  )
}

// ── Agent 面板: Prompt + Skill + 日志 + 执行模式 ──

function AgentDetailView({ nodeId, nodeData, logs }: {
  nodeId: string
  nodeData: AgentNodeData
  logs: LogEntry[]
  onSubAgentCreated?: () => void
}) {
  const [activeTab, setActiveTab] = useState<'prompt' | 'tools' | 'logs'>('prompt')
  const [executionMode, setExecutionMode] = useState<string>('react')
  const [hasChildren, setHasChildren] = useState(false)

  useEffect(() => {
    fetchAgents().then(data => {
      const agents = data.agents || []
      const agent = agents.find((a: Record<string, unknown>) => a.id === nodeId)
      if (agent) {
        setExecutionMode((agent as Record<string, unknown>).execution_mode as string || 'react')
        setHasChildren(((agent as Record<string, unknown>).children as unknown[])?.length > 0)
      }
    }).catch(() => {})
  }, [nodeId])

  const toggleExecutionMode = useCallback(async () => {
    const newMode = executionMode === 'react' ? 'parallel' : 'react'
    try {
      await updateAgent(nodeId, { execution_mode: newMode })
      setExecutionMode(newMode)
    } catch { /* ignore */ }
  }, [nodeId, executionMode])

  return (
    <div className="h-full flex flex-col">
      <NodeHeader nodeData={nodeData} />
      <TabBar
        tabs={[
          { key: 'prompt', label: 'System Prompt' },
          { key: 'tools', label: 'Skill' },
          { key: 'logs', label: `日志 (${logs.filter(l => l.agent === nodeId).length})` },
        ]}
        active={activeTab}
        onChange={(t) => setActiveTab(t as 'prompt' | 'tools' | 'logs')}
      />

      {hasChildren && (
        <div className="px-3 py-1.5 border-b border-border flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-gray-400">子 Agent 执行模式:</span>
          <button
            onClick={toggleExecutionMode}
            className={`text-[10px] px-2 py-0.5 rounded font-medium transition-colors ${
              executionMode === 'parallel'
                ? 'bg-amber-600/20 text-amber-400 hover:bg-amber-600/30'
                : 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30'
            }`}
          >
            {executionMode === 'parallel' ? '并行' : '串行 (ReAct)'}
          </button>
          <span className="text-[10px] text-gray-500">
            {executionMode === 'parallel' ? '所有子 Agent 同时执行' : 'LLM 逐个决定调用顺序'}
          </span>
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        {activeTab === 'prompt' && <PromptEditor agentId={nodeId} />}
        {activeTab === 'tools' && <ToolCheckboxList agentId={nodeId} />}
        {activeTab === 'logs' && <AgentRunLog agentId={nodeId} logs={logs} />}
      </div>
    </div>
  )
}

// ── 质量门控面板 ──

function QualityGateDetail({ nodeData, logs }: {
  nodeData: AgentNodeData
  logs: LogEntry[]
}) {
  return (
    <div className="h-full flex flex-col">
      <NodeHeader nodeData={nodeData} />
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {nodeData.qualityScore !== undefined && (
          <div className="bg-surface-light rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-300 mb-2">VLM 评分</h4>
            <div className="flex items-center gap-3">
              <span className={`text-3xl font-bold ${
                nodeData.qualityScore >= 70 ? 'text-green-400' :
                nodeData.qualityScore >= 50 ? 'text-yellow-400' : 'text-red-400'
              }`}>
                {nodeData.qualityScore}
              </span>
              <span className="text-gray-500 text-sm">/ 100</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                nodeData.qualityScore >= 70
                  ? 'bg-green-900/50 text-green-400'
                  : 'bg-red-900/50 text-red-400'
              }`}>
                {nodeData.qualityScore >= 70 ? '通过' : '不通过'}
              </span>
            </div>
          </div>
        )}
        <AgentRunLog agentId="quality_gate" logs={logs} />
      </div>
    </div>
  )
}

// ── Human Feedback 面板 ──

function HumanFeedbackDetail({ nodeData, logs }: {
  nodeData: AgentNodeData
  logs: LogEntry[]
}) {
  return (
    <div className="h-full flex flex-col">
      <NodeHeader nodeData={nodeData} />
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {nodeData.status === 'waiting' && (
          <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg p-3">
            <p className="text-xs text-yellow-400">Agent 正在等待你的回复，请在底部对话区输入回复。</p>
          </div>
        )}
        <AgentRunLog agentId="human_feedback" logs={logs} />
      </div>
    </div>
  )
}

// ── 项目概览 ──

function ProjectOverview({ nodes }: { nodes: Node<AgentNodeData>[] }) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="font-semibold text-white">项目概览</h3>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-4">
        <section>
          <h4 className="text-sm font-medium text-gray-300 mb-2">Agent 状态</h4>
          <div className="space-y-2">
            {nodes.map(node => {
              const data = node.data as unknown as AgentNodeData
              return (
                <div key={node.id} className="flex items-center gap-2 bg-surface-light rounded-lg p-2.5">
                  <StatusDot status={data.status} />
                  <span className="text-sm text-white flex-1">{data.label}</span>
                  <span className="text-xs text-gray-400">{data.status}</span>
                </div>
              )
            })}
          </div>
        </section>
        <p className="text-xs text-gray-500">
          点击左侧流程图中的节点查看详细配置
        </p>
      </div>
    </div>
  )
}

// ── 共用组件 ──

function NodeHeader({ nodeData }: { nodeData: AgentNodeData }) {
  return (
    <div className="px-4 py-3 border-b border-border shrink-0">
      <div className="flex items-center gap-2">
        <StatusDot status={nodeData.status} />
        <h3 className="font-semibold text-white">{nodeData.label}</h3>
        <span className="text-xs px-1.5 py-0.5 rounded bg-white/10 text-gray-400">
          {nodeData.agentType}
        </span>
      </div>
    </div>
  )
}

function TabBar({ tabs, active, onChange }: {
  tabs: { key: string; label: string }[]
  active: string
  onChange: (key: string) => void
}) {
  return (
    <div className="flex border-b border-border shrink-0">
      {tabs.map(tab => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`px-4 py-2 text-xs font-medium transition-colors ${
            active === tab.key
              ? 'text-blue-400 border-b-2 border-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

function StatusDot({ status }: { status: string }) {
  const styles: Record<string, string> = {
    idle: 'bg-gray-500',
    running: 'bg-blue-500 animate-pulse',
    success: 'bg-green-500',
    error: 'bg-red-500',
    waiting: 'bg-yellow-500 animate-pulse',
  }
  return <span className={`w-2 h-2 rounded-full shrink-0 ${styles[status] ?? styles.idle}`} />
}

// ── Skill 容器面板 ──

function SkillGroupPanel({ containerId, refId, onChanged }: { containerId: string; refId: string; onChanged?: () => void }) {
  const [items, setItems] = useState<string[]>([])
  const [skillInfos, setSkillInfos] = useState<Array<{ name: string; title: string; description: string }>>([])
  const [allSkills, setAllSkills] = useState<Array<{ name: string; title: string }>>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [skillContent, setSkillContent] = useState('')
  const [editedContent, setEditedContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [showCreator, setShowCreator] = useState(false)

  const loadItems = useCallback(async () => {
    try {
      const res = await fetch(`/api/admin/canvas/nodes`)
      const data = await res.json()
      const node = (data.nodes || []).find((n: Record<string, unknown>) => n.id === containerId)
      const nodeItems = ((node?.config as Record<string, unknown>)?.items as string[]) || []
      setItems(nodeItems)

      const skillsRes = await fetch('/api/admin/skills')
      const skillsData = await skillsRes.json()
      const allSkillList = skillsData.skills || []
      setSkillInfos(allSkillList.filter((s: Record<string, string>) => nodeItems.includes(s.name)))
      setAllSkills(allSkillList)
    } catch { /* ignore */ }
  }, [containerId])

  useEffect(() => { loadItems() }, [loadItems])

  const updateContainerItems = useCallback(async (newItems: string[]) => {
    try {
      await fetch(`/api/admin/canvas/nodes/${encodeURIComponent(containerId)}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: { items: newItems } }),
      })
      loadItems()
      onChanged?.()
    } catch { /* ignore */ }
  }, [containerId, loadItems, onChanged])

  const handleAdd = useCallback(async (skillName: string) => {
    if (items.includes(skillName)) return
    await updateContainerItems([...items, skillName])
    setShowAdd(false)
  }, [items, updateContainerItems])

  const handleRemove = useCallback(async (skillName: string) => {
    await updateContainerItems(items.filter(i => i !== skillName))
  }, [items, updateContainerItems])

  const handleExpand = useCallback(async (skillName: string) => {
    if (expanded === skillName) { setExpanded(null); return }
    setExpanded(skillName)
    try {
      const res = await fetch(`/api/admin/skills/${skillName}/content`)
      const data = await res.json()
      setSkillContent(data.content || '')
      setEditedContent(data.content || '')
    } catch { setSkillContent('加载失败'); setEditedContent('') }
  }, [expanded])

  const handleSaveContent = useCallback(async (skillName: string) => {
    setSaving(true)
    try {
      await fetch(`/api/admin/skills/${skillName}/content`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editedContent }),
      })
      setSkillContent(editedContent)
    } catch { /* ignore */ }
    setSaving(false)
  }, [editedContent])

  if (showCreator) {
    return (
      <SkillCreator
        agentId={refId}
        onCreated={async () => {
          setShowCreator(false)
          const skillsRes = await fetch('/api/admin/skills')
          const data = await skillsRes.json()
          const latest = (data.skills || []).map((s: Record<string, string>) => s.name)
          const newSkills = latest.filter((n: string) => !items.includes(n))
          if (newSkills.length > 0) await updateContainerItems([...items, ...newSkills])
          else loadItems()
        }}
        onClose={() => setShowCreator(false)}
      />
    )
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
            <h3 className="font-semibold text-white">Skill 容器</h3>
            <span className="text-xs text-gray-500">{refId}</span>
          </div>
          <div className="flex gap-1">
            <button onClick={() => setShowCreator(true)}
              className="text-[10px] px-2 py-1 rounded bg-emerald-600/20 text-emerald-400 hover:bg-emerald-600/30">
              <Plus size={10} className="inline mr-0.5" />AI 新建
            </button>
            <button onClick={() => setShowAdd(!showAdd)}
              className="text-[10px] px-2 py-1 rounded bg-gray-600/20 text-gray-400 hover:bg-gray-600/30">
              添加已有
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3 space-y-2">
        {showAdd && (
          <div className="border border-gray-500/20 rounded-lg p-2 bg-gray-950/10 space-y-1 mb-3">
            <div className="text-[10px] text-gray-400 mb-1">从全局 Skill 池添加:</div>
            {allSkills.filter(s => !items.includes(s.name)).length === 0 && (
              <div className="text-[10px] text-gray-600">所有 Skill 都已添加</div>
            )}
            {allSkills.filter(s => !items.includes(s.name)).map(s => (
              <button key={s.name} onClick={() => handleAdd(s.name)}
                className="w-full text-left text-xs px-2 py-1 rounded hover:bg-gray-700 text-gray-200">
                {s.title || s.name}
              </button>
            ))}
          </div>
        )}

        {items.length === 0 && !showAdd && (
          <div className="text-xs text-gray-500">暂无 Skill，点击上方 [AI 新建] 或 [添加已有]</div>
        )}

        {skillInfos.map(s => (
          <div key={s.name} className="bg-surface-light rounded-lg overflow-hidden">
            <div className="flex items-center px-3 py-2 cursor-pointer hover:bg-white/5"
              onClick={() => handleExpand(s.name)}>
              <span className="text-xs font-medium text-white flex-1">{s.title || s.name}</span>
              <button onClick={(e) => { e.stopPropagation(); handleRemove(s.name) }}
                className="text-[9px] text-red-400 hover:text-red-300 px-1">移除</button>
              <span className="text-[10px] text-gray-500 ml-1">{expanded === s.name ? '▼' : '▸'}</span>
            </div>
            {expanded === s.name && (
              <div className="px-3 py-2 border-t border-border space-y-2">
                <textarea value={editedContent} onChange={e => setEditedContent(e.target.value)}
                  className="w-full text-[10px] text-gray-300 bg-gray-900 border border-gray-700 rounded p-2 font-mono resize-y min-h-[80px] max-h-[240px] focus:outline-none focus:border-emerald-500" rows={8} />
                <div className="flex items-center gap-2">
                  <button onClick={() => handleSaveContent(s.name)} disabled={saving || editedContent === skillContent}
                    className="text-[10px] px-2.5 py-1 rounded bg-emerald-600 text-white disabled:opacity-40 hover:bg-emerald-500">
                    {saving ? '保存中...' : '保存'}
                  </button>
                  {editedContent !== skillContent && <span className="text-[9px] text-yellow-500">未保存</span>}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── SubAgent 容器面板 ──

function SubAgentGroupPanel({ agentId, onChanged }: { agentId: string; onChanged?: () => void }) {
  const [children, setChildren] = useState<Array<{ id: string; name: string; description: string }>>([])
  const [showCreate, setShowCreate] = useState(false)
  const [newId, setNewId] = useState('')
  const [newName, setNewName] = useState('')
  const [executionMode, setExecutionMode] = useState('react')
  const [err, setErr] = useState('')

  const loadChildren = useCallback(async () => {
    try {
      const res = await fetch(`/api/admin/agents/${agentId}/children`)
      const data = await res.json()
      setChildren(data.children || [])
    } catch { /* ignore */ }

    try {
      const res = await fetch(`/api/admin/agents/${agentId}`)
      const data = await res.json()
      setExecutionMode(data.execution_mode || 'react')
    } catch { /* ignore */ }
  }, [agentId])

  useEffect(() => { loadChildren() }, [loadChildren])

  const handleCreate = useCallback(async () => {
    if (!newId.trim() || !newName.trim()) return
    setErr('')
    try {
      await createAgent({ id: newId.trim(), name: newName.trim(), parent_id: agentId, agent_type: 'react' })
      setNewId('')
      setNewName('')
      setShowCreate(false)
      loadChildren()
      onChanged?.()
    } catch (e) {
      setErr(String(e).replace('Error: ', ''))
    }
  }, [newId, newName, agentId, loadChildren, onChanged])

  const toggleMode = useCallback(async () => {
    const newMode = executionMode === 'react' ? 'parallel' : 'react'
    try {
      await updateAgent(agentId, { execution_mode: newMode })
      setExecutionMode(newMode)
    } catch { /* ignore */ }
  }, [agentId, executionMode])

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
            <h3 className="font-semibold text-white">Sub-Agent 容器</h3>
            <span className="text-xs text-gray-500">{agentId}</span>
          </div>
          <button onClick={() => setShowCreate(!showCreate)}
            className="text-[10px] px-2 py-1 rounded bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30">
            <Plus size={10} className="inline mr-0.5" />新建
          </button>
        </div>
      </div>

      {children.length > 0 && (
        <div className="px-3 py-1.5 border-b border-border flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-gray-400">执行模式:</span>
          <button onClick={toggleMode}
            className={`text-[10px] px-2 py-0.5 rounded font-medium ${
              executionMode === 'parallel'
                ? 'bg-amber-600/20 text-amber-400'
                : 'bg-blue-600/20 text-blue-400'
            }`}>
            {executionMode === 'parallel' ? '并行' : '串行 (ReAct)'}
          </button>
        </div>
      )}

      <div className="flex-1 overflow-auto p-3 space-y-2">
        {showCreate && (
          <div className="border border-indigo-500/20 rounded-lg p-2 bg-indigo-950/10 space-y-1.5 mb-3">
            <input value={newId} onChange={e => setNewId(e.target.value)} placeholder="ID (如 image_agent)"
              className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1 text-white placeholder:text-gray-500" />
            <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="名称 (如 图像处理)"
              className="w-full text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1 text-white placeholder:text-gray-500" />
            {err && <div className="text-[10px] text-red-400">{err}</div>}
            <button onClick={handleCreate} disabled={!newId.trim() || !newName.trim()}
              className="w-full text-[10px] py-1 rounded bg-indigo-600 text-white disabled:opacity-40">创建</button>
          </div>
        )}

        {children.length === 0 && !showCreate && (
          <div className="text-xs text-gray-500">暂无子 Agent，点击上方 [新建]</div>
        )}

        {children.map(c => (
          <div key={c.id} className="bg-surface-light rounded-lg px-3 py-2">
            <div className="text-xs font-medium text-white">{c.name}</div>
            <div className="text-[10px] text-gray-400">{c.id} | {c.description || 'Sub-Agent'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Skill 详情面板 ──

function SkillDetailView({ skillName }: {
  skillName: string
  nodeData?: Record<string, unknown>
}) {
  const [activeTab, setActiveTab] = useState<'info' | 'instructions' | 'scripts' | 'resources'>('info')
  const [meta, setMeta] = useState<{ name: string; title: string; description: string; trigger: string[]; readme: string } | null>(null)
  const [files, setFiles] = useState<{ scripts: Array<{ name: string; path: string }>; references: Array<{ name: string; path: string }>; assets: Array<{ name: string; path: string }> }>({ scripts: [], references: [], assets: [] })
  const [editingFile, setEditingFile] = useState<{ path: string; content: string; original: string } | null>(null)
  const [fileSaving, setFileSaving] = useState(false)
  const [newFileName, setNewFileName] = useState('')
  const [newFileDir, setNewFileDir] = useState<'scripts' | 'references' | 'assets'>('scripts')

  const loadMeta = useCallback(async () => {
    try {
      const res = await fetch(`/api/admin/skills/${skillName}/metadata`)
      setMeta(await res.json())
    } catch { /* ignore */ }
  }, [skillName])

  const loadFiles = useCallback(async () => {
    try {
      const res = await fetch(`/api/admin/skills/${skillName}/files`)
      const data = await res.json()
      setFiles({ scripts: data.scripts || [], references: data.references || [], assets: data.assets || [] })
    } catch { /* ignore */ }
  }, [skillName])

  useEffect(() => { loadMeta(); loadFiles() }, [loadMeta, loadFiles])

  const openFile = useCallback(async (path: string) => {
    if (editingFile?.path === path) { setEditingFile(null); return }
    try {
      const res = await fetch(`/api/admin/skills/${skillName}/files/${path}`)
      const data = await res.json()
      setEditingFile({ path, content: data.content, original: data.content })
    } catch { /* ignore */ }
  }, [skillName, editingFile])

  const saveFile = useCallback(async () => {
    if (!editingFile) return
    setFileSaving(true)
    try {
      await fetch(`/api/admin/skills/${skillName}/files/${editingFile.path}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editingFile.content }),
      })
      setEditingFile(prev => prev ? { ...prev, original: prev.content } : null)
    } catch { /* ignore */ }
    setFileSaving(false)
  }, [skillName, editingFile])

  const createFile = useCallback(async () => {
    if (!newFileName.trim()) return
    try {
      await fetch(`/api/admin/skills/${skillName}/files/${newFileDir}/${newFileName.trim()}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: `# ${newFileName.trim()}\n` }),
      })
      setNewFileName('')
      loadFiles()
    } catch { /* ignore */ }
  }, [skillName, newFileDir, newFileName, loadFiles])

  const deleteFile = useCallback(async (path: string) => {
    try {
      await fetch(`/api/admin/skills/${skillName}/files/${path}`, { method: 'DELETE' })
      if (editingFile?.path === path) setEditingFile(null)
      loadFiles()
    } catch { /* ignore */ }
  }, [skillName, editingFile, loadFiles])

  const saveInstructions = useCallback(async (content: string) => {
    const skillMd = meta ? `---\nname: ${meta.name}\ntitle: ${meta.title}\ndescription: ${meta.description}\ntrigger:\n${meta.trigger.map(t => `  - "${t}"`).join('\n')}\n---\n\n${content}` : content
    try {
      await fetch(`/api/admin/skills/${skillName}/content`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: skillMd }),
      })
      loadMeta()
    } catch { /* ignore */ }
  }, [skillName, meta, loadMeta])

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
          <h3 className="font-semibold text-white">{meta?.title || skillName}</h3>
          <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-900/30 text-emerald-400">Skill</span>
        </div>
      </div>

      <TabBar
        tabs={[
          { key: 'info', label: '基本信息' },
          { key: 'instructions', label: '指令' },
          { key: 'scripts', label: `脚本 (${files.scripts.length})` },
          { key: 'resources', label: `资源 (${files.references.length + files.assets.length})` },
        ]}
        active={activeTab}
        onChange={(t) => setActiveTab(t as 'info' | 'instructions' | 'scripts' | 'resources')}
      />

      <div className="flex-1 overflow-auto p-3 space-y-2">
        {activeTab === 'info' && meta && (
          <>
            <div className="bg-surface-light rounded-lg p-3 space-y-2">
              <div><span className="text-[10px] text-gray-500">Name</span><div className="text-xs text-white font-mono">{meta.name}</div></div>
              <div><span className="text-[10px] text-gray-500">Title</span><div className="text-xs text-white">{meta.title}</div></div>
              <div><span className="text-[10px] text-gray-500">Description</span><div className="text-xs text-gray-300">{meta.description}</div></div>
              <div><span className="text-[10px] text-gray-500">Trigger</span><div className="text-xs text-emerald-400">{meta.trigger?.join(', ')}</div></div>
            </div>
          </>
        )}

        {activeTab === 'instructions' && meta && (
          <SkillInstructionsEditor readme={meta.readme} onSave={saveInstructions} />
        )}

        {activeTab === 'scripts' && (
          <>
            {files.scripts.map(f => (
              <div key={f.path} className="bg-surface-light rounded-lg overflow-hidden">
                <div className="flex items-center px-3 py-1.5 cursor-pointer hover:bg-white/5" onClick={() => openFile(f.path)}>
                  <span className="text-xs text-yellow-300 font-mono flex-1">{f.name}</span>
                  <button onClick={(e) => { e.stopPropagation(); deleteFile(f.path) }} className="text-[9px] text-red-400 px-1">删除</button>
                  <span className="text-[10px] text-gray-500 ml-1">{editingFile?.path === f.path ? '▼' : '▸'}</span>
                </div>
                {editingFile?.path === f.path && (
                  <div className="px-3 py-2 border-t border-border space-y-1.5">
                    <textarea value={editingFile.content} onChange={e => setEditingFile(prev => prev ? { ...prev, content: e.target.value } : null)}
                      className="w-full text-[10px] text-gray-300 bg-gray-900 border border-gray-700 rounded p-2 font-mono resize-y min-h-[100px] max-h-[300px] focus:outline-none focus:border-yellow-500" rows={10} />
                    <button onClick={saveFile} disabled={fileSaving || editingFile.content === editingFile.original}
                      className="text-[10px] px-2.5 py-1 rounded bg-yellow-600 text-white disabled:opacity-40">{fileSaving ? '保存中...' : '保存'}</button>
                  </div>
                )}
              </div>
            ))}
            <div className="flex gap-1.5 items-center mt-2">
              <input value={newFileName} onChange={e => setNewFileName(e.target.value)} placeholder="新文件名 (如 tool.py)"
                className="flex-1 text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1 text-white placeholder:text-gray-500 focus:outline-none focus:border-yellow-500" />
              <button onClick={() => { setNewFileDir('scripts'); createFile() }} disabled={!newFileName.trim()}
                className="text-[10px] px-2 py-1 rounded bg-yellow-600/20 text-yellow-400 disabled:opacity-40">+ 脚本</button>
            </div>
          </>
        )}

        {activeTab === 'resources' && (
          <>
            {files.references.length > 0 && (
              <div>
                <div className="text-[10px] text-gray-500 mb-1">References</div>
                {files.references.map(f => (
                  <div key={f.path} className="bg-surface-light rounded px-3 py-1.5 flex items-center mb-1 cursor-pointer hover:bg-white/5" onClick={() => openFile(f.path)}>
                    <span className="text-xs text-blue-300 font-mono flex-1">{f.name}</span>
                    <button onClick={(e) => { e.stopPropagation(); deleteFile(f.path) }} className="text-[9px] text-red-400 px-1">删除</button>
                  </div>
                ))}
              </div>
            )}
            {files.assets.length > 0 && (
              <div>
                <div className="text-[10px] text-gray-500 mb-1">Assets</div>
                {files.assets.map(f => (
                  <div key={f.path} className="bg-surface-light rounded px-3 py-1.5 flex items-center mb-1">
                    <span className="text-xs text-orange-300 font-mono flex-1">{f.name}</span>
                    <button onClick={() => deleteFile(f.path)} className="text-[9px] text-red-400 px-1">删除</button>
                  </div>
                ))}
              </div>
            )}
            {editingFile && !editingFile.path.startsWith('scripts/') && (
              <div className="border-t border-border pt-2 space-y-1.5">
                <div className="text-[10px] text-gray-400">{editingFile.path}</div>
                <textarea value={editingFile.content} onChange={e => setEditingFile(prev => prev ? { ...prev, content: e.target.value } : null)}
                  className="w-full text-[10px] text-gray-300 bg-gray-900 border border-gray-700 rounded p-2 font-mono resize-y min-h-[80px] max-h-[200px] focus:outline-none focus:border-blue-500" rows={6} />
                <button onClick={saveFile} disabled={fileSaving || editingFile.content === editingFile.original}
                  className="text-[10px] px-2.5 py-1 rounded bg-blue-600 text-white disabled:opacity-40">{fileSaving ? '保存中...' : '保存'}</button>
              </div>
            )}
            <div className="flex gap-1.5 items-center mt-2">
              <input value={newFileName} onChange={e => setNewFileName(e.target.value)} placeholder="新文件名"
                className="flex-1 text-xs bg-gray-900 border border-gray-600 rounded px-2 py-1 text-white placeholder:text-gray-500 focus:outline-none" />
              <select value={newFileDir} onChange={e => setNewFileDir(e.target.value as 'references' | 'assets')}
                className="text-[10px] bg-gray-900 border border-gray-600 rounded px-1 py-1 text-white">
                <option value="references">references</option>
                <option value="assets">assets</option>
              </select>
              <button onClick={createFile} disabled={!newFileName.trim()}
                className="text-[10px] px-2 py-1 rounded bg-blue-600/20 text-blue-400 disabled:opacity-40">+ 添加</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function SkillInstructionsEditor({ readme, onSave }: { readme: string; onSave: (content: string) => void }) {
  const [content, setContent] = useState(readme)
  const [saving, setSaving] = useState(false)

  useEffect(() => { setContent(readme) }, [readme])

  const handleSave = useCallback(async () => {
    setSaving(true)
    await onSave(content)
    setSaving(false)
  }, [content, onSave])

  return (
    <div className="space-y-2">
      <textarea
        value={content}
        onChange={e => setContent(e.target.value)}
        className="w-full text-[11px] text-gray-300 bg-gray-900 border border-gray-700 rounded p-3 font-mono resize-y min-h-[150px] max-h-[400px] focus:outline-none focus:border-emerald-500"
        rows={12}
      />
      <button onClick={handleSave} disabled={saving || content === readme}
        className="text-[10px] px-3 py-1 rounded bg-emerald-600 text-white disabled:opacity-40 hover:bg-emerald-500">
        {saving ? '保存中...' : '保存指令'}
      </button>
    </div>
  )
}

// ── MCP 面板 ──

function McpDetailView({ mcpId }: { mcpId: string }) {
  const [activeTab, setActiveTab] = useState<'status' | 'tools' | 'config'>('status')
  const [server, setServer] = useState<Record<string, unknown> | null>(null)
  const [reconnecting, setReconnecting] = useState(false)

  useEffect(() => {
    fetch(`/api/admin/mcp/${mcpId}`).then(r => r.json()).then(setServer).catch(() => {})
  }, [mcpId])

  const handleReconnect = useCallback(async () => {
    setReconnecting(true)
    try {
      const res = await fetch(`/api/admin/mcp/${mcpId}/reconnect`, { method: 'POST' })
      const data = await res.json()
      setServer(prev => prev ? { ...prev, status: data.status ?? 'connected', discovered_tools: data.tools ?? [] } : prev)
    } catch {
      // ignore
    } finally {
      setReconnecting(false)
    }
  }, [mcpId])

  const status = (server?.status as string) || 'disconnected'
  const tools = (server?.discovered_tools as Array<Record<string, string>>) || []

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full shrink-0 ${
            status === 'connected' ? 'bg-green-500' : status === 'error' ? 'bg-yellow-500' : 'bg-red-500'
          }`} />
          <h3 className="font-semibold text-white">{(server?.name as string) || mcpId}</h3>
          <span className="text-xs px-1.5 py-0.5 rounded bg-orange-900/30 text-orange-400">MCP</span>
        </div>
      </div>

      <TabBar
        tabs={[
          { key: 'status', label: '状态' },
          { key: 'tools', label: `工具 (${tools.length})` },
          { key: 'config', label: '配置' },
        ]}
        active={activeTab}
        onChange={(t) => setActiveTab(t as 'status' | 'tools' | 'config')}
      />

      <div className="flex-1 overflow-auto p-4 space-y-3">
        {activeTab === 'status' && (
          <>
            <div className="bg-surface-light rounded-lg p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">连接状态</span>
                <span className={`text-xs font-medium ${
                  status === 'connected' ? 'text-green-400' : status === 'error' ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {status === 'connected' ? '已连接' : status === 'error' ? '连接错误' : '未连接'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">传输方式</span>
                <span className="text-xs text-white">{(server?.transport as string) || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">可用工具</span>
                <span className="text-xs text-white">{tools.length} 个</span>
              </div>
            </div>
            <button
              onClick={handleReconnect}
              disabled={reconnecting}
              className="w-full text-xs py-1.5 rounded bg-orange-600 text-white hover:bg-orange-500 disabled:opacity-40"
            >
              {reconnecting ? '连接中...' : '重新连接'}
            </button>
          </>
        )}

        {activeTab === 'tools' && (
          <div className="space-y-1">
            {tools.length === 0 ? (
              <div className="text-xs text-gray-500">暂无工具。请先连接 MCP 服务。</div>
            ) : (
              tools.map((t, i) => (
                <div key={i} className="bg-surface-light rounded p-2">
                  <div className="text-xs font-medium text-white">{t.name}</div>
                  {t.description && <div className="text-[10px] text-gray-400 mt-0.5">{t.description}</div>}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'config' && (
          <div className="space-y-2">
            <div className="bg-surface-light rounded-lg p-3">
              <h4 className="text-xs font-medium text-gray-300 mb-1">Server ID</h4>
              <code className="text-xs text-orange-400">{mcpId}</code>
            </div>
            {server?.url && (
              <div className="bg-surface-light rounded-lg p-3">
                <h4 className="text-xs font-medium text-gray-300 mb-1">URL</h4>
                <code className="text-xs text-gray-300 break-all">{server.url as string}</code>
              </div>
            )}
            {server?.command && (
              <div className="bg-surface-light rounded-lg p-3">
                <h4 className="text-xs font-medium text-gray-300 mb-1">Command</h4>
                <code className="text-xs text-gray-300 break-all">{server.command as string}</code>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
