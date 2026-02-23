import { useMemo, useEffect, useState } from 'react'
import {
  ReactFlow,
  type Node,
  type Edge,
  Background,
  BackgroundVariant,
  Controls,
} from '@xyflow/react'
import { SkillNode } from './nodes/SkillNode'
import { ChevronRight } from 'lucide-react'
import type { SkillNodeData } from '@/types'

interface SkillDrilldownViewProps {
  agentId: string
  agentName: string
  onBack: () => void
  onSkillClick?: (skillName: string) => void
}

const nodeTypes = { skillNode: SkillNode }

export function SkillDrilldownView({ agentId, agentName, onBack, onSkillClick }: SkillDrilldownViewProps) {
  const [skills, setSkills] = useState<Array<{ name: string; title: string; description: string }>>([])

  useEffect(() => {
    fetch(`/api/admin/agents/${agentId}/tools`)
      .then(r => r.json())
      .then(data => {
        const skillTools = (data.tools || []).filter((t: Record<string, string>) => t.type === 'skill')
        setSkills(skillTools)
      })
      .catch(() => setSkills([]))
  }, [agentId])

  const { nodes } = useMemo(() => {
    const cols = 4
    const gapX = 180
    const gapY = 100
    const startX = 80
    const startY = 80

    const flowNodes: Node<SkillNodeData>[] = skills.map((s, i) => ({
      id: `skill:${s.name}`,
      type: 'skillNode',
      position: { x: startX + (i % cols) * gapX, y: startY + Math.floor(i / cols) * gapY },
      data: { label: s.title || s.name, skillName: s.name, description: s.description },
    }))

    return { nodes: flowNodes }
  }, [skills])

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-2 border-b border-border bg-surface flex items-center gap-1.5 text-xs shrink-0">
        <button onClick={onBack} className="text-blue-400 hover:text-blue-300 transition-colors font-medium">
          全局视图
        </button>
        <ChevronRight size={12} className="text-gray-500" />
        <span className="text-white font-medium">{agentName}</span>
        <ChevronRight size={12} className="text-gray-500" />
        <span className="text-emerald-400 font-medium">Skill ({skills.length})</span>
      </div>
      <div className="flex-1">
        <ReactFlow
          nodes={nodes}
          edges={[] as Edge[]}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => {
            const id = node.id
            if (id.startsWith('skill:') && onSkillClick) {
              onSkillClick(id.replace('skill:', ''))
            }
          }}
          fitView
          fitViewOptions={{ padding: 0.4 }}
          minZoom={0.5}
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
