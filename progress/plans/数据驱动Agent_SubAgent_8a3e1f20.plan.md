---
name: 数据驱动Agent + Sub-Agent
overview: "Agent 定义从代码硬编码改为 DB (agent_configs 表) 配置驱动。GenericAgent 替代 3 个专用 Agent 类，支持 Agent-as-a-Tool 模式。创建子 Agent 后自动添加到父 Agent 的 available_tools 并在 React Flow 画布上显示为独立可配置节点。前端交互: [+ 子Agent] 在 NodeDetailPanel header, [+ Skill] 在 Skill Tab, 子 Agent 节点可单独配置 Prompt 和 Skill。"
todos:
  - id: db-agent-config
    content: 新建 agent_configs 表 (id/name/description/agent_type/parent_id/system_prompt/available_tools/llm_config/enabled)
    status: completed
  - id: generic-agent
    content: "GenericAgent: 从 DB 读配置，TOOL_REGISTRY 解析 Skill，agent_configs 解析 Sub-Agent 包装为 @tool"
    status: completed
  - id: workflow-adapt
    content: planner_node/producer_node/editor_node 改为 get_agent_config() → GenericAgent().run()，Router/QualityGate 保持代码逻辑
    status: completed
  - id: admin-api-db
    content: 删除 AGENT_REGISTRY，全部改 DB 查询。Agent CRUD (POST/PUT/DELETE)，创建子 Agent 自动加入父 available_tools，删除自动移除
    status: completed
  - id: seed-migration
    content: 启动时 6 个顶层 Agent 写入 agent_configs，PromptVersion 保持兼容
    status: completed
  - id: frontend-ux
    content: "前端交互重构: [+ 子Agent] 在 NodeDetailPanel header (仅 planner/producer/editor)，创建后自动出现为 React Flow 节点 (紫色边框+虚线连接父节点)，点击子 Agent 节点可独立配置 Prompt/Skill/日志"
    status: completed
  - id: frontend-skill-tab
    content: "Skill Tab 改为纯 Skill 管理: [+ Skill] 按钮从全局 Skill 池选择添加，勾选启用/禁用，编辑 SKILL.md"
    status: completed
  - id: verify
    content: "TypeScript + Vite 构建通过，API 验证: 创建/删除子 Agent 正确联动 available_tools 和 React Flow 节点"
    status: completed
isProject: false
---

# 数据驱动 Agent + Sub-Agent (Agent-as-a-Tool)

## 设计原则

- **LangGraph 顶层图不变**: 6 个节点 (Router/Planner/Producer/Editor/HumanFeedback/QualityGate) 保持固定，这是稳定的工作流骨架
- **Agent 内部可配置**: 每个 Agent 可以包含 Sub-Agent 作为工具，Sub-Agent 又有自己的 Prompt 和 Skill
- **全部存 DB**: Agent 定义、Sub-Agent 层级、Prompt、工具分配都在 DB 里，前端可配置
- **GenericAgent 统一执行**: 一个通用类替代 PlannerAgent/ProducerAgent/EditorAgent

## 1. 新建 agent_configs 表

**改动文件**: `backend/app/models/database.py`

