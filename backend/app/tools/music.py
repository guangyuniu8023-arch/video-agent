"""音乐生成工具 — Seedance 原生音频优先，备选 Suno API

当前实现: 利用 Seedance 生成时自带的原生音频作为 BGM。
后续: 接入 Suno 或字节内部音乐生成能力。
"""

import logging
import os

from app.tools import register_tool

logger = logging.getLogger(__name__)


@register_tool("generate_music")
async def generate_music(
    style: str = "cinematic",
    mood: str = "uplifting",
    duration: int = 30,
    output_dir: str = "./outputs",
) -> dict:
    """生成背景音乐。当前使用占位实现，优先依赖 Seedance 原生音频。

    Args:
        style: 音乐风格 (cinematic/electronic/acoustic/ambient)
        mood: 情绪 (uplifting/tense/calm/energetic)
        duration: 时长(秒)
        output_dir: 输出目录

    Returns:
        {"music_path": str, "style": str, "mood": str, "duration": int, "source": str}
    """
    logger.info(f"Music generation requested: style={style}, mood={mood}, duration={duration}s")

    os.makedirs(output_dir, exist_ok=True)

    return {
        "music_path": None,
        "style": style,
        "mood": mood,
        "duration": duration,
        "source": "seedance_native",
        "message": "使用 Seedance 原生音频，无需单独生成 BGM。如需独立配乐，请接入 Suno API。",
    }
