"""Producer Agent (ReAct) - 资源调度域

职责: 按 plan.scenes 调用 Seedance API 生成视频 → 质量检测 → 失败重试
"""

import json
import logging

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agents.base import BaseAgent
from app.config import get_settings
from app.graph.callbacks import push_agent_status, push_log_entry, StreamingWSCallback
from app.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

PRODUCER_SYSTEM_PROMPT = """\
你是一位专业的视频制作人 (Producer)。你的任务是根据制作计划 (plan) 调用视频生成工具，逐镜生成视频。

## 工作流程
1. 分析 plan 中的 scenes 列表
2. 按 scene_id 顺序逐个处理每个分镜
3. 根据每个分镜的 generation_mode 选择对应的工具:
   - t2v → 调用 generate_video_t2v
   - i2v → 调用 generate_video_i2v（需要图片 URL）
   - r2v → 调用 generate_video_r2v（需要参考视频 URL）
   - extend → 调用 generate_video_extend（需要前一镜的 video_url）
4. 每次生成后记录结果
5. 全部完成后调用 report_results 汇报所有结果

## 衔接策略执行
- extend 策略: 使用前一镜的 video_url 调用 generate_video_extend
- first_frame_ref 策略: 使用前一镜的 last_frame_url 调用 generate_video_i2v
- camera_ref 策略: 使用参考视频 URL 调用 generate_video_r2v
- hard_cut / none: 直接使用 generate_video_t2v

## 注意事项
- 按顺序生成，因为后续分镜可能依赖前一镜的输出
- 如果某镜生成失败，记录错误继续下一镜
- 全部生成完成后，直接输出结果 JSON 数组，格式:
[{"scene_id": 1, "video_url": "...", "last_frame_url": "...", "task_id": "...", "status": "success"}]
"""


