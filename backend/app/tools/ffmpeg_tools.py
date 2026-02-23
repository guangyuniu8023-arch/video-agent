"""FFmpeg 工具集 - 7 个独立视频编辑工具

所有工具通过 asyncio.create_subprocess_exec 调用 ffmpeg 命令行。
"""

import asyncio
import os
import logging
import uuid

from app.config import get_settings
from app.tools import register_tool

logger = logging.getLogger(__name__)


def _output_dir() -> str:
    settings = get_settings()
    os.makedirs(settings.output_dir, exist_ok=True)
    return settings.output_dir


def _gen_path(suffix: str = ".mp4") -> str:
    return os.path.join(_output_dir(), f"{uuid.uuid4().hex[:12]}{suffix}")


async def _run_ffmpeg(*args: str) -> str:
    """执行 ffmpeg 命令，返回 stderr 输出。失败时抛异常。"""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    stderr_text = stderr.decode()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {stderr_text[-500:]}")
    return stderr_text


# ── 1. 裁剪 ─────────────────────────────────────────────────────

@register_tool("ffmpeg_trim")
async def ffmpeg_trim(
    input_path: str,
    start: float,
    end: float,
    output_path: str | None = None,
) -> dict:
    """裁剪视频片段。指定起止时间(秒)，提取子片段。"""
    output_path = output_path or _gen_path()
    duration = end - start

    await _run_ffmpeg(
        "-ss", str(start),
        "-i", input_path,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path,
    )

    logger.info(f"Trimmed: {input_path} [{start}s-{end}s] -> {output_path}")
    return {"output_path": output_path, "start": start, "end": end, "duration": duration}


# ── 2. 拼接 ─────────────────────────────────────────────────────

@register_tool("ffmpeg_concat")
async def ffmpeg_concat(
    input_paths: list[str],
    output_path: str | None = None,
) -> dict:
    """按顺序拼接多个视频文件。使用 concat demuxer。"""
    output_path = output_path or _gen_path()

    concat_file = os.path.join(_output_dir(), f"concat_{uuid.uuid4().hex[:8]}.txt")
    with open(concat_file, "w") as f:
        for path in input_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")

    try:
        await _run_ffmpeg(
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        )
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

    logger.info(f"Concatenated {len(input_paths)} files -> {output_path}")
    return {"output_path": output_path, "input_count": len(input_paths)}


# ── 3. 过渡效果 ─────────────────────────────────────────────────

@register_tool("ffmpeg_transition")
async def ffmpeg_transition(
    input1: str,
    input2: str,
    transition_type: str = "fade",
    duration: float = 1.0,
    output_path: str | None = None,
) -> dict:
    """在两段视频之间添加过渡效果。

    支持的过渡类型: fade, dissolve, wipeleft, wiperight, wipeup, wipedown,
    slideleft, slideright, slideup, slidedown, circlecrop, rectcrop, distance,
    fadeblack, fadewhite, smoothleft, smoothright
    """
    output_path = output_path or _gen_path()

    dur1_proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input1,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    dur1_out, _ = await dur1_proc.communicate()
    dur1 = float(dur1_out.decode().strip())
    offset = max(0, dur1 - duration)

    await _run_ffmpeg(
        "-i", input1,
        "-i", input2,
        "-filter_complex",
        f"[0:v][1:v]xfade=transition={transition_type}:duration={duration}:offset={offset}[v];"
        f"[0:a][1:a]acrossfade=d={duration}[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        output_path,
    )

    logger.info(f"Transition ({transition_type}, {duration}s): {input1} + {input2} -> {output_path}")
    return {
        "output_path": output_path,
        "transition_type": transition_type,
        "transition_duration": duration,
    }


# ── 4. 统一分辨率/帧率 ──────────────────────────────────────────

