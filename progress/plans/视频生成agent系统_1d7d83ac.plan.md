---
name: 视频生成Agent系统
overview: Multi-Agent 视频生成系统。n8n 风格可视化节点编排器 + LLM 对话式 Skill 创建器 + 动态 LangGraph + MCP 集成。三种外部调用方式 (REST API / MCP Server / LangGraph RemoteGraph)。
todos:
  - id: done-core
    content: "已完成: 核心系统 + n8n 编排器 + Skill 自包含 + MCP + 外部 API + 发布"
    status: completed
  - id: e2e-test
    content: "待执行: 端到端调通测试 + 最佳实践文档"
    status: pending
isProject: false
---

# 视频生成 Agent 系统 — 完整 Plan

## 一、项目概述

基于 LLM/VLM 驱动的 Multi-Agent 视频生成系统。

**核心能力**: 用户描述视频需求 → Agent 自动规划分镜 → 调用视频生成 API → 后期合成 → 质量评估 → 输出最终视频。

**调试面板**: n8n 风格的可视化节点编排器，支持拖拽连线自由组合工作流。

**外部调用**: 调试完成后发布为版本，通过 REST API / MCP / LangGraph RemoteGraph 供外部系统调用。

## 二、子 Plan 索引


| Plan         | 文件                                                                   | 状态          |
| ------------ | -------------------------------------------------------------------- | ----------- |
| n8n 风格节点编排器  | [n8n_风格节点编排器_0fb856c6.plan.md](n8n_风格节点编排器_0fb856c6.plan.md)         | 已完成         |
| Skill 自包含+搜索 | [skill_自动注册+代码可见_c9188aab.plan.md](skill_自动注册+代码可见_c9188aab.plan.md) | 已完成         |
| 可编辑子图 (废弃)   | [可编辑子图_自由连线_a7c3d421.plan.md](可编辑子图_自由连线_a7c3d421.plan.md)           | 已被 n8n 方案替代 |


## 三、技术栈


| 层        | 技术                                 |
| -------- | ---------------------------------- |
| 后端框架     | Python 3.12 / FastAPI / Uvicorn    |
| Agent 编排 | LangGraph (StateGraph, 动态构建)       |
| LLM 调用   | LangChain + ChatOpenAI (豆包/GPT-4o) |
| 数据库      | PostgreSQL (SQLAlchemy async)      |
| 缓存       | Redis (Prompt 版本缓存)                |
| 前端框架     | React 18 + TypeScript + Vite       |
| 流程图      | @xyflow/react (React Flow)         |
| UI 组件    | TailwindCSS + 自定义组件                |
| 视频生成     | Seedance 2.0 (火山方舟 SDK)            |
| 视频编辑     | FFmpeg (本地命令行)                     |
| VLM 评估   | GPT-4o / 豆包多模态                     |
| MCP      | Model Context Protocol (SSE/stdio) |


## 四、系统架构

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│ 前端 (React + React Flow)                                    │
│ ┌──────────────────┬──────────────┬────────────────────────┐ │
│ │ 画布 (节点编排)     │ 右侧配置面板    │ 底部对话+日志            │ │
│ └──────────────────┴──────────────┴────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ 后端 (FastAPI)                                               │
│ ┌───────────┬────────────┬──────────┬─────────────────────┐ │
│ │ Canvas API│ Agent API  │ Video API│ MCP/Publish API     │ │
│ ├───────────┴────────────┴──────────┴─────────────────────┤ │
│ │ LangGraph Workflow (动态构建)                              │ │
│ │ GenericAgent (react/parallel 模式)                        │ │
│ │ SkillRegistry (scripts/ 自动注册)                          │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ PostgreSQL │ Redis │ Seedance API │ FFmpeg │ VLM        │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ 外部接口                                                     │
│ ┌──────────┬──────────┬──────────────────────────────────┐  │
│ │ REST API │ MCP Server│ LangGraph RemoteGraph (后续)     │  │
│ └──────────┴──────────┴──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 工作流 (默认 Pipeline)

```
[Chat Trigger] → Router → Planner → Producer → Editor → QualityGate → 完成
                   │                                        │
                   └── 路由规则跳过某些阶段              回环重试 ──┘
```

**节点职责**:


| 节点           | agent_type | 职责                              |
| ------------ | ---------- | ------------------------------- |
| Chat Trigger | trigger    | 用户输入入口                          |
| Router       | function   | LLM 意图路由，根据规则决定执行路径             |
| Planner      | react      | 理解需求、创建角色、分镜、生成 Seedance prompt |
| Producer     | react      | 按分镜调用 Seedance API 逐镜生成视频       |
| Editor       | react      | FFmpeg 裁剪/拼接/过渡/配乐 + VLM 衔接评估   |
| QualityGate  | function   | VLM 评分，>=70 通过，<70 回环 Producer  |


