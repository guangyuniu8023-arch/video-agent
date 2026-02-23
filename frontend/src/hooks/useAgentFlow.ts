import { useState, useCallback, useMemo, useEffect, useRef } from 'react'
import { type Node, type Edge, MarkerType } from '@xyflow/react'
import { useWebSocket } from './useWebSocket'
import {
  fetchCanvasNodes, fetchCanvasEdges, fetchAgents,
  createCanvasEdge, deleteCanvasEdge, updateCanvasNodePosition,
} from '@/services/api'
import type { AgentNodeData, AgentStatus, WSEvent, LogEntry, ChatMessage, ToolCallInfo } from '@/types'

function canvasNodeToFlowNode(
  cn: { id: string; node_type: string; ref_id: string; position_x: number; position_y: number },
  agentMap: Map<string, Record<string, unknown>>,
): Node | null {
  if (cn.node_type === 'agent') {
    const agentInfo = agentMap.get(cn.ref_id)
    const isSubAgent = !!(agentInfo?.parent_id)

    if (isSubAgent) {
      return {
        id: cn.id,
        type: 'subAgentGroupNode',
        position: { x: cn.position_x, y: cn.position_y },
        data: {
          label: (agentInfo?.name as string) || cn.ref_id,
          agentId: cn.ref_id,
          count: ((agentInfo?.available_tools as string[]) || []).length,
        },
      }
    }

    return {
      id: cn.id,
      type: 'agentNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: {
        label: (agentInfo?.name as string) || cn.ref_id,
        agentType: (agentInfo?.description as string) || 'Agent',
        status: 'idle',
        isSubAgent: false,
        bypass: agentInfo?.bypass === true,
      } as AgentNodeData,
    }
  }

  if (cn.node_type === 'skill') {
    return {
      id: cn.id,
      type: 'skillNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: { label: cn.ref_id, skillName: cn.ref_id },
    }
  }

  if (cn.node_type === 'mcp') {
    return {
      id: cn.id,
      type: 'mcpNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: { label: cn.ref_id, mcpId: cn.ref_id, status: 'disconnected', toolCount: 0 },
    }
  }

  if (cn.node_type === 'trigger') {
    return {
      id: cn.id,
      type: 'triggerNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: { label: cn.ref_id === 'chat' ? 'Chat Trigger' : cn.ref_id, status: 'idle' },
    }
  }

  if (cn.node_type === 'skillgroup') {
    const items = ((cn as Record<string, unknown>).config as Record<string, unknown>)?.items as string[] || []
    return {
      id: cn.id,
      type: 'skillGroupNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: { label: 'Skill', agentId: cn.ref_id, count: items.length },
    }
  }

  if (cn.node_type === 'subagentgroup') {
    const items = ((cn as Record<string, unknown>).config as Record<string, unknown>)?.items as string[] || []
    return {
      id: cn.id,
      type: 'subAgentGroupNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: { label: 'Sub-Agent', agentId: cn.ref_id, count: items.length },
    }
  }

  if (cn.node_type === 'mcpgroup') {
    const items = ((cn as Record<string, unknown>).config as Record<string, unknown>)?.items as string[] || []
    return {
      id: cn.id,
      type: 'mcpGroupNode',
      position: { x: cn.position_x, y: cn.position_y },
      data: { label: 'MCP', agentId: cn.ref_id, count: items.length },
    }
  }

  return null
}

const EDGE_COLORS: Record<string, string> = {
  skill: '#22c55e',
  skillgroup: '#22c55e',
  agent: '#6366f1',
  subagentgroup: '#6366f1',
  mcp: '#f97316',
  mcpgroup: '#f97316',
}

function canvasEdgeToFlowEdge(
  ce: { id: number; source_id: string; target_id: string; edge_type: string },
  nodeTypeMap: Map<string, string>,
): Edge {
  const isFlow = ce.edge_type === 'flow'
  const targetType = nodeTypeMap.get(ce.target_id) || ''
  const color = isFlow ? '#6b7280' : (EDGE_COLORS[targetType] || '#6366f1')

  return {
    id: `ce-${ce.id}`,
    source: ce.source_id,
    target: ce.target_id,
    sourceHandle: isFlow ? 'flow-out' : 'tool-out',
    targetHandle: isFlow ? 'flow-in' : 'tool-in',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, color },
    style: {
      stroke: color,
      strokeWidth: isFlow ? 2 : 1.5,
      ...(isFlow ? {} : { strokeDasharray: '4 4' }),
    },
    data: { dbId: ce.id, edgeType: ce.edge_type },
  }
}

