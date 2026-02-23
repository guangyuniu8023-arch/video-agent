---
name: Skill驱动工具加载
overview: 修正当前 Agent 硬编码工具的实现，改为通过 Skill 机制动态加载。SKILL.md 声明工具 -> SkillRegistry 注册 -> Agent 配置引用 Skill -> Agent.run() 动态解析工具 -> 工具 Tab 勾选真正影响行为。前端可查看/编辑 SKILL.md，支持热插拔。
todos:
  - id: register-agent-tools
    content: "Step 1: 把 Agent 包装工具 (think/submit_plan/generate_video_*/...) 注册到 TOOL_REGISTRY"
    status: completed
  - id: create-agent-skills
    content: "Step 2: 新建 planner_skill/producer_skill/editor_skill 的 SKILL.md"
    status: completed
  - id: dynamic-tool-loading
    content: "Step 3: Agent.run() 改用 await self.get_tools() 动态加载，self._tools 作为兜底"
    status: completed
  - id: fix-seed-data
    content: "Step 4: main.py 种子数据修正，每个 Agent 只写入其对应 Skill 的工具"
    status: completed
  - id: skill-crud-api
    content: "Step 5: 后端 Skill CRUD API — 读取/更新/新建/删除 SKILL.md + 热更新 SkillRegistry"
    status: completed
  - id: fix-tools-api
    content: "Step 6: admin API /agents/{id}/tools 返回正确的工具列表，附带 Skill 归属信息"
    status: completed
  - id: frontend-skill-editor
    content: "Step 7: 前端工具 Tab 改造 — 按 Skill 分组显示工具 + Skill 详情/编辑 + 热插拔操作"
    status: completed
  - id: verify-e2e
    content: "Step 8: E2E 测试 + 实际工作流验证"
    status: completed
isProject: false
---

# Skill 驱动工具动态加载

## 当前断裂分析

主 plan 要求的链路：

```
SKILL.md 声明工具 → SkillRegistry 注册 → Agent 配置引用 Skill
→ BaseAgent.get_tools() 动态解析 → 前端工具 Tab 可配置
```

实际实现中断在**3 个地方**：

### 断裂 1: Agent 工具硬编码

3 个 Agent 都在各自文件里用 `@tool` 定义了包装函数，再硬编码到 `self._tools`：

- `planner.py`: `self._tools = [think, submit_plan]` — 这两个工具甚至不在 TOOL_REGISTRY 里
- `producer.py`: `self._tools = [generate_video_t2v, ...]` — 这些是包装函数，包装了 TOOL_REGISTRY 中的 seedance_* 函数
- `editor.py`: `self._tools = [evaluate_video_transition, ...]` — 同上，包装了 TOOL_REGISTRY 中的 ffmpeg_* 等函数

### 断裂 2: BaseAgent.get_tools() 从未被调用

`base.py` 有 `get_tools()` 方法能从 DB 动态解析工具名到 TOOL_REGISTRY 函数，但 3 个 Agent 的 `run()` 都用 `self._tools` 创建 agent：

```python
agent = create_react_agent(llm, self._tools)  # 硬编码，不走 get_tools()
```

### 断裂 3: TOOL_REGISTRY 和 Agent 实际工具脱节

- TOOL_REGISTRY 有 16 个底层工具 (seedance_t2v, ffmpeg_trim, ...)
- Agent 用的是各自定义的包装工具 (generate_video_t2v, trim_video, ...)
- 名称不同，一一对应关系也不明确

---

## 修复方案

### 核心思路

1. 把 Agent 的包装工具 (`@tool` 装饰的函数) 也注册到 TOOL_REGISTRY
2. Agent `run()` 改为调用 `await self.get_tools()` 动态获取工具
3. 新增 Planner Skill，把 `think`/`submit_plan` 也纳入 Skill 体系
4. 前端工具 Tab 只显示和操作该 Agent 的**当前工具**，勾选真正影响行为

### Step 1: 扩展 TOOL_REGISTRY 注册 Agent 包装工具

