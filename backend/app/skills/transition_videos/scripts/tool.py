"""过渡效果 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_transition

@tool
async def transition_videos(input1: str, input2: str, transition_type: str = "fade", duration: float = 1.0, output_path: str | None = None) -> dict:
    """在两段视频之间添加过渡效果。支持: fade/dissolve/wipeleft/slideright 等。"""
    return await ffmpeg_transition(input1, input2, transition_type, duration, output_path)
