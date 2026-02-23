# Video Agent 系统 — 开发进度

## 项目位置
`/Users/bytedance/video-agent/`

## 技术栈
- 后端: Python 3.12 / FastAPI / LangGraph / LangChain / SQLAlchemy / PostgreSQL / Redis
- 前端: React 18 / TypeScript / Vite / @xyflow/react (React Flow) / TailwindCSS
- 视频生成: Seedance 2.0 (火山方舟 SDK)
- 视频编辑: FFmpeg
- VLM 评估: GPT-4o / 豆包多模态

## 启动方式
```bash
# 基础设施
docker-compose up -d  # PostgreSQL + Redis

# 后端
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm run dev

# 回归测试
cd backend && python scripts/regression_test.py
```

## Plan 文档位置
- 主 Plan: `progress/plans/01_主Plan_视频生成Agent系统.md`
- 前端 Plan: `progress/plans/02_前端Plan.md`
- 后端 Plan: `progress/plans/03_后端Plan.md`
- 开发规范 Skill: `~/.cursor/skills/feature-development/SKILL.md`

---

## 后端状态: 基本完成 ✓

### 已完成的后端功能

| 模块 | 文件 | 状态 |
|------|------|------|
| DB 模型 | `models/database.py` | ✓ CanvasNode(含config/parent_canvas), CanvasEdge, McpServer, AgentConfig, WorkflowVersion |
| 画布 API | `api/canvas.py` | ✓ 节点/边 CRUD, 连线副作用(available_tools同步, parent_id自动设置/清除), 容器config更新 |
| Agent API | `api/admin.py` | ✓ Agent/Skill/路由规则 CRUD, Skill文件管理(scripts/references/assets) |
| MCP API | `api/mcp.py` | ✓ MCP服务 CRUD + 重连 + 工具列表 |
| Video API | `api/video_api.py` | ✓ 外部调用接口 (generate/status/result/cancel) |
| 版本管理 | `api/publish.py` | ✓ 发布/保存/加载/删除版本, 快照只含画布上的Agent |
| Skill 创建器 | `api/skill_creator.py` | ✓ LLM 对话生成 Skill |
| MCP 客户端 | `services/mcp_client.py` | ✓ SSE/stdio 连接, 工具发现 |
| GenericAgent | `agents/generic.py` | ✓ react/parallel 执行模式, Skill+SubAgent+MCP 工具解析 |
| 动态工作流 | `graph/workflow.py` | ✓ 从 canvas_edges flow 边动态构建 LangGraph |
| Skill 自包含 | `skills/*/scripts/tool.py` | ✓ 14个Skill全部自包含, scripts/自动注册到TOOL_REGISTRY |
| MCP Server | `mcp_server.py` | ✓ 独立进程, SSE/stdio, generate_video + get_video_status |

### 后端回归测试: 35/35 通过

---

## 前端状态: 需要修复 ✗

### 已有的前端组件

| 组件 | 文件 | 状态 |
|------|------|------|
| 主页面 | `WorkspacePage.tsx` | ⚠️ 基本可用但有层级画布问题 |
| 画布 | `AgentFlowCanvas.tsx` | ⚠️ 主画布可用, 需要完善双击/连线交互 |
| Agent 节点 | `nodes/AgentNode.tsx` | ⚠️ Handle 布局需优化 |
| Skill 节点 | `nodes/SkillNode.tsx` | ✓ |
| MCP 节点 | `nodes/McpNode.tsx` | ✓ |
| Trigger 节点 | `nodes/TriggerNode.tsx` | ✓ |
| Skill 容器 | `nodes/SkillGroupNode.tsx` | ✓ 组件可用 |
| SubAgent 容器 | `nodes/SubAgentGroupNode.tsx` | ✓ 组件可用 |
| MCP 容器 | `nodes/McpGroupNode.tsx` | ✓ 组件可用 |
| NodePicker | `NodePicker.tsx` | ⚠️ 基本可用, 需要验证子画布创建 |
| 右侧面板 | `NodeDetailPanel.tsx` | ⚠️ 面板路由需要验证各节点类型 |
| Skill 容器面板 | NodeDetailPanel 内 | ⚠️ 改成了从 config.items 读取, 需验证 |
| Skill 详情面板 | NodeDetailPanel 内 | ✓ 四 Tab (基本信息/指令/脚本/资源) |
| Skill 创建器 | `SkillCreator.tsx` | ✓ LLM 对话式 |
| MCP 面板 | NodeDetailPanel 内 | ✓ 三 Tab (状态/工具/配置) |
| 数据加载 | `useAgentFlow.ts` | ⚠️ 支持 parentCanvas 过滤, 需验证 |
| 顶部工具栏 | `TopToolbar.tsx` | ✓ 运行/保存/版本历史/发布 |
| 底部面板 | `BottomPanel.tsx` | ✓ 对话+日志 |

