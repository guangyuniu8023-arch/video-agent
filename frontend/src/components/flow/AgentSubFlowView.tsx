import { useMemo, useEffect, useState, useCallback } from 'react'
import {
  ReactFlow,
  type Node,
  type Edge,
  MarkerType,
  Background,
  BackgroundVariant,
  Controls,
  Position,
} from '@xyflow/react'
import { ToolNode } from './nodes/ToolNode'
import { AgentNode } from './nodes/AgentNode'
import { ChevronRight } from 'lucide-react'
import { fetchAgentTools, fetchAgentChildren, type ToolEntry } from '@/services/api'
import type { ToolCallInfo, ToolNodeData, AgentNodeData } from '@/types'

interface AgentSubFlowViewProps {
  agentId: string
  agentData: AgentNodeData
  toolCalls: ToolCallInfo[]
  onBack: () => void
  onSubAgentClick?: (subAgentId: string) => void
}

const nodeTypes = { toolNode: ToolNode, agentNode: AgentNode }

function getHandlePosition(angle: number): Position {
  const deg = ((angle * 180) / Math.PI + 360) % 360
  if (deg >= 315 || deg < 45) return Position.Left
  if (deg >= 45 && deg < 135) return Position.Top
  if (deg >= 135 && deg < 225) return Position.Right
  return Position.Bottom
}

function oppositePosition(pos: Position): Position {
  switch (pos) {
    case Position.Top: return Position.Bottom
    case Position.Bottom: return Position.Top
    case Position.Left: return Position.Right
    case Position.Right: return Position.Left
  }
}

interface ChildAgent {
  id: string
  name: string
  description: string
  available_tools: string[]
}

export function AgentSubFlowView({ agentId, agentData, toolCalls, onBack, onSubAgentClick }: AgentSubFlowViewProps) {
  const [toolEntries, setToolEntries] = useState<ToolEntry[]>([])
  const [children, setChildren] = useState<ChildAgent[]>([])

  useEffect(() => {
    fetchAgentTools(agentId)
      .then(data => setToolEntries(data.tools ?? []))
      .catch(() => setToolEntries([]))
    fetchAgentChildren(agentId)
      .then(data => setChildren(data.children ?? []))
      .catch(() => setChildren([]))
  }, [agentId])

  const skillEntries = toolEntries.filter(t => t.type === 'skill')
  const descMap: Record<string, string> = {}
  for (const t of toolEntries) {
    descMap[t.name] = t.title || t.description
  }

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    if (node.id.startsWith('sub-') && onSubAgentClick) {
      onSubAgentClick(node.id.replace('sub-', ''))
    }
  }, [onSubAgentClick])

  const { nodes, edges } = useMemo(() => {
    const centerX = 400
    const centerY = 300

    const llmNode: Node = {
      id: 'llm-center',
      type: 'default',
      position: { x: centerX - 70, y: centerY - 25 },
      data: { label: `${agentData.label} (LLM)` },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      style: {
        background: '#1e293b',
        border: agentData.status === 'running' ? '2px solid #3b82f6' : '2px solid #475569',
        borderRadius: '12px',
        color: '#f1f5f9',
        padding: '12px 24px',
        fontSize: '13px',
        fontWeight: 600,
        width: 'auto',
        textAlign: 'center' as const,
        boxShadow: agentData.status === 'running' ? '0 0 20px rgba(59,130,246,0.3)' : 'none',
      },
    }

    const allItems = [
      ...skillEntries.map(t => ({ type: 'skill' as const, id: t.name, name: t.name, desc: descMap[t.name] ?? '工具' })),
      ...children.map(c => ({ type: 'agent' as const, id: c.id, name: c.name, desc: c.description || 'Sub-Agent' })),
    ]

    const radius = 240
    const resultNodes: Node[] = [llmNode]
    const resultEdges: Edge[] = []

    allItems.forEach((item, i) => {
      const angle = (2 * Math.PI * i) / allItems.length - Math.PI / 2
      const x = centerX + radius * Math.cos(angle) - 88
      const y = centerY + radius * Math.sin(angle) - 40

      if (item.type === 'skill') {
        const calls = toolCalls.filter(c => c.toolName === item.id)
        const latestCall = calls[calls.length - 1]
        const status = latestCall?.status ?? 'idle'
        const handlePos = getHandlePosition(angle)

        resultNodes.push({
          id: `tool-${item.id}`,
          type: 'toolNode',
          position: { x, y },
          sourcePosition: handlePos,
          targetPosition: handlePos,
          data: {
            name: item.name,
            description: item.desc,
            status,
            input: latestCall?.input,
            output: latestCall?.output,
            callCount: calls.length,
          } as ToolNodeData,
        })

        const isCalling = latestCall?.status === 'calling'
        const wasCalled = calls.length > 0
        const toolHandlePos = getHandlePosition(angle)
        const llmHandlePos = oppositePosition(toolHandlePos)

        resultEdges.push({
          id: `llm->${item.id}`,
          source: 'llm-center',
          target: `tool-${item.id}`,
          sourceHandle: llmHandlePos,
          targetHandle: toolHandlePos,
          animated: isCalling,
          markerEnd: { type: MarkerType.ArrowClosed, color: isCalling ? '#3b82f6' : wasCalled ? '#22c55e' : '#64748b' },
          style: { stroke: isCalling ? '#3b82f6' : wasCalled ? '#22c55e' : '#64748b', strokeWidth: isCalling ? 2.5 : 1.5 },
        })
      } else {
        resultNodes.push({
          id: `sub-${item.id}`,
          type: 'agentNode',
          position: { x, y },
          data: {
            label: item.name,
            agentType: item.desc,
            status: 'idle',
            isSubAgent: true,
            parentId: agentId,
          } as AgentNodeData,
        })

        resultEdges.push({
          id: `llm->${item.id}`,
          source: 'llm-center',
          target: `sub-${item.id}`,
          animated: false,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#6366f1' },
          style: { stroke: '#6366f1', strokeWidth: 1.5, strokeDasharray: '4 4' },
        })
      }
    })

    return { nodes: resultNodes, edges: resultEdges }
  }, [skillEntries, children, toolCalls, agentData, agentId, descMap])

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-border bg-surface flex items-center gap-1.5 text-xs shrink-0">
        <button onClick={onBack} className="text-blue-400 hover:text-blue-300 transition-colors font-medium">
          全局视图
        </button>
        <ChevronRight size={12} className="text-gray-500" />
        <span className="text-white font-medium">{agentData.label}</span>
        <span className="text-gray-500 ml-1">({agentData.agentType})</span>
        {children.length > 0 && (
          <span className="ml-2 text-indigo-400 text-[10px]">
            {children.length} 个子 Agent
          </span>
        )}
        {agentData.status === 'running' && (
          <span className="ml-2 flex items-center gap-1 text-blue-400">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            运行中
          </span>
        )}
      </div>
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.4 }}
          minZoom={0.4}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#2a2a3e" />
          <Controls showInteractive={false} className="!bg-surface !border-border !shadow-none [&>button]:!bg-surface-light [&>button]:!border-border [&>button]:!text-gray-400" />
        </ReactFlow>
      </div>
    </div>
  )
}
