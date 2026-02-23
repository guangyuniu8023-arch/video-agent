"""Video Agent - FastAPI 入口

Sprint 4: 数据库初始化 + PromptManager/RouteManager 依赖注入
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api.websocket import router as ws_router
from app.api.chat import router as chat_router
from app.api.projects import router as projects_router
from app.api.admin import router as admin_router
from app.api.canvas import router as canvas_router
from app.api.mcp import router as mcp_router
from app.api.skill_creator import router as skill_creator_router
from app.api.video_api import router as video_api_router
from app.api.publish import router as publish_router

logger = logging.getLogger(__name__)


async def _init_services():
    """初始化 DB 表 + PromptManager + RouteManager + 默认 Prompt 种子数据"""
    from app.models.database import init_db
    from app.services.prompt_manager import PromptManager
    from app.services.route_manager import RouteManager
    from app.agents.base import set_global_prompt_manager
    try:
        from app.graph.workflow import set_route_manager
    except ImportError:
        set_route_manager = lambda rm: None

    redis_client = None
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning(f"Redis not available, running without cache: {e}")
        redis_client = None

    try:
        await init_db()
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.warning(f"Database init failed, running in memory-only mode: {e}")
        return redis_client

    pm = PromptManager(redis_client=redis_client)
    rm = RouteManager(redis_client=redis_client)

    set_global_prompt_manager(pm)
    set_route_manager(rm)

    await _seed_default_prompts(pm)
    logger.info("PromptManager + RouteManager initialized")
    return redis_client


async def _seed_default_prompts(pm):
    """首次启动时写入 agent_configs + PromptVersion 默认数据"""
    from app.graph.workflow import ROUTER_SYSTEM_PROMPT
    from app.agents.planner import PLANNER_SYSTEM_PROMPT
    from app.agents.producer import PRODUCER_SYSTEM_PROMPT
    from app.agents.editor import EDITOR_SYSTEM_PROMPT
    from app.models.database import AgentConfig, get_session_factory
    from sqlalchemy import select

    agent_seeds = [
        {"id": "router", "name": "Router", "description": "意图路由 - 根据规则表判断执行路径",
         "agent_type": "function", "system_prompt": ROUTER_SYSTEM_PROMPT, "available_tools": []},
        {"id": "planner", "name": "Planner", "description": "创意理解 - 理解需求、创建角色、构建世界观、拆解分镜",
         "agent_type": "react", "system_prompt": PLANNER_SYSTEM_PROMPT, "available_tools": ["web_search"]},
        {"id": "producer", "name": "Producer", "description": "资源调度 - 调用 Seedance API 生成视频",
         "agent_type": "react", "system_prompt": PRODUCER_SYSTEM_PROMPT,
         "available_tools": ["generate_video_t2v", "generate_video_i2v", "generate_video_r2v", "generate_video_extend"]},
        {"id": "editor", "name": "Editor", "description": "后期合成 - 衔接评估、裁剪拼接、过渡效果、音频混合",
         "agent_type": "react", "system_prompt": EDITOR_SYSTEM_PROMPT,
         "available_tools": ["evaluate_video_transition", "evaluate_video_quality", "trim_video",
                             "concat_videos", "transition_videos", "normalize_video",
                             "color_correct_video", "stabilize_video", "mix_audio"]},
        {"id": "human_feedback", "name": "Human Feedback", "description": "用户回复节点",
         "agent_type": "function", "system_prompt": "用户回复节点，不使用 LLM", "available_tools": []},
        {"id": "quality_gate", "name": "Quality Gate", "description": "质量门控 - VLM 评估视频质量",
         "agent_type": "function", "system_prompt": "VLM 自动评估，评分>=70通过",
         "available_tools": ["evaluate_video"]},
    ]

    session_factory = get_session_factory()
    async with session_factory() as session:
        for seed in agent_seeds:
            existing = await session.execute(
                select(AgentConfig).where(AgentConfig.id == seed["id"])
            )
            if existing.scalar_one_or_none() is None:
                session.add(AgentConfig(**seed))
                logger.info(f"Seeded agent_config: {seed['id']}")
        await session.commit()

    prompt_defaults = {
        "router": (ROUTER_SYSTEM_PROMPT, []),
        "planner": (PLANNER_SYSTEM_PROMPT, ["web_search"]),
        "producer": (PRODUCER_SYSTEM_PROMPT, ["generate_video_t2v", "generate_video_i2v", "generate_video_r2v", "generate_video_extend"]),
        "editor": (EDITOR_SYSTEM_PROMPT, ["evaluate_video_transition", "evaluate_video_quality", "trim_video",
                                           "concat_videos", "transition_videos", "normalize_video",
                                           "color_correct_video", "stabilize_video", "mix_audio"]),
        "human_feedback": ("用户回复节点，不使用 LLM", []),
        "quality_gate": ("VLM 自动评估，评分>=70通过", ["evaluate_video"]),
    }
    for agent_id, (prompt, tools) in prompt_defaults.items():
        try:
            await pm.ensure_default(agent_id, prompt, tools)
        except Exception as e:
            logger.warning(f"Failed to seed prompt for {agent_id}: {e}")

    await _seed_canvas(get_session_factory())


async def _seed_canvas(session_factory):
    """首次启动时创建画布节点 + 连线 (独立模块: Agent + Skill + flow/tool 边)"""
    from app.models.database import CanvasNode, CanvasEdge
    from sqlalchemy import select

    async with session_factory() as session:
        existing = await session.execute(select(CanvasNode).limit(1))
        if existing.scalar_one_or_none() is not None:
            return

        main_nodes = [
            ("trigger:chat",    "trigger", "chat",         -200, 250, {}, None),
            ("agent:router",    "agent",   "router",        100, 250, {}, None),
            ("agent:planner",   "agent",   "planner",       400, 250, {}, None),
            ("agent:producer",  "agent",   "producer",      750, 250, {}, None),
            ("agent:editor",    "agent",   "editor",        1150, 250, {}, None),
            ("agent:quality_gate","agent", "quality_gate",   1550, 250, {}, None),
            # Skill 容器 (独立模块, config.items 存 skill 列表)
            ("skillgroup:planner_skills",  "skillgroup", "planner_skills",  400,  430,
             {"items": ["web_search"]}, None),
            ("skillgroup:producer_skills", "skillgroup", "producer_skills", 750,  430,
             {"items": ["generate_video_t2v", "generate_video_i2v", "generate_video_r2v", "generate_video_extend"]}, None),
            ("skillgroup:editor_skills",   "skillgroup", "editor_skills",   1150, 430,
             {"items": ["evaluate_video_transition", "evaluate_video_quality", "trim_video", "concat_videos", "transition_videos", "normalize_video", "color_correct_video", "stabilize_video", "mix_audio"]}, None),
            ("skillgroup:qg_skills",       "skillgroup", "qg_skills",       1550, 430,
             {"items": ["evaluate_video_quality"]}, None),
        ]

        flow_edges = [
            ("trigger:chat",    "agent:router",       "flow"),
            ("agent:router",    "agent:planner",      "flow"),
            ("agent:planner",   "agent:producer",     "flow"),
            ("agent:producer",  "agent:editor",       "flow"),
            ("agent:editor",    "agent:quality_gate",  "flow"),
        ]

        tool_edges = [
            ("agent:planner",      "skillgroup:planner_skills",   "tool"),
            ("agent:producer",     "skillgroup:producer_skills",  "tool"),
            ("agent:editor",       "skillgroup:editor_skills",    "tool"),
            ("agent:quality_gate", "skillgroup:qg_skills",        "tool"),
        ]

        for nid, ntype, ref, px, py, cfg, parent in main_nodes:
            session.add(CanvasNode(id=nid, node_type=ntype, ref_id=ref,
                                   position_x=px, position_y=py, config=cfg, parent_canvas=parent))

        for src, tgt, etype in flow_edges + tool_edges:
            session.add(CanvasEdge(source_id=src, target_id=tgt, edge_type=etype))

        await session.commit()
        logger.info(f"Seeded canvas: {len(main_nodes)} nodes, {len(flow_edges)} flow + {len(tool_edges)} tool edges")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)

    redis_client = await _init_services()

    yield

    if redis_client:
        try:
            await redis_client.close()
        except Exception:
            pass


app = FastAPI(
    title="Video Agent",
    description="Seedance 2.0 Video Generation Multi-Agent System",
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router, prefix="/ws", tags=["websocket"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(canvas_router, prefix="/api/admin", tags=["canvas"])
app.include_router(mcp_router, prefix="/api/admin", tags=["mcp"])
app.include_router(skill_creator_router, prefix="/api/admin", tags=["skill-creator"])
app.include_router(video_api_router, prefix="/api/v1/video", tags=["video-api"])
app.include_router(publish_router, prefix="/api/v1", tags=["publish"])

settings = get_settings()
app.mount("/files/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
app.mount("/files/outputs", StaticFiles(directory=settings.output_dir), name="outputs")


@app.get("/health")
async def health():
    from app.agents.base import get_global_prompt_manager
    from app.graph.workflow import get_route_manager

    return {
        "status": "ok",
        "version": "0.5.0",
        "prompt_manager": "active" if get_global_prompt_manager() else "inactive",
        "route_manager": "active" if get_route_manager() else "inactive",
    }
