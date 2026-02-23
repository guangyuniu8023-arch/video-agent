# 前端 Plan — 画布、面板、交互

## 一、路由 (App.tsx)

- `/workspace`、`/workspace/:projectId` → WorkspacePage
- `*` → 重定向到 `/workspace`
- 无 ChatPage

---

## 二、n8n 风格节点编排器

### 2.1 节点类型与组件

| 节点 | 组件 | Handle | 说明 |
|------|------|--------|------|
| Trigger | TriggerNode.tsx | 右: flow-out | Chat Trigger 入口 |
| Agent | AgentNode.tsx | 左: flow-in / 右: flow-out / 顶: tool-in / 底: tool-out | 统一 tool-out |
| Skill 容器 | SkillGroupNode.tsx | 上: tool-in | 绿色，双击钻入 |
| SubAgent 容器 | SubAgentGroupNode.tsx | 上: tool-in | 紫色 |
| MCP 容器 | McpGroupNode.tsx | 上: tool-in | 橙色 |
| Skill 小节点 | SkillNode.tsx | — | 钻入视图中显示 |

### 2.2 画布交互

- **AgentFlowCanvas.tsx**: ReactFlow 画布，6 种节点，拖拽连线，位置保存
- **双击空白** → 弹出 NodePicker
- **双击容器** (skillGroupNode/subAgentGroupNode/mcpGroupNode) → push canvasStack，钻入子画布
- **NodePicker**: 4 Tab — 搜索 / Agent / Skill / MCP（无 SubAgent 单独 Tab，SubAgent 由 Agent 连线后自动变）
- **搜索**: 已有节点搜索、定位、删除、添加到画布

### 2.3 层级画布 (canvasStack)

- 主画布: `parentCanvas=null`
- 子画布: `parentCanvas=containerId`，复用 AgentFlowCanvas，传 `parentCanvas` 过滤
- WorkspacePage 维护 `canvasStack`，面包屑「主画布 > 容器名」导航返回
- 子画布支持: 双击加节点、点击配置、拖拽连线

---

## 三、面板布局与交互

### 3.1 可拖拽调整

- 右侧详情面板: `rightWidth` 可拖拽，min/max 约束
- 底部面板: `bottomHeight` 可拖拽
- 原生 CSS `mousedown/mousemove` 实现 (无 react-resizable-panels)

### 3.2 上传区 (BottomPanel 内)

- 虚线框: 图片框 + 视频框并排，`accept` 分离 image/video
- 全局拖拽 overlay: 拖文件时显示「释放以上传」

### 3.3 右侧面板 (NodeDetailPanel)

按 `parseCanvasId(selectedNodeId)` 解析：`id` 格式为 `type:refId`（如 agent:planner、skillgroup:xxx）。

| 节点类型 (nodeType) | 面板内容 |
|---------------------|----------|
| trigger | Chat Trigger 说明 |
| agent (refId=router) | RouterDetailView: Prompt + 路由规则 + 日志 |
| agent (refId=quality_gate) | QualityGateDetail |
| agent (refId=human_feedback) | HumanFeedbackDetail |
| agent (其他) | AgentDetailView: Prompt、Skill、执行模式、子 Agent |
| skillgroup | SkillGroupPanel: 从 /api/admin/canvas/nodes 取 config.items，添加/移除，AI 新建 |
| subagentgroup | SubAgentGroupPanel |
| mcpgroup | McpDetailView: 三 Tab 状态/工具/配置 |
| skill | SkillDetailView: 四 Tab 基本信息/指令/脚本/资源 |
| mcp | McpDetailView |
| 无选中 | ProjectOverview: 项目概览 |

### 3.4 父 Agent 串行/并行

- AgentDetailView 检测是否有子 Agent (`parent_id` 指向当前)
- 有则显示执行模式切换: react(串行) / parallel(并行)

---

## 四、其他前端功能

### 4.1 Skill 创建器 (SkillCreator.tsx)

- LLM 对话式 UI
- 生成 SKILL.md + scripts/ 结构，保存到文件系统

### 4.2 顶部工具栏 (TopToolbar)

- 运行 / 停止 / 重置
- 保存: POST /api/v1/save
- 发布: POST /api/v1/publish
- 版本历史: GET /api/v1/versions，加载 POST /api/v1/versions/{id}/load，删除 DELETE /api/v1/versions/{id}

### 4.3 底部面板 (BottomPanel)

- 两 Tab: chat / logs
- 对话输入、等待回复时 onReply
- 实时日志流
- 虚线框上传区 (图片/视频)
- 发送状态锁: `sending`、`canSend`，running 时禁止重复发送

### 4.4 工具级 WebSocket 事件

- `tool_call_start` / `tool_call_end` — 工具调用状态
- ToolNode 组件: 工具名、描述、调用状态、输入输出预览

---

## 五、API 调用 (api.ts, BASE_URL='/api')

| 模块 | 路径 | 说明 |
|------|------|------|
| Chat | /api/chat/start, reply, status, stop, upload | 工作流对话 |
| Admin | /api/admin/agents, canvas/nodes, canvas/edges, skills, routes | Agent/画布/Skill/路由 |
| 版本 | /api/v1/save, publish, versions | 保存/发布/版本列表 |

---

## 六、数据流

- **useAgentFlow.ts**: 从 /api/admin/canvas/nodes、edges 加载，支持 `parentCanvas` 过滤 (parent_canvas 匹配)
- **canvasNodeToFlowNode**: 识别 agent/skill/mcp/trigger/skillgroup/subagentgroup/mcpgroup，映射到对应 Flow 组件
- **handleConnect / handleEdgeDelete**: 调用 API 后 `loadCanvas()` 刷新

---

## 七、未使用组件 (遗留)

- ContainerDrilldownView.tsx
- SkillDrilldownView.tsx
- AgentSubFlowView.tsx

当前子画布由 AgentFlowCanvas + parentCanvas 实现，上述组件未在 WorkspacePage 引用。

---

## 八、待完善 (P0)

1. 连线交互: Agent tool-out → Skill/SubAgent 确认可连
2. 单击 Skill 容器: 右侧显示 config.items 内容
3. 双击容器: 进入子画布
4. SubAgent 自动变形: Agent→Agent tool 边后 target 变紫色容器
