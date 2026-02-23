# 前端 Plan — 画布、面板、交互

## 一、n8n 风格节点编排器

### 1.1 节点类型与组件

| 节点 | 组件 | Handle | 说明 |
|------|------|--------|------|
| Trigger | TriggerNode.tsx | 右: flow-out | Chat Trigger 入口 |
| Agent | AgentNode.tsx | 左右: flow / 底部: tool-out / 顶部: tool-in | 3 彩色 Handle 已简化为统一 tool-out |
| Skill 容器 | SkillGroupNode.tsx | 上: tool-in | 绿色，双击钻入 |
| SubAgent 容器 | SubAgentGroupNode.tsx | 上: tool-in | 紫色 |
| MCP 容器 | McpGroupNode.tsx | 上: tool-in | 橙色 |
| Skill 小节点 | SkillNode.tsx | — | 钻入视图中显示 |

### 1.2 画布交互

- **AgentFlowCanvas.tsx**: ReactFlow 画布，6 种节点，拖拽连线，位置保存
- **双击空白** → 弹出 NodePicker
- **双击容器** → 钻入子画布 (Skill/SubAgent/MCP)
- **NodePicker**: 5 Tab — 搜索 / Agent / Skill / SubAgent / MCP
- **搜索**: 已有节点搜索、定位、删除、添加到画布

### 1.3 层级画布 (canvasStack)

- 主画布: `parent_canvas=null`
- 子画布: `parent_canvas=containerId`，复用 AgentFlowCanvas
- WorkspacePage 维护 `canvasStack`，面包屑导航返回
- 子画布支持: 双击加节点、点击配置、拖拽连线

---

## 二、面板布局与交互

### 2.1 可拖拽调整

- 右侧详情面板: `rightWidth` 可拖拽，min/max 约束
- 底部面板: `bottomHeight` 可拖拽
- 原生 CSS `mousedown/mousemove` 实现 (无 react-resizable-panels)

### 2.2 上传区

- 虚线框: 图片框 + 视频框并排，`accept` 分离 image/video
- 全局拖拽 overlay: 拖文件时显示「释放以上传」
- 删除 ChatPage: `/` 直接进 WorkspacePage

### 2.3 右侧面板 (NodeDetailPanel)

| 节点类型 | 面板内容 |
|----------|----------|
| Agent | Prompt 编辑、Skill 列表、执行模式(串行/并行)、子 Agent 列表 |
| Skill 容器 | 从 config.items 读取 Skill 列表，添加/移除，AI 新建 |
| SubAgent 容器 | 子 Agent 列表、执行模式切换 |
| MCP 容器 | 三 Tab: 状态+重连 / 工具列表 / 配置 |
| Skill 详情 | 四 Tab: 基本信息 / 指令 / 脚本 / 资源 |
| Trigger | Chat Trigger 说明 |

### 2.4 父 Agent 串行/并行

- AgentDetailView 检测是否有子 Agent (`parent_id` 指向当前)
- 有则显示执行模式切换按钮: react(串行) / parallel(并行)

---

## 三、其他前端功能

### 3.1 Skill 创建器

- SkillCreator.tsx: LLM 对话式 UI
- 生成 SKILL.md + scripts/ 结构，保存到文件系统

### 3.2 顶部工具栏 (TopToolbar)

- 运行 / 停止 / 重置
- 保存 (更新当前版本或创建草稿)
- 发布 (新建版本)
- 版本历史下拉: 加载 / 删除

### 3.3 底部面板 (BottomPanel)

- 对话输入 (ChatInput)
- 实时日志流 (LogStream)
- 发送状态锁: running 时禁止重复发送

### 3.4 工具级 WebSocket 事件

- `tool_call_start` / `tool_call_end` — 工具调用状态
- ToolNode 组件: 工具名、描述、调用状态、输入输出预览

---

## 四、数据流

- **useAgentFlow.ts**: 从 Canvas API 加载 nodes/edges，支持 `parentCanvas` 过滤
- **canvasNodeToFlowNode**: 识别 6 种 node_type，映射到对应组件
- **handleConnect / handleEdgeDelete**: 调用 API 后 `loadCanvas()` 刷新

---

## 五、待完善 (P0)

1. 连线交互: Agent tool-out → Skill/SubAgent 确认可连
2. 单击 Skill 容器: 右侧显示 config.items 内容
3. 双击容器: 进入子画布
4. SubAgent 自动变形: Agent→Agent tool 边后 target 变紫色容器
