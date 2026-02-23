import { Handle, Position, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { SkipForward } from 'lucide-react'
import type { AgentNodeData } from '@/types'

const statusStyles: Record<string, string> = {
  idle: 'border-gray-500/40 bg-gray-900/60',
  running: 'border-blue-500 bg-blue-950/60 shadow-blue-500/20 shadow-lg',
  success: 'border-green-500 bg-green-950/60',
  error: 'border-red-500 bg-red-950/60',
  waiting: 'border-yellow-500 bg-yellow-950/60',
}

const statusDotStyles: Record<string, string> = {
  idle: 'bg-gray-500',
  running: 'bg-blue-500 animate-pulse',
  success: 'bg-green-500',
  error: 'bg-red-500',
  waiting: 'bg-yellow-500 animate-pulse',
}

const statusLabels: Record<string, string> = {
  idle: '空闲',
  running: '运行中',
  success: '已完成',
  error: '出错',
  waiting: '等待中',
}

export function AgentNode({ data, selected, id }: NodeProps) {
  const d = data as unknown as AgentNodeData
  const isSubAgent = d.isSubAgent
  const isBypassed = d.bypass

  return (
    <div
      className={cn(
        'rounded-xl border-2 p-4 transition-all duration-300 backdrop-blur-sm',
        isSubAgent ? 'w-48' : 'w-56',
        isBypassed ? 'border-gray-600/30 bg-gray-900/30 opacity-50' :
        isSubAgent ? 'border-indigo-500/30 bg-indigo-950/40' :
        (statusStyles[d.status] ?? statusStyles.idle),
        selected && 'ring-2 ring-blue-400 ring-offset-2 ring-offset-gray-900',
      )}
    >
      {/* Left Handle: flow 入 */}
      <Handle
        type="target"
        position={Position.Left}
        id="flow-in"
        className="!bg-gray-400 !w-2.5 !h-2.5 !border-0 hover:!bg-blue-400"
      />

      {/* Top Handle: 被其他 Agent 连接为工具 (SubAgent / 容器连线) */}
      <Handle
        type="target"
        position={Position.Top}
        id="tool-in"
        className="!bg-indigo-400 !w-2.5 !h-2.5 !border-0 hover:!bg-indigo-300"
      />

      <div className="flex items-center gap-2 mb-1.5">
        <span className={cn('w-2.5 h-2.5 rounded-full shrink-0', isBypassed ? 'bg-gray-600' : (statusDotStyles[d.status] ?? statusDotStyles.idle))} />
        <span className={cn('font-semibold text-white truncate flex-1', isSubAgent ? 'text-xs' : 'text-sm', isBypassed && 'line-through text-gray-500')}>
          {d.label}
        </span>

        {d.onBypassToggle && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              d.onBypassToggle?.(id, !isBypassed)
            }}
            className={cn(
              'p-0.5 rounded transition-colors shrink-0',
              isBypassed
                ? 'bg-yellow-600/30 text-yellow-400 hover:bg-yellow-600/50'
                : 'text-gray-600 hover:text-gray-400 hover:bg-white/5'
            )}
            title={isBypassed ? '取消跳过' : '跳过此节点'}
          >
            <SkipForward size={12} />
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 mb-1">
        <span className={cn('px-1.5 py-0.5 rounded bg-white/10 text-gray-300', isSubAgent ? 'text-[9px]' : 'text-[10px]')}>
          {isSubAgent ? 'Sub-Agent' : d.agentType}
        </span>
        {isBypassed ? (
          <span className="text-[10px] text-yellow-500">已跳过</span>
        ) : (
          <span className="text-[10px] text-gray-400">{statusLabels[d.status] ?? d.status}</span>
        )}
      </div>

      {!isBypassed && !isSubAgent && d.status === 'running' && d.progress !== undefined && (
        <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden mb-2">
          <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${d.progress}%` }} />
        </div>
      )}

      {d.qualityScore !== undefined && d.qualityScore > 0 && (
        <div className={cn(
          'text-xs font-mono px-2 py-0.5 rounded inline-block mb-1',
          d.qualityScore >= 80 ? 'bg-green-900/60 text-green-300' :
          d.qualityScore >= 60 ? 'bg-yellow-900/60 text-yellow-300' :
          'bg-red-900/60 text-red-300',
        )}>
          质量: {d.qualityScore}分
        </div>
      )}

      {d.status === 'waiting' && !isBypassed && (
        <div className="text-xs text-yellow-400 mt-1">等待用户回复...</div>
      )}

      {d.error && !isBypassed && (
        <div className="text-xs text-red-400 mt-1 truncate" title={d.error}>{d.error}</div>
      )}

      {/* Right Handle: flow 出 */}
      <Handle
        type="source"
        position={Position.Right}
        id="flow-out"
        className="!bg-gray-400 !w-2.5 !h-2.5 !border-0 hover:!bg-blue-400"
      />

      {/* Bottom Handle: 连接 Skill / Agent / MCP */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="tool-out"
        isConnectable
        className="!bg-indigo-400 !w-2.5 !h-2.5 !border-0 hover:!bg-indigo-300 hover:!w-3.5 hover:!h-3.5 transition-all"
      />
    </div>
  )
}
