import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Wrench } from 'lucide-react'
import type { SkillNodeData } from '@/types'

export function SkillNode({ data, selected }: NodeProps) {
  const d = data as unknown as SkillNodeData

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2 w-40 transition-all duration-200 backdrop-blur-sm
        border-emerald-500/40 bg-emerald-950/40
        ${selected ? 'ring-2 ring-emerald-400 ring-offset-1 ring-offset-gray-900' : ''}
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        id="tool-in"
        className="!bg-emerald-400 !w-2 !h-2 !border-0 hover:!bg-emerald-300"
      />

      <div className="flex items-center gap-1.5 mb-0.5">
        <Wrench size={11} className="text-emerald-400 shrink-0" />
        <span className="text-xs font-medium text-white truncate">{d.label}</span>
      </div>
      {d.description && (
        <div className="text-[9px] text-gray-400 truncate">{d.description}</div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-emerald-400 !w-2 !h-2 !border-0 hover:!bg-emerald-300"
      />
    </div>
  )
}
