# Sprint 6 交接说明

## 项目位置
`/Users/bytedance/video-agent/`

## Sprint 6 完成内容

### 一、前端面板灵活性优化

1. **面板拖拽调整大小** — 去掉 react-resizable-panels (v4 API 不兼容)，改为原生 CSS `mousedown/mousemove` 拖拽。右侧 `rightWidth` + 底部 `bottomHeight`，有 min/max 约束
2. **虚线框上传区** — 删除 Paperclip 附件按钮，改为始终可见的图片/视频两个虚线框 (`border-dashed`)，各自 `accept="image/*"` / `accept="video/*"`
3. **全局拖拽 overlay** — 拖文件到面板区域时显示半透明提示 "释放以上传文件"
4. **删除 ChatPage** — `/` 直接进 WorkspacePage，这是调试平台不需要用户产品入口
5. **消息去重修复** — 后端 `chat.py` 不再 broadcast 用户消息（前端 `addChatMessage` 已处理）
6. **发送状态锁** — `sending` + `canSend` 状态，running 时禁止重复发送，发送按钮显示 loading spinner

### 二、Agent 双击展开子图

1. **后端 tool_call_start/tool_call_end WebSocket 事件** — `StreamingWSCallback` 新增 `on_tool_start`/`on_tool_end` 回调
2. **ToolNode 组件** — 显示工具名+描述+调用状态+输入输出折叠预览
3. **AgentSubFlowView** — 双击 Planner/Producer/Editor 进入子图，LLM 中心 + 工具/子Agent 节点放射状环绕，面包屑导航返回
4. **AgentFlowCanvas 双击钻入** — `viewMode` 状态切换全局视图/Agent 子图

### 三、Skill 1:1 重构

1. **SKILL.md 通用协议** — 4 个字段: `name` (技术标识), `title` (人类可读名), `description`, `trigger` (规则条件)。不绑定 Agent，不含 parameters/tags/version
2. **14 个 Skill** — web_search + 4 个 Seedance + 9 个 Editor 工具。每个 Skill 对应 1 个工具
3. **Planner 改为纯 LLM 调用** — 删除 think/submit_plan (假工具)，有工具 (web_search) 时走 ReAct，无工具时直接 `llm.ainvoke()`
4. **Producer 删 report_results，Editor 删 submit_edit_result** — 改为 System Prompt 指导直接输出 JSON
5. **trigger 规则引擎** — `always` / `uploaded_assets 包含 image` / `scenes 中有 generation_mode=i2v` / `raw_clips 数量 > 1` / `plan.music.generate == true`
6. **新建 web_search 工具** — `tools/web_search.py`，DuckDuckGo 免费搜索，Planner 的唯一 Skill

### 四、Skill 驱动工具加载

1. **Agent 包装工具注册到 TOOL_REGISTRY** — 从 16 个底层工具扩展到包含 Agent 包装工具
2. **Agent.run() 动态加载** — `get_dynamic_tools(state)`: DB available_tools → SkillRegistry trigger 过滤 → TOOL_REGISTRY 解析
3. **Skill CRUD API** — `GET/PUT /skills/{name}/content` (读写 SKILL.md) + `POST /skills` (创建) + `DELETE /skills/{name}` (删除) + `POST /skills/reload` (热更新)
4. **前端工具 Tab** — 按 Skill 平铺显示，[+ Skill] 从全局池添加，勾选启用/禁用，编辑 SKILL.md

### 五、数据驱动 Agent + Sub-Agent

1. **agent_configs 表** — id/name/description/agent_type/parent_id/system_prompt/available_tools/llm_config/bypass/enabled。替代硬编码 AGENT_REGISTRY
2. **GenericAgent** (`agents/generic.py`) — 通用执行器，从 DB 读配置，自动识别 Skill 和 Sub-Agent。Sub-Agent 通过 `_wrap_sub_agent()` 包装为 `@tool`
3. **workflow.py 节点改造** — planner_node/producer_node/editor_node 改为 `get_agent_config()` → `GenericAgent().run()`。Router/QualityGate 保持代码逻辑
4. **Admin API 全改 DB** — 删除 AGENT_REGISTRY，Agent CRUD (POST/PUT/DELETE)，创建子 Agent 自动加入父 available_tools，删除自动移除
5. **前端子 Agent 交互** — [+ 子Agent] 在 NodeDetailPanel header，创建后 React Flow 画布出现独立节点 (紫色边框 + 虚线连接父节点)，点击可独立配置 Prompt/Skill

