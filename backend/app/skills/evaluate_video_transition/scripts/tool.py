"""衔接质量评估 — VLM 评估两段视频衔接"""
from langchain_core.tools import tool
from app.tools.analysis import evaluate_transition

@tool
async def evaluate_video_transition(video1_path: str, video2_path: str) -> dict:
    """VLM 评估两段视频的衔接质量。返回 0-100 分: >80 直接拼接, 50-80 需过渡, <50 重新生成。"""
    return await evaluate_transition(video1_path, video2_path)
