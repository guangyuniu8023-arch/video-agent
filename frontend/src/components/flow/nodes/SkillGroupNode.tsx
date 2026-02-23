import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Wrench } from 'lucide-react'

export interface SkillGroupData {
  label: string
  agentId: string
  count: number
}

export function SkillGroupNode({ data, selected }: NodeProps) {
  const d = data as unknown as SkillGroupData

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2.5 w-36 transition-all duration-200 backdrop-blur-sm cursor-pointer
        border-emerald-500/50 bg-emerald-950/30 hover:bg-emerald-950/50
        ${selected ? 'ring-2 ring-emerald-400 ring-offset-1 ring-offset-gray-900' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} id="tool-in"
        className="!bg-emerald-400 !w-2.5 !h-2.5 !border-0" />

      <div className="flex items-center gap-1.5">
        <Wrench size={12} className="text-emerald-400 shrink-0" />
        <span className="text-xs font-medium text-emerald-300">Skill</span>
        <span className="text-[10px] text-emerald-500 ml-auto">({d.count})</span>
      </div>
      <div className="text-[9px] text-gray-500 mt-0.5">双击查看</div>
    </div>
  )
}