```python
class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id = Column(String(64), primary_key=True)         # "producer", "image_agent"
    name = Column(String(128), nullable=False)         # "Producer", "图像生成"
    description = Column(Text, default="")
    agent_type = Column(String(32), default="react")   # react | llm | function
    parent_id = Column(String(64), nullable=True)      # NULL=顶层, "producer"=子Agent
    system_prompt = Column(Text, default="")
    available_tools = Column(JSON, default=list)        # ["generate_video_i2v"] 或 ["image_agent"]
    llm_config = Column(JSON, default=dict)             # {"temperature": 0.3}
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

`available_tools` 里的字符串可以是:

- Skill 名 (TOOL_REGISTRY key) → 加载为普通工具
- Agent id (agent_configs.id) → 包装为 Agent-as-a-Tool

解析优先级: TOOL_REGISTRY 优先，未找到则查 agent_configs。

层级示例:

```
id: "producer"       parent_id: NULL        tools: ["image_agent", "video_agent"]
id: "image_agent"    parent_id: "producer"  tools: ["generate_video_i2v"]
id: "video_agent"    parent_id: "producer"  tools: ["generate_video_t2v", "generate_video_r2v", "generate_video_extend"]
```

## 2. GenericAgent 替代 3 个专用类

**新建文件**: `backend/app/agents/generic.py`

```python
class GenericAgent:
    """数据驱动的通用 Agent 执行器"""

    async def run(self, config: AgentConfig, state: dict) -> dict:
        llm = self._build_llm(config.llm_config, callbacks)
        tools = await self._resolve_tools(config.available_tools, state)

        if config.agent_type == "llm" or not tools:
            result = await llm.ainvoke(messages)
        else:
            agent = create_react_agent(llm, tools)
            result = await agent.ainvoke({"messages": messages})

        return self._parse_output(result)

    async def _resolve_tools(self, tool_names, state):
        resolved = []
        for name in tool_names:
            # 1. 先查 TOOL_REGISTRY (普通 Skill)
            if name in TOOL_REGISTRY:
                # 做 SkillRegistry trigger 过滤
                skill = get_skill_registry().get(name)
                if skill and not self._check_trigger(skill, state):
                    continue
                resolved.append(TOOL_REGISTRY[name])
                continue
            # 2. 再查 agent_configs (Sub-Agent → 包装为 Tool)
            sub_config = await self._get_agent_config(name)
            if sub_config:
                resolved.append(self._wrap_as_tool(sub_config, state))
        return resolved

    def _wrap_as_tool(self, sub_config, parent_state):
        """将 Sub-Agent 包装为 @tool 函数"""
        @tool
        async def sub_agent_tool(task: str) -> str:
            result = await GenericAgent().run(sub_config, {**parent_state, "sub_task": task})
            return json.dumps(result)
        sub_agent_tool.name = sub_config.id
        sub_agent_tool.description = f"{sub_config.name}: {sub_config.description}"
        return sub_agent_tool
```

## 3. Workflow 节点改造

**改动文件**: `backend/app/graph/workflow.py`

节点函数从调用特定 Agent 类改为查 DB + GenericAgent:

```python
# 之前
planner_agent = PlannerAgent()
async def planner_node(state):
    result = await planner_agent.run(dict(state))

# 之后
async def planner_node(state):
    config = await get_agent_config("planner")
    result = await GenericAgent().run(config, dict(state))
```

Router 和 QualityGate (agent_type="function") 保持原有代码逻辑不变。

## 4. 种子数据

启动时写入 6 个顶层 Agent 配置:


| id             | name           | agent_type | available_tools                                                                             |
| -------------- | -------------- | ---------- | ------------------------------------------------------------------------------------------- |
| router         | Router         | function   | []                                                                                          |
| planner        | Planner        | react      | ["web_search"]                                                                              |
| producer       | Producer       | react      | ["generate_video_t2v", "generate_video_i2v", "generate_video_r2v", "generate_video_extend"] |
| editor         | Editor         | react      | ["trim_video", "concat_videos", ...]                                                        |
| human_feedback | Human Feedback | function   | []                                                                                          |
| quality_gate   | Quality Gate   | function   | ["evaluate_video"]                                                                          |


## 5. Admin API

删除硬编码的 AGENT_REGISTRY，改为 DB 查询:

```
GET    /api/admin/agents                    — 列出所有 Agent (含 Sub-Agent 层级)
POST   /api/admin/agents                    — 创建新 Agent/Sub-Agent
GET    /api/admin/agents/{id}               — 获取 Agent 详情 (含子 Agent 列表)
PUT    /api/admin/agents/{id}               — 更新 Agent 配置 (prompt/tools/llm_config)
DELETE /api/admin/agents/{id}               — 删除 Agent
GET    /api/admin/agents/{id}/children      — 获取子 Agent 列表
```

tools 返回格式区分 Skill 和 Sub-Agent:

```json
{
  "id": "producer",
  "name": "Producer",
  "tools": [
    {"name": "image_agent", "type": "agent", "title": "图像生成"},
    {"name": "video_agent", "type": "agent", "title": "视频生成"}
  ],
  "children": [
    {"id": "image_agent", "name": "图像生成", "tools": ["generate_video_i2v"]},
    {"id": "video_agent", "name": "视频生成", "tools": ["generate_video_t2v", ...]}
  ]
}
```

## 6. 前端交互设计 (实际实现)

### 子 Agent 创建

- 点击顶层 Agent 节点 (planner/producer/editor) → 右侧面板 Tab 栏右侧有 **[+ 子Agent]** 按钮 (紫色)
- 点击后展开表单: 输入 ID + 名称 → 创建
- 创建成功后:
  - 后端: 自动将子 Agent id 加入父 Agent 的 `available_tools`
  - 前端: React Flow 画布自动出现新节点 (紫色边框 `border-indigo-500/30`，虚线连接父节点)
- 删除时: 后端自动从父 `available_tools` 移除

### 子 Agent 配置

- 点击子 Agent 节点 → 右侧面板显示与顶层 Agent 相同的配置面板:
  - **System Prompt** Tab: Monaco Editor 编辑子 Agent 的 prompt
  - **Skill** Tab: 为子 Agent 分配工具 ([+ Skill] 从全局池选择)
  - **日志** Tab: 该子 Agent 的运行日志

### Skill 管理

- **[+ Skill]** 绿色按钮在 Skill Tab 顶部
- 点击展开全局 Skill 列表 (从 SkillRegistry 获取)，选择未分配的 Skill 添加
- 每个 Skill 可勾选启用/禁用，点文件图标编辑 SKILL.md
- 保存后通过 `PUT /agents/{id}/tools` 同步到 DB，立即生效

### React Flow 节点样式区分

- 顶层 Agent: `w-56`，状态着色 (idle灰/running蓝/success绿/error红)
- 子 Agent: `w-48`，紫色边框 `border-indigo-500/30 bg-indigo-950/40`，标签显示 "Sub-Agent"
- 顶层连接: 实线 + 箭头，左进右出
- 子 Agent 连接: 虚线 + 紫色箭头，上进下出

```
┌──────┐    ┌──────────┐    ┌──────────┐
│Router│───→│ Planner  │───→│ Producer │───→ Editor ───→ QualityGate
└──────┘    └──────────┘    └────┬─────┘
                                 │ (虚线紫色)
                            ┌────▼──────┐
                            │image_agent│ (紫色节点)
                            └───────────┘
