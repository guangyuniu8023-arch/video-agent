const BASE_URL = '/api'

// ── 类型定义 ──

interface StartResponse {
  project_id: string
  status: string
  message: string
}

interface ReplyResponse {
  project_id: string
  status: string
  message: string
}

interface UploadResponse {
  filename: string
  original_name: string
  path: string
  url: string
  size: number
  content_type: string
}

interface WorkflowStatus {
  project_id: string
  running: boolean
  cancelled?: boolean
  waiting_for_reply?: boolean
  message?: string
}

// ── Chat API ──

export async function startWorkflow(
  message: string,
  projectId?: string,
  uploadedAssets: Record<string, unknown>[] = [],
): Promise<StartResponse> {
  const res = await fetch(`${BASE_URL}/chat/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      project_id: projectId,
      uploaded_assets: uploadedAssets,
    }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function replyToAgent(
  projectId: string,
  message: string,
): Promise<ReplyResponse> {
  const res = await fetch(`${BASE_URL}/chat/reply/${projectId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function uploadFile(
  file: File,
  projectId?: string,
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (projectId) {
    formData.append('project_id', projectId)
  }
  const res = await fetch(`${BASE_URL}/chat/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function getWorkflowStatus(projectId: string): Promise<WorkflowStatus> {
  const res = await fetch(`${BASE_URL}/chat/status/${projectId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function stopWorkflow(projectId: string) {
  const res = await fetch(`${BASE_URL}/chat/stop/${projectId}`, { method: 'POST' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Admin: Agent 管理 ──

export interface AgentInfo {
  id: string
  name: string
  description: string
  agent_type?: string
  parent_id?: string | null
  system_prompt?: string
  prompt_length?: number
  available_tools?: string[]
  children?: AgentInfo[]
}

export async function fetchAgents(): Promise<{ agents: AgentInfo[] }> {
  const res = await fetch(`${BASE_URL}/admin/agents`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchAgentPrompt(agentId: string): Promise<{
  prompt: string
  is_custom: boolean
  tools: string[]
  version?: number
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/prompt`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateAgentPrompt(agentId: string, prompt: string): Promise<{
  message: string
  version?: number
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/prompt`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function resetAgentPrompt(agentId: string): Promise<{ prompt: string }> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/prompt/reset`, { method: 'POST' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ── Admin: Prompt 版本历史 ──

export async function fetchAgentVersions(agentId: string): Promise<{
  agent_id: string
  versions: Array<{
    version: number
    system_prompt: string
    available_tools: string[]
    is_active: boolean
    editor: string
    created_at: string
  }>
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/versions`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function rollbackAgentPrompt(agentId: string, version: number): Promise<{
  agent_id: string
  version: number
  rolled_back_to: number
  system_prompt: string
  available_tools: string[]
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ version }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

// ── Admin: 工具管理 ──

export interface ToolEntry {
  name: string
  type: 'skill' | 'agent' | 'unknown'
  title: string
  description: string
  trigger?: string[]
  tools?: string[]
}

export async function fetchAgentTools(agentId: string): Promise<{
  agent_id: string
  current_tools: string[]
  tools: ToolEntry[]
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/tools`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchSkillContent(skillName: string): Promise<{
  skill_name: string
  content: string
  path: string
}> {
  const res = await fetch(`${BASE_URL}/admin/skills/${skillName}/content`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateSkillContent(skillName: string, content: string): Promise<{
  skill_name: string
  message: string
  tools: string[]
}> {
  const res = await fetch(`${BASE_URL}/admin/skills/${skillName}/content`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function createSkill(data: {
  name: string; description?: string; tools?: string[]; tags?: string[]
}): Promise<{ skill_name: string; message: string }> {
  const res = await fetch(`${BASE_URL}/admin/skills`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteSkill(skillName: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/skills/${skillName}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

// ── Admin: Agent CRUD ──

export async function createAgent(data: {
  id: string; name: string; description?: string; agent_type?: string;
  parent_id?: string; system_prompt?: string; available_tools?: string[];
}): Promise<{ id: string; message: string }> {
  const res = await fetch(`${BASE_URL}/admin/agents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function updateAgent(agentId: string, data: {
  name?: string; description?: string; system_prompt?: string;
  available_tools?: string[]; llm_config?: Record<string, unknown>; enabled?: boolean;
  execution_mode?: string;
} & Record<string, unknown>): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteAgent(agentId: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function fetchAgentChildren(agentId: string): Promise<{
  parent_id: string
  children: Array<{ id: string; name: string; description: string; available_tools: string[] }>
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/children`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function updateAgentTools(agentId: string, tools: string[]): Promise<{
  message: string
  version?: number
}> {
  const res = await fetch(`${BASE_URL}/admin/agents/${agentId}/tools`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tools }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

// ── Admin: Canvas (画布节点/边) ──

export interface CanvasNodeData {
  id: string
  node_type: string
  ref_id: string
  position_x: number
  position_y: number
  config?: Record<string, unknown>
  parent_canvas?: string | null
}

export interface CanvasEdgeData {
  id: number
  source_id: string
  target_id: string
  edge_type: 'flow' | 'tool'
}

export async function fetchCanvasNodes(): Promise<{ nodes: CanvasNodeData[] }> {
  const res = await fetch(`${BASE_URL}/admin/canvas/nodes`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function fetchCanvasEdges(): Promise<{ edges: CanvasEdgeData[] }> {
  const res = await fetch(`${BASE_URL}/admin/canvas/edges`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createCanvasNode(data: {
  id: string; node_type: string; ref_id: string; position_x: number; position_y: number;
  parent_canvas?: string; config?: Record<string, unknown>
} & Record<string, unknown>): Promise<CanvasNodeData> {
  const res = await fetch(`${BASE_URL}/admin/canvas/nodes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function updateCanvasNodePosition(nodeId: string, position_x: number, position_y: number): Promise<CanvasNodeData> {
  const res = await fetch(`${BASE_URL}/admin/canvas/nodes/${encodeURIComponent(nodeId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ position_x, position_y }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteCanvasNode(nodeId: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/canvas/nodes/${encodeURIComponent(nodeId)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function createCanvasEdge(data: {
  source_id: string; target_id: string; edge_type: string
}): Promise<CanvasEdgeData> {
  const res = await fetch(`${BASE_URL}/admin/canvas/edges`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteCanvasEdge(edgeId: number): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/canvas/edges/${edgeId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

// ── Admin: 路由规则管理 ──

interface RoutingRule {
  id: number
  name: string
  description: string
  priority: number
  enabled: boolean
  target_type: string
  target_skill: string | null
  skip_agents: string[]
  match_description: string
  created_at: string
  updated_at: string
}

export async function fetchRoutingRules(): Promise<{ rules: RoutingRule[] }> {
  const res = await fetch(`${BASE_URL}/admin/routes`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createRoutingRule(data: Partial<RoutingRule>): Promise<RoutingRule> {
  const res = await fetch(`${BASE_URL}/admin/routes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function updateRoutingRule(ruleId: number, data: Partial<RoutingRule>): Promise<RoutingRule> {
  const res = await fetch(`${BASE_URL}/admin/routes/${ruleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function toggleRoutingRule(ruleId: number, enabled: boolean): Promise<RoutingRule> {
  const res = await fetch(`${BASE_URL}/admin/routes/${ruleId}/toggle`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function reorderRoutingRules(ruleIds: number[]): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/routes/reorder`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rule_ids: ruleIds }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}

export async function deleteRoutingRule(ruleId: number): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/admin/routes/${ruleId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
  return res.json()
}
