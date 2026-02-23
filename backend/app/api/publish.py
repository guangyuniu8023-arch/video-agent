"""发布 API — 快照当前画布配置为版本"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.models.database import (
    WorkflowVersion, CanvasNode, CanvasEdge, AgentConfig,
    get_session_factory,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _take_snapshot(session) -> dict:
    """获取当前画布+Agent配置的完整快照。只保存画布上实际存在的 Agent。"""
    nodes = (await session.execute(select(CanvasNode))).scalars().all()
    edges = (await session.execute(select(CanvasEdge))).scalars().all()
    agents = (await session.execute(select(AgentConfig))).scalars().all()

    canvas_agent_ids = {n.ref_id for n in nodes if n.node_type == 'agent'}

    return {
        "canvas_nodes": [
            {"id": n.id, "node_type": n.node_type, "ref_id": n.ref_id,
             "position_x": n.position_x, "position_y": n.position_y}
            for n in nodes
        ],
        "canvas_edges": [
            {"source_id": e.source_id, "target_id": e.target_id, "edge_type": e.edge_type}
            for e in edges
        ],
        "agent_configs": [
            {"id": a.id, "name": a.name, "description": a.description,
             "agent_type": a.agent_type, "parent_id": a.parent_id,
             "system_prompt": a.system_prompt, "available_tools": a.available_tools,
             "llm_config": a.llm_config, "execution_mode": getattr(a, 'execution_mode', 'react'),
             "bypass": a.bypass, "enabled": a.enabled}
            for a in agents
            if a.id in canvas_agent_ids
        ],
    }


@router.post("/save")
async def save_current():
    """保存当前画布。如果有当前发布版本则更新该版本快照，否则存为草稿。"""
    sf = get_session_factory()
    async with sf() as session:
        snapshot = await _take_snapshot(session)

        published = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.is_published == True)
        )
        current = published.scalar_one_or_none()

        if current:
            current.snapshot = snapshot
            version_name = current.version
        else:
            existing = await session.execute(
                select(WorkflowVersion).where(WorkflowVersion.version == "_draft")
            )
            draft = existing.scalar_one_or_none()
            if draft:
                draft.snapshot = snapshot
            else:
                draft = WorkflowVersion(version="_draft", description="自动保存草稿", is_published=False, snapshot=snapshot)
                session.add(draft)
            version_name = "_draft"

        await session.commit()

    return {
        "message": f"已保存到 {version_name}",
        "version": version_name,
        "nodes": len(snapshot["canvas_nodes"]),
        "edges": len(snapshot["canvas_edges"]),
    }


class PublishRequest(BaseModel):
    version: str
    description: str = ""


@router.post("/publish")
async def publish_version(body: PublishRequest):
    """快照当前画布配置为新版本"""
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.version == body.version)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, f"版本 '{body.version}' 已存在")

        snapshot = await _take_snapshot(session)

        prev_published = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.is_published == True)
        )
        for pv in prev_published.scalars():
            pv.is_published = False

        version = WorkflowVersion(
            version=body.version,
            description=body.description,
            is_published=True,
            snapshot=snapshot,
        )
        session.add(version)
        await session.commit()

    logger.info(f"Published version {body.version}")
    return {
        "version": body.version,
        "message": f"版本 {body.version} 已发布",
        "nodes": len(snapshot["canvas_nodes"]),
        "edges": len(snapshot["canvas_edges"]),
        "agents": len(snapshot["agent_configs"]),
    }


@router.get("/versions")
async def list_versions():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(WorkflowVersion).order_by(WorkflowVersion.id.desc())
        )
        versions = result.scalars().all()

    return {
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "description": v.description,
                "is_published": v.is_published,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "nodes": len(v.snapshot.get("canvas_nodes", [])),
                "edges": len(v.snapshot.get("canvas_edges", [])),
                "agents": len(v.snapshot.get("agent_configs", [])),
            }
            for v in versions
        ]
    }


@router.get("/versions/{version_id}")
async def get_version(version_id: int):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == version_id)
        )
        v = result.scalar_one_or_none()
        if not v:
            raise HTTPException(404, f"版本 {version_id} 不存在")

    return {
        "id": v.id,
        "version": v.version,
        "description": v.description,
        "is_published": v.is_published,
        "snapshot": v.snapshot,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


@router.post("/versions/{version_id}/load")
async def load_version(version_id: int):
    """加载某个版本的快照到当前画布 (覆盖当前 canvas_nodes + canvas_edges + agent_configs)"""
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == version_id)
        )
        v = result.scalar_one_or_none()
        if not v:
            raise HTTPException(404, f"版本 {version_id} 不存在")

        snapshot = v.snapshot

        from sqlalchemy import delete as sql_delete
        await session.execute(sql_delete(CanvasEdge))
        await session.execute(sql_delete(CanvasNode))

        for n in snapshot.get("canvas_nodes", []):
            session.add(CanvasNode(
                id=n["id"], node_type=n["node_type"], ref_id=n["ref_id"],
                position_x=n["position_x"], position_y=n["position_y"],
            ))

        for e in snapshot.get("canvas_edges", []):
            session.add(CanvasEdge(
                source_id=e["source_id"], target_id=e["target_id"], edge_type=e["edge_type"],
            ))

        snapshot_agent_ids = {a["id"] for a in snapshot.get("agent_configs", [])}

        all_agents = (await session.execute(select(AgentConfig))).scalars().all()
        for agent in all_agents:
            if agent.id not in snapshot_agent_ids:
                await session.delete(agent)

        for a in snapshot.get("agent_configs", []):
            existing = await session.execute(
                select(AgentConfig).where(AgentConfig.id == a["id"])
            )
            agent = existing.scalar_one_or_none()
            if agent:
                agent.name = a["name"]
                agent.description = a.get("description", "")
                agent.agent_type = a.get("agent_type", "react")
                agent.parent_id = a.get("parent_id")
                agent.system_prompt = a.get("system_prompt", "")
                agent.available_tools = a.get("available_tools", [])
                agent.llm_config = a.get("llm_config", {})
                agent.bypass = a.get("bypass", False)
                agent.enabled = a.get("enabled", True)
            else:
                session.add(AgentConfig(**{k: v for k, v in a.items() if k != 'execution_mode'}))

        prev_published = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.is_published == True)
        )
        for pv in prev_published.scalars():
            pv.is_published = False
        v.is_published = True

        await session.commit()

    try:
        from app.graph.workflow import rebuild_workflow
        await rebuild_workflow()
    except Exception as e:
        logger.warning(f"Failed to rebuild workflow after version load: {e}")

    return {
        "message": f"已加载版本 {v.version}",
        "version": v.version,
        "nodes": len(snapshot.get("canvas_nodes", [])),
        "edges": len(snapshot.get("canvas_edges", [])),
    }


@router.delete("/versions/{version_id}")
async def delete_version(version_id: int):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == version_id)
        )
        v = result.scalar_one_or_none()
        if not v:
            raise HTTPException(404, f"版本 {version_id} 不存在")
        await session.delete(v)
        await session.commit()
    return {"message": f"版本 {version_id} 已删除"}
