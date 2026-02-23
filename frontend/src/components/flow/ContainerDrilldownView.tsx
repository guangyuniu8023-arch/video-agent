import { useMemo, useEffect, useState } from 'react'
import {
  ReactFlow,
  type Node,
  type Edge,
  MarkerType,
  Background,
  BackgroundVariant,
  Controls,
} from '@xyflow/react'
import { AgentNode } from './nodes/AgentNode'
import { SkillNode } from './nodes/SkillNode'
import { SkillGroupNode } from './nodes/SkillGroupNode'
import { McpNode } from './nodes/McpNode'
import { McpGroupNode } from './nodes/McpGroupNode'
import { ChevronRight } from 'lucide-react'

interface ContainerDrilldownViewProps {
  containerId: string
  containerType: string
  containerLabel: string
  onBack: () => void
  onNodeClick?: (nodeId: string) => void
}

const nodeTypes = {
  agentNode: AgentNode,
  skillNode: SkillNode,
  skillGroupNode: SkillGroupNode,
  mcpNode: McpNode,
  mcpGroupNode: McpGroupNode,
}

export function ContainerDrilldownView({ containerId, containerType, containerLabel, onBack, onNodeClick }: ContainerDrilldownViewProps) {
  const [items, setItems] = useState<string[]>([])
  const [skillInfos, setSkillInfos] = useState<Record<string, { title: string; description: string }>>({})
  const [agentInfo, setAgentInfo] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    fetch('/api/admin/canvas/nodes').then(r => r.json()).then(data => {
      const node = (data.nodes || []).find((n: Record<string, unknown>) => n.id === containerId)
      const nodeItems = ((node?.config as Record<string, unknown>)?.items as string[]) || []
      setItems(nodeItems)

      if (containerType === 'agent') {
        const refId = (node?.ref_id as string) || ''
        fetch(`/api/admin/agents/${refId}`).then(r => r.json()).then(setAgentInfo).catch(() => {})
      }
    }).catch(() => {})

    fetch('/api/admin/skills').then(r => r.json()).then(data => {
      const map: Record<string, { title: string; description: string }> = {}
      for (const s of (data.skills || [])) map[s.name] = { title: s.title, description: s.description || '' }
      setSkillInfos(map)
    }).catch(() => {})
  }, [containerId, containerType])

  const { nodes, edges } = useMemo(() => {
    if (containerType === 'skillgroup') {
      const cols = 4, gapX = 180, gapY = 100
      const flowNodes: Node[] = items.map((item, i) => ({
        id: `skill:${item}`,
        type: 'skillNode',
        position: { x: 80 + (i % cols) * gapX, y: 80 + Math.floor(i / cols) * gapY },
        data: { label: skillInfos[item]?.title || item, skillName: item, description: skillInfos[item]?.description },
      }))
      return { nodes: flowNodes, edges: [] as Edge[] }
    }

    if (containerType === 'mcpgroup') {
      const flowNodes: Node[] = items.map((item, i) => ({
        id: `mcp:${item}`,
        type: 'mcpNode',
        position: { x: 80 + i * 180, y: 80 },
        data: { label: item, mcpId: item, status: 'disconnected', toolCount: 0 },
      }))
      return { nodes: flowNodes, edges: [] as Edge[] }
    }

    // SubAgent (containerType === 'agent'): 显示 Agent 节点 + Skill 容器 + MCP 容器
    if (agentInfo) {
      const refId = containerId.replace('agent:', '')
      const tools = (agentInfo.available_tools as string[]) || []
      const skillTools = tools.filter(t => !t.startsWith('mcp_'))
      const mcpTools = tools.filter(t => t.startsWith('mcp_'))

      const flowNodes: Node[] = [
        {
          id: `inner-agent:${refId}`,
          type: 'agentNode',
          position: { x: 300, y: 80 },
          data: {
            label: (agentInfo.name as string) || refId,
            agentType: (agentInfo.description as string) || 'Agent',
            status: 'idle',
            isSubAgent: false,
            bypass: false,
          },
        },
      ]
      const flowEdges: Edge[] = []

      if (skillTools.length > 0) {
        flowNodes.push({
          id: `inner-skillgroup:${refId}`,
          type: 'skillGroupNode',
          position: { x: 200, y: 250 },
          data: { label: 'Skill', agentId: refId, count: skillTools.length },
        })
        flowEdges.push({
          id: `inner-edge-skill`,
          source: `inner-agent:${refId}`,
          target: `inner-skillgroup:${refId}`,
          sourceHandle: 'tool-out',
          targetHandle: 'tool-in',
          style: { stroke: '#22c55e', strokeWidth: 1.5, strokeDasharray: '4 4' },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#22c55e' },
        })
      }

      if (mcpTools.length > 0) {
        flowNodes.push({
          id: `inner-mcpgroup:${refId}`,
          type: 'mcpGroupNode',
          position: { x: 450, y: 250 },
          data: { label: 'MCP', agentId: refId, count: mcpTools.length },
        })
        flowEdges.push({
          id: `inner-edge-mcp`,
          source: `inner-agent:${refId}`,
          target: `inner-mcpgroup:${refId}`,
          sourceHandle: 'tool-out',
          targetHandle: 'tool-in',
          style: { stroke: '#f97316', strokeWidth: 1.5, strokeDasharray: '4 4' },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#f97316' },
        })
      }

      return { nodes: flowNodes, edges: flowEdges }
    }

    return { nodes: [], edges: [] }
  }, [items, skillInfos, agentInfo, containerType, containerId])

  const typeLabel = containerType === 'skillgroup' ? 'Skill' : containerType === 'mcpgroup' ? 'MCP' : 'Sub-Agent'
  const typeColor = containerType === 'skillgroup' ? 'text-emerald-400' : containerType === 'mcpgroup' ? 'text-orange-400' : 'text-indigo-400'

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-border bg-surface flex items-center gap-1.5 text-xs shrink-0">
        <button onClick={onBack} className="text-blue-400 hover:text-blue-300 transition-colors font-medium">
          全局视图
        </button>
        <ChevronRight size={12} className="text-gray-500" />
        <span className={`font-medium ${typeColor}`}>{typeLabel}</span>
        <span className="text-white font-medium ml-1">{containerLabel}</span>
      </div>
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => onNodeClick?.(node.id)}
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
