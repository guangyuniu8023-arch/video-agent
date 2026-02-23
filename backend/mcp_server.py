"""Video Agent MCP Server — 暴露 generate_video + get_video_status 工具

启动方式:
  python mcp_server.py                     # stdio 模式 (默认, 供 Claude Desktop 等连接)
  python mcp_server.py --transport sse     # SSE 模式 (HTTP, 供其他系统连接)
  python mcp_server.py --port 3100         # 自定义端口

环境变量:
  VIDEO_AGENT_API_URL: 视频 Agent REST API 地址 (默认 http://localhost:8000)
"""

import argparse
import json
import os

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

API_URL = os.environ.get("VIDEO_AGENT_API_URL", "http://localhost:8000")

server = Server("video-agent")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="generate_video",
            description="启动视频生成任务。根据文本描述生成视频。返回 project_id 用于查询进度。",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "视频创作需求描述，如：拍一个30秒的日落延时摄影",
                    },
                    "uploaded_assets": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "上传素材列表 [{type: 'image'|'video', url: '...'}]",
                        "default": [],
                    },
                },
                "required": ["prompt"],
            },
        ),
        Tool(
            name="get_video_status",
            description="查询视频生成进度和结果。当 status 为 complete 时返回 final_video_url。processing 时需要等待后再查。",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "generate_video 返回的 project_id",
                    },
                },
                "required": ["project_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    async with httpx.AsyncClient(timeout=30) as client:
        if name == "generate_video":
            resp = await client.post(
                f"{API_URL}/api/v1/video/generate",
                json={
                    "prompt": arguments["prompt"],
                    "uploaded_assets": arguments.get("uploaded_assets", []),
                },
            )
            return [TextContent(type="text", text=resp.text)]

        elif name == "get_video_status":
            project_id = arguments["project_id"]
            resp = await client.get(f"{API_URL}/api/v1/video/{project_id}/result")
            return [TextContent(type="text", text=resp.text)]

        else:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


def run_sse(port: int = 3100):
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    import uvicorn

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    app = Starlette(routes=[
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ])
    uvicorn.run(app, host="0.0.0.0", port=port)


async def run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Video Agent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=3100)
    args = parser.parse_args()

    if args.transport == "sse":
        run_sse(args.port)
    else:
        asyncio.run(run_stdio())
