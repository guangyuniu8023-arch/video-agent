"""VLM 分析/评估工具 - 视频质量评估 + 衔接评估

通过将视频截帧为图片，发送给 VLM (doubao-seed-2-0-pro) 进行评估。
"""

import asyncio
import base64
import json
import logging
import os
import uuid

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.tools import register_tool

logger = logging.getLogger(__name__)


def _get_vlm() -> ChatOpenAI:
    settings = get_settings()
    llm_key = settings.ark_llm_api_key or settings.ark_api_key
    if not llm_key or not settings.ark_llm_endpoint_id:
        raise RuntimeError("VLM requires ARK_LLM_API_KEY + ARK_LLM_ENDPOINT_ID")
    return ChatOpenAI(
        model=settings.ark_llm_endpoint_id,
        api_key=llm_key,
        base_url=settings.ark_llm_base_url,
        temperature=0.1,
        max_tokens=1024,
    )


async def _extract_frames(video_path: str, count: int = 4) -> list[str]:
    """从视频中均匀提取 N 帧，返回 base64 编码的图片列表"""
    output_dir = os.path.join(get_settings().output_dir, f"frames_{uuid.uuid4().hex[:8]}")
    os.makedirs(output_dir, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    duration = float(stdout.decode().strip())

    frames = []
    for i in range(count):
        t = duration * (i + 0.5) / count
        frame_path = os.path.join(output_dir, f"frame_{i:02d}.jpg")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-ss", str(t),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "3",
            frame_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0 and os.path.exists(frame_path):
            with open(frame_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            frames.append(b64)
            os.remove(frame_path)

    try:
        os.rmdir(output_dir)
    except OSError:
        pass

    return frames


def _build_image_content(frames_b64: list[str], text: str) -> list[dict]:
    """构建多模态消息内容 (图片 + 文本)"""
    content = []
    for b64 in frames_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })
    content.append({"type": "text", "text": text})
    return content


