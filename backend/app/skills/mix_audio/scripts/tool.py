"""音频混合 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_audio_mix

@tool
async def mix_audio(video_path: str, audio_path: str, output_path: str | None = None, video_volume: float = 1.0, audio_volume: float = 0.3) -> dict:
    """将背景音乐与视频混合。可分别调节音量。"""
    return await ffmpeg_audio_mix(video_path, audio_path, output_path, video_volume, audio_volume)
