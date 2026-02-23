import { useState } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { ToolNodeData } from '@/types'

const statusStyles: Record<string, string> = {
  idle: 'border-gray-600/40 bg-gray-900/60',
  calling: 'border-blue-500 bg-blue-950/60 shadow-blue-500/20 shadow-md',
  success: 'border-green-500/60 bg-green-950/40',
  error: 'border-red-500/60 bg-red-950/40',
}

const statusDotStyles: Record<string, string> = {
  idle: 'bg-gray-500',
  calling: 'bg-blue-500 animate-pulse',
  success: 'bg-green-500',
  error: 'bg-red-500',
}

export function ToolNode({ data }: NodeProps) {
  const d = data as unknown as ToolNodeData
  const [expanded, setExpanded] = useState(false)
  const hasIO = d.input || d.output

  return (
    <div
      className={cn(
        'rounded-lg border p-3 w-44 transition-all duration-200 backdrop-blur-sm text-xs',
        statusStyles[d.status] ?? statusStyles.idle,
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-500 !w-2 !h-2 !border-0" />

      <div className="flex items-center gap-1.5 mb-1">
        <span className={cn('w-2 h-2 rounded-full shrink-0', statusDotStyles[d.status] ?? statusDotStyles.idle)} />
        <span className="font-semibold text-white truncate flex-1">{d.name}</span>
        {d.callCount > 0 && (
          <span className="text-[9px] px-1 py-0.5 rounded bg-white/10 text-gray-300">{d.callCount}x</span>
        )}
      </div>

      <p className="text-gray-400 text-[10px] leading-tight mb-1 line-clamp-2">{d.description}</p>

      {hasIO && (
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
          className="flex items-center gap-0.5 text-[10px] text-gray-500 hover:text-gray-300 transition-colors mt-1"
        >
          {expanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          参数详情
        </button>
      )}

      {expanded && hasIO && (
        <div className="mt-1.5 space-y-1">
          {d.input && (
            <div>
              <span className="text-[9px] text-blue-400 font-medium">输入:</span>
              <pre className="text-[9px] text-gray-400 bg-black/30 rounded p-1 mt-0.5 max-h-20 overflow-auto whitespace-pre-wrap break-all">
                {d.input}
              </pre>
            </div>
          )}
          {d.output && (
            <div>
              <span className="text-[9px] text-green-400 font-medium">输出:</span>
              <pre className="text-[9px] text-gray-400 bg-black/30 rounded p-1 mt-0.5 max-h-20 overflow-auto whitespace-pre-wrap break-all">
                {d.output}
              </pre>
            </div>
          )}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-gray-500 !w-2 !h-2 !border-0" />
    </div>
  )
}
