"""视频质量评估 — VLM 截帧评分"""
from langchain_core.tools import tool
from app.tools.analysis import evaluate_video

@tool
async def evaluate_video_quality(video_path: str, criteria: str = "overall") -> dict:
    """VLM 评估视频质量。从视频中提取关键帧，用 VLM 评分 0-100。criteria: overall/visual_quality/motion/composition"""
    return await evaluate_video(video_path, criteria)