```

## 7. PromptVersion 兼容性

- AgentConfig.system_prompt = 当前活跃 prompt
- PromptVersion 继续记录版本历史
- 编辑 prompt → 同时写 AgentConfig + PromptVersion
- 回滚 → 从 PromptVersion 恢复到 AgentConfig

## 8. 数据流总结

```
前端操作
  ├── [+ 子Agent] → POST /agents (parent_id=xxx) → agent_configs 表 + 父 available_tools 更新
  ├── [+ Skill] → PUT /agents/{id}/tools → agent_configs.available_tools 更新
  └── 编辑 Prompt → PUT /agents/{id}/prompt → AgentConfig + PromptVersion
  ↓
agent_configs 表 (DB)
  ↓ GenericAgent._resolve_all_tools()
  ├── name in TOOL_REGISTRY → 普通 Skill (做 SkillRegistry trigger 过滤)
  └── name in agent_configs → Sub-Agent → _wrap_sub_agent() 包装为 @tool
  ↓
create_react_agent(llm, tools) 或 llm.ainvoke()
  ↓
LangGraph 节点执行
```

## 关键改动文件清单


| 文件                            | 改动                                                                   |
| ----------------------------- | -------------------------------------------------------------------- |
| `models/database.py`          | 新增 AgentConfig 表                                                     |
| `agents/generic.py`           | 新建 GenericAgent 通用执行器                                                |
| `graph/workflow.py`           | planner/producer/editor 节点改用 GenericAgent                            |
| `api/admin.py`                | 删除 AGENT_REGISTRY，全改 DB 查询 + Agent CRUD + 创建/删除自动联动父 available_tools |
| `main.py`                     | 种子数据写入 agent_configs                                                 |
| `hooks/useAgentFlow.ts`       | 初始化时从 API 加载子 Agent 为 React Flow 节点，暴露 loadSubAgents                 |
| `flow/nodes/AgentNode.tsx`    | 子 Agent 紫色样式 + Handle 位置上下                                           |
| `panels/NodeDetailPanel.tsx`  | 子 Agent 节点支持 Prompt/Skill/日志 Tab + [+ 子Agent] 按钮                     |
| `panels/ToolCheckboxList.tsx` | 纯 Skill 管理 + [+ Skill] 从全局池添加                                        |
| `services/api.ts`             | Agent CRUD API + ToolEntry 类型更新                                      |


## 不涉及的范围

- LangGraph 顶层图结构不变 (6 节点)
- VideoProjectState 不变
- WebSocket 事件类型不变
- SKILL.md 4 字段协议不变 (name/title/description/trigger)
- Seedance/FFmpeg 工具实现不变

