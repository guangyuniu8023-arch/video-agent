import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Users } from 'lucide-react'

export interface SubAgentGroupData {
  label: string
  agentId: string
  count: number
}

export function SubAgentGroupNode({ data, selected }: NodeProps) {
  const d = data as unknown as SubAgentGroupData

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2.5 w-44 transition-all duration-200 backdrop-blur-sm cursor-pointer
        border-indigo-500/50 bg-indigo-950/30 hover:bg-indigo-950/50
        ${selected ? 'ring-2 ring-indigo-400 ring-offset-1 ring-offset-gray-900' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} id="tool-in"
        className="!bg-indigo-400 !w-2.5 !h-2.5 !border-0" />

      <div className="flex items-center gap-1.5 mb-0.5">
        <Users size={12} className="text-indigo-400 shrink-0" />
        <span className="text-xs font-medium text-indigo-300 truncate">{d.label}</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-gray-500">Sub-Agent</span>
        <span className="text-[9px] text-gray-500">双击展开</span>
      </div>

      <Handle type="source" position={Position.Bottom} id="tool-out"
        className="!bg-indigo-400 !w-2.5 !h-2.5 !border-0" />
    </div>
  )
}