def _parse_score(text: str) -> int:
    """从 VLM 回复中提取分数"""
    import re
    patterns = [
        r'"score"\s*:\s*(\d+)',
        r'(\d+)\s*/\s*100',
        r'(\d+)\s*分',
        r'\b(\d{1,3})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            score = int(match.group(1))
            if 0 <= score <= 100:
                return score
    return 50


@register_tool("evaluate_video")
async def evaluate_video(
    video_path: str,
    criteria: str = "overall",
) -> dict:
    """VLM 评估视频质量。从视频中提取关键帧，用 VLM 评分 0-100。

    criteria: 评估维度，可选 overall / visual_quality / motion / composition
    """
    frames = await _extract_frames(video_path, count=4)
    if not frames:
        return {"score": 0, "reason": "无法提取视频帧", "criteria": criteria}

    criteria_prompts = {
        "overall": (
            "请评估这段视频的整体质量。从以下维度综合评分:\n"
            "1. 画面清晰度和质量\n2. 运动流畅度和自然度\n"
            "3. 构图和美感\n4. 主体完整性\n5. 色彩和光照"
        ),
        "visual_quality": "请评估这段视频的画面清晰度、细节丰富度、无伪影程度",
        "motion": "请评估这段视频中运动/动作的流畅度和自然度，是否有明显的抖动或不连贯",
        "composition": "请评估这段视频的构图、色彩搭配、光照效果和整体美感",
    }

    prompt_text = (
        f"你是一个专业的视频质量评估专家。\n\n"
        f"以下是从一段视频中均匀提取的 {len(frames)} 帧关键画面。\n\n"
        f"评估维度: {criteria_prompts.get(criteria, criteria_prompts['overall'])}\n\n"
        f"请给出 0-100 的评分，并简述理由。\n"
        f"输出格式: {{\"score\": <0-100整数>, \"reason\": \"简短理由\"}}"
    )

    vlm = _get_vlm()
    content = _build_image_content(frames, prompt_text)

    try:
        response = await vlm.ainvoke([HumanMessage(content=content)])
        reply = response.content

        score = _parse_score(reply)
        try:
            parsed = json.loads(reply)
            reason = parsed.get("reason", reply[:200])
        except json.JSONDecodeError:
            reason = reply[:200]

        logger.info(f"Video evaluation: {video_path} -> {score}/100 ({criteria})")
        return {"score": score, "reason": reason, "criteria": criteria}
    except Exception as e:
        logger.error(f"VLM evaluation failed: {e}", exc_info=True)
        return {"score": 60, "reason": f"VLM 评估异常，给予默认分: {e}", "criteria": criteria}


@register_tool("evaluate_transition")
async def evaluate_transition(
    video1_path: str,
    video2_path: str,
) -> dict:
    """VLM 评估两段视频的衔接质量。

    提取第一段视频的最后 2 帧和第二段视频的前 2 帧，评估视觉连续性。
    返回 0-100 分: >80 可直接拼接, 50-80 需过渡效果, <50 建议重新生成。
    """
    proc1 = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video1_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout1, _ = await proc1.communicate()
    dur1 = float(stdout1.decode().strip())

    frames = []
    timestamps = [
        (video1_path, max(0, dur1 - 1.0)),
        (video1_path, max(0, dur1 - 0.1)),
        (video2_path, 0.1),
        (video2_path, 1.0),
    ]

    output_dir = os.path.join(get_settings().output_dir, f"trans_{uuid.uuid4().hex[:8]}")
    os.makedirs(output_dir, exist_ok=True)

    for idx, (vpath, t) in enumerate(timestamps):
        frame_path = os.path.join(output_dir, f"f_{idx}.jpg")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-ss", str(t),
            "-i", vpath,
            "-vframes", "1",
            "-q:v", "3",
            frame_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode == 0 and os.path.exists(frame_path):
            with open(frame_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            frames.append(b64)
            os.remove(frame_path)

    try:
        os.rmdir(output_dir)
    except OSError:
        pass

    if len(frames) < 2:
        return {"score": 50, "reason": "无法提取足够的帧进行衔接评估", "suggestion": "transition"}

    prompt_text = (
        "你是一个专业的视频剪辑专家。\n\n"
        "以下图片按时间顺序排列:\n"
        "- 前两张: 第一段视频的结尾帧\n"
        "- 后两张: 第二段视频的开头帧\n\n"
        "请评估这两段视频的衔接质量，考虑:\n"
        "1. 场景/背景连续性\n2. 主体外观一致性\n3. 运动方向连贯性\n"
        "4. 色彩/光照一致性\n5. 构图过渡自然度\n\n"
        "评分标准:\n"
        "- 80-100: 衔接自然，可直接拼接\n"
        "- 50-79: 需要添加过渡效果\n"
        "- 0-49: 衔接差，建议重新生成\n\n"
        "输出格式: {\"score\": <0-100>, \"reason\": \"简短理由\", "
        "\"suggestion\": \"direct_concat 或 transition 或 regenerate\"}"
    )

    vlm = _get_vlm()
    content = _build_image_content(frames, prompt_text)

    try:
        response = await vlm.ainvoke([HumanMessage(content=content)])
        reply = response.content

        score = _parse_score(reply)
        try:
            parsed = json.loads(reply)
            reason = parsed.get("reason", reply[:200])
            suggestion = parsed.get("suggestion", "transition")
        except json.JSONDecodeError:
            reason = reply[:200]
            suggestion = "direct_concat" if score >= 80 else ("transition" if score >= 50 else "regenerate")

        logger.info(f"Transition evaluation: {video1_path} <-> {video2_path} -> {score}/100")
        return {"score": score, "reason": reason, "suggestion": suggestion}
    except Exception as e:
        logger.error(f"VLM transition evaluation failed: {e}", exc_info=True)
        return {"score": 65, "reason": f"VLM 评估异常，给予默认分: {e}", "suggestion": "transition"}
