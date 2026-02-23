"""MCP Server 管理 API — 注册/连接/发现工具/状态查询"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.models.database import McpServer, get_session_factory

logger = logging.getLogger(__name__)
router = APIRouter()


def _mcp_to_dict(s: McpServer) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "transport": s.transport,
        "url": s.url or "",
        "command": s.command or "",
        "env_vars": s.env_vars or {},
        "status": s.status,
        "discovered_tools": s.discovered_tools or [],
        "last_health_check": s.last_health_check.isoformat() if s.last_health_check else None,
    }


@router.get("/mcp")
async def list_mcp_servers():
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(McpServer))
        servers = list(result.scalars().all())
    return {"servers": [_mcp_to_dict(s) for s in servers]}


class McpServerCreate(BaseModel):
    id: str
    name: str
    transport: str = "sse"
    url: str = ""
    command: str = ""
    env_vars: dict = {}


@router.post("/mcp")
async def create_mcp_server(body: McpServerCreate):
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(select(McpServer).where(McpServer.id == body.id))
        if existing.scalar_one_or_none():
            raise HTTPException(400, f"MCP server '{body.id}' already exists")

        server = McpServer(
            id=body.id,
            name=body.name,
            transport=body.transport,
            url=body.url or None,
            command=body.command or None,
            env_vars=body.env_vars,
            status="disconnected",
            discovered_tools=[],
        )
        session.add(server)
        await session.commit()
        await session.refresh(server)

    return _mcp_to_dict(server)


class McpServerUpdate(BaseModel):
    name: str | None = None
    transport: str | None = None
    url: str | None = None
    command: str | None = None
    env_vars: dict | None = None


@router.put("/mcp/{server_id}")
async def update_mcp_server(server_id: str, body: McpServerUpdate):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(McpServer).where(McpServer.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(404, f"MCP server '{server_id}' not found")

        if body.name is not None: server.name = body.name
        if body.transport is not None: server.transport = body.transport
        if body.url is not None: server.url = body.url
        if body.command is not None: server.command = body.command
        if body.env_vars is not None: server.env_vars = body.env_vars

        await session.commit()
        await session.refresh(server)

    return _mcp_to_dict(server)


@router.delete("/mcp/{server_id}")
async def delete_mcp_server(server_id: str):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(McpServer).where(McpServer.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(404, f"MCP server '{server_id}' not found")
        await session.delete(server)
        await session.commit()

    return {"message": f"MCP server '{server_id}' deleted"}


@router.get("/mcp/{server_id}")
async def get_mcp_server(server_id: str):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(McpServer).where(McpServer.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(404, f"MCP server '{server_id}' not found")
    return _mcp_to_dict(server)


@router.get("/mcp/{server_id}/tools")
async def get_mcp_tools(server_id: str):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(McpServer).where(McpServer.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(404, f"MCP server '{server_id}' not found")
    return {
        "server_id": server_id,
        "status": server.status,
        "tools": server.discovered_tools or [],
    }


@router.post("/mcp/{server_id}/reconnect")
async def reconnect_mcp_server(server_id: str):
    """触发重连 MCP 服务 + 重新发现工具"""
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(McpServer).where(McpServer.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            raise HTTPException(404, f"MCP server '{server_id}' not found")

        try:
            from app.services.mcp_client import get_mcp_manager
            manager = get_mcp_manager()
            tools = await manager.connect_and_discover(server)

            import datetime
            server.status = "connected"
            server.discovered_tools = tools
            server.last_health_check = datetime.datetime.utcnow()
            await session.commit()

            return {"status": "connected", "tools": tools, "count": len(tools)}
        except Exception as e:
            server.status = "error"
            await session.commit()
            raise HTTPException(500, f"MCP 连接失败: {e}")