@register_tool("ffmpeg_normalize")
async def ffmpeg_normalize(
    input_path: str,
    output_path: str | None = None,
    resolution: str = "1920x1080",
    fps: int = 30,
) -> dict:
    """统一视频分辨率和帧率。确保所有片段规格一致后再拼接。"""
    output_path = output_path or _gen_path()
    width, height = resolution.split("x")

    await _run_ffmpeg(
        "-i", input_path,
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "aac",
        "-ar", "44100",
        output_path,
    )

    logger.info(f"Normalized: {input_path} -> {output_path} ({resolution}, {fps}fps)")
    return {"output_path": output_path, "resolution": resolution, "fps": fps}


# ── 5. 色彩一致性 ────────────────────────────────────────────────

@register_tool("ffmpeg_color_correct")
async def ffmpeg_color_correct(
    input_path: str,
    output_path: str | None = None,
    brightness: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    gamma: float = 1.0,
) -> dict:
    """色彩校正。调节亮度/对比度/饱和度/伽马，确保多片段色彩一致。

    brightness: 亮度偏移 (-1.0 ~ 1.0, 默认 0)
    contrast: 对比度倍数 (0.0 ~ 3.0, 默认 1.0)
    saturation: 饱和度倍数 (0.0 ~ 3.0, 默认 1.0)
    gamma: 伽马值 (0.1 ~ 10.0, 默认 1.0)
    """
    output_path = output_path or _gen_path()

    await _run_ffmpeg(
        "-i", input_path,
        "-vf", f"eq=brightness={brightness}:contrast={contrast}"
               f":saturation={saturation}:gamma={gamma}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-c:a", "copy",
        output_path,
    )

    logger.info(f"Color corrected: {input_path} -> {output_path}")
    return {
        "output_path": output_path,
        "brightness": brightness,
        "contrast": contrast,
        "saturation": saturation,
        "gamma": gamma,
    }


# ── 6. 视频稳定化 ────────────────────────────────────────────────

@register_tool("ffmpeg_stabilize")
async def ffmpeg_stabilize(
    input_path: str,
    output_path: str | None = None,
    shakiness: int = 5,
    accuracy: int = 15,
) -> dict:
    """视频稳定化（去抖）。两遍处理: 分析抖动 → 应用稳定。

    shakiness: 抖动检测灵敏度 (1-10, 默认 5)
    accuracy: 检测精度 (1-15, 默认 15)
    """
    output_path = output_path or _gen_path()

    transforms_file = os.path.join(
        _output_dir(), f"transforms_{uuid.uuid4().hex[:8]}.trf"
    )

    try:
        await _run_ffmpeg(
            "-i", input_path,
            "-vf", f"vidstabdetect=shakiness={shakiness}:accuracy={accuracy}"
                   f":result={transforms_file}",
            "-f", "null", "-",
        )

        await _run_ffmpeg(
            "-i", input_path,
            "-vf", f"vidstabtransform=input={transforms_file}:smoothing=10,"
                   f"unsharp=5:5:0.8:3:3:0.4",
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "copy",
            output_path,
        )
    finally:
        if os.path.exists(transforms_file):
            os.remove(transforms_file)

    logger.info(f"Stabilized: {input_path} -> {output_path}")
    return {"output_path": output_path, "shakiness": shakiness, "accuracy": accuracy}


# ── 7. 音频混合 ──────────────────────────────────────────────────

@register_tool("ffmpeg_audio_mix")
async def ffmpeg_audio_mix(
    video_path: str,
    audio_path: str,
    output_path: str | None = None,
    video_volume: float = 1.0,
    audio_volume: float = 0.3,
) -> dict:
    """将背景音乐/音频与视频混合。可分别调节音量。

    video_volume: 视频原声音量 (0.0 ~ 2.0, 默认 1.0)
    audio_volume: 叠加音频音量 (0.0 ~ 2.0, 默认 0.3)
    """
    output_path = output_path or _gen_path()

    await _run_ffmpeg(
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex",
        f"[0:a]volume={video_volume}[a0];"
        f"[1:a]volume={audio_volume}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        output_path,
    )

    logger.info(f"Audio mixed: {video_path} + {audio_path} -> {output_path}")
    return {
        "output_path": output_path,
        "video_volume": video_volume,
        "audio_volume": audio_volume,
    }
