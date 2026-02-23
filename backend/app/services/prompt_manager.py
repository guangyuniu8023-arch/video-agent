"""PromptManager — DB 存版本历史 + Redis 缓存激活版本

替换 Sprint 1~3 的 _prompt_store 内存方案。
优雅降级: Redis 不可用时仍可工作 (每次查 DB)。
"""

import json
import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import PromptVersion, get_session_factory

logger = logging.getLogger(__name__)

REDIS_PREFIX = "prompt:"
REDIS_TTL = 30  # seconds


class PromptManager:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._session_factory = get_session_factory()

    async def get_active_prompt(self, agent_id: str) -> dict:
        """获取 Agent 当前激活的 prompt 配置 (Redis 缓存 → DB 回退)"""
        cached = await self._get_from_cache(agent_id)
        if cached:
            return cached

        async with self._session_factory() as session:
            result = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.agent_id == agent_id, PromptVersion.is_active == True)
                .order_by(PromptVersion.version.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        config = {
            "agent_id": row.agent_id,
            "version": row.version,
            "system_prompt": row.system_prompt,
            "available_tools": row.available_tools or [],
            "is_active": True,
            "editor": row.editor,
        }
        await self._set_cache(agent_id, config)
        return config

    async def update_prompt(
        self, agent_id: str, new_prompt: str, editor: str = "admin"
    ) -> dict:
        """更新 prompt: 旧版本 deactivate → 新版本 activate → 清 Redis 缓存"""
        async with self._session_factory() as session:
            next_version = await self._next_version(session, agent_id)

            # 旧版本 deactivate
            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.agent_id == agent_id,
                    PromptVersion.is_active == True,
                )
            )
            for old in result.scalars():
                old.is_active = False

            new_row = PromptVersion(
                agent_id=agent_id,
                version=next_version,
                system_prompt=new_prompt,
                available_tools=await self._current_tools(session, agent_id),
                is_active=True,
                editor=editor,
            )
            session.add(new_row)
            await session.commit()

        await self._invalidate_cache(agent_id)
        logger.info(f"Prompt updated: agent={agent_id} version={next_version} editor={editor}")

        return {
            "agent_id": agent_id,
            "version": next_version,
            "system_prompt": new_prompt,
            "is_active": True,
            "editor": editor,
        }

    async def update_tools(
        self, agent_id: str, tools: list[str], editor: str = "admin"
    ) -> dict:
        """更新 Agent 可用工具列表 (创建新版本)"""
        async with self._session_factory() as session:
            next_version = await self._next_version(session, agent_id)
            current_prompt = await self._current_prompt_text(session, agent_id)

            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.agent_id == agent_id,
                    PromptVersion.is_active == True,
                )
            )
            for old in result.scalars():
                old.is_active = False

            new_row = PromptVersion(
                agent_id=agent_id,
                version=next_version,
                system_prompt=current_prompt,
                available_tools=tools,
                is_active=True,
                editor=editor,
            )
            session.add(new_row)
            await session.commit()

        await self._invalidate_cache(agent_id)
        return {
            "agent_id": agent_id,
            "version": next_version,
            "available_tools": tools,
        }

    async def rollback(self, agent_id: str, target_version: int) -> dict:
        """回滚到指定版本"""
        async with self._session_factory() as session:
            target = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.agent_id == agent_id,
                    PromptVersion.version == target_version,
                )
            )
            target_row = target.scalar_one_or_none()
            if target_row is None:
                raise ValueError(f"Version {target_version} not found for agent {agent_id}")

            result = await session.execute(
                select(PromptVersion).where(
                    PromptVersion.agent_id == agent_id,
                    PromptVersion.is_active == True,
                )
            )
            for old in result.scalars():
                old.is_active = False

            next_ver = await self._next_version(session, agent_id)
            new_row = PromptVersion(
                agent_id=agent_id,
                version=next_ver,
                system_prompt=target_row.system_prompt,
                available_tools=target_row.available_tools,
                is_active=True,
                editor="rollback",
            )
            session.add(new_row)
            await session.commit()

        await self._invalidate_cache(agent_id)
        return {
            "agent_id": agent_id,
            "version": next_ver,
            "rolled_back_to": target_version,
            "system_prompt": target_row.system_prompt,
            "available_tools": target_row.available_tools,
        }

    async def list_versions(self, agent_id: str) -> list[dict]:
        """列出所有版本历史"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(PromptVersion)
                .where(PromptVersion.agent_id == agent_id)
                .order_by(PromptVersion.version.desc())
            )
            rows = result.scalars().all()

        return [
            {
                "version": r.version,
                "system_prompt": r.system_prompt[:200] + ("..." if len(r.system_prompt) > 200 else ""),
                "available_tools": r.available_tools or [],
                "is_active": r.is_active,
                "editor": r.editor,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in rows
        ]

    async def ensure_default(self, agent_id: str, default_prompt: str, default_tools: list[str]):
        """确保 Agent 在 DB 中有默认记录 (首次启动时调用)"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).where(PromptVersion.agent_id == agent_id)
            )
            count = result.scalar()
            if count == 0:
                row = PromptVersion(
                    agent_id=agent_id,
                    version=1,
                    system_prompt=default_prompt,
                    available_tools=default_tools,
                    is_active=True,
                    editor="system",
                )
                session.add(row)
                await session.commit()
                logger.info(f"Default prompt seeded for agent '{agent_id}'")

    # ── 内部方法 ──

    async def _next_version(self, session: AsyncSession, agent_id: str) -> int:
        result = await session.execute(
            select(func.max(PromptVersion.version)).where(PromptVersion.agent_id == agent_id)
        )
        max_ver = result.scalar() or 0
        return max_ver + 1

    async def _current_tools(self, session: AsyncSession, agent_id: str) -> list[str]:
        result = await session.execute(
            select(PromptVersion.available_tools)
            .where(PromptVersion.agent_id == agent_id, PromptVersion.is_active == True)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row or []

    async def _current_prompt_text(self, session: AsyncSession, agent_id: str) -> str:
        result = await session.execute(
            select(PromptVersion.system_prompt)
            .where(PromptVersion.agent_id == agent_id, PromptVersion.is_active == True)
            .limit(1)
        )
        return result.scalar_one_or_none() or ""

    async def _get_from_cache(self, agent_id: str) -> Optional[dict]:
        if not self._redis:
            return None
        try:
            data = await self._redis.get(f"{REDIS_PREFIX}{agent_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
        return None

    async def _set_cache(self, agent_id: str, config: dict):
        if not self._redis:
            return
        try:
            await self._redis.set(
                f"{REDIS_PREFIX}{agent_id}",
                json.dumps(config, ensure_ascii=False),
                ex=REDIS_TTL,
            )
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    async def _invalidate_cache(self, agent_id: str):
        if not self._redis:
            return
        try:
            await self._redis.delete(f"{REDIS_PREFIX}{agent_id}")
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
