import { useMemo } from 'react'
import type { LogEntry } from '@/types'

interface AgentRunLogProps {
  agentId: string
  logs: LogEntry[]
}

export function AgentRunLog({ agentId, logs }: AgentRunLogProps) {
  const filteredLogs = useMemo(
    () => logs.filter(l => l.agent === agentId),
    [logs, agentId]
  )

  if (filteredLogs.length === 0) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-gray-500">暂无执行日志</p>
        <p className="text-[10px] text-gray-600 mt-1">启动工作流后，日志将实时显示在这里</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* 头部 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-xs text-gray-400">{filteredLogs.length} 条日志</span>
      </div>

      {/* 日志列表 */}
      <div className="flex-1 overflow-auto p-3 space-y-1 font-mono">
        {filteredLogs.map((log, i) => (
          <LogItem key={i} log={log} />
        ))}
      </div>
    </div>
  )
}

function LogItem({ log }: { log: LogEntry }) {
  const time = new Date(log.timestamp * 1000).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  const isError = log.message.includes('失败') || log.message.includes('错误') || log.message.includes('error')
  const isSuccess = log.message.includes('完成') || log.message.includes('通过') || log.message.includes('success')

  return (
    <div className="text-xs py-1 px-2 rounded hover:bg-white/5 transition-colors">
      <div className="flex items-start gap-2">
        <span className="text-gray-600 shrink-0 tabular-nums">{time}</span>
        <span className={`flex-1 ${
          isError ? 'text-red-400' : isSuccess ? 'text-green-400' : 'text-gray-300'
        }`}>
          {log.message}
        </span>
      </div>
    </div>
  )
}
