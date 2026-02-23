"""Editor Agent (ReAct) - 后期合成域

职责: 衔接评估 → 裁剪不自然帧 → 轨道校正 → 过渡效果 → 拼接成片 → 音频处理
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

from app.tools.analysis import evaluate_transition, evaluate_video
from app.tools.ffmpeg_tools import (
    ffmpeg_trim,
    ffmpeg_concat,
    ffmpeg_transition,
    ffmpeg_normalize,
    ffmpeg_color_correct,
    ffmpeg_stabilize,
    ffmpeg_audio_mix,
)
from app.tools.file_ops import download_video

logger = logging.getLogger(__name__)

EDITOR_SYSTEM_PROMPT = """\
你是一位专业的视频后期剪辑师 (Editor)。你的任务是将 Producer 生成的多段原始视频片段 (raw_clips) \
合成为一部完整流畅的最终视频。

## 工作流程

### 第一步: 了解素材
分析收到的所有视频片段信息 (scene_id, local_path, duration 等)。

### 第二步: 轨道校正 (如果需要)
- 检查所有片段的分辨率和帧率是否一致
- 如不一致，使用 normalize_video 统一为 1920x1080 / 30fps
- 必要时使用 color_correct_video 做色彩校正

### 第三步: 衔接评估 (多段视频时)
对相邻的两段视频调用 evaluate_video_transition:
- 评分 > 80: 直接拼接，无需过渡效果
- 评分 50-80: 裁剪头尾不自然帧 (0.5-1.5s)，添加过渡效果 (fade/dissolve)
- 评分 < 50: 标记该对需要重新生成（输出到 scenes_to_regenerate）

### 第四步: 裁剪 (如需)
对需要裁剪的片段使用 trim_video:
- 去除头部 0.5-1.5s 的不自然生成帧
- 去除尾部 0.5-1.5s 的衰减帧

### 第五步: 合成
- 如果只有 1 段 → 无需拼接
- 如果有多段且衔接分 > 80 → concat_videos 直接拼接
- 如果有多段且 50-80 → transition_videos 添加过渡
- 使用 concat_videos 做最终拼接

### 第六步: 音频处理
- 默认保留 Seedance 原生音频
- 如需叠加 BGM，使用 mix_audio

### 特殊情况
- 只有 1 段短视频 (<=15s): 通常只需简单检查即可，不需要复杂处理
- 所有衔接评分 < 50: 标记需要重新生成，不进行拼接

## 输出要求
处理完成后，直接输出结果 JSON:
{
    "final_video_path": "最终视频的本地路径",
    "edit_actions": [{"action": "操作名", "detail": "详情"}],
    "scenes_to_regenerate": [],
    "summary": "编辑操作摘要"
}

