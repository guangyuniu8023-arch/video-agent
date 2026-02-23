---
name: Skill 1对1 重构
overview: 1 Skill = 1 Tool 通用协议。SKILL.md 只有 4 个字段 (name/title/description/trigger)，不绑定 Agent。Agent-Skill 映射由 DB available_tools 管理。Planner 改为纯 LLM 调用 + web_search Skill。Producer 删 report_results，Editor 删 submit_edit_result。trigger 只做规则匹配，语义决策交给 System Prompt。
todos:
  - id: rebuild-skill-dirs
    content: "删除旧 17 个 Skill 目录，重建 15 个 (Planner: web_search, Producer: 4, Editor: 9) + 新建 web_search 工具"
    status: completed
  - id: simplify-registry
    content: "SkillRegistry 简化: SkillInfo 只留 name/title/description/trigger，去掉 agent 字段，match_skills 改为接收 tool_names 列表"
    status: completed
  - id: refactor-planner
    content: Planner 改为纯 LLM 调用 (不走 ReAct)，删除 think/submit_plan，新增 web_search Skill (always 加载)
    status: completed
  - id: refactor-producer-editor
    content: Producer 删 report_results，Editor 删 submit_edit_result，改 System Prompt 指导直接输出 JSON
    status: completed
  - id: fix-dynamic-loading
    content: BaseAgent.get_dynamic_tools 改为从 DB available_tools 取工具名列表 → SkillRegistry 匹配 trigger → TOOL_REGISTRY 解析函数
    status: completed
  - id: fix-api-frontend
    content: admin API + 前端工具 Tab 适配简化后的 SKILL.md (显示 title + trigger + 编辑)
    status: completed
  - id: seed-verify-restart
    content: 种子数据修正 + 编译验证 + 重启
    status: completed
isProject: false
---

# Skill 1:1 重构 (第二轮精简)

## 设计原则

- **1 Skill = 1 Tool**: 每个 SKILL.md 描述一个工具
- **SKILL.md 不绑定 Agent**: 只是通用的工具描述文件，Agent-Skill 映射由 DB `available_tools` 配置
- **SKILL.md 只有 4 个字段**: `name` (技术标识), `title` (人类可读名), `description` (一句话说明), `trigger` (规则条件)
- **语义决策交给 System Prompt**: 模型自己判断是否调用某个工具，SKILL.md 的 trigger 只做代码级的规则过滤
- **真实能力才是 Skill**: 调 API、跑 FFmpeg、VLM 评估。纯输出格式校验不算 Skill

## SKILL.md 通用协议

```yaml
---
name: web_search
title: 网络搜索
description: 搜索互联网获取风格参考、场景描述等创作灵感
trigger:
  - always
---

搜索互联网获取与视频创作相关的参考信息。
Planner 自行判断是否需要搜索。
```

4 个字段，没有 `agent`、`version`、`tags`、`parameters`、`trigger_type`。

## 改动清单

### 1. Planner 改造

**从**: ReAct Agent + think + submit_plan (2 个假工具)
**到**: 纯 LLM 调用 + web_search (1 个真实 Skill)

改动:

- 删除 `think`、`submit_plan` 的 @tool 定义和 TOOL_REGISTRY 注册
- 删除 `skills/think/` 和 `skills/submit_plan/` 目录
- `planner.py` 的 `run()` 改为直接 `llm.ainvoke()` 而不是 `create_react_agent()`
- 但如果有工具 (如 web_search)，仍走 ReAct
- System Prompt 末尾改为: "直接输出完整的制作计划 JSON" (去掉 "必须调用 submit_plan")
- 新建 `tools/web_search.py` + `skills/web_search/SKILL.md`

### 2. Producer 精简

删除 `report_results`:

- 删除 @tool 定义和 TOOL_REGISTRY 注册
- 删除 `skills/report_results/` 目录
- System Prompt 改为: "完成所有分镜后，直接输出结果 JSON 数组"
- `_extract_results()` 已有从 tool responses 解析结果的兜底逻辑

保留 4 个真实 Skill: `generate_video_t2v`, `generate_video_i2v`, `generate_video_r2v`, `generate_video_extend`

### 3. Editor 精简

删除 `submit_edit_result`:

- 删除 @tool 定义和 TOOL_REGISTRY 注册
- 删除 `skills/submit_edit_result/` 目录
- System Prompt 改为: "处理完成后直接输出结果 JSON"

保留 9 个真实 Skill: evaluate_video_transition, evaluate_video_quality, trim_video, concat_videos, transition_videos, normalize_video, color_correct_video, stabilize_video, mix_audio

### 4. SkillRegistry 简化

`SkillInfo` 字段: `name`, `title`, `description`, `trigger`, `path`, `readme`
去掉: `agent`, `version`, `tags`, `required_state_fields`, `output_state_fields`

去掉 `get_skills_for_agent(agent_id)` (不再按 agent 过滤)

`match_skills()` 签名改为:

```python
def match_skills(self, tool_names: list[str], state: dict) -> list[SkillInfo]:
    """从给定的工具名列表中，根据 trigger 条件筛选需要加载的"""
```

### 5. BaseAgent.get_dynamic_tools 改造

```python
async def get_dynamic_tools(self, state: dict) -> list:
    # 1. 从 DB 获取该 Agent 配置的工具名列表
    tool_names = await self.get_available_tool_names()
    # 2. SkillRegistry 根据 trigger 过滤
    registry = get_skill_registry()
    matched = registry.match_skills(tool_names, state)
    matched_names = [s.name for s in matched]
    # 3. TOOL_REGISTRY 解析为函数
    return self._resolve_tools(matched_names)
```

数据流: DB available_tools → SkillRegistry trigger 过滤 → TOOL_REGISTRY 解析

### 6. 最终 Skill 清单 (15 个)

Planner (DB 配置 1 个):

- `web_search` — always

Producer (DB 配置 4 个):

- `generate_video_t2v` — always
- `generate_video_i2v` — uploaded_assets 包含 image / scenes 有 i2v
- `generate_video_r2v` — uploaded_assets 包含 video / scenes 有 r2v
- `generate_video_extend` — scenes 有 extend / raw_clips >= 1

Editor (DB 配置 9 个):

- `evaluate_video_quality` — always
- `trim_video` — always
- `evaluate_video_transition` — raw_clips > 1
- `concat_videos` — raw_clips > 1
- `transition_videos` — raw_clips > 1
- `normalize_video` — raw_clips > 1
- `color_correct_video` — raw_clips > 1
- `stabilize_video` — raw_clips >= 1
- `mix_audio` — plan.music.generate == true

### 7. admin API 适配

`GET /agents/{id}/tools` 返回:

```json
{
  "agent_id": "producer",
  "current_tools": ["generate_video_t2v", ...],
  "skills": [
    {
      "name": "generate_video_t2v",
      "title": "文生视频",
      "description": "纯文本 prompt 生成视频",
      "trigger": ["always"]
    }
  ]
}
```

---

## 不涉及的范围

- 不改 LangGraph 图结构
- 不改 WebSocket 事件
- 不改 State 定义 (VideoProjectState)
- 不改 Seedance/FFmpeg 工具的实际执行逻辑

