import { useState, useCallback, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { AgentFlowCanvas } from '@/components/flow/AgentFlowCanvas'
import { NodeDetailPanel } from '@/components/panels/NodeDetailPanel'
import { BottomPanel } from '@/components/bottom/BottomPanel'
import { TopToolbar } from '@/components/shared/TopToolbar'
import { useAgentFlow } from '@/hooks/useAgentFlow'
import { startWorkflow, stopWorkflow, replyToAgent } from '@/services/api'
import type { UploadedFile } from '@/types'
import { ChevronRight } from 'lucide-react'

interface CanvasLevel {
  id: string
  label: string
}

export function WorkspacePage() {
  const { projectId: routeProjectId } = useParams<{ projectId: string }>()
  const [projectId, setProjectId] = useState<string | null>(routeProjectId ?? null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [canvasStack, setCanvasStack] = useState<CanvasLevel[]>([])
  const [running, setRunning] = useState(false)
  const [sending, setSending] = useState(false)
  const [bottomHeight, setBottomHeight] = useState(260)
  const [rightWidth, setRightWidth] = useState(380)
  const draggingRef = useRef<'bottom' | 'right' | null>(null)

  const currentParentCanvas = canvasStack.length > 0 ? canvasStack[canvasStack.length - 1].id : null

  const {
    nodes, edges, logs, chatMessages, waitingForReply, streamingText,
    connected, toolCalls, setNodes, setEdges, addChatMessage, resetFlow,
    loadCanvas, handleConnect, handleEdgeDelete, saveNodePosition,
  } = useAgentFlow(projectId, currentParentCanvas)

  const handleStart = useCallback(async () => {
    const message = prompt('请描述你想创作的视频:')
    if (!message?.trim()) return

    try {
      setSending(true)
      const res = await startWorkflow(message, projectId ?? undefined)
      setProjectId(res.project_id)
      setRunning(true)
      resetFlow()
    } catch (err) {
      console.error('Failed to start workflow:', err)
      alert(`启动失败: ${err}`)
    } finally {
      setSending(false)
    }
  }, [projectId, resetFlow])

  const handleStop = useCallback(async () => {
    if (!projectId) return
    try {
      await stopWorkflow(projectId)
      setRunning(false)
    } catch (err) {
      console.error('Failed to stop workflow:', err)
    }
  }, [projectId])

  const handleReset = useCallback(() => {
    resetFlow()
    setSelectedNodeId(null)
    setRunning(false)
    setSending(false)
  }, [resetFlow])

  const handleSendMessage = useCallback(async (message: string, attachments?: UploadedFile[]) => {
    if (sending) return

    addChatMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now() / 1000,
      attachments,
    })

    try {
      setSending(true)
      const uploadedAssets = attachments?.map(a => ({
        type: a.contentType?.startsWith('video/') ? 'video' : 'image',
        path: a.filename,
        url: a.url,
      })) ?? []
      const res = await startWorkflow(message, projectId ?? undefined, uploadedAssets)
      setProjectId(res.project_id)
      setRunning(true)
    } catch (err) {
      console.error('Failed to send message:', err)
      addChatMessage({
        id: `err-${Date.now()}`,
        role: 'system',
        content: `发送失败: ${err}`,
        timestamp: Date.now() / 1000,
      })
    } finally {
      setSending(false)
    }
  }, [projectId, addChatMessage, sending])

  const handleReply = useCallback(async (message: string) => {
    if (!projectId || sending) return

    addChatMessage({
      id: `user-reply-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: Date.now() / 1000,
    })

    try {
      setSending(true)
      await replyToAgent(projectId, message)
    } catch (err) {
      console.error('Failed to reply:', err)
      addChatMessage({
        id: `err-${Date.now()}`,
        role: 'system',
        content: `回复失败: ${err}`,
        timestamp: Date.now() / 1000,
      })
    } finally {
      setSending(false)
    }
  }, [projectId, addChatMessage, sending])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!draggingRef.current) return
    if (draggingRef.current === 'bottom') {
      const newH = window.innerHeight - e.clientY
      setBottomHeight(Math.max(120, Math.min(newH, window.innerHeight * 0.6)))
    } else if (draggingRef.current === 'right') {
      const newW = window.innerWidth - e.clientX
      setRightWidth(Math.max(280, Math.min(newW, window.innerWidth * 0.5)))
    }
  }, [])

  const handleMouseUp = useCallback(() => {
    draggingRef.current = null
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [])

  const startDrag = useCallback((dir: 'bottom' | 'right') => {
    draggingRef.current = dir
    document.body.style.cursor = dir === 'bottom' ? 'row-resize' : 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  const canSend = !sending && !(running && !waitingForReply)

  return (
    <div
      className="h-screen flex flex-col bg-surface select-none"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <TopToolbar
        projectId={projectId}
        running={running}
        onStart={handleStart}
        onStop={handleStop}
        onReset={handleReset}
        onVersionLoaded={loadCanvas}
      />

      <div className="flex-1 flex flex-col min-h-0">
        {/* 上半: Flow + Detail */}
        <div className="flex-1 flex min-h-0">
          {/* 左: React Flow (支持层级导航) */}
          <div className="flex-1 min-w-0 relative flex flex-col">
            {canvasStack.length > 0 && (
              <div className="px-4 py-1.5 border-b border-border bg-surface flex items-center gap-1 text-xs shrink-0">
                <button onClick={() => setCanvasStack([])} className="text-blue-400 hover:text-blue-300 font-medium">
                  主画布
                </button>
                {canvasStack.map((level, i) => (
                  <span key={level.id} className="flex items-center gap-1">
                    <ChevronRight size={10} className="text-gray-500" />
                    <button
                      onClick={() => setCanvasStack(canvasStack.slice(0, i + 1))}
                      className={i === canvasStack.length - 1 ? 'text-white font-medium' : 'text-blue-400 hover:text-blue-300'}
                    >
                      {level.label}
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="flex-1 min-h-0">
              <AgentFlowCanvas
                nodes={nodes}
                edges={edges}
                setNodes={setNodes}
                setEdges={setEdges}
                parentCanvas={currentParentCanvas}
                onNodeClick={(nodeId) => setSelectedNodeId(nodeId)}
                onNodeDoubleClick={(nodeId) => {
                  const node = nodes.find(n => n.id === nodeId)
                  if (!node) return
                  const type = node.type
                  if (type === 'skillGroupNode' || type === 'subAgentGroupNode' || type === 'mcpGroupNode') {
                    const label = (node.data as Record<string, unknown>)?.label as string || nodeId
                    setCanvasStack(prev => [...prev, { id: nodeId, label }])
                    setSelectedNodeId(null)
                  }
                }}
                onPaneClick={() => setSelectedNodeId(null)}
                onConnect={handleConnect}
                onEdgeDelete={handleEdgeDelete}
                onNodeDragStop={saveNodePosition}
                onNodeCreated={loadCanvas}
              />
            </div>
            <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-black/50 backdrop-blur px-2 py-1 rounded text-[10px]">
              <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-gray-400">{connected ? '已连接' : '未连接'}</span>
            </div>
          </div>

          {/* 右侧拖拽手柄 */}
          <div
            className="w-1 bg-border hover:bg-primary/40 active:bg-primary/60 cursor-col-resize transition-colors shrink-0"
            onMouseDown={() => startDrag('right')}
          />

          {/* 右: Detail Panel */}
          <div style={{ width: rightWidth }} className="shrink-0 bg-surface overflow-hidden">
            <NodeDetailPanel
              selectedNodeId={selectedNodeId}
              nodes={nodes}
              logs={logs}
              onSubAgentCreated={loadCanvas}
            />
          </div>
        </div>

        {/* 底部拖拽手柄 */}
        <div
          className="h-1 bg-border hover:bg-primary/40 active:bg-primary/60 cursor-row-resize transition-colors shrink-0"
          onMouseDown={() => startDrag('bottom')}
        />

        {/* 下半: 对话 + 日志 */}
        <div style={{ height: bottomHeight }} className="shrink-0">
          <BottomPanel
            logs={logs}
            chatMessages={chatMessages}
            waitingForReply={waitingForReply}
            streamingText={streamingText}
            projectId={projectId}
            onSendMessage={handleSendMessage}
            onReply={handleReply}
            connected={connected}
            canSend={canSend}
            sending={sending}
          />
        </div>
      </div>
    </div>
  )
}
