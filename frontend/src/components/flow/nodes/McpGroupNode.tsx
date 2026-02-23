import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Server } from 'lucide-react'

export interface McpGroupData {
  label: string
  agentId: string
  count: number
}

export function McpGroupNode({ data, selected }: NodeProps) {
  const d = data as unknown as McpGroupData

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2.5 w-36 transition-all duration-200 backdrop-blur-sm cursor-pointer
        border-orange-500/50 bg-orange-950/30 hover:bg-orange-950/50
        ${selected ? 'ring-2 ring-orange-400 ring-offset-1 ring-offset-gray-900' : ''}
      `}
    >
      <Handle type="target" position={Position.Top} id="tool-in"
        className="!bg-orange-400 !w-2.5 !h-2.5 !border-0" />

      <div className="flex items-center gap-1.5">
        <Server size={12} className="text-orange-400 shrink-0" />
        <span className="text-xs font-medium text-orange-300">MCP</span>
        <span className="text-[10px] text-orange-500 ml-auto">({d.count})</span>
      </div>
      <div className="text-[9px] text-gray-500 mt-0.5">双击查看</div>
    </div>
  )
}
