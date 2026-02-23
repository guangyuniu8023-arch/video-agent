"""图生视频 — 调用 Seedance 2.0 API"""
import json
from langchain_core.tools import tool
from app.tools.seedance import seedance_i2v

@tool
async def generate_video_i2v(image_urls: list[str], prompt: str, duration: int = 15) -> str:
    """图生视频: 用参考图片+文本生成视频（角色一致性/首帧参考）。返回 JSON。"""
    result = await seedance_i2v(image_urls, prompt, duration)
    return json.dumps(result, ensure_ascii=False)
