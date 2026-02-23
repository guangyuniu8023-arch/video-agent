"""MCP Client Manager — 连接外部 MCP 服务, 发现工具, 包装为 LangChain Tool

支持两种传输方式:
  - SSE: HTTP Server-Sent Events (url: http://localhost:3001/sse)
  - stdio: 子进程通信 (command: "npx @modelcontextprotocol/server-xxx")

当前实现: 通过 HTTP 模拟 MCP tools/list 调用。
完整 MCP SDK 集成可在后续迭代中加入。
"""

import json
import logging
from typing import Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


class McpClientManager:
    """管理所有 MCP 服务连接"""

    def __init__(self):
        self._connections: dict[str, dict] = {}

    async def connect_and_discover(self, server) -> list[dict]:
        """连接 MCP 服务并发现工具列表"""
        if server.transport == "sse" and server.url:
            return await self._discover_sse(server.id, server.url)
        elif server.transport == "stdio" and server.command:
            return await self._discover_stdio(server.id, server.command, server.env_vars or {})
        return []

    async def _discover_sse(self, server_id: str, url: str) -> list[dict]:
        """通过 SSE/HTTP 发现 MCP 工具"""
        try:
            base_url = url.rstrip('/').replace('/sse', '')
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{base_url}/tools/list", json={})
                if resp.status_code == 200:
                    data = resp.json()
                    tools = data.get("tools", [])
                    self._connections[server_id] = {"url": base_url, "transport": "sse"}
                    logger.info(f"MCP {server_id}: discovered {len(tools)} tools via SSE")
                    return [{"name": t["name"], "description": t.get("description", "")} for t in tools]
        except Exception as e:
            logger.warning(f"MCP {server_id} SSE discovery failed: {e}")
        return []

    async def _discover_stdio(self, server_id: str, command: str, env_vars: dict) -> list[dict]:
        """通过 stdio 子进程发现 MCP 工具 (占位实现)"""
        logger.info(f"MCP {server_id}: stdio transport (command: {command}) - placeholder")
        self._connections[server_id] = {"command": command, "transport": "stdio"}
        return []

    async def call_tool(self, server_id: str, tool_name: str, arguments: dict) -> str:
        """调用 MCP 服务的工具"""
        conn = self._connections.get(server_id)
        if not conn:
            return json.dumps({"error": f"MCP server {server_id} not connected"})

        if conn["transport"] == "sse":
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{conn['url']}/tools/call",
                        json={"name": tool_name, "arguments": arguments},
                    )
                    return resp.text
            except Exception as e:
                return json.dumps({"error": str(e)})

        return json.dumps({"error": "Transport not supported yet"})

    def wrap_tools_for_agent(self, server_id: str, discovered_tools: list[dict]) -> list:
        """将 MCP 服务的 discovered_tools 包装为 LangChain @tool 函数"""
        wrapped = []
        manager = self

        for tool_def in discovered_tools:
            tname = tool_def["name"]
            tdesc = tool_def.get("description", f"MCP tool: {tname}")
            func_name = f"mcp_{server_id}_{tname}"

            @tool
            async def mcp_fn(args: str = "{}", _sid=server_id, _tn=tname) -> str:
                try:
                    parsed = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    parsed = {"input": args}
                return await manager.call_tool(_sid, _tn, parsed)

            mcp_fn.name = func_name
            mcp_fn.__doc__ = tdesc
            wrapped.append(mcp_fn)

        return wrapped


_mcp_manager: Optional[McpClientManager] = None


def get_mcp_manager() -> McpClientManager:
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = McpClientManager()
    return _mcp_manager
