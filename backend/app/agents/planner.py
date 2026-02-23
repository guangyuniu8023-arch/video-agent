"""Planner Agent - 创意理解域

职责: 理解用户意图 → 创建角色 → 构建世界观 → 拆解分镜 → 为每镜生成 Seedance prompt
无工具时纯 LLM 调用，有工具 (如 web_search) 时走 ReAct。
"""

import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agents.base import BaseAgent
from app.config import get_settings
from app.graph.callbacks import push_agent_status, push_log_entry, StreamingWSCallback

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """\
你是一位专业的AI视频导演和编剧。你的任务是将用户的视频创意需求转化为结构化的制作计划。

## 工作流程
根据用户需求，自行判断需要完成哪些步骤:
- 分析用户输入，提取关键信息（主题、风格、时长、角色、场景等）
- 如有角色，创建角色卡（visual_description + consistency_prompt）
- 确定视觉风格、色调、光照、运镜偏好
- 规划分镜:
  - 简单场景 (<=15s): 一个完整 prompt，使用时间标记 [0s-5s]...[5s-10s]...
  - 复杂场景 (>15s): 拆分多个分镜（每镜 <=15s），标注衔接策略
- 为每个分镜生成高质量的英文 Seedance prompt

如果用户提到了特定的风格、电影、动画或你不确定的视觉参考，可以使用 web_search 工具搜索相关信息。

## Seedance Prompt 最佳实践
- 使用**英文**描述，简洁而精确
- 明确指定: 主体动作、摄影机运动、光照氛围、画面构图
- 角色描述保持一致性（重复关键外观特征）
- 时间标记格式: [0s-5s] description, [5s-10s] description

## 分镜衔接策略（按优先级）
1. **extend**: 前一镜续拍（最佳连续性），适用于连续动作
2. **first_frame_ref**: 取前一镜最后帧作参考图 (i2v)，适用于同场景切角度
3. **camera_ref**: 用参考视频控制运镜 (r2v)，适用于风格统一
4. **hard_cut**: 硬切+后期过渡，适用于场景切换

## 输出格式
直接输出完整的制作计划 JSON，格式如下:
{
    "project_type": "short 或 long",
    "total_duration": 预计总时长(秒),
    "characters": [
        {
            "name": "角色名",
            "visual_description": "详细外观描述(英文)",
            "consistency_prompt": "一致性提示词(英文)"
        }
    ],
    "world_setting": {
        "visual_style": "视觉风格",
        "color_palette": "色调",
        "lighting": "光照风格",
        "camera_preferences": "运镜偏好",
        "mood": "整体情绪"
    },
    "scenes": [
        {
            "scene_id": 1,
            "duration": 15,
            "seedance_prompt": "英文prompt",
            "generation_mode": "t2v 或 i2v 或 r2v 或 extend",
            "transition_from_prev": {
                "strategy": "extend 或 first_frame_ref 或 camera_ref 或 hard_cut 或 none"
            },
            "description": "这一镜的中文说明"
        }
    ],
    "music": {
        "style": "音乐风格",
        "mood_curve": "情绪曲线描述",
        "generate": true
    }
}
"""


class PlannerAgent(BaseAgent):
    """Planner Agent - 将用户创意转化为结构化制作计划"""

    def __init__(self, prompt_manager=None):
        super().__init__("planner", prompt_manager)
        self._tools = []

    def _default_prompt(self) -> str:
        return PLANNER_SYSTEM_PROMPT

    def get_tool_names(self) -> list[str]:
        return ["web_search"]

    def _get_llm(self, callbacks=None):
        settings = get_settings()
        extra = {"streaming": True}
        if callbacks:
            extra["callbacks"] = callbacks
        llm_key = settings.ark_llm_api_key or settings.ark_api_key
        if llm_key and settings.ark_llm_endpoint_id:
            return ChatOpenAI(
                model=settings.ark_llm_endpoint_id,
                api_key=llm_key,
                base_url=settings.ark_llm_base_url,
                temperature=0.7,
                max_tokens=4096,
                **extra,
            )
        if settings.openai_api_key:
            return ChatOpenAI(
                model="gpt-4o",
                api_key=settings.openai_api_key,
                temperature=0.7,
                max_tokens=4096,
                **extra,
            )
        raise RuntimeError(
            "No LLM configured. Set ARK_LLM_API_KEY + ARK_LLM_ENDPOINT_ID or OPENAI_API_KEY"
        )

    async def run(self, state: dict) -> dict:
        project_id = state.get("project_id", "default")

        await push_agent_status(project_id, "planner", "running")
        await push_log_entry(project_id, "planner", "开始分析用户需求...")

        try:
            system_prompt = await self.get_system_prompt()
            streaming_cb = StreamingWSCallback(project_id, "planner")
            llm = self._get_llm(callbacks=[streaming_cb])

            user_message = state["user_request"]
            if state.get("uploaded_assets"):
                asset_desc = ", ".join(
                    f"{a['type']}: {a.get('url', a.get('path', 'unknown'))}"
                    for a in state["uploaded_assets"]
                )
                user_message += f"\n\n用户上传的素材: {asset_desc}"

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]

            tools = await self.get_dynamic_tools(state)
            if tools:
                agent = create_react_agent(llm, tools)
                result = await agent.ainvoke({"messages": messages})
            else:
                result = await llm.ainvoke(messages)
                result = {"messages": [result]}

            plan = self._extract_plan(result)

            if plan is None:
                reply = self._extract_text_reply(result)
                await push_log_entry(project_id, "planner", f"需要更多信息: {reply[:100]}")
                await push_agent_status(project_id, "planner", "waiting")
                return {
                    "plan": None,
                    "current_phase": "planning",
                    "needs_clarification": True,
                    "clarification_question": reply,
                }

            await push_log_entry(project_id, "planner", f"计划生成完成: {len(plan.get('scenes', []))} 个分镜")
            await push_agent_status(project_id, "planner", "success")

            return {
                "plan": plan,
                "current_phase": "producing",
                "needs_clarification": False,
                "clarification_question": "",
            }

        except Exception as e:
            logger.error(f"Planner failed: {e}", exc_info=True)
            await push_agent_status(project_id, "planner", "error", error=str(e))
            await push_log_entry(project_id, "planner", f"计划生成失败: {e}")
            return {
                "plan": None,
                "current_phase": "error",
                "needs_clarification": False,
                "clarification_question": "",
            }

    def _extract_plan(self, result: dict) -> dict | None:
        messages = result.get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", None) or str(msg)
            if not content or len(content) < 20:
                continue
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                candidate = json.loads(content[start:end])
                if "scenes" in candidate:
                    return candidate
            except (ValueError, json.JSONDecodeError):
                continue
        return None

    def _extract_text_reply(self, result: dict) -> str:
        messages = result.get("messages", [])
        for msg in reversed(messages):
            content = getattr(msg, "content", None)
            if content and isinstance(content, str) and len(content) > 2:
                if not content.startswith("{"):
                    return content
        return "请描述你想创作的视频内容，例如：主题、风格、时长、角色等。"
