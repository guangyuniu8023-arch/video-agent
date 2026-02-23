"""Seedance 2.0 API 封装 - 基于火山方舟 SDK (volcengine-python-sdk)

SDK 参数:
  create: model, content, duration, ratio, resolution, return_last_frame, generate_audio, ...
  get: task_id
  响应: ContentGenerationTask (status, content.video_url, content.last_frame_url, ...)
"""

import asyncio
import logging
from dataclasses import dataclass, field

from app.tools import register_tool

logger = logging.getLogger(__name__)


@dataclass
class SeedanceResult:
    task_id: str
    video_url: str
    last_frame_url: str = ""
    duration: int = 0


class SeedanceClient:
    """Seedance 2.0 API 客户端 (同步 SDK，异步包装)"""

    def __init__(self, api_key: str, endpoint_id: str):
        from volcenginesdkarkruntime import Ark
        self.client = Ark(api_key=api_key)
        self.endpoint_id = endpoint_id

    async def text_to_video(
        self,
        prompt: str,
        duration: int = 15,
        ratio: str = "16:9",
        return_last_frame: bool = True,
    ) -> SeedanceResult:
        """文生视频 (t2v)"""
        content = [{"type": "text", "text": prompt}]
        return await self._generate(
            content, duration=duration, ratio=ratio,
            return_last_frame=return_last_frame,
        )

    async def image_to_video(
        self,
        image_urls: list[str],
        prompt: str,
        duration: int = 15,
        return_last_frame: bool = True,
    ) -> SeedanceResult:
        """图生视频 (i2v) - 用于角色一致性"""
        content = []
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        content.append({"type": "text", "text": prompt})
        return await self._generate(
            content, duration=duration,
            return_last_frame=return_last_frame,
        )

    async def reference_video_to_video(
        self,
        video_urls: list[str],
        prompt: str,
        duration: int = 15,
        return_last_frame: bool = True,
    ) -> SeedanceResult:
        """参考视频生视频 (r2v) - 用于运镜参考和续拍"""
        content = []
        for url in video_urls:
            content.append({
                "type": "video_url",
                "video_url": {"url": url},
                "role": "reference_video",
            })
        content.append({"type": "text", "text": prompt})
        return await self._generate(
            content, duration=duration,
            return_last_frame=return_last_frame,
        )

    async def extend_video(
        self,
        video_url: str,
        prompt: str,
        duration: int = 15,
        return_last_frame: bool = True,
    ) -> SeedanceResult:
        """视频延长/续拍 (extend)"""
        content = [
            {"type": "video_url", "video_url": {"url": video_url}, "role": "reference_video"},
            {"type": "text", "text": prompt},
        ]
        return await self._generate(
            content, duration=duration,
            return_last_frame=return_last_frame,
        )

    async def _generate(self, content: list[dict], **kwargs) -> SeedanceResult:
        """提交生成任务并轮询结果"""
        loop = asyncio.get_event_loop()
        task = await loop.run_in_executor(
            None,
            lambda: self.client.content_generation.tasks.create(
                model=self.endpoint_id,
                content=content,
                **kwargs,
            )
        )
        logger.info(f"Seedance task created: {task.id}")
        return await self._poll_task(task.id)

    async def _poll_task(self, task_id: str, timeout: int = 300) -> SeedanceResult:
        """轮询任务结果"""
        loop = asyncio.get_event_loop()
        start = loop.time()
        while loop.time() - start < timeout:
            result = await loop.run_in_executor(
                None,
                lambda: self.client.content_generation.tasks.get(task_id=task_id)
            )
            if result.status == "succeeded":
                return SeedanceResult(
                    task_id=task_id,
                    video_url=result.content.video_url,
                    last_frame_url=getattr(result.content, "last_frame_url", ""),
                    duration=getattr(result, "duration", 0),
                )
            elif result.status == "failed":
                error_msg = getattr(result.error, "message", "Unknown error")
                raise RuntimeError(f"Seedance task {task_id} failed: {error_msg}")
            await asyncio.sleep(5)
        raise TimeoutError(f"Seedance task {task_id} timed out after {timeout}s")


_client: SeedanceClient | None = None


def get_seedance_client() -> SeedanceClient:
    global _client
    if _client is None:
        from app.config import get_settings
        settings = get_settings()
        if not settings.ark_api_key or not settings.ark_seedance_endpoint_id:
            raise RuntimeError(
                "ARK_API_KEY and ARK_SEEDANCE_ENDPOINT_ID must be set in .env"
            )
        _client = SeedanceClient(
            api_key=settings.ark_api_key,
            endpoint_id=settings.ark_seedance_endpoint_id,
        )
    return _client


@register_tool("seedance_t2v")
async def seedance_t2v(
    prompt: str, duration: int = 15, ratio: str = "16:9"
) -> dict:
    """文生视频: 根据文本描述生成视频"""
    client = get_seedance_client()
    result = await client.text_to_video(prompt, duration, ratio)
    return {
        "task_id": result.task_id,
        "video_url": result.video_url,
        "last_frame_url": result.last_frame_url,
    }


@register_tool("seedance_i2v")
async def seedance_i2v(
    image_urls: list[str], prompt: str, duration: int = 15
) -> dict:
    """图生视频: 用角色参考图生成视频，保持角色一致性"""
    client = get_seedance_client()
    result = await client.image_to_video(image_urls, prompt, duration)
    return {
        "task_id": result.task_id,
        "video_url": result.video_url,
        "last_frame_url": result.last_frame_url,
    }


@register_tool("seedance_r2v")
async def seedance_r2v(
    video_urls: list[str], prompt: str, duration: int = 15
) -> dict:
    """参考视频生视频: 用参考视频控制运镜/风格"""
    client = get_seedance_client()
    result = await client.reference_video_to_video(video_urls, prompt, duration)
    return {
        "task_id": result.task_id,
        "video_url": result.video_url,
        "last_frame_url": result.last_frame_url,
    }


@register_tool("seedance_extend")
async def seedance_extend(
    video_url: str, prompt: str, duration: int = 15
) -> dict:
    """视频延长: 从上一镜直接续拍，保持连续性"""
    client = get_seedance_client()
    result = await client.extend_video(video_url, prompt, duration)
    return {
        "task_id": result.task_id,
        "video_url": result.video_url,
        "last_frame_url": result.last_frame_url,
    }
