import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Server } from 'lucide-react'
import type { McpNodeData } from '@/types'

const statusColor: Record<string, string> = {
  connected: 'bg-green-500',
  disconnected: 'bg-red-500',
  error: 'bg-yellow-500',
}

export function McpNode({ data, selected }: NodeProps) {
  const d = data as unknown as McpNodeData

  return (
    <div
      className={`rounded-lg border-2 px-3 py-2 w-40 transition-all duration-200 backdrop-blur-sm
        border-orange-500/40 bg-orange-950/40
        ${selected ? 'ring-2 ring-orange-400 ring-offset-1 ring-offset-gray-900' : ''}
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        id="tool-in"
        className="!bg-orange-400 !w-2 !h-2 !border-0 hover:!bg-orange-300"
      />

      <div className="flex items-center gap-1.5 mb-0.5">
        <Server size={11} className="text-orange-400 shrink-0" />
        <span className="text-xs font-medium text-white truncate">{d.label}</span>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusColor[d.status] ?? statusColor.disconnected}`} />
      </div>
      <div className="text-[9px] text-gray-400">
        {d.toolCount} tools | MCP
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-orange-400 !w-2 !h-2 !border-0 hover:!bg-orange-300"
      />
    </div>
  )
}