export function useAgentFlow(projectId: string | null, parentCanvas: string | null = null) {
  const [nodes, setNodes] = useState<Node[]>([])
  const [edges, setEdges] = useState<Edge[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [waitingForReply, setWaitingForReply] = useState(false)
  const [streamingText, setStreamingText] = useState<{ agent: string; content: string } | null>(null)
  const [toolCalls, setToolCalls] = useState<Record<string, ToolCallInfo[]>>({})
  const positionSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const updateNodeStatus = useCallback((agentId: string, status: AgentStatus, extra?: Record<string, unknown>) => {
    const canvasId = `agent:${agentId}`
    setNodes(prev => prev.map(node => {
      if (node.id !== canvasId) return node
      return { ...node, data: { ...node.data, status, ...(extra?.error ? { error: String(extra.error) } : {}), ...(extra?.data && typeof extra.data === 'object' ? extra.data as Partial<AgentNodeData> : {}) } }
    }))
  }, [])

  const updateEdgeAnimation = useCallback((edgeId: string, active: boolean) => {
    setEdges(prev => prev.map(edge => edge.id !== edgeId ? edge : { ...edge, animated: active }))
  }, [])

  const appendLog = useCallback((entry: LogEntry) => { setLogs(prev => [...prev, entry]) }, [])
  const addChatMessage = useCallback((msg: ChatMessage) => { setChatMessages(prev => [...prev, msg]) }, [])

  const onMessage = useCallback((event: WSEvent) => {
    switch (event.type) {
      case 'agent_status':
        if (event.agent && event.status) {
          updateNodeStatus(event.agent, event.status, event)
          if (event.agent === 'human_feedback' && event.status === 'waiting') setWaitingForReply(true)
          else if (event.agent === 'human_feedback' && event.status === 'success') setWaitingForReply(false)
        }
        break
      case 'edge_active':
        if (event.edge_id !== undefined && event.active !== undefined) updateEdgeAnimation(event.edge_id, event.active)
        break
      case 'log_entry':
        if (event.agent && event.message) appendLog({ agent: event.agent, message: event.message, timestamp: event.timestamp ?? Date.now() / 1000 })
        break
      case 'quality_score':
        updateNodeStatus('quality_gate', 'success', { data: { qualityScore: event.score } })
        break
      case 'video_generated':
        updateNodeStatus('producer', 'success', { data: { thumbnail: event.thumbnail_url } })
        break
      case 'clarification_needed':
        setWaitingForReply(true)
        if (event.question) addChatMessage({ id: `agent-${Date.now()}`, role: 'assistant', content: event.question, timestamp: Date.now() / 1000 })
        break
      case 'chat_message':
        if (event.role && event.content) addChatMessage({ id: `msg-${Date.now()}`, role: event.role as 'user' | 'assistant', content: event.content, timestamp: Date.now() / 1000 })
        break
      case 'llm_stream_start':
        if (event.agent) setStreamingText(prev => prev?.agent === event.agent ? prev : { agent: event.agent!, content: '' })
        break
      case 'llm_token':
        if (event.agent && event.token) setStreamingText(prev => ({ agent: event.agent!, content: (prev?.agent === event.agent ? prev.content : '') + event.token! }))
        break
      case 'llm_stream_end':
        setStreamingText(null)
        break
      case 'tool_call_start':
        if (event.agent && event.tool) {
          setToolCalls(prev => {
            const calls = [...(prev[event.agent!] ?? [])]
            if (calls.some(c => c.toolName === event.tool && c.status === 'calling')) return prev
            calls.push({ toolName: event.tool!, status: 'calling', input: event.input, startTime: event.timestamp })
            return { ...prev, [event.agent!]: calls }
          })
        }
        break
      case 'tool_call_end':
        if (event.agent && event.tool) {
          setToolCalls(prev => {
            const calls = [...(prev[event.agent!] ?? [])]
            const idx = calls.findLastIndex(c => c.toolName === event.tool && c.status === 'calling')
            if (idx >= 0) calls[idx] = { ...calls[idx], status: 'success', output: event.output, endTime: event.timestamp }
            return { ...prev, [event.agent!]: calls }
          })
        }
        break
    }
  }, [updateNodeStatus, updateEdgeAnimation, appendLog, addChatMessage])

  const handleBypassToggle = useCallback(async (nodeId: string, bypass: boolean) => {
    const refId = nodeId.replace('agent:', '')
    try {
      await fetch(`/api/admin/agents/${refId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ bypass }) })
      setNodes(prev => prev.map(n => n.id !== nodeId ? n : { ...n, data: { ...n.data, bypass } }))
    } catch (err) { console.error('Failed to toggle bypass:', err) }
  }, [])

  const loadCanvas = useCallback(async () => {
    try {
      const [canvasData, edgeData, agentsData] = await Promise.all([
        fetchCanvasNodes(), fetchCanvasEdges(), fetchAgents(),
      ])

      const agentMap = new Map<string, Record<string, unknown>>()
      for (const a of (agentsData.agents || [])) {
        agentMap.set(a.id, a as unknown as Record<string, unknown>)
        for (const child of (a.children || [])) {
          agentMap.set(child.id, { ...child, parent_id: a.id } as unknown as Record<string, unknown>)
        }
      }

      const filteredNodes = canvasData.nodes.filter(cn => {
        const pc = cn.parent_canvas ?? null
        return pc === parentCanvas
      })

      const filteredNodeIds = new Set(filteredNodes.map(n => n.id))

      const nodeTypeMap = new Map<string, string>()
      for (const cn of canvasData.nodes) nodeTypeMap.set(cn.id, cn.node_type)

      const flowNodes: Node[] = []
      for (const cn of filteredNodes) {
        const node = canvasNodeToFlowNode(cn, agentMap)
        if (node) {
          if (node.type === 'agentNode') (node.data as AgentNodeData).onBypassToggle = handleBypassToggle
          flowNodes.push(node)
        }
      }

      const filteredEdges = edgeData.edges.filter(e =>
        filteredNodeIds.has(e.source_id) && filteredNodeIds.has(e.target_id)
      )

      setNodes(flowNodes)
      setEdges(filteredEdges.map(e => canvasEdgeToFlowEdge(e, nodeTypeMap)))
    } catch (err) { console.error('Failed to load canvas:', err) }
  }, [handleBypassToggle, parentCanvas])

  useEffect(() => { loadCanvas() }, [loadCanvas])

  const handleConnect = useCallback(async (sourceId: string, targetId: string, sourceHandle: string | null) => {
    const edgeType = sourceHandle === 'flow-out' ? 'flow' : 'tool'
    try {
      await createCanvasEdge({ source_id: sourceId, target_id: targetId, edge_type: edgeType })
      loadCanvas()
    } catch (err) { console.error('Failed to create edge:', err) }
  }, [loadCanvas])

  const handleEdgeDelete = useCallback(async (flowEdgeId: string) => {
    const edge = edges.find(e => e.id === flowEdgeId)
    if (!edge?.data?.dbId) return
    try {
      await deleteCanvasEdge(edge.data.dbId as number)
      loadCanvas()
    } catch (err) { console.error('Failed to delete edge:', err) }
  }, [edges, loadCanvas])

  const saveNodePosition = useCallback((nodeId: string, x: number, y: number) => {
    if (positionSaveTimer.current) clearTimeout(positionSaveTimer.current)
    positionSaveTimer.current = setTimeout(() => {
      updateCanvasNodePosition(nodeId, x, y).catch(err => console.error('Failed to save position:', err))
    }, 500)
  }, [])

  const { connected, send } = useWebSocket({ projectId, onMessage })

  const resetFlow = useCallback(() => {
    setLogs([]); setChatMessages([]); setWaitingForReply(false); setStreamingText(null); setToolCalls({})
    loadCanvas()
  }, [loadCanvas])

  return useMemo(() => ({
    nodes, edges, logs, chatMessages, waitingForReply, streamingText,
    connected, toolCalls, send, setNodes, setEdges,
    addChatMessage, resetFlow, loadCanvas,
    handleConnect, handleEdgeDelete, saveNodePosition,
  }), [
    nodes, edges, logs, chatMessages, waitingForReply, streamingText,
    connected, toolCalls, send, setNodes, setEdges,
    addChatMessage, resetFlow, loadCanvas,
    handleConnect, handleEdgeDelete, saveNodePosition,
  ])
}
