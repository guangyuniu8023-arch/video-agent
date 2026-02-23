"""Canvas API — 画布节点/边 CRUD，连线即生效 (自动同步 available_tools)"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete

from app.models.database import (
    CanvasNode, CanvasEdge, AgentConfig, McpServer, get_session_factory,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _node_to_dict(n: CanvasNode) -> dict:
    return {
        "id": n.id,
        "node_type": n.node_type,
        "ref_id": n.ref_id,
        "position_x": n.position_x,
        "position_y": n.position_y,
        "config": n.config or {},
        "parent_canvas": n.parent_canvas,
    }


def _edge_to_dict(e: CanvasEdge) -> dict:
    return {
        "id": e.id,
        "source_id": e.source_id,
        "target_id": e.target_id,
        "edge_type": e.edge_type,
    }


# ── Canvas Nodes ─────────────────────────────────────────────────

@router.get("/canvas/nodes")
async def list_canvas_nodes():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(CanvasNode))
        nodes = list(result.scalars().all())

    enriched = []
    for n in nodes:
        d = _node_to_dict(n)
        enriched.append(d)

    return {"nodes": enriched}


class CanvasNodeCreate(BaseModel):
    id: str
    node_type: str
    ref_id: str
    position_x: float = 0
    position_y: float = 0
    config: dict = {}
    parent_canvas: str | None = None


@router.post("/canvas/nodes")
async def create_canvas_node(body: CanvasNodeCreate):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(select(CanvasNode).where(CanvasNode.id == body.id))
        if existing.scalar_one_or_none():
            raise HTTPException(400, f"Canvas node '{body.id}' already exists")

        node = CanvasNode(
            id=body.id,
            node_type=body.node_type,
            ref_id=body.ref_id,
            position_x=body.position_x,
            position_y=body.position_y,
            config=body.config,
            parent_canvas=body.parent_canvas,
        )
        session.add(node)
        await session.commit()

    return _node_to_dict(node)


class CanvasNodePositionUpdate(BaseModel):
    position_x: float
    position_y: float


@router.put("/canvas/nodes/{node_id}")
async def update_canvas_node(node_id: str, body: CanvasNodePositionUpdate):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(CanvasNode).where(CanvasNode.id == node_id))
        node = result.scalar_one_or_none()
        if not node:
            raise HTTPException(404, f"Canvas node '{node_id}' not found")
        node.position_x = body.position_x
        node.position_y = body.position_y
        await session.commit()

    return _node_to_dict(node)


class CanvasNodeConfigUpdate(BaseModel):
    config: dict


@router.put("/canvas/nodes/{node_id}/config")
async def update_canvas_node_config(node_id: str, body: CanvasNodeConfigUpdate):
    """更新容器节点的 config (items 列表)"""
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(CanvasNode).where(CanvasNode.id == node_id))
        node = result.scalar_one_or_none()
        if not node:
            raise HTTPException(404, f"Canvas node '{node_id}' not found")
        node.config = body.config

        # 如果容器已连线到 Agent, 同步 available_tools
        edges = (await session.execute(
            select(CanvasEdge).where(CanvasEdge.target_id == node_id, CanvasEdge.edge_type == "tool")
        )).scalars().all()

        for edge in edges:
            source_cn = (await session.execute(select(CanvasNode).where(CanvasNode.id == edge.source_id))).scalar_one_or_none()
            if source_cn and source_cn.node_type == "agent":
                await _sync_available_tools_on_create(session, source_cn, node)

        await session.commit()
    return _node_to_dict(node)


@router.put("/canvas/nodes/batch-positions")
async def batch_update_positions(body: list[dict]):
    """批量更新节点位置 (拖拽后保存)"""
    sf = get_session_factory()
    async with sf() as session:
        for item in body:
            result = await session.execute(
                select(CanvasNode).where(CanvasNode.id == item["id"])
            )
            node = result.scalar_one_or_none()
            if node:
                node.position_x = item["position_x"]
                node.position_y = item["position_y"]
        await session.commit()
    return {"message": f"Updated {len(body)} node positions"}


@router.delete("/canvas/nodes/{node_id}")
async def delete_canvas_node(node_id: str):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(CanvasNode).where(CanvasNode.id == node_id))
        node = result.scalar_one_or_none()
        if not node:
            raise HTTPException(404, f"Canvas node '{node_id}' not found")

        edges = await session.execute(
            select(CanvasEdge).where(
                (CanvasEdge.source_id == node_id) | (CanvasEdge.target_id == node_id)
            )
        )
        for edge in edges.scalars():
            await _sync_available_tools_on_delete(session, edge)
            await session.delete(edge)

        await session.delete(node)
        await session.commit()

    return {"message": f"Canvas node '{node_id}' deleted"}


# ── Canvas Edges ─────────────────────────────────────────────────

@router.get("/canvas/edges")
async def list_canvas_edges():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(CanvasEdge))
        edges = list(result.scalars().all())
    return {"edges": [_edge_to_dict(e) for e in edges]}


class CanvasEdgeCreate(BaseModel):
    source_id: str
    target_id: str
    edge_type: str = "tool"  # "flow" | "tool"


@router.post("/canvas/edges")
async def create_canvas_edge(body: CanvasEdgeCreate):
    sf = get_session_factory()
    async with sf() as session:
        for nid in (body.source_id, body.target_id):
            r = await session.execute(select(CanvasNode).where(CanvasNode.id == nid))
            if not r.scalar_one_or_none():
                raise HTTPException(400, f"Canvas node '{nid}' not found")

        dup = await session.execute(
            select(CanvasEdge).where(
                CanvasEdge.source_id == body.source_id,
                CanvasEdge.target_id == body.target_id,
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(400, "Edge already exists")

        source_node = (await session.execute(
            select(CanvasNode).where(CanvasNode.id == body.source_id)
        )).scalar_one()
        target_node = (await session.execute(
            select(CanvasNode).where(CanvasNode.id == body.target_id)
        )).scalar_one()

        if body.edge_type == "tool":
            if source_node.node_type not in ("agent",):
                raise HTTPException(400, "tool 边的 source 必须是 agent 节点")
            if target_node.node_type not in ("skill", "agent", "mcp", "skillgroup", "subagentgroup", "mcpgroup"):
                raise HTTPException(400, "tool 边的 target 必须是 skill/agent/mcp 节点")

        if body.edge_type == "flow":
            if source_node.node_type not in ("agent", "trigger"):
                raise HTTPException(400, "flow 边的 source 必须是 agent 或 trigger 节点")
            if target_node.node_type not in ("agent",):
                raise HTTPException(400, "flow 边的 target 必须是 agent 节点")

        edge = CanvasEdge(
            source_id=body.source_id,
            target_id=body.target_id,
            edge_type=body.edge_type,
        )
        session.add(edge)

        if body.edge_type == "tool":
            await _sync_available_tools_on_create(session, source_node, target_node)

        await session.commit()
        await session.refresh(edge)

    if body.edge_type == "flow":
        await _rebuild_workflow_safe()

    return _edge_to_dict(edge)


@router.delete("/canvas/edges/{edge_id}")
async def delete_canvas_edge(edge_id: int):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(CanvasEdge).where(CanvasEdge.id == edge_id))
        edge = result.scalar_one_or_none()
        if not edge:
            raise HTTPException(404, f"Edge {edge_id} not found")

        if edge.edge_type == "tool":
            await _sync_available_tools_on_delete(session, edge)

        is_flow = edge.edge_type == "flow"
        await session.delete(edge)
        await session.commit()

    if is_flow:
        await _rebuild_workflow_safe()

    return {"message": f"Edge {edge_id} deleted", "id": edge_id}


async def _rebuild_workflow_safe():
    """安全重建工作流"""
    try:
        from app.graph.workflow import rebuild_workflow
        await rebuild_workflow()
    except Exception as e:
        logger.warning(f"Failed to rebuild workflow: {e}")


# ── available_tools 自动同步 ─────────────────────────────────────

async def _sync_available_tools_on_create(session, source_node: CanvasNode, target_node: CanvasNode):
    """创建 tool 边时，把 target 的工具加入 source agent 的 available_tools"""
    agent_result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == source_node.ref_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return

    tools = list(agent.available_tools or [])

    if target_node.node_type == "skill":
        if target_node.ref_id not in tools:
            tools.append(target_node.ref_id)
    elif target_node.node_type == "skillgroup":
        items = (target_node.config or {}).get("items", [])
        for item in items:
            if item not in tools:
                tools.append(item)
    elif target_node.node_type == "agent":
        if target_node.ref_id not in tools:
            tools.append(target_node.ref_id)
        child_result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == target_node.ref_id)
        )
        child = child_result.scalar_one_or_none()
        if child:
            child.parent_id = source_node.ref_id
    elif target_node.node_type == "subagentgroup":
        items = (target_node.config or {}).get("items", [])
        for item in items:
            if item not in tools:
                tools.append(item)
            child_result = await session.execute(
                select(AgentConfig).where(AgentConfig.id == item)
            )
            child = child_result.scalar_one_or_none()
            if child:
                child.parent_id = source_node.ref_id
    elif target_node.node_type == "mcp":
        mcp_result = await session.execute(
            select(McpServer).where(McpServer.id == target_node.ref_id)
        )
        mcp = mcp_result.scalar_one_or_none()
        if mcp and mcp.discovered_tools:
            for t in mcp.discovered_tools:
                tool_name = f"mcp_{mcp.id}_{t['name']}"
                if tool_name not in tools:
                    tools.append(tool_name)
    elif target_node.node_type == "mcpgroup":
        items = (target_node.config or {}).get("items", [])
        for mcp_id in items:
            mcp_result = await session.execute(
                select(McpServer).where(McpServer.id == mcp_id)
            )
            mcp = mcp_result.scalar_one_or_none()
            if mcp and mcp.discovered_tools:
                for t in mcp.discovered_tools:
                    tool_name = f"mcp_{mcp.id}_{t['name']}"
                    if tool_name not in tools:
                        tools.append(tool_name)

    agent.available_tools = tools


async def _sync_available_tools_on_delete(session, edge: CanvasEdge):
    """删除 tool 边时，从 source agent 的 available_tools 移除 target 的工具"""
    if edge.edge_type != "tool":
        return

    source_result = await session.execute(
        select(CanvasNode).where(CanvasNode.id == edge.source_id)
    )
    source_node = source_result.scalar_one_or_none()
    if not source_node or source_node.node_type != "agent":
        return

    target_result = await session.execute(
        select(CanvasNode).where(CanvasNode.id == edge.target_id)
    )
    target_node = target_result.scalar_one_or_none()
    if not target_node:
        return

    agent_result = await session.execute(
        select(AgentConfig).where(AgentConfig.id == source_node.ref_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return

    tools = list(agent.available_tools or [])

    if target_node.node_type == "skill":
        tools = [t for t in tools if t != target_node.ref_id]
    elif target_node.node_type == "skillgroup":
        from app.skills.registry import get_skill_registry
        skill_names = {s.name for s in get_skill_registry()._skills.values()}
        tools = [t for t in tools if t not in skill_names]
    elif target_node.node_type == "agent":
        tools = [t for t in tools if t != target_node.ref_id]
        child_result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == target_node.ref_id)
        )
        child = child_result.scalar_one_or_none()
        if child and child.parent_id == source_node.ref_id:
            child.parent_id = None
    elif target_node.node_type == "subagentgroup":
        children = (await session.execute(
            select(AgentConfig).where(AgentConfig.parent_id == source_node.ref_id)
        )).scalars().all()
        child_ids = {c.id for c in children}
        tools = [t for t in tools if t not in child_ids]
        for child in children:
            child.parent_id = None
    elif target_node.node_type == "mcp":
        prefix = f"mcp_{target_node.ref_id}_"
        tools = [t for t in tools if not t.startswith(prefix)]
    elif target_node.node_type == "mcpgroup":
        tools = [t for t in tools if not t.startswith("mcp_")]

    agent.available_tools = tools
