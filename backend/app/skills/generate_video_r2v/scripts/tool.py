"""参考视频生成 — 调用 Seedance 2.0 API"""
import json
from langchain_core.tools import tool
from app.tools.seedance import seedance_r2v

@tool
async def generate_video_r2v(video_urls: list[str], prompt: str, duration: int = 15) -> str:
    """参考视频生成: 用参考视频控制运镜/风格。返回 JSON。"""
    result = await seedance_r2v(video_urls, prompt, duration)
    return json.dumps(result, ensure_ascii=False)