### 4.3 画布节点类型


| 类型          | 颜色  | Handle                            | 用途                 |
| ----------- | --- | --------------------------------- | ------------------ |
| Trigger     | 蓝绿  | 右: flow-out                       | 用户输入入口             |
| Agent       | 蓝   | 左右: flow / 底部: skill+subagent+mcp | LLM/VLM 执行器        |
| Skill 容器    | 绿   | 上: tool-in                        | 工具集合，双击钻入看具体 Skill |
| SubAgent 容器 | 紫   | 上: tool-in                        | 子 Agent 集合         |
| MCP 容器      | 橙   | 上: tool-in                        | MCP 服务集合           |


## 五、目录结构

### 后端

```
backend/
├── app/
│   ├── main.py                    # FastAPI 入口 + 种子数据 + 路由注册
│   ├── config.py                  # 环境变量配置
│   ├── agents/
│   │   ├── base.py                # BaseAgent + PromptManager 注入
│   │   ├── generic.py             # GenericAgent 通用执行器
│   │   ├── producer.py            # Producer 默认 prompt + ProducerAgent
│   │   ├── planner.py             # Planner 默认 prompt
│   │   └── editor.py              # Editor 默认 prompt
│   ├── graph/
│   │   ├── workflow.py            # 动态 LangGraph 构建 + 节点函数 + 路由逻辑
│   │   ├── state.py               # VideoProjectState TypedDict
│   │   └── callbacks.py           # WebSocket 推送 (状态/日志/流式输出)
│   ├── tools/
│   │   ├── __init__.py            # TOOL_REGISTRY (空, 由 SkillRegistry 填充)
│   │   ├── seedance.py            # Seedance 2.0 SDK 封装 (t2v/i2v/r2v/extend)
│   │   ├── ffmpeg_tools.py        # FFmpeg 7 个底层工具函数
│   │   ├── analysis.py            # VLM 截帧评估 (视频质量 + 衔接)
│   │   ├── file_ops.py            # download_video + extract_last_frame
│   │   ├── music.py               # 音乐生成 (占位)
│   │   └── web_search.py          # (已迁移到 skills/, 保留兼容)
│   ├── skills/                    # 14 个 Skill 目录 (Agent Skills 规范)
│   │   ├── registry.py            # SkillRegistry + scripts/ 自动发现注册
│   │   ├── generate_video_t2v/
│   │   │   ├── SKILL.md           # 元数据 + 指令
│   │   │   └── scripts/tool.py    # @tool 函数 (调用 seedance_t2v)
│   │   ├── trim_video/
│   │   │   ├── SKILL.md
│   │   │   └── scripts/tool.py    # @tool 函数 (调用 ffmpeg_trim)
│   │   └── ... (14 个, 全部自包含)
│   ├── api/
│   │   ├── canvas.py              # 画布 CRUD (8 端点, 连线即生效)
│   │   ├── admin.py               # Agent/Skill/路由规则管理
│   │   ├── mcp.py                 # MCP 服务管理 (7 端点)
│   │   ├── skill_creator.py       # LLM 对话式 Skill 生成 (2 端点)
│   │   ├── video_api.py           # 外部视频 API (generate/status/result/cancel)
│   │   ├── publish.py             # 版本发布 (publish/versions)
│   │   ├── chat.py                # 内部对话入口
│   │   └── websocket.py           # WebSocket 端点
│   ├── services/
│   │   ├── mcp_client.py          # MCP 客户端管理器 (SSE/stdio)
│   │   ├── prompt_manager.py      # Prompt 版本管理 + Redis 缓存
│   │   └── route_manager.py       # 路由规则管理
│   └── models/
│       ├── database.py            # 7 张表的 SQLAlchemy 模型
│       └── schemas.py             # Pydantic 请求/响应模型
├── mcp_server.py                  # 独立 MCP Server 进程
└── docker-compose.yml             # PostgreSQL + Redis
```

### 前端

