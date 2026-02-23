"""Agent 基类 - Prompt 热加载 + 动态 Tool 解析

Sprint 4: 接入 PromptManager (DB + Redis) 替换 _prompt_store 内存方案。
保留 _prompt_store 作为兜底，在 DB 不可用时仍可工作。
"""

import logging
from typing import Optional

from app.tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

# 内存兜底: 当 PromptManager (DB) 不可用时使用
_prompt_store: dict[str, str] = {}
_tools_store: dict[str, list[str]] = {}

# 全局 PromptManager 实例 (由 main.py lifespan 注入)
_prompt_manager = None


def set_global_prompt_manager(pm):
    global _prompt_manager
    _prompt_manager = pm


def get_global_prompt_manager():
    return _prompt_manager


class BaseAgent:
    def __init__(self, agent_id: str, prompt_manager=None):
        self.agent_id = agent_id
        self.prompt_manager = prompt_manager

    def _get_prompt_manager(self):
        return self.prompt_manager or _prompt_manager

    async def get_system_prompt(self) -> str:
        """获取当前生效的 system prompt (DB → 内存兜底 → 默认)"""
        # 1. 内存覆盖优先 (兼容旧接口)
        if self.agent_id in _prompt_store:
            return _prompt_store[self.agent_id]

        # 2. PromptManager (DB + Redis)
        pm = self._get_prompt_manager()
        if pm:
            try:
                config = await pm.get_active_prompt(self.agent_id)
                if config:
                    return config["system_prompt"]
            except Exception as e:
                logger.warning(f"PromptManager failed for {self.agent_id}: {e}")

        # 3. 子类默认
        return self._default_prompt()

    async def get_tools(self) -> list:
        """获取当前可用工具列表 (DB → 内存兜底 → 子类默认)"""
        # 1. 内存覆盖
        if self.agent_id in _tools_store:
            return self._resolve_tools(_tools_store[self.agent_id])

        # 2. PromptManager (DB + Redis)
        pm = self._get_prompt_manager()
        if pm:
            try:
                config = await pm.get_active_prompt(self.agent_id)
                if config and config.get("available_tools"):
                    return self._resolve_tools(config["available_tools"])
            except Exception as e:
                logger.warning(f"PromptManager tools failed for {self.agent_id}: {e}")

        # 3. 子类默认
        return []

    async def get_dynamic_tools(self, state: dict) -> list:
        """DB available_tools → SkillRegistry trigger 过滤 → TOOL_REGISTRY 解析"""
        from app.skills.registry import get_skill_registry
        tool_names = await self.get_available_tool_names()
        if not tool_names:
            return []
        registry = get_skill_registry()
        matched = registry.match_skills(tool_names, state)
        if matched:
            matched_names = [s.name for s in matched]
            resolved = self._resolve_tools(matched_names)
            if resolved:
                logger.info(f"Agent '{self.agent_id}' loaded {len(resolved)} tools: {matched_names}")
                return resolved
        all_resolved = self._resolve_tools(tool_names)
        if all_resolved:
            logger.info(f"Agent '{self.agent_id}' fallback all {len(all_resolved)} tools")
            return all_resolved
        return []

    async def get_available_tool_names(self) -> list[str]:
        """获取当前可用工具名列表"""
        if self.agent_id in _tools_store:
            return _tools_store[self.agent_id]

        pm = self._get_prompt_manager()
        if pm:
            try:
                config = await pm.get_active_prompt(self.agent_id)
                if config and config.get("available_tools"):
                    return config["available_tools"]
            except Exception:
                pass

        return self.get_tool_names()

    def _resolve_tools(self, tool_names: list[str]) -> list:
        return [TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY]

    def _default_prompt(self) -> str:
        return ""

    def get_tool_names(self) -> list[str]:
        """返回该 Agent 的默认工具名列表（子类覆写）"""
        return []


# ── 兼容 Sprint 1~3 的内存 API ──

def get_prompt(agent_id: str) -> Optional[str]:
    return _prompt_store.get(agent_id)


def set_prompt(agent_id: str, prompt: str):
    _prompt_store[agent_id] = prompt
    logger.info(f"Prompt updated in memory for agent '{agent_id}' ({len(prompt)} chars)")


def reset_prompt(agent_id: str):
    _prompt_store.pop(agent_id, None)
    logger.info(f"Prompt reset in memory for agent '{agent_id}'")


def get_tools_override(agent_id: str) -> Optional[list[str]]:
    return _tools_store.get(agent_id)


def set_tools_override(agent_id: str, tools: list[str]):
    _tools_store[agent_id] = tools
    logger.info(f"Tools updated in memory for agent '{agent_id}': {tools}")


def reset_tools_override(agent_id: str):
    _tools_store.pop(agent_id, None)