**改动文件**: [tools/**init**.py](backend/app/tools/__init__.py)

当前 TOOL_REGISTRY 只有 16 个底层工具。需要新增 Agent 包装工具的注册：

- Planner 的 `think`, `submit_plan`
- Producer 的 `generate_video_t2v`, `generate_video_i2v`, `generate_video_r2v`, `generate_video_extend`, `report_results`
- Editor 的 `evaluate_video_transition`, `evaluate_video_quality`, `trim_video`, `concat_videos`, `transition_videos`, `normalize_video`, `color_correct_video`, `stabilize_video`, `mix_audio`, `submit_edit_result`

方式：在各 Agent 文件中用 `register_tool` 注册这些包装函数。

### Step 2: 新增 Planner/Producer/Editor 的 SKILL.md

**新建文件**:

- `skills/planner_skill/SKILL.md` — 声明 tools: [think, submit_plan]
- `skills/producer_skill/SKILL.md` — 声明 tools: [generate_video_t2v, generate_video_i2v, generate_video_r2v, generate_video_extend, report_results]
- `skills/editor_skill/SKILL.md` — 声明 tools: [evaluate_video_transition, evaluate_video_quality, trim_video, concat_videos, transition_videos, normalize_video, color_correct_video, stabilize_video, mix_audio, submit_edit_result]

这些 SKILL.md 代替现有的 seedance_skill/ffmpeg_skill/music_skill，因为 Agent 用的是包装工具名，不是底层工具名。

### Step 3: Agent run() 改用动态工具加载

**改动文件**: [agents/planner.py](backend/app/agents/planner.py), [agents/producer.py](backend/app/agents/producer.py), [agents/editor.py](backend/app/agents/editor.py)

核心变更：

```python
# 之前 (硬编码)
agent = create_react_agent(llm, self._tools)

# 之后 (动态加载)
tools = await self.get_tools()
if not tools:
    tools = self._tools  # 兜底：DB 不可用时用默认
agent = create_react_agent(llm, tools)
```

`BaseAgent.get_tools()` 已经实现了 DB → 内存兜底 → 默认 的三级回退：

1. 读 DB 中该 Agent 的 `available_tools` 字段（工具名列表）
2. 通过 `_resolve_tools()` 从 TOOL_REGISTRY 解析为实际函数
3. DB 不可用时回退到 `self._tools`

### Step 4: 修正种子数据

**改动文件**: [main.py](backend/app/main.py) 中的 `_seed_default_prompts`

确保每个 Agent 的默认 `available_tools` 只包含其对应 Skill 声明的工具：

- planner → `['think', 'submit_plan']`
- producer → `['generate_video_t2v', 'generate_video_i2v', ...]`
- editor → `['evaluate_video_transition', 'evaluate_video_quality', ...]`

### Step 5: 后端 Skill CRUD API

**改动文件**: [api/admin.py](backend/app/api/admin.py)

新增 Skill 文件操作接口：

```
GET    /api/admin/skills/{name}/content    — 返回 SKILL.md 原始内容
PUT    /api/admin/skills/{name}/content    — 更新 SKILL.md 内容 → 自动重新扫描 SkillRegistry
POST   /api/admin/skills                   — 新建 Skill (创建目录 + SKILL.md)
DELETE /api/admin/skills/{name}            — 删除 Skill (删除目录)
POST   /api/admin/skills/reload            — 已有，手动触发重新扫描
```

关键行为：

- PUT 更新 SKILL.md 后，自动调用 `get_skill_registry().scan()` 热更新
- 新建 Skill 时创建 `skills/{name}_skill/SKILL.md`，写入模板
- 删除时移除目录（需确认操作）

### Step 6: admin API /agents/{id}/tools 修正

**改动文件**: [api/admin.py](backend/app/api/admin.py)

修改返回结构，增加 Skill 归属信息：

```json
{
  "agent_id": "planner",
  "current_tools": ["think", "submit_plan"],
  "tools_by_skill": [
    {
      "skill_name": "planner_reasoning",
      "skill_description": "Planner 推理和计划提交工具集",
      "tools": [
        {"name": "think", "description": "内部推理思考", "enabled": true},
        {"name": "submit_plan", "description": "提交制作计划", "enabled": true}
      ]
    }
  ],
  "all_available_tools": [...]
}
```

前端通过 `tools_by_skill` 按 Skill 分组展示，每个 Skill 可折叠/展开。

### Step 7: 前端工具 Tab 改造 + Skill 编辑器

**改动文件**: [ToolCheckboxList.tsx](frontend/src/components/panels/ToolCheckboxList.tsx)

改造为**按 Skill 分组**的工具管理面板：

```
┌──────────────────────────────────────┐
│ 工具管理                    [+ 添加 Skill] │
├──────────────────────────────────────┤
│                                        │
│ ▼ planner_reasoning (2 个工具)  [编辑]   │
│   ☑ think         内部推理思考          │
│   ☑ submit_plan   提交制作计划          │
│                                        │
│ ▼ seedance_generation (4 个工具) [编辑]  │
│   ☑ generate_video_t2v  文生视频        │
│   ☑ generate_video_i2v  图生视频        │
│   ☐ generate_video_r2v  参考视频生成    │
│   ☑ generate_video_extend 视频续拍     │
│                                        │
│                         [保存变更]       │
└──────────────────────────────────────┘
```

点击 Skill 名旁的 **[编辑]** → 弹出 Monaco Editor 显示该 Skill 的 SKILL.md 内容，可修改保存。

点击 **[+ 添加 Skill]** → 弹出对话框输入 Skill 名称 → 创建带模板的 SKILL.md → 自动刷新列表。

### Step 8: Agent 子图 (AgentSubFlowView) 联动

子图从 `fetchAgentTools` 获取工具列表。Step 3/6 修正后，API 返回该 Agent 真正配置的工具，子图自然正确。

工具节点可增加**点击查看 Skill 定义**的交互（点击后右侧面板切到对应 Skill 的编辑视图）。

---

## 完整数据流 + 实时性保障

```
SKILL.md (文件系统)
  ↓ scan()
SkillRegistry (内存, 热更新)
  ↓ 声明工具名
TOOL_REGISTRY (内存, 工具名→函数)
  ↓ DB available_tools 字段引用工具名
PromptManager (DB + Redis 30s TTL)
  ↓ update_tools() 清 Redis 缓存 → 立即生效
  ↓ BaseAgent.get_tools() 每次 run() 都读 DB 最新
Agent.run() → create_react_agent(llm, tools)
  ↓ WebSocket 推送 tool_call_start/end
前端 AgentSubFlowView + ToolCheckboxList
```

### 实时性保障（3 层变更各自的生效路径）

**1. 前端勾选/取消工具 → Agent 立即生效**

- PUT /agents/{id}/tools → `PromptManager.update_tools()` → 写 DB + `_invalidate_cache()` 清 Redis
- 下次 Agent.run() → `get_tools()` → Redis 未命中 → 查 DB → 拿到最新工具列表
- `_resolve_tools()` 从 TOOL_REGISTRY 解析函数 → `create_react_agent(llm, tools)` 用新工具

**2. 前端编辑 SKILL.md → Skill 元数据立即更新**

- PUT /skills/{name}/content → 写文件 → `SkillRegistry.scan()` → 内存中元数据更新
- 下次前端请求 /skills 或 /agents/{id}/tools → 返回新的 Skill 信息

**3. LangGraph 图无需重新编译**

- `_compiled_app` 是单例，图结构（节点/边）不变
- 每个节点函数 (planner_node 等) 调 Agent.run()
- Agent.run() 内部每次都动态解析工具，不缓存
- 所以工具变更对 LangGraph 是透明的

**注意**: 如果有**正在运行的工作流**，变更在当前运行的 Agent 节点完成后、下一个节点开始时才生效（每个节点入口调一次 `get_tools()`）。不会影响正在执行的节点中途换工具。

---

## 不涉及的范围

- 不改变 LangGraph 状态图结构
- 不改变 Agent 的 System Prompt 逻辑
- 不改变工具的实际执行逻辑