## 注意
- 所有视频文件路径都是本地路径
- 操作是在本地文件上进行的
- 保持谨慎：宁可少处理也不要过度处理导致画质下降
"""


@tool
async def evaluate_video_transition(video1_path: str, video2_path: str) -> str:
    """评估两段视频的衔接质量。返回 0-100 分和建议 (direct_concat/transition/regenerate)。"""
    result = await evaluate_transition(video1_path, video2_path)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["evaluate_video_transition"] = evaluate_video_transition


@tool
async def evaluate_video_quality(video_path: str, criteria: str = "overall") -> str:
    """评估视频质量。返回 0-100 分。criteria 可选: overall/visual_quality/motion/composition。"""
    result = await evaluate_video(video_path, criteria)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["evaluate_video_quality"] = evaluate_video_quality


@tool
async def trim_video(input_path: str, start: float, end: float) -> str:
    """裁剪视频：指定起止时间(秒)。用于去除头尾不自然帧。"""
    result = await ffmpeg_trim(input_path, start, end)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["trim_video"] = trim_video


@tool
async def concat_videos(input_paths: list[str]) -> str:
    """按顺序拼接多段视频。输入路径列表，输出合并后的视频路径。"""
    result = await ffmpeg_concat(input_paths)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["concat_videos"] = concat_videos


@tool
async def transition_videos(
    input1: str, input2: str,
    transition_type: str = "fade", duration: float = 1.0,
) -> str:
    """在两段视频之间添加过渡效果。transition_type: fade/dissolve/wipeleft/slideright 等。"""
    result = await ffmpeg_transition(input1, input2, transition_type, duration)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["transition_videos"] = transition_videos


@tool
async def normalize_video(
    input_path: str, resolution: str = "1920x1080", fps: int = 30,
) -> str:
    """统一视频的分辨率和帧率。确保所有片段规格一致。"""
    result = await ffmpeg_normalize(input_path, resolution=resolution, fps=fps)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["normalize_video"] = normalize_video


@tool
async def color_correct_video(
    input_path: str,
    brightness: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
) -> str:
    """色彩校正: 调整亮度/对比度/饱和度以保持片段间色彩一致。"""
    result = await ffmpeg_color_correct(
        input_path, brightness=brightness, contrast=contrast, saturation=saturation,
    )
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["color_correct_video"] = color_correct_video


@tool
async def stabilize_video(input_path: str) -> str:
    """视频稳定化(去抖)。"""
    result = await ffmpeg_stabilize(input_path)
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["stabilize_video"] = stabilize_video


@tool
async def mix_audio(
    video_path: str, audio_path: str,
    video_volume: float = 1.0, audio_volume: float = 0.3,
) -> str:
    """将背景音乐与视频混合。可调节原声和 BGM 的音量比。"""
    result = await ffmpeg_audio_mix(
        video_path, audio_path,
        video_volume=video_volume, audio_volume=audio_volume,
    )
    return json.dumps(result, ensure_ascii=False)

TOOL_REGISTRY["mix_audio"] = mix_audio


class EditorAgent(BaseAgent):
    """Editor Agent - 视频后期合成"""

    def __init__(self, prompt_manager=None):
        super().__init__("editor", prompt_manager)
        self._tools = [
            evaluate_video_transition,
            evaluate_video_quality,
            trim_video,
            concat_videos,
            transition_videos,
            normalize_video,
            color_correct_video,
            stabilize_video,
            mix_audio,
        ]

    def _default_prompt(self) -> str:
        return EDITOR_SYSTEM_PROMPT

    def get_tool_names(self) -> list[str]:
        return [t.name for t in self._tools]

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
                temperature=0.2,
                max_tokens=4096,
                **extra,
            )
        if settings.openai_api_key:
            return ChatOpenAI(
                model="gpt-4o",
                api_key=settings.openai_api_key,
                temperature=0.2,
                max_tokens=4096,
                **extra,
            )
        raise RuntimeError(
            "No LLM configured. Set ARK_LLM_API_KEY + ARK_LLM_ENDPOINT_ID or OPENAI_API_KEY"
        )

    async def run(self, state: dict) -> dict:
        """执行 Editor Agent，后期合成视频"""
        project_id = state.get("project_id", "default")
        raw_clips = state.get("raw_clips", [])

        if not raw_clips:
            await push_agent_status(project_id, "editor", "error", error="无可编辑的视频片段")
            return {
                "final_video_path": None,
                "edit_log": [{"action": "error", "detail": "无可编辑的视频片段"}],
                "current_phase": "error",
            }

        await push_agent_status(project_id, "editor", "running",
                                data={"clips_count": len(raw_clips)})
        await push_log_entry(project_id, "editor",
                             f"开始后期处理: {len(raw_clips)} 个片段")

        if len(raw_clips) == 1:
            return await self._handle_single_clip(state, raw_clips[0])

        try:
            system_prompt = await self.get_system_prompt()
            streaming_cb = StreamingWSCallback(project_id, "editor")
            llm = self._get_llm(callbacks=[streaming_cb])

            tools = await self.get_dynamic_tools(state) or self._tools
            agent = create_react_agent(llm, tools)
            task_description = self._build_task_description(state)

            result = await agent.ainvoke({
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=task_description),
                ]
            })

            edit_result = self._extract_result(result)

            final_path = edit_result.get("final_video_path", "")
            edit_log = edit_result.get("edit_actions", [])
            scenes_to_regen = edit_result.get("scenes_to_regenerate", [])

            await push_log_entry(project_id, "editor",
                                 f"后期处理完成: {edit_result.get('summary', 'done')}")
            await push_agent_status(project_id, "editor", "success")

            return {
                "final_video_path": final_path,
                "edit_log": edit_log,
                "scenes_to_regenerate": scenes_to_regen,
                "current_phase": "complete" if not scenes_to_regen else "producing",
            }

        except Exception as e:
            logger.error(f"Editor failed: {e}", exc_info=True)
            await push_agent_status(project_id, "editor", "error", error=str(e))
            await push_log_entry(project_id, "editor", f"后期处理失败: {e}")

            fallback_path = raw_clips[0].get("local_path", raw_clips[0].get("video_url", ""))
            return {
                "final_video_path": fallback_path,
                "edit_log": [{"action": "error", "detail": str(e)}],
                "current_phase": "complete",
            }

    async def _handle_single_clip(self, state: dict, clip: dict) -> dict:
        """单片段简化处理: 跳过衔接评估和拼接"""
        project_id = state.get("project_id", "default")
        local_path = clip.get("local_path", "")

        await push_log_entry(project_id, "editor", "单片段视频，简化处理")
        await push_agent_status(project_id, "editor", "success")

        return {
            "final_video_path": local_path,
            "edit_log": [{"action": "single_clip_passthrough", "detail": "单片段无需拼接"}],
            "current_phase": "complete",
        }

    def _build_task_description(self, state: dict) -> str:
        """构建 Editor Agent 的任务描述"""
        raw_clips = state.get("raw_clips", [])
        plan = state.get("plan", {})
        scenes = plan.get("scenes", [])

        parts = [
            f"## 待处理的视频片段 ({len(raw_clips)} 段)\n",
            "```json",
            json.dumps(raw_clips, ensure_ascii=False, indent=2),
            "```\n",
        ]

        if scenes:
            parts.append("## 分镜计划 (含衔接策略)\n")
            for scene in scenes:
                transition = scene.get("transition_from_prev", {})
                strategy = transition.get("strategy", "none")
                parts.append(
                    f"- 分镜 {scene.get('scene_id', '?')}: "
                    f"时长 {scene.get('duration', '?')}s, "
                    f"衔接策略: {strategy}"
                )
            parts.append("")

        parts.append(
            "请按照工作流程处理这些片段：\n"
            "1. 检查分辨率/帧率一致性\n"
            "2. 评估相邻片段衔接质量\n"
            "3. 根据衔接评分决定裁剪/过渡策略\n"
            "4. 执行合成\n"
            "5. 提交最终结果\n\n"
            "注意: 所有文件路径使用 local_path 字段的值。"
        )

        return "\n".join(parts)

    def _extract_result(self, result: dict) -> dict:
        """从 Agent 输出中提取编辑结果"""
        messages = result.get("messages", [])

        for msg in reversed(messages):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "submit_edit_result":
                        try:
                            return json.loads(tc["args"]["result_json"])
                        except (json.JSONDecodeError, KeyError):
                            continue

        for msg in reversed(messages):
            content = getattr(msg, "content", "") or ""
            if len(content) < 10:
                continue
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                candidate = json.loads(content[start:end])
                if "final_video_path" in candidate:
                    return candidate
            except (ValueError, json.JSONDecodeError):
                continue

        return {
            "final_video_path": "",
            "edit_actions": [{"action": "no_result", "detail": "Agent 未返回有效结果"}],
            "scenes_to_regenerate": [],
            "summary": "未获取到编辑结果",
        }
