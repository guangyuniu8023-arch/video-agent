"""色彩校正 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_color_correct

@tool
async def color_correct_video(input_path: str, output_path: str | None = None, brightness: float = 0.0, contrast: float = 1.0, saturation: float = 1.0, gamma: float = 1.0) -> dict:
    """色彩校正。调节亮度/对比度/饱和度/伽马。"""
    return await ffmpeg_color_correct(input_path, output_path, brightness, contrast, saturation, gamma)
