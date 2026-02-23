# 后端 Plan — API、Skill、Agent、工作流

## 一、数据模型 (7 张表)

| 表 | 用途 | 关键字段 |
|----|------|----------|
| agent_configs | Agent 配置 | id, name, agent_type, execution_mode, parent_id, system_prompt, available_tools, bypass |
| canvas_nodes | 画布节点 | id, node_type, ref_id, position_x/y, config, parent_canvas |
| canvas_edges | 画布连线 | source_id, target_id, edge_type (flow/tool) |
| mcp_servers | MCP 服务 | id, transport, url, status, discovered_tools |
| workflow_versions | 版本快照 | version, is_published, snapshot (JSON) |
| prompt_versions | Prompt 历史 | agent_id, version, system_prompt, is_active |
| routing_rules | 路由规则 | name, target_type, match_description, priority, enabled |

### canvas_nodes 关键字段

- `config`: JSON，容器用 `{"items": [...]}` 存内容
- `parent_canvas`: null=主画布，非 null=嵌套在容器内

---

## 二、画布 API (canvas.py)

### 2.1 端点

- `GET/POST /admin/canvas/nodes` — 列表/创建
- `PUT/DELETE /admin/canvas/nodes/{id}` — 更新/删除
- `PUT /admin/canvas/nodes/{id}/config` — 更新容器 config
- `POST /admin/canvas/edges` — 创建边
- `DELETE /admin/canvas/edges/{id}` — 删除边

### 2.2 连线副作用

**创建 tool 边时**:
- Agent → Skill/SkillGroup: 同步 available_tools (Skill 名或容器内 items)
- Agent → Agent: 设置 target.parent_id，target 变 SubAgent
- Agent → MCP/McpGroup: 加入 MCP discovered_tools

**删除 tool 边时**:
- 从 source Agent 的 available_tools 移除对应项
- Agent→Agent: 清除 target.parent_id

**flow 边变更**: 触发 `rebuild_workflow()` 热重建 LangGraph

---

## 三、Skill 机制

### 3.1 Skill 自包含 (Agent Skills 规范)

```
skills/{name}/
├── SKILL.md       # YAML frontmatter (name/title/description/trigger) + Markdown 指令
└── scripts/
    └── tool.py    # @tool 装饰的 Python 函数
```

- `SkillRegistry.scan()`: 扫描 SKILL.md + scripts/*.py
- `_auto_register_scripts()`: 自动注册到 TOOL_REGISTRY
- 14 个 Skill 全部自包含，无 tool_source 外部引用

### 3.2 SKILL.md 协议 (4 字段)

```yaml
---
name: web_search
title: 网络搜索
description: 搜索互联网获取参考
trigger: [always]
---
```

- 不绑定 Agent，Agent-Skill 映射由 DB available_tools 管理
- trigger: 规则匹配 (always / uploaded_assets 包含 image / raw_clips > 1 等)

### 3.3 动态工具加载

`GenericAgent._resolve_tools(available_tools, state)`:
1. 查 TOOL_REGISTRY (Skill 名) → SkillRegistry trigger 过滤 → 返回工具
2. 查 agent_configs (SubAgent id) → `_wrap_sub_agent()` 包装为 @tool
3. 查 MCP discovered_tools → 包装为 LangChain Tool

---

## 四、GenericAgent 与 Sub-Agent

### 4.1 执行模式

- `execution_mode = react`: LLM 逐个决定调用工具 (串行 ReAct)
- `execution_mode = parallel`: 所有子 Agent 并发执行，结果合并

### 4.2 Agent-as-a-Tool

```python
def _wrap_sub_agent(self, sub_config, parent_state):
    """将 Sub-Agent 包装为 @tool"""
    @tool
    async def sub_agent_tool(task: str) -> str:
        result = await GenericAgent().run(sub_config, {**parent_state, "sub_task": task})
        return json.dumps(result)
    sub_agent_tool.name = sub_config.id
    sub_agent_tool.description = f"{sub_config.name}: {sub_config.description}"
    return sub_agent_tool
```

- available_tools 中的 Agent id → 查 agent_configs → 包装为可调用工具
- 父 Agent 的 LLM 通过 ReAct 决定是否/何时调用

### 4.3 子 Agent 接入扩展

| 类型 | 当前支持 | 扩展方向 |
|------|----------|----------|
| 同系统 Agent | ✓ agent_configs | — |
| 外部 LangGraph | — | HTTP 包装 / RemoteGraph，agent_type=remote |
| 其他架构 | — | MCP 工具 / HTTP 适配器包装为 Skill |

---

## 五、动态 LangGraph (workflow.py)

- `build_workflow(flow_edges)`: 从 canvas_edges (type=flow) 构建拓扑
- 入口: 无入边的节点
- 节点函数: `_generic_node_fn` 包装，内部 `GenericAgent().run(config, state)`
- Router / QualityGate: 保持原有条件路由逻辑
- `rebuild_workflow()`: flow 边变更时热重建

---

## 六、其他 API 模块

### 6.1 Admin API (admin.py)

- Agent CRUD
- Skill 元数据、文件管理 (scripts/references/assets)
- 路由规则 CRUD

### 6.2 MCP API (mcp.py)

- MCP 服务 CRUD、重连
- 工具列表 (discovered_tools)

### 6.3 Skill 创建器 (skill_creator.py)

- LLM 对话生成 Skill 定义
- 保存到文件系统

### 6.4 版本管理 (publish.py)

- 保存/发布/加载/删除版本
- 快照: canvas_nodes + canvas_edges + agent_configs (仅画布上的 Agent)

### 6.5 Video API (video_api.py)

- 外部调用: generate / status / result / cancel

---

## 七、目录结构 (关键文件)

```
backend/app/
├── agents/generic.py      # GenericAgent 通用执行器
├── graph/workflow.py     # 动态 LangGraph 构建
├── skills/registry.py    # SkillRegistry + scripts 自动注册
├── api/
│   ├── canvas.py         # 画布 CRUD + 连线副作用
│   ├── admin.py          # Agent/Skill/路由
│   ├── mcp.py            # MCP 服务
│   ├── publish.py        # 版本管理
│   └── video_api.py      # 外部视频 API
├── services/mcp_client.py
└── models/database.py
```