### 前端需要修复/完善的问题

#### P0: 核心交互问题
1. **连线交互** — 从 Agent 底部 Handle 拖线到 Skill 容器/其他 Agent, 需要确认能正常连上
2. **单击 Skill 容器** — 右侧面板需要正确显示容器内的 Skill 列表 (从 config.items 读取)
3. **双击容器进入** — Skill 容器/SubAgent 容器/MCP 容器双击进入内部视图
4. **SubAgent 自动变形** — Agent→Agent tool 边连线后, target 自动变成紫色 SubAgent 容器

#### P1: 子画布功能
5. **子画布完整交互** — 双击空白添加节点, 点击节点右侧面板, 连线 (需要传 parentCanvas)
6. **面包屑导航** — 主画布 > 容器名, 支持多级返回
7. **子画布节点创建** — NodePicker 创建节点时带 parent_canvas 参数

#### P2: 面板功能
8. **父 Agent 串行/并行按钮** — 有子 Agent 时显示执行模式切换
9. **Skill 容器面板** — 从 config.items 读取内容, 添加/移除 Skill, AI 新建
10. **SubAgent 容器面板** — 子 Agent 列表

#### 建议的修复策略
- **不要推翻重来** — 当前组件都在, 只是组合方式和数据流有问题
- **从主画布开始验证** — 先确保主画布的节点显示、连线、点击面板都正常
- **再验证容器交互** — 双击进入、面板内容
- **最后做子画布** — 确保 parentCanvas 过滤和 NodePicker 传参正确
- **每修一个功能跑一次回归测试**

---

## 设计要点 (给下次开发的上下文)

### 节点类型
- **agent**: LLM/VLM Agent, 左右 flow Handle + 底部 tool-out Handle + 顶部 tool-in Handle
- **skill**: 独立 Skill 工具节点 (绿色)
- **mcp**: 独立 MCP 服务节点 (橙色)
- **trigger**: Chat Trigger 入口 (蓝绿色)
- **skillgroup**: Skill 容器, config.items 存 skill name 列表 (绿色)
- **subagentgroup**: SubAgent 容器 (紫色) — Agent 被 tool 边连接后自动变成此类型
- **mcpgroup**: MCP 容器 (橙色)

### 核心设计: 独立模块 + 连线即关系
- 所有节点创建后都是独立模块, 不绑定特定 Agent
- 画布连线建立关系 (tool 边 → available_tools 同步)
- 断线解除关系
- Agent→Agent tool 边 → target 自动设 parent_id, 变成 SubAgent
- 容器通过 config.items 存储内容, 连线时整体加载

### canvas_nodes 关键字段
- `config`: JSON, 容器用 {"items": [...]} 存储内容
- `parent_canvas`: 所属画布 ID, null=主画布, 非null=嵌套在某个容器里

### 回归测试
```bash
cd backend && python scripts/regression_test.py  # 35 项检查
```

### 开发规范
参考 `~/.cursor/skills/feature-development/SKILL.md`:
- 增量修改不推翻重做
- 改动前后都跑回归测试
- Plan 用 StrReplace 增量修改不用 Write 覆盖
