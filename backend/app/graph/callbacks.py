"""LangGraph 执行回调 - WebSocket 推送 + 日志 + LLM 流式输出"""

import time
import asyncio
import logging

from langchain_core.callbacks import AsyncCallbackHandler
from app.api.websocket import ws_manager

logger = logging.getLogger(__name__)


async def push_agent_status(project_id: str, agent: str, status: str, **extra):
    """推送 Agent 状态到前端 React Flow"""
    await ws_manager.broadcast(project_id, {
        "type": "agent_status",
        "agent": agent,
        "status": status,
        "timestamp": time.time(),
        **extra,
    })


async def push_edge_active(project_id: str, edge_id: str, active: bool):
    """激活/取消数据流动画边"""
    await ws_manager.broadcast(project_id, {
        "type": "edge_active",
        "edge_id": edge_id,
        "active": active,
    })


async def push_log_entry(project_id: str, agent: str, message: str, **extra):
    """推送日志条目到底部日志流"""
    await ws_manager.broadcast(project_id, {
        "type": "log_entry",
        "agent": agent,
        "message": message,
        "timestamp": time.time(),
        **extra,
    })


class StreamingWSCallback(AsyncCallbackHandler):
    """LLM 流式输出回调 — 每个 token 实时推送到前端

    通过 WebSocket 推送 llm_token 事件，前端渐进式显示 Agent 的思考过程。
    内置节流: 累积 token 批量发送，避免 WebSocket 消息风暴。
    """

    def __init__(self, project_id: str, agent_name: str, throttle_ms: int = 50):
        super().__init__()
        self.project_id = project_id
        self.agent_name = agent_name
        self._throttle = throttle_ms / 1000
        self._buffer = ""
        self._last_flush = 0.0
        self._flush_task: asyncio.Task | None = None

    async def on_llm_start(self, serialized, prompts=None, **kwargs) -> None:
        await ws_manager.broadcast(self.project_id, {
            "type": "llm_stream_start",
            "agent": self.agent_name,
            "timestamp": time.time(),
        })

    async def on_chat_model_start(self, serialized, messages, **kwargs) -> None:
        await ws_manager.broadcast(self.project_id, {
            "type": "llm_stream_start",
            "agent": self.agent_name,
            "timestamp": time.time(),
        })

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        if not token:
            return
        self._buffer += token
        now = time.monotonic()
        if now - self._last_flush >= self._throttle:
            await self._flush()
        elif not self._flush_task or self._flush_task.done():
            self._flush_task = asyncio.create_task(self._delayed_flush())

    async def on_llm_end(self, response, **kwargs) -> None:
        await self._flush()
        await ws_manager.broadcast(self.project_id, {
            "type": "llm_stream_end",
            "agent": self.agent_name,
            "timestamp": time.time(),
        })

    async def on_tool_start(self, serialized, input_str, **kwargs) -> None:
        tool_name = serialized.get("name", "unknown")
        truncated_input = str(input_str)[:500] if input_str else ""
        try:
            await ws_manager.broadcast(self.project_id, {
                "type": "tool_call_start",
                "agent": self.agent_name,
                "tool": tool_name,
                "input": truncated_input,
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.warning(f"Failed to push tool_call_start: {e}")

    async def on_tool_end(self, output, **kwargs) -> None:
        tool_name = kwargs.get("name", "unknown")
        truncated_output = str(output)[:500] if output else ""
        try:
            await ws_manager.broadcast(self.project_id, {
                "type": "tool_call_end",
                "agent": self.agent_name,
                "tool": tool_name,
                "output": truncated_output,
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.warning(f"Failed to push tool_call_end: {e}")

    async def _delayed_flush(self):
        await asyncio.sleep(self._throttle)
        await self._flush()

    async def _flush(self):
        if not self._buffer:
            return
        chunk = self._buffer
        self._buffer = ""
        self._last_flush = time.monotonic()
        try:
            await ws_manager.broadcast(self.project_id, {
                "type": "llm_token",
                "agent": self.agent_name,
                "token": chunk,
            })
        except Exception as e:
            logger.warning(f"Failed to push llm_token: {e}")
