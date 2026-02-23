import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  BackgroundVariant,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  applyNodeChanges,
  applyEdgeChanges,
  useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useCallback, useMemo, useState, useRef } from 'react'
import { AgentNode } from './nodes/AgentNode'
import { SkillNode } from './nodes/SkillNode'
import { McpNode } from './nodes/McpNode'
import { TriggerNode } from './nodes/TriggerNode'
import { SkillGroupNode } from './nodes/SkillGroupNode'
import { SubAgentGroupNode } from './nodes/SubAgentGroupNode'
import { McpGroupNode } from './nodes/McpGroupNode'
import { NodePicker } from './NodePicker'

interface AgentFlowCanvasProps {
  nodes: Node[]
  edges: Edge[]
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>
  onNodeClick?: (nodeId: string) => void
  onNodeDoubleClick?: (nodeId: string) => void
  onPaneClick?: () => void
  onConnect?: (sourceId: string, targetId: string, sourceHandle: string | null) => void
  onEdgeDelete?: (edgeId: string) => void
  onNodeDragStop?: (nodeId: string, x: number, y: number) => void
  onNodeCreated?: () => void
  parentCanvas?: string | null
}

function FlowCanvas({
  nodes, edges, setNodes, setEdges,
  onNodeClick, onNodeDoubleClick, onPaneClick, onConnect, onEdgeDelete, onNodeDragStop, onNodeCreated, parentCanvas,
}: AgentFlowCanvasProps) {
  const [picker, setPicker] = useState<{ x: number; y: number; canvasX: number; canvasY: number } | null>(null)
  const lastPaneClickTime = useRef(0)
  const { screenToFlowPosition } = useReactFlow()

  const nodeTypes = useMemo(() => ({
    agentNode: AgentNode,
    skillNode: SkillNode,
    mcpNode: McpNode,
    triggerNode: TriggerNode,
    skillGroupNode: SkillGroupNode,
    subAgentGroupNode: SubAgentGroupNode,
    mcpGroupNode: McpGroupNode,
  }), [])

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [setNodes],
  )
  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [setEdges],
  )

  const handleConnect: OnConnect = useCallback((params) => {
    if (params.source && params.target && onConnect) {
      onConnect(params.source, params.target, params.sourceHandle ?? null)
    }
  }, [onConnect])

  const handleEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
    if (edge.data?.dbId && onEdgeDelete) {
      if (confirm('删除此连线？')) {
        onEdgeDelete(edge.id)
      }
    }
  }, [onEdgeDelete])

  const handleNodeDragStop = useCallback((_: React.MouseEvent, node: Node) => {
    onNodeDragStop?.(node.id, node.position.x, node.position.y)
  }, [onNodeDragStop])

  const handlePaneClick = useCallback((event: React.MouseEvent) => {
    const now = Date.now()
    if (now - lastPaneClickTime.current < 400) {
      const flowPos = screenToFlowPosition({ x: event.clientX, y: event.clientY })
      setPicker({ x: event.clientX, y: event.clientY, canvasX: flowPos.x, canvasY: flowPos.y })
    } else {
      setPicker(null)
      onPaneClick?.()
    }
    lastPaneClickTime.current = now
  }, [screenToFlowPosition, onPaneClick])

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onNodeClick={(_, node) => { onNodeClick?.(node.id); setPicker(null) }}
        onNodeDoubleClick={(_, node) => { onNodeDoubleClick?.(node.id) }}
        onEdgeClick={handleEdgeClick}
        onNodeDragStop={handleNodeDragStop}
        onPaneClick={handlePaneClick}
        nodesDraggable
        nodesConnectable
        fitView
        fitViewOptions={{ padding: 0.3 }}
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#3a3a4e" />
        <Controls
          showInteractive={false}
          className="!bg-gray-800 !border-gray-600 !shadow-lg [&>button]:!bg-gray-800 [&>button]:!border-gray-600 [&>button]:!fill-gray-300 [&>button:hover]:!bg-gray-700"
        />
      </ReactFlow>

      {picker && (
        <NodePicker
          x={picker.x} y={picker.y}
          canvasX={picker.canvasX} canvasY={picker.canvasY}
          parentCanvas={parentCanvas ?? undefined}
          onClose={() => setPicker(null)}
          onNodeCreated={() => { setPicker(null); onNodeCreated?.() }}
          onLocateNode={(nodeId) => { setPicker(null); onNodeClick?.(nodeId) }}
          onDeleteNode={() => onNodeCreated?.()}
        />
      )}
    </div>
  )
}

export function AgentFlowCanvas(props: AgentFlowCanvasProps) {
  return (
    <ReactFlowProvider>
      <FlowCanvas {...props} />
    </ReactFlowProvider>
  )
}
