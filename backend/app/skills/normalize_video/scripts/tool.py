"""规格统一 — FFmpeg"""
from langchain_core.tools import tool
from app.tools.ffmpeg_tools import ffmpeg_normalize

@tool
async def normalize_video(input_path: str, output_path: str | None = None, resolution: str = "1920x1080", fps: int = 30) -> dict:
    """统一视频分辨率和帧率。确保所有片段规格一致后再拼接。"""
    return await ffmpeg_normalize(input_path, output_path, resolution, fps)
