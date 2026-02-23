"""文生视频 — 调用 Seedance 2.0 API"""
import json
from langchain_core.tools import tool
from app.tools.seedance import seedance_t2v

@tool
async def generate_video_t2v(prompt: str, duration: int = 15, ratio: str = "16:9") -> str:
    """文生视频: 根据文本描述生成视频。返回 JSON 包含 video_url 和 last_frame_url。"""
    result = await seedance_t2v(prompt, duration, ratio)
    return json.dumps(result, ensure_ascii=False)
