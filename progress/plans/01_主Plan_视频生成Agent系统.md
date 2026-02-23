# 视频生成 Agent 系统 — 主 Plan

## 一、项目概述

基于 LLM/VLM 驱动的 Multi-Agent 视频生成系统。

**核心能力**: 用户描述视频需求 → Agent 自动规划分镜 → 调用视频生成 API → 后期合成 → 质量评估 → 输出最终视频。

**调试面板**: n8n 风格的可视化节点编排器，支持拖拽连线自由组合工作流。

**外部调用**: 调试完成后发布为版本，通过 REST API / MCP / LangGraph RemoteGraph 供外部系统调用。

---

## 二、技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | Python 3.12 / FastAPI / Uvicorn |
| Agent 编排 | LangGraph (StateGraph, 动态构建) |
| LLM 调用 | LangChain + ChatOpenAI (豆包/GPT-4o) |
| 数据库 | PostgreSQL (SQLAlchemy async) |
| 缓存 | Redis (Prompt 版本缓存) |
| 前端框架 | React 18 + TypeScript + Vite |
| 流程图 | @xyflow/react (React Flow) |
| UI 组件 | TailwindCSS + 自定义组件 |
| 视频生成 | Seedance 2.0 (火山方舟 SDK) |
| 视频编辑 | FFmpeg (本地命令行) |
| VLM 评估 | GPT-4o / 豆包多模态 |
| MCP | Model Context Protocol (SSE/stdio) |

---

## 三、系统架构

### 3.1 整体架构

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

### 3.2 工作流 (默认 Pipeline)

```
[Chat Trigger] → Router → Planner → Producer → Editor → QualityGate → 完成
                   │                                        │
                   └── 路由规则跳过某些阶段              回环重试 ──┘
```

| 节点 | agent_type | 职责 |
|------|------------|------|
| Chat Trigger | trigger | 用户输入入口 |
| Router | function | LLM 意图路由，根据规则决定执行路径 |
| Planner | react | 理解需求、创建角色、分镜、生成 Seedance prompt |
| Producer | react | 按分镜调用 Seedance API 逐镜生成视频 |
| Editor | react | FFmpeg 裁剪/拼接/过渡/配乐 + VLM 衔接评估 |
| QualityGate | function | VLM 评分，>=70 通过，<70 回环 Producer |

### 3.3 画布节点类型

| 类型 | 颜色 | Handle | 用途 |
|------|------|--------|------|
| Trigger | 蓝绿 | 右: flow-out | 用户输入入口 |
| Agent | 蓝 | 左右: flow / 底部: tool-out / 顶部: tool-in | LLM/VLM 执行器 |
| Skill 容器 | 绿 | 上: tool-in | 工具集合，双击钻入 |
| SubAgent 容器 | 紫 | 上: tool-in | 子 Agent 集合 |
| MCP 容器 | 橙 | 上: tool-in | MCP 服务集合 |

---

## 四、子 Agent 接入机制

### 4.1 当前实现 (同系统 Agent)

- **SubAgent** = `agent_configs` 表中的 Agent，通过 `tool` 边连接到父 Agent
- **GenericAgent._wrap_as_tool()**: 将 SubAgent 包装为 `@tool` 函数，父 Agent 的 LLM 通过 ReAct 决定是否调用
- **连线即生效**: Agent → Agent 的 tool 边创建时，自动设置 target 的 `parent_id`，target 变为 SubAgent 容器
- **执行模式**: 父 Agent 面板可切换 `react`(串行) / `parallel`(并行)

### 4.2 扩展: 外部 Agent 接入 (后续迭代)

| 来源 | 接入方式 | 说明 |
|------|----------|------|
| 其他 LangGraph 系统 | HTTP API 包装 / LangGraph RemoteGraph | 将外部 LangGraph 部署为服务，本系统通过 HTTP 或 RemoteGraph 调用 |
| 其他架构 Agent | MCP / HTTP 工具包装 | 若外部 Agent 暴露 MCP 工具，可通过 MCP 容器接入；或写 HTTP 适配器包装为 Skill |
| 自定义 Agent | agent_configs + 自定义执行器 | 扩展 `agent_type`，支持 `remote` 类型，配置 url 等 |

---

## 五、核心机制

### 5.1 画布即配置 (连线即生效)

创建 `tool` 类型 canvas_edge 时:
- source 是 Agent → target 是 Skill: 自动把 Skill name 加入 Agent 的 `available_tools`
- source 是 Agent → target 是 SubAgent: 自动把 SubAgent id 加入 `available_tools`
- source 是 Agent → target 是 MCP: 自动把 MCP 的 discovered_tools 加入

删除 edge 时自动从 `available_tools` 移除。创建/删除 `flow` 边时触发 `rebuild_workflow()` 热重建 LangGraph。

### 5.2 动态 LangGraph

`build_workflow(flow_edges)`: 从 `canvas_edges (type=flow)` 读取 Agent 间拓扑，入口点=无入边节点，保留 Router/QualityGate 条件路由，新增 Agent 用 `_generic_node_fn` 包装。

---

## 六、外部调用方式

### 6.1 REST API

- `POST /api/v1/video/generate` — 启动生成
- `GET /api/v1/video/{id}/status` — 查询进度
- `GET /api/v1/video/{id}/result` — 获取结果
- `POST /api/v1/video/{id}/cancel` — 取消

### 6.2 MCP Server

- `generate_video(prompt, assets?)` — 启动视频生成
- `get_video_status(project_id)` — 查询进度/结果

### 6.3 版本管理

- `POST /api/v1/save` — 保存当前画布（有发布版本则更新，否则存为草稿 _draft）
- `POST /api/v1/publish` — 发布新版本
- `GET /api/v1/versions` — 版本列表
- `POST /api/v1/versions/{id}/load` — 加载版本到画布
- `DELETE /api/v1/versions/{id}` — 删除版本

---

## 七、启动方式

```bash
docker-compose up -d
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
# 访问: http://localhost:5173
```

---

## 八、Skill 清单 (14 个)

| name | title | trigger |
|------|-------|---------|
| web_search | 网络搜索 | always |
| generate_video_t2v | 文生视频 | always |
| generate_video_i2v | 图生视频 | uploaded_assets 包含 image |
| generate_video_r2v | 参考视频生成 | uploaded_assets 包含 video |
| generate_video_extend | 视频续拍 | scenes 有 extend |
| evaluate_video_quality | 视频质量评估 | always |
| evaluate_video_transition | 衔接质量评估 | raw_clips > 1 |
| trim_video | 视频裁剪 | always |
| concat_videos | 视频拼接 | raw_clips > 1 |
| transition_videos | 过渡效果 | raw_clips > 1 |
| normalize_video | 规格统一 | raw_clips > 1 |
| color_correct_video | 色彩校正 | raw_clips > 1 |
| stabilize_video | 视频稳定化 | raw_clips >= 1 |
| mix_audio | 音频混合 | plan.music.generate |
