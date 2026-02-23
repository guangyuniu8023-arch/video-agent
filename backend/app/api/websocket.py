"""WebSocket 端点 - Agent 状态实时推送"""

import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

    async def broadcast(self, project_id: str, message: dict):
        """向指定项目的所有连接推送消息"""
        if project_id not in self.active_connections:
            return
        disconnected = []
        for ws in self.active_connections[project_id]:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws, project_id)

    async def broadcast_all(self, message: dict):
        """向所有连接推送消息"""
        for project_id in list(self.active_connections.keys()):
            await self.broadcast(project_id, message)


ws_manager = ConnectionManager()


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await ws_manager.connect(websocket, project_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "user_reply":
                from app.graph.workflow import submit_human_feedback, has_pending_feedback
                reply_text = message.get("content", "")
                if has_pending_feedback(project_id) and reply_text:
                    submit_human_feedback(project_id, reply_text)
                    await ws_manager.broadcast(project_id, {
                        "type": "chat_message",
                        "role": "user",
                        "content": reply_text,
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "当前没有等待回复的追问",
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, project_id)
