"""视频续拍 — 调用 Seedance 2.0 API"""
import json
from langchain_core.tools import tool
from app.tools.seedance import seedance_extend

@tool
async def generate_video_extend(video_url: str, prompt: str, duration: int = 15) -> str:
    """视频续拍: 从上一镜末尾续拍，保持最佳连续性。返回 JSON。"""
    result = await seedance_extend(video_url, prompt, duration)
    return json.dumps(result, ensure_ascii=False)