### 六、Bypass 功能

1. **AgentConfig.bypass 字段** — DB 持久化
2. **workflow 节点判断** — bypass 时透传 state，不执行 Agent
3. **前端 AgentNode** — SkipForward 图标按钮，点击切换 bypass，节点半透明 + 删除线 + "已跳过"

### 七、Seedance 视频 role 修复

`reference_video_to_video` 和 `extend_video` 的 video content 添加 `"role": "reference_video"`

## 当前架构

```
前端操作
  ├── [+ 子Agent] → POST /agents → agent_configs 表 + 父 available_tools 更新
  ├── [+ Skill] → PUT /agents/{id}/tools → agent_configs.available_tools 更新
  ├── 编辑 Prompt → PUT /agents/{id}/prompt → AgentConfig + PromptVersion
  └── Bypass 切换 → PUT /agents/{id} → AgentConfig.bypass
  ↓
agent_configs 表 (DB, 支持层级)
  ↓ GenericAgent._resolve_all_tools()
  ├── name in TOOL_REGISTRY → 普通 Skill (SkillRegistry trigger 过滤)
  └── name in agent_configs → Sub-Agent → _wrap_sub_agent() 包装为 @tool
  ↓
create_react_agent(llm, tools) 或 llm.ainvoke()
  ↓
LangGraph 节点执行 (6 节点拓扑不变)
```

## 当前 Skill 清单 (14 个)

| name | title | trigger |
|------|-------|---------|
| web_search | 网络搜索 | always |
| generate_video_t2v | 文生视频 | always |
| generate_video_i2v | 图生视频 | uploaded_assets 包含 image / scenes 有 i2v |
| generate_video_r2v | 参考视频生成 | uploaded_assets 包含 video / scenes 有 r2v |
| generate_video_extend | 视频续拍 | scenes 有 extend / raw_clips >= 1 |
| evaluate_video_transition | 衔接质量评估 | raw_clips > 1 |
| evaluate_video_quality | 视频质量评估 | always |
| trim_video | 视频裁剪 | always |
| concat_videos | 视频拼接 | raw_clips > 1 |
| transition_videos | 过渡效果 | raw_clips > 1 |
| normalize_video | 规格统一 | raw_clips > 1 |
| color_correct_video | 色彩校正 | raw_clips > 1 |
| stabilize_video | 视频稳定化 | raw_clips >= 1 |
| mix_audio | 音频混合 | plan.music.generate == true |

## 当前 Agent 配置 (DB seed)

| id | name | agent_type | available_tools |
|----|------|-----------|----------------|
| router | Router | function | [] |
| planner | Planner | react | [web_search] |
| producer | Producer | react | [generate_video_t2v, i2v, r2v, extend] |
| editor | Editor | react | [9 个 FFmpeg/VLM 工具] |
| human_feedback | Human Feedback | function | [] |
| quality_gate | Quality Gate | function | [evaluate_video] |

## Plan 文档清单

| Plan 文件 | 状态 | 说明 |
|-----------|------|------|
| `视频生成agent系统_1d7d83ac.plan.md` | 主 plan | 全局架构设计 |
| `前端面板灵活性优化_d766bd66.plan.md` | 完成 | 面板拖拽 + 上传区 + 子图 |
| `skill驱动工具加载_705ceb9f.plan.md` | 完成 | Skill 机制打通 |
| `skill_1对1_重构_b14f0d60.plan.md` | 完成 | 1 Skill = 1 Tool 协议 |
| `数据驱动Agent_SubAgent_8a3e1f20.plan.md` | 完成 | DB 驱动 + GenericAgent + Sub-Agent |
| `可编辑子图_自由连线_a7c3d421.plan.md` | **待执行** | 子 Agent 间拖拽连线 + 子图执行 |

## 待执行: 可编辑子图方案

详见 `可编辑子图_自由连线_a7c3d421.plan.md`，核心改动:
1. 新增 `agent_edges` 表存储子 Agent 之间的连线
2. GenericAgent 子图执行模式 (有边时按拓扑序执行，沿边传递输出)
3. 实线(必经)/虚线(条件) 样式区分
4. React Flow 编辑模式 (拖拽连线)
5. 条件配置 UI

## 启动方式
```bash
# 基础设施
cd /Users/bytedance/video-agent && docker-compose up -d

# 后端
cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend && npm run dev

# E2E 测试
cd backend && python scripts/test_e2e.py
```
