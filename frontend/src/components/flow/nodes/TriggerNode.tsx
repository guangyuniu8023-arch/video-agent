import { Handle, Position, type NodeProps } from '@xyflow/react'
import { MessageCircle } from 'lucide-react'

export interface TriggerNodeData {
  label: string
  status: string
}

export function TriggerNode({ data, selected }: NodeProps) {
  const d = data as unknown as TriggerNodeData
  const isWaiting = d.status === 'waiting'

  return (
    <div
      className={`rounded-xl border-2 px-5 py-3 w-48 transition-all duration-300 backdrop-blur-sm
        border-teal-500/60 bg-teal-950/40
        ${isWaiting ? 'shadow-teal-500/20 shadow-lg border-teal-400' : ''}
        ${selected ? 'ring-2 ring-teal-400 ring-offset-2 ring-offset-gray-900' : ''}
      `}
    >
      <div className="flex items-center gap-2 mb-1">
        <div className="w-7 h-7 rounded-lg bg-teal-600/30 flex items-center justify-center">
          <MessageCircle size={14} className="text-teal-300" />
        </div>
        <div>
          <div className="text-xs font-semibold text-white">{d.label}</div>
          <div className="text-[9px] text-teal-400">Trigger</div>
        </div>
      </div>
      {isWaiting && (
        <div className="text-[10px] text-teal-300 mt-1 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse" />
          等待输入...
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        id="flow-out"
        className="!bg-teal-400 !w-2.5 !h-2.5 !border-0 hover:!bg-teal-300"
      />
    </div>
  )
}
