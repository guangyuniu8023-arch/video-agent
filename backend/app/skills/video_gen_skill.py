"""Agent-as-a-Tool — 将整个视频生成 Pipeline 包装为单个可调用 Skill

外部系统可通过此接口一次性调用完整的视频生成流程:
  输入: 故事描述 + 素材
  输出: 最终视频路径
"""

import logging

from app.graph.workflow import get_workflow_app, create_initial_state

logger = logging.getLogger(__name__)


async def video_generation_skill(
    story: str,
    assets: list[dict] | None = None,
    project_id: str | None = None,
) -> dict:
    """输入故事描述+角色+风格，输出完整视频。

    Args:
        story: 视频创作需求描述
        assets: 上传的素材 [{type, path, url}]
        project_id: 项目 ID (可选)

    Returns:
        {
            "video_url": str,
            "plan": dict,
            "clips_count": int,
            "quality_score": int,
            "status": "complete" | "error",
        }
    """
    app = get_workflow_app()
    initial_state = create_initial_state(
        user_request=story,
        project_id=project_id,
        uploaded_assets=assets or [],
    )

    try:
        final_state = await app.ainvoke(initial_state)
        return {
            "video_url": final_state.get("final_video_path"),
            "plan": final_state.get("plan"),
            "clips_count": len(final_state.get("raw_clips", [])),
            "quality_score": -1,
            "status": final_state.get("current_phase", "unknown"),
        }
    except Exception as e:
        logger.error(f"video_generation_skill failed: {e}", exc_info=True)
        return {
            "video_url": None,
            "plan": None,
            "clips_count": 0,
            "quality_score": -1,
            "status": "error",
            "error": str(e),
        }