```
frontend/src/
├── App.tsx                         # 路由 (/ → WorkspacePage)
├── pages/
│   └── WorkspacePage.tsx           # 主页: 画布 + 右侧面板 + 底部对话
├── components/
│   ├── flow/
│   │   ├── AgentFlowCanvas.tsx     # ReactFlow 画布主组件
│   │   ├── NodePicker.tsx          # 节点选择器 (搜索+Agent/Skill/SubAgent/MCP)
│   │   ├── SkillDrilldownView.tsx  # Skill 容器钻入视图
│   │   └── nodes/                  # 6 种节点组件
│   │       ├── AgentNode.tsx       # Agent (3 彩色 Handle)
│   │       ├── TriggerNode.tsx     # Chat Trigger (入口)
│   │       ├── SkillGroupNode.tsx  # Skill 容器 (绿, 双击钻入)
│   │       ├── SubAgentGroupNode.tsx # SubAgent 容器 (紫)
│   │       ├── McpGroupNode.tsx    # MCP 容器 (橙)
│   │       └── SkillNode.tsx       # 钻入视图中的独立 Skill 节点
│   ├── panels/
│   │   ├── NodeDetailPanel.tsx     # 右侧面板路由 (根据节点类型切换)
│   │   ├── SkillCreator.tsx        # LLM 对话式 Skill 创建器
│   │   ├── PromptEditor.tsx        # Prompt 编辑器
│   │   ├── ToolCheckboxList.tsx    # 工具列表
│   │   ├── RoutingRulesManager.tsx # 路由规则管理
│   │   └── AgentRunLog.tsx         # Agent 执行日志
│   ├── bottom/
│   │   ├── BottomPanel.tsx         # 底部面板 (对话+日志)
│   │   ├── ChatInput.tsx           # 对话输入
│   │   └── LogStream.tsx           # 实时日志流
│   └── shared/
│       ├── TopToolbar.tsx          # 顶部工具栏 (运行/停止/重置/发布)
│       └── VideoPreview.tsx        # 视频播放器
├── hooks/
│   ├── useAgentFlow.ts             # 画布数据管理 (从 Canvas API 加载)
│   └── useWebSocket.ts             # WebSocket 连接
├── services/api.ts                 # 所有 API 调用封装
└── types.ts                        # TypeScript 类型定义
```

## 六、数据模型 (7 张表)


| 表                   | 用途          | 关键字段                                                                                    |
| ------------------- | ----------- | --------------------------------------------------------------------------------------- |
| `agent_configs`     | Agent 配置    | id, name, agent_type, execution_mode, parent_id, system_prompt, available_tools, bypass |
| `canvas_nodes`      | 画布节点位置      | id, node_type (trigger/agent/skillgroup/subagentgroup/mcpgroup), ref_id, position_x/y   |
| `canvas_edges`      | 画布连线        | source_id, target_id, edge_type (flow/tool)                                             |
| `mcp_servers`       | MCP 服务注册    | id, transport (sse/stdio), url, status, discovered_tools                                |
| `workflow_versions` | 工作流版本快照     | version, is_published, snapshot (JSON)                                                  |
| `prompt_versions`   | Prompt 版本历史 | agent_id, version, system_prompt, is_active                                             |
| `routing_rules`     | 路由规则        | name, target_type, match_description, priority, enabled                                 |


## 七、核心机制

### 7.1 画布即配置 (连线即生效)

创建 `tool` 类型的 canvas_edge 时:

- source 是 Agent → target 是 Skill: 自动把 Skill name 加入 Agent 的 `available_tools`
- source 是 Agent → target 是 SubAgent: 自动把 SubAgent id 加入 `available_tools`
- source 是 Agent → target 是 MCP: 自动把 MCP 的所有 discovered_tools 加入

删除 edge 时自动从 `available_tools` 移除。

创建/删除 `flow` 类型 edge 时自动调用 `rebuild_workflow()` 热重建 LangGraph。

### 7.2 Skill 自包含 (Agent Skills 规范)

每个 Skill 是一个独立目录:

```
skills/generate_video_t2v/
├── SKILL.md           # YAML frontmatter (name/title/description/trigger) + Markdown 指令
└── scripts/
    └── tool.py        # @tool 装饰的 Python 函数 (自动注册到 TOOL_REGISTRY)
```

`SkillRegistry.scan()` → 扫描所有 `skills/*/SKILL.md` + `scripts/*.py` → 动态导入 → 注册到 `TOOL_REGISTRY`。

### 7.3 GenericAgent 通用执行器

从 DB `agent_configs` 读取配置，动态组装:

- `available_tools` 中的名字 → 查 `TOOL_REGISTRY` (Skill 函数) 或 `agent_configs` (Sub-Agent → 包装为 @tool)
- `execution_mode = react`: LLM 逐个决定调用工具 (串行)
- `execution_mode = parallel`: 所有子 Agent 并发执行, 结果合并

### 7.4 动态 LangGraph

`build_workflow(flow_edges)`:

- 从 `canvas_edges (type=flow)` 读取 Agent 间拓扑
- 入口点 = 无入边的节点
- 保留 Router/Planner/QualityGate 的条件路由逻辑
- 新增 Agent 自动用 `_generic_node_fn` 包装

