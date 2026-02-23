"""视频稳定化 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_stabilize

@tool
async def stabilize_video(input_path: str, output_path: str | None = None, shakiness: int = 5, accuracy: int = 15) -> dict:
    """视频稳定化（去抖）。两遍处理: 分析抖动 → 应用稳定。"""
    return await ffmpeg_stabilize(input_path, output_path, shakiness, accuracy)
