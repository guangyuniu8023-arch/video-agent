export type AgentStatus = 'idle' | 'running' | 'success' | 'error' | 'waiting'
export type ToolCallStatus = 'idle' | 'calling' | 'success' | 'error'

export interface AgentNodeData {
  label: string
  agentType: string
  status: AgentStatus
  selected?: boolean
  progress?: number
  qualityScore?: number
  thumbnail?: string
  duration?: number
  error?: string
  clipsCount?: number
  isSubAgent?: boolean
  parentId?: string
  bypass?: boolean
  onBypassToggle?: (nodeId: string, bypass: boolean) => void
}

export interface SkillNodeData {
  label: string
  skillName: string
  description?: string
}

export interface McpNodeData {
  label: string
  mcpId: string
  status: 'connected' | 'disconnected' | 'error'
  toolCount: number
}

export interface ToolNodeData {
  name: string
  description: string
  status: ToolCallStatus
  input?: string
  output?: string
  callCount: number
}

export interface ToolCallInfo {
  toolName: string
  status: ToolCallStatus
  input?: string
  output?: string
  startTime?: number
  endTime?: number
}

export interface WSEvent {
  type: string
  agent?: string
  status?: AgentStatus
  edge_id?: string
  active?: boolean
  message?: string
  timestamp?: number
  data?: Record<string, unknown>
  score?: number
  thumbnail_url?: string
  error?: string
  question?: string
  role?: string
  content?: string
  token?: string
  tool?: string
  input?: string
  output?: string
}

export interface LogEntry {
  agent: string
  message: string
  timestamp: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  attachments?: UploadedFile[]
}

export interface UploadedFile {
  filename: string
  originalName: string
  url: string
  size: number
  contentType: string
}
