"""视频裁剪 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_trim

@tool
async def trim_video(input_path: str, start: float, end: float, output_path: str | None = None) -> dict:
    """裁剪视频片段。指定起止时间(秒)，提取子片段。"""
    return await ffmpeg_trim(input_path, start, end, output_path)