class ProducerAgent(BaseAgent):
    """Producer Agent - 调用 Seedance API 逐镜生成视频"""

    def __init__(self, prompt_manager=None):
        super().__init__("producer", prompt_manager)
        self._tool_names = [
            "generate_video_t2v",
            "generate_video_i2v",
            "generate_video_r2v",
            "generate_video_extend",
        ]

    def _default_prompt(self) -> str:
        return PRODUCER_SYSTEM_PROMPT

    @property
    def _tools(self):
        return [TOOL_REGISTRY[n] for n in self._tool_names if n in TOOL_REGISTRY]

    def get_tool_names(self) -> list[str]:
        return self._tool_names

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
                temperature=0.3,
                max_tokens=4096,
                **extra,
            )
        if settings.openai_api_key:
            return ChatOpenAI(
                model="gpt-4o",
                api_key=settings.openai_api_key,
                temperature=0.3,
                max_tokens=4096,
                **extra,
            )
        raise RuntimeError(
            "No LLM configured. Set ARK_LLM_API_KEY + ARK_LLM_ENDPOINT_ID or OPENAI_API_KEY"
        )

    async def run(self, state: dict) -> dict:
        """执行 Producer Agent，逐镜生成视频"""
        project_id = state.get("project_id", "default")
        plan = state.get("plan")

        if not plan or not plan.get("scenes"):
            await push_agent_status(project_id, "producer", "error", error="无有效制作计划")
            return {
                "raw_clips": [],
                "generation_errors": [{"error": "无有效制作计划"}],
                "current_phase": "error",
            }

        scenes = plan["scenes"]
        scenes_to_regen = state.get("scenes_to_regenerate", [])
        if scenes_to_regen:
            scenes = [s for s in scenes if s["scene_id"] in scenes_to_regen]

        await push_agent_status(project_id, "producer", "running",
                                data={"total_scenes": len(scenes)})
        await push_log_entry(project_id, "producer",
                             f"开始生成视频: {len(scenes)} 个分镜")

        try:
            system_prompt = await self.get_system_prompt()
            streaming_cb = StreamingWSCallback(project_id, "producer")
            llm = self._get_llm(callbacks=[streaming_cb])

            tools = await self.get_dynamic_tools(state) or self._tools
            agent = create_react_agent(llm, tools)

            task_description = self._build_task_description(state, scenes)

            result = await agent.ainvoke({
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=task_description),
                ]
            })

            raw_clips, errors = self._extract_results(result, state)

            await push_log_entry(
                project_id, "producer",
                f"生成完成: {len(raw_clips)} 个视频片段, {len(errors)} 个错误"
            )
            await push_agent_status(project_id, "producer", "success",
                                    data={"clips_count": len(raw_clips)})

            existing_clips = state.get("raw_clips", [])
            if scenes_to_regen:
                existing_ids = {c["scene_id"] for c in existing_clips}
                new_ids = {c["scene_id"] for c in raw_clips}
                merged = [c for c in existing_clips if c["scene_id"] not in new_ids]
                merged.extend(raw_clips)
                raw_clips = sorted(merged, key=lambda c: c["scene_id"])

            return {
                "raw_clips": raw_clips,
                "generation_errors": errors,
                "scenes_to_regenerate": [],
                "current_phase": "editing",
            }

        except Exception as e:
            logger.error(f"Producer failed: {e}", exc_info=True)
            await push_agent_status(project_id, "producer", "error", error=str(e))
            await push_log_entry(project_id, "producer", f"生成失败: {e}")
            return {
                "raw_clips": state.get("raw_clips", []),
                "generation_errors": [{"error": str(e)}],
                "current_phase": "error",
            }

    def _build_task_description(self, state: dict, scenes: list[dict]) -> str:
        """构建给 Producer LLM 的任务描述"""
        plan = state["plan"]
        existing_clips = state.get("raw_clips", [])

        parts = [f"## 制作计划\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```"]

        if existing_clips:
            parts.append(
                f"\n## 已生成的视频片段\n```json\n"
                f"{json.dumps(existing_clips, ensure_ascii=False, indent=2)}\n```"
            )

        parts.append(f"\n## 待生成的分镜\n请按顺序处理以下 {len(scenes)} 个分镜:")
        for scene in scenes:
            parts.append(
                f"\n### 分镜 {scene['scene_id']}\n"
                f"- 时长: {scene.get('duration', 15)}s\n"
                f"- 模式: {scene.get('generation_mode', 't2v')}\n"
                f"- Prompt: {scene.get('seedance_prompt', '')}\n"
                f"- 衔接: {scene.get('transition_from_prev', {}).get('strategy', 'none')}"
            )

        parts.append("\n请逐个调用生成工具，完成后调用 report_results 汇报结果。")
        return "\n".join(parts)

    def _extract_results(self, result: dict, state: dict) -> tuple[list[dict], list[dict]]:
        """从 Agent 输出中提取生成结果"""
        raw_clips = []
        errors = []
        messages = result.get("messages", [])

        for msg in messages:
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc["name"] == "report_results":
                        try:
                            results = json.loads(tc["args"]["results_json"])
                            for r in results:
                                if r.get("status") == "success":
                                    raw_clips.append({
                                        "scene_id": r["scene_id"],
                                        "video_url": r.get("video_url", ""),
                                        "last_frame_url": r.get("last_frame_url", ""),
                                        "task_id": r.get("task_id", ""),
                                        "quality_score": r.get("quality_score", 0),
                                    })
                                else:
                                    errors.append({
                                        "scene_id": r.get("scene_id"),
                                        "error": r.get("error", "unknown"),
                                    })
                        except (json.JSONDecodeError, KeyError):
                            continue

        if not raw_clips and not errors:
            raw_clips, errors = self._extract_from_tool_responses(messages)

        return raw_clips, errors

    def _extract_from_tool_responses(self, messages) -> tuple[list[dict], list[dict]]:
        """从工具调用响应中提取结果"""
        raw_clips = []
        errors = []
        scene_counter = 0

        for msg in messages:
            if hasattr(msg, "name") and msg.name and msg.name.startswith("generate_video_"):
                scene_counter += 1
                try:
                    content = msg.content if hasattr(msg, "content") else str(msg)
                    data = json.loads(content)
                    raw_clips.append({
                        "scene_id": scene_counter,
                        "video_url": data.get("video_url", ""),
                        "last_frame_url": data.get("last_frame_url", ""),
                        "task_id": data.get("task_id", ""),
                        "quality_score": 0,
                    })
                except (json.JSONDecodeError, AttributeError):
                    errors.append({
                        "scene_id": scene_counter,
                        "error": "Failed to parse tool response",
                    })

        return raw_clips, errors