## 八、外部调用方式

### 8.1 REST API

**服务地址**: `http://{host}:8000/api/v1/video/`

**启动生成**:

```bash
curl -X POST http://localhost:8000/api/v1/video/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "拍一个30秒的日落延时摄影"}'

# 响应: {"project_id": "abc-123", "status": "processing", "message": "视频生成任务已启动"}
```

**查询进度**:

```bash
curl http://localhost:8000/api/v1/video/abc-123/status
# 响应: {"project_id": "abc-123", "status": "processing", "running": true}
```

**获取结果**:

```bash
curl http://localhost:8000/api/v1/video/abc-123/result
# 响应: {"project_id": "abc-123", "status": "complete", "final_video_url": "http://...", "raw_clips": [...]}
```

**取消生成**:

```bash
curl -X POST http://localhost:8000/api/v1/video/abc-123/cancel
```

### 8.2 MCP Server

**启动 MCP 服务**:

```bash
# stdio 模式 (Claude Desktop / Cursor 等)
cd backend && python mcp_server.py

# SSE 模式 (HTTP, 其他系统连接)
cd backend && python mcp_server.py --transport sse --port 3100
```

**Claude Desktop 配置** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "video-agent": {
      "command": "python",
      "args": ["/path/to/backend/mcp_server.py"],
      "env": {
        "VIDEO_AGENT_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

**提供的工具**:

- `generate_video(prompt, assets?)` → 启动视频生成, 返回 project_id
- `get_video_status(project_id)` → 查询进度/结果

**调用方 Agent 自主轮询**:

```
用户: 帮我拍一个30秒武打片
Agent → generate_video("30秒武打片") → {project_id: "abc", status: "processing"}
Agent: 视频正在生成中，我帮你查一下进度...
Agent → get_video_status("abc") → {status: "producing", progress: 40}
Agent: 正在生成第2个分镜 (40%)...
Agent → get_video_status("abc") → {status: "complete", video_url: "http://..."}
Agent: 视频生成完成! [播放链接]
```

### 8.3 LangGraph RemoteGraph (后续迭代)

需要先部署 LangGraph Agent Server:

```bash
# 1. 创建 langgraph.json
# 2. langgraph up (Docker)
# 3. 其他系统用 RemoteGraph 连接
```

### 8.4 版本管理

**发布版本** (前端 [发布] 按钮或 API):

```bash
curl -X POST http://localhost:8000/api/v1/publish \
  -H 'Content-Type: application/json' \
  -d '{"version": "v1.0", "description": "首个生产版本"}'
```

**查看版本列表**:

```bash
curl http://localhost:8000/api/v1/versions
```

发布会快照当前所有 canvas_nodes + canvas_edges + agent_configs, 保存到 `workflow_versions` 表。

## 九、启动方式

```bash
# 1. 基础设施
cd /Users/bytedance/video-agent && docker-compose up -d

# 2. 后端
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 前端
cd frontend && npm run dev

# 4. MCP Server (可选, 供外部 Agent 连接)
cd backend && python mcp_server.py --transport sse --port 3100

# 访问调试面板: http://localhost:5173
# 外部 API: http://localhost:8000/api/v1/video/
```

## 十、Skill 清单 (14 个)


| name                      | title  | trigger                  | 底层依赖             |
| ------------------------- | ------ | ------------------------ | ---------------- |
| web_search                | 网络搜索   | always                   | DuckDuckGo       |
| generate_video_t2v        | 文生视频   | always                   | Seedance t2v     |
| generate_video_i2v        | 图生视频   | uploaded_assets 包含 image | Seedance i2v     |
| generate_video_r2v        | 参考视频生成 | uploaded_assets 包含 video | Seedance r2v     |
| generate_video_extend     | 视频续拍   | scenes 有 extend          | Seedance extend  |
| evaluate_video_quality    | 视频质量评估 | always                   | VLM 截帧评分         |
| evaluate_video_transition | 衔接质量评估 | raw_clips > 1            | VLM 截帧评分         |
| trim_video                | 视频裁剪   | always                   | FFmpeg trim      |
| concat_videos             | 视频拼接   | raw_clips > 1            | FFmpeg concat    |
| transition_videos         | 过渡效果   | raw_clips > 1            | FFmpeg xfade     |
| normalize_video           | 规格统一   | raw_clips > 1            | FFmpeg scale+fps |
| color_correct_video       | 色彩校正   | raw_clips > 1            | FFmpeg eq        |
| stabilize_video           | 视频稳定化  | raw_clips >= 1           | FFmpeg vidstab   |
| mix_audio                 | 音频混合   | plan.music.generate      | FFmpeg amix      |


