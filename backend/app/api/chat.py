"""对话式创建接口 - 启动视频生成工作流 + Human-in-the-loop 回复 + 文件上传"""

import os
import uuid
import asyncio
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.graph.workflow import (
    get_workflow_app,
    create_initial_state,
    submit_human_feedback,
    has_pending_feedback,
)
from app.graph.callbacks import push_agent_status, push_log_entry
from app.api.websocket import ws_manager
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

_running_tasks: dict[str, asyncio.Task] = {}


class StartRequest(BaseModel):
    message: str = Field(..., description="用户的视频创作需求描述")
    project_id: str | None = Field(None, description="项目 ID（不传则自动生成）")
    uploaded_assets: list[dict] = Field(default_factory=list, description="上传的素材")


class StartResponse(BaseModel):
    project_id: str
    status: str
    message: str


class ReplyRequest(BaseModel):
    message: str = Field(..., description="用户对 Agent 追问的回复")


class ReplyResponse(BaseModel):
    project_id: str
    status: str
    message: str


async def _run_workflow(project_id: str, initial_state: dict):
    """后台执行工作流"""
    try:
        app = get_workflow_app()
        await push_log_entry(project_id, "system", "工作流启动")

        final_state = await app.ainvoke(initial_state)

        phase = final_state.get("current_phase", "unknown")
        if phase == "complete":
            await push_log_entry(
                project_id, "system",
                f"工作流完成! 最终视频: {final_state.get('final_video_path', 'N/A')}"
            )
        elif phase == "error":
            errors = final_state.get("generation_errors", [])
            await push_log_entry(project_id, "system", f"工作流出错: {errors}")
        else:
            await push_log_entry(project_id, "system", f"工作流结束, 阶段: {phase}")

    except asyncio.CancelledError:
        await push_log_entry(project_id, "system", "工作流已取消")
    except Exception as e:
        logger.error(f"Workflow failed for project {project_id}: {e}", exc_info=True)
        await push_log_entry(project_id, "system", f"工作流异常: {e}")
        await push_agent_status(project_id, "system", "error", error=str(e))
    finally:
        _running_tasks.pop(project_id, None)


@router.post("/start", response_model=StartResponse)
async def start_chat(req: StartRequest):
    """启动新的视频创建工作流"""
    project_id = req.project_id or str(uuid.uuid4())

    if project_id in _running_tasks:
        task = _running_tasks[project_id]
        if not task.done():
            return StartResponse(
                project_id=project_id,
                status="already_running",
                message="该项目已有正在运行的工作流",
            )

    initial_state = create_initial_state(
        user_request=req.message,
        project_id=project_id,
        uploaded_assets=req.uploaded_assets,
    )

    task = asyncio.create_task(_run_workflow(project_id, initial_state))
    _running_tasks[project_id] = task

    return StartResponse(
        project_id=project_id,
        status="started",
        message="工作流已启动，请通过 WebSocket 连接获取实时状态",
    )


@router.post("/reply/{project_id}", response_model=ReplyResponse)
async def reply_to_agent(project_id: str, req: ReplyRequest):
    """回复 Agent 的追问（Human-in-the-loop）"""
    if not has_pending_feedback(project_id):
        raise HTTPException(
            status_code=400,
            detail="该项目当前没有等待回复的追问",
        )

    submit_human_feedback(project_id, req.message)

    return ReplyResponse(
        project_id=project_id,
        status="replied",
        message="回复已提交，工作流将继续执行",
    )


@router.get("/status/{project_id}")
async def get_status(project_id: str):
    """查询工作流运行状态"""
    pending = has_pending_feedback(project_id)
    if project_id in _running_tasks:
        task = _running_tasks[project_id]
        return {
            "project_id": project_id,
            "running": not task.done(),
            "cancelled": task.cancelled(),
            "waiting_for_reply": pending,
        }
    return {
        "project_id": project_id,
        "running": False,
        "waiting_for_reply": pending,
        "message": "无运行中的工作流",
    }


@router.post("/stop/{project_id}")
async def stop_workflow(project_id: str):
    """停止正在运行的工作流"""
    if project_id in _running_tasks:
        task = _running_tasks[project_id]
        task.cancel()
        _running_tasks.pop(project_id, None)
        return {"status": "cancelled", "project_id": project_id}
    return {"status": "not_found", "project_id": project_id}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), project_id: str | None = None):
    """上传角色参考图片或素材文件"""
    settings = get_settings()
    pid = project_id or "shared"
    upload_dir = os.path.join(settings.upload_dir, pid)
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "upload")[1] or ".png"
    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    file_path = os.path.join(upload_dir, safe_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    file_url = f"/files/uploads/{pid}/{safe_name}"

    return {
        "filename": safe_name,
        "original_name": file.filename,
        "path": file_path,
        "url": file_url,
        "size": len(content),
        "content_type": file.content_type,
    }
