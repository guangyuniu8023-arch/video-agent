"""外部视频生成 API — /api/v1/video/

正式的外部调用接口，供其他系统/Agent 调用。
内部复用 chat.py 的工作流启动逻辑。
"""

import asyncio
import uuid
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.graph.workflow import (
    get_workflow_app,
    create_initial_state,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_tasks: dict[str, asyncio.Task] = {}
_results: dict[str, dict] = {}


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="视频创作需求描述")
    uploaded_assets: list[dict] = Field(default_factory=list, description="上传素材 [{type, url}]")
    webhook_url: str | None = Field(None, description="完成后回调 URL (可选)")


class GenerateResponse(BaseModel):
    project_id: str
    status: str
    message: str


async def _run_and_store(project_id: str, initial_state: dict):
    """后台执行工作流，完成后存储结果"""
    try:
        app = get_workflow_app()
        final_state = await app.ainvoke(initial_state)
        _results[project_id] = {
            "status": final_state.get("current_phase", "unknown"),
            "final_video_url": final_state.get("final_video_path", ""),
            "raw_clips": final_state.get("raw_clips", []),
            "plan": final_state.get("plan"),
            "errors": final_state.get("generation_errors", []),
        }
    except asyncio.CancelledError:
        _results[project_id] = {"status": "cancelled", "errors": ["已取消"]}
    except Exception as e:
        logger.error(f"Video generation failed: {project_id}: {e}", exc_info=True)
        _results[project_id] = {"status": "error", "errors": [str(e)]}
    finally:
        _tasks.pop(project_id, None)


@router.post("/generate", response_model=GenerateResponse)
async def generate_video(req: GenerateRequest):
    """启动视频生成任务"""
    project_id = str(uuid.uuid4())

    initial_state = create_initial_state(
        user_request=req.prompt,
        project_id=project_id,
        uploaded_assets=req.uploaded_assets,
    )

    task = asyncio.create_task(_run_and_store(project_id, initial_state))
    _tasks[project_id] = task

    return GenerateResponse(
        project_id=project_id,
        status="processing",
        message="视频生成任务已启动",
    )


@router.get("/{project_id}/status")
async def get_video_status(project_id: str):
    """查询视频生成进度"""
    if project_id in _tasks:
        task = _tasks[project_id]
        return {
            "project_id": project_id,
            "status": "processing",
            "running": not task.done(),
        }

    if project_id in _results:
        result = _results[project_id]
        return {
            "project_id": project_id,
            "status": result["status"],
            "running": False,
        }

    raise HTTPException(404, f"项目 {project_id} 不存在")


@router.get("/{project_id}/result")
async def get_video_result(project_id: str):
    """获取视频生成结果"""
    if project_id in _tasks:
        task = _tasks[project_id]
        if not task.done():
            return {
                "project_id": project_id,
                "status": "processing",
                "message": "任务仍在执行中",
            }

    if project_id in _results:
        result = _results[project_id]
        return {
            "project_id": project_id,
            **result,
        }

    raise HTTPException(404, f"项目 {project_id} 不存在")


@router.post("/{project_id}/cancel")
async def cancel_video(project_id: str):
    """取消视频生成任务"""
    if project_id in _tasks:
        task = _tasks[project_id]
        if not task.done():
            task.cancel()
            _tasks.pop(project_id, None)
            _results[project_id] = {"status": "cancelled", "errors": ["用户取消"]}
            return {"project_id": project_id, "status": "cancelled"}
        return {"project_id": project_id, "status": "already_done"}

    raise HTTPException(404, f"项目 {project_id} 不存在")
