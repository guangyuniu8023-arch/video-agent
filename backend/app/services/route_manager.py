"""RouteManager — 路由规则 CRUD + Redis 缓存

路由规则存储在 PostgreSQL，Redis 缓存活跃规则列表。
"""

import json
import logging
from typing import Optional

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import RoutingRule, get_session_factory

logger = logging.getLogger(__name__)

REDIS_KEY = "routing_rules:active"
REDIS_TTL = 30


class RouteManager:
    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._session_factory = get_session_factory()

    async def get_active_rules(self) -> list[dict]:
        """获取所有启用的路由规则 (Redis 缓存 → DB 回退)，按 priority 排序"""
        cached = await self._get_from_cache()
        if cached is not None:
            return cached

        async with self._session_factory() as session:
            result = await session.execute(
                select(RoutingRule)
                .where(RoutingRule.enabled == True)
                .order_by(RoutingRule.priority.asc())
            )
            rows = result.scalars().all()

        rules = [self._row_to_dict(r) for r in rows]
        await self._set_cache(rules)
        return rules

    async def get_all_rules(self) -> list[dict]:
        """获取所有规则（含禁用的），按 priority 排序"""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoutingRule).order_by(RoutingRule.priority.asc())
            )
            rows = result.scalars().all()
        return [self._row_to_dict(r) for r in rows]

    async def get_rule(self, rule_id: int) -> Optional[dict]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoutingRule).where(RoutingRule.id == rule_id)
            )
            row = result.scalar_one_or_none()
        return self._row_to_dict(row) if row else None

    async def create_rule(self, data: dict) -> dict:
        async with self._session_factory() as session:
            rule = RoutingRule(
                name=data["name"],
                description=data.get("description", ""),
                priority=data.get("priority", 100),
                enabled=data.get("enabled", True),
                target_type=data.get("target_type", "full_pipeline"),
                target_skill=data.get("target_skill"),
                skip_agents=data.get("skip_agents", []),
                match_description=data.get("match_description", ""),
            )
            session.add(rule)
            await session.commit()
            await session.refresh(rule)

        await self._invalidate_cache()
        logger.info(f"Routing rule created: id={rule.id} name={rule.name}")
        return self._row_to_dict(rule)

    async def update_rule(self, rule_id: int, updates: dict) -> Optional[dict]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoutingRule).where(RoutingRule.id == rule_id)
            )
            rule = result.scalar_one_or_none()
            if not rule:
                return None

            for key, value in updates.items():
                if value is not None and hasattr(rule, key):
                    setattr(rule, key, value)
            await session.commit()
            await session.refresh(rule)

        await self._invalidate_cache()
        return self._row_to_dict(rule)

    async def toggle_rule(self, rule_id: int, enabled: bool) -> Optional[dict]:
        return await self.update_rule(rule_id, {"enabled": enabled})

    async def reorder_rules(self, rule_ids: list[int]):
        """根据传入的 ID 列表重新排序 (列表顺序 = 新 priority)"""
        async with self._session_factory() as session:
            for idx, rid in enumerate(rule_ids):
                await session.execute(
                    update(RoutingRule)
                    .where(RoutingRule.id == rid)
                    .values(priority=idx + 1)
                )
            await session.commit()
        await self._invalidate_cache()

    async def delete_rule(self, rule_id: int) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(RoutingRule).where(RoutingRule.id == rule_id)
            )
            await session.commit()
        await self._invalidate_cache()
        return result.rowcount > 0

    # ── 内部方法 ──

    def _row_to_dict(self, row: RoutingRule) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "priority": row.priority,
            "enabled": row.enabled,
            "target_type": row.target_type,
            "target_skill": row.target_skill,
            "skip_agents": row.skip_agents or [],
            "match_description": row.match_description,
            "created_at": row.created_at.isoformat() if row.created_at else "",
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

    async def _get_from_cache(self) -> Optional[list[dict]]:
        if not self._redis:
            return None
        try:
            data = await self._redis.get(REDIS_KEY)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
        return None

    async def _set_cache(self, rules: list[dict]):
        if not self._redis:
            return
        try:
            await self._redis.set(
                REDIS_KEY,
                json.dumps(rules, ensure_ascii=False),
                ex=REDIS_TTL,
            )
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")

    async def _invalidate_cache(self):
        if not self._redis:
            return
        try:
            await self._redis.delete(REDIS_KEY)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
