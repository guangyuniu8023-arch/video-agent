"""视频拼接 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_concat

@tool
async def concat_videos(input_paths: list[str], output_path: str | None = None) -> dict:
    """按顺序拼接多个视频文件。"""
    return await ffmpeg_concat(input_paths, output_path)
