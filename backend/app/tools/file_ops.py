"""文件操作工具 - 视频下载 + 最后帧提取"""

import asyncio
import os
import logging

import httpx

from app.config import get_settings
from app.tools import register_tool

logger = logging.getLogger(__name__)


@register_tool("download_video")
async def download_video(url: str, output_path: str | None = None) -> dict:
    """下载远程视频到本地。返回本地路径。"""
    settings = get_settings()
    if output_path is None:
        os.makedirs(settings.output_dir, exist_ok=True)
        filename = url.split("/")[-1].split("?")[0] or "video.mp4"
        if not filename.endswith(".mp4"):
            filename += ".mp4"
        output_path = os.path.join(settings.output_dir, filename)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)

    file_size = os.path.getsize(output_path)
    logger.info(f"Downloaded video: {url} -> {output_path} ({file_size} bytes)")

    return {
        "local_path": output_path,
        "file_size": file_size,
        "source_url": url,
    }


@register_tool("extract_last_frame")
async def extract_last_frame(video_path: str, output_path: str | None = None) -> dict:
    """用 ffmpeg 提取视频最后一帧为 PNG 图片。返回图片路径。"""
    if output_path is None:
        base = os.path.splitext(video_path)[0]
        output_path = f"{base}_last_frame.png"

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    duration_cmd = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await duration_cmd.communicate()
    if duration_cmd.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode()}")

    duration = float(stdout.decode().strip())
    seek_time = max(0, duration - 0.1)

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-ss", str(seek_time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg extract_last_frame failed: {stderr.decode()}")

    logger.info(f"Extracted last frame: {video_path} -> {output_path}")

    return {
        "frame_path": output_path,
        "source_video": video_path,
        "timestamp": seek_time,
    }
