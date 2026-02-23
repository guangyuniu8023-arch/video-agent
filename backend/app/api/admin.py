"""Admin API - 数据驱动 Agent/Skill/路由规则管理

Agent 定义存 DB (agent_configs)，不再硬编码 AGENT_REGISTRY。
支持 Sub-Agent 层级 (Agent-as-a-Tool)。
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.base import get_global_prompt_manager
from app.models.database import AgentConfig, CanvasNode, CanvasEdge, get_session_factory
from app.models.schemas import (
    PromptUpdate, ToolsUpdate,
    RoutingRuleCreate, RoutingRuleUpdate, RoutingRuleToggle, RoutingRuleReorder,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_config(agent_id: str) -> AgentConfig:
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        return config


async def _get_children(parent_id: str) -> list[AgentConfig]:
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.parent_id == parent_id).order_by(AgentConfig.id)
        )
        return list(result.scalars().all())


def _config_to_dict(c: AgentConfig, children: list[AgentConfig] | None = None) -> dict:
    d = {
        "id": c.id,
        "name": c.name,
        "description": c.description or "",
        "agent_type": c.agent_type,
        "parent_id": c.parent_id,
        "system_prompt": c.system_prompt or "",
        "prompt_length": len(c.system_prompt or ""),
        "available_tools": c.available_tools or [],
        "llm_config": c.llm_config or {},
        "bypass": c.bypass if hasattr(c, 'bypass') else False,
        "execution_mode": getattr(c, 'execution_mode', 'react') or 'react',
        "enabled": c.enabled,
    }
    if children is not None:
        d["children"] = [_config_to_dict(ch) for ch in children]
    return d


# ── Agent CRUD ───────────────────────────────────────────────────

@router.get("/agents")
async def list_agents():
    """列出所有顶层 Agent (含子 Agent 计数)"""
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.parent_id == None).order_by(AgentConfig.id)
        )
        top_level = list(result.scalars().all())

    agents = []
    for c in top_level:
        children = await _get_children(c.id)
        agents.append(_config_to_dict(c, children))

    return {"agents": agents}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """获取 Agent 详情 (含子 Agent 列表)"""
    config = await _get_config(agent_id)
    children = await _get_children(agent_id)
    return _config_to_dict(config, children)


class AgentCreateRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    agent_type: str = "react"
    parent_id: str | None = None
    system_prompt: str = ""
    available_tools: list[str] = []
    llm_config: dict = {}


@router.post("/agents")
async def create_agent(body: AgentCreateRequest):
    """创建新 Agent/Sub-Agent"""
    sf = get_session_factory()
    async with sf() as session:
        existing = await session.execute(select(AgentConfig).where(AgentConfig.id == body.id))
        if existing.scalar_one_or_none():
            raise HTTPException(400, f"Agent '{body.id}' already exists")

        if body.parent_id:
            parent = await session.execute(select(AgentConfig).where(AgentConfig.id == body.parent_id))
            if not parent.scalar_one_or_none():
                raise HTTPException(404, f"Parent agent '{body.parent_id}' not found")

        config = AgentConfig(
            id=body.id,
            name=body.name,
            description=body.description,
            agent_type=body.agent_type,
            parent_id=body.parent_id,
            system_prompt=body.system_prompt,
            available_tools=body.available_tools,
            llm_config=body.llm_config,
        )
        session.add(config)

        if body.parent_id:
            parent_result = await session.execute(select(AgentConfig).where(AgentConfig.id == body.parent_id))
            parent_config = parent_result.scalar_one_or_none()
            if parent_config:
                tools = list(parent_config.available_tools or [])
                if body.id not in tools:
                    tools.append(body.id)
                    parent_config.available_tools = tools

        await session.commit()

    return {"message": f"Agent '{body.id}' created", "id": body.id}


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_type: str | None = None
    execution_mode: str | None = None
    system_prompt: str | None = None
    available_tools: list[str] | None = None
    llm_config: dict | None = None
    bypass: bool | None = None
    enabled: bool | None = None


@router.put("/agents/{agent_id}")
async def update_agent(agent_id: str, body: AgentUpdateRequest):
    """更新 Agent 配置"""
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(404, f"Agent '{agent_id}' not found")

        if body.name is not None:
            config.name = body.name
        if body.description is not None:
            config.description = body.description
        if body.agent_type is not None:
            config.agent_type = body.agent_type
        if body.execution_mode is not None:
            config.execution_mode = body.execution_mode
        if body.system_prompt is not None:
            config.system_prompt = body.system_prompt
            pm = get_global_prompt_manager()
            if pm:
                try:
                    await pm.update_prompt(agent_id, body.system_prompt, editor="admin")
                except Exception:
                    pass
        if body.available_tools is not None:
            config.available_tools = body.available_tools
            pm = get_global_prompt_manager()
            if pm:
                try:
                    await pm.update_tools(agent_id, body.available_tools, editor="admin")
                except Exception:
                    pass
        if body.llm_config is not None:
            config.llm_config = body.llm_config
        if body.bypass is not None:
            config.bypass = body.bypass
        if body.enabled is not None:
            config.enabled = body.enabled

        await session.commit()

    return {"message": f"Agent '{agent_id}' updated"}


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """删除 Agent (同时删除子 Agent)"""
    top_level_ids = {"router", "planner", "producer", "editor", "human_feedback", "quality_gate"}
    if agent_id in top_level_ids:
        raise HTTPException(400, f"Cannot delete top-level agent '{agent_id}'")

    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(404, f"Agent '{agent_id}' not found")

        children = await session.execute(select(AgentConfig).where(AgentConfig.parent_id == agent_id))
        for child in children.scalars():
            child_canvas_id = f"agent:{child.id}"
            child_cn = await session.execute(select(CanvasNode).where(CanvasNode.id == child_canvas_id))
            cn = child_cn.scalar_one_or_none()
            if cn:
                child_edges = await session.execute(
                    select(CanvasEdge).where(
                        (CanvasEdge.source_id == child_canvas_id) | (CanvasEdge.target_id == child_canvas_id)
                    )
                )
                for ce in child_edges.scalars():
                    await session.delete(ce)
                await session.delete(cn)
            await session.delete(child)

        canvas_node_id = f"agent:{agent_id}"
        cn_result = await session.execute(select(CanvasNode).where(CanvasNode.id == canvas_node_id))
        cn = cn_result.scalar_one_or_none()
        if cn:
            related_edges = await session.execute(
                select(CanvasEdge).where(
                    (CanvasEdge.source_id == canvas_node_id) | (CanvasEdge.target_id == canvas_node_id)
                )
            )
            for edge in related_edges.scalars():
                await session.delete(edge)
            await session.delete(cn)

        if config.parent_id:
            parent_result = await session.execute(select(AgentConfig).where(AgentConfig.id == config.parent_id))
            parent_config = parent_result.scalar_one_or_none()
            if parent_config:
                tools = [t for t in (parent_config.available_tools or []) if t != agent_id]
                parent_config.available_tools = tools

        await session.delete(config)
        await session.commit()

    return {"message": f"Agent '{agent_id}' deleted"}


@router.get("/agents/{agent_id}/children")
async def list_children(agent_id: str):
    """获取子 Agent 列表"""
    await _get_config(agent_id)
    children = await _get_children(agent_id)
    return {"parent_id": agent_id, "children": [_config_to_dict(c) for c in children]}


# ── Prompt 管理 (兼容旧接口) ─────────────────────────────────────

@router.get("/agents/{agent_id}/prompt")
async def get_agent_prompt(agent_id: str):
    config = await _get_config(agent_id)
    pm = get_global_prompt_manager()
    prompt = config.system_prompt
    version = None

    if pm:
        try:
            pv = await pm.get_active_prompt(agent_id)
            if pv:
                prompt = pv["system_prompt"]
                version = pv.get("version")
        except Exception:
            pass

    return {"agent_id": agent_id, "prompt": prompt, "version": version}


@router.put("/agents/{agent_id}/prompt")
async def update_agent_prompt(agent_id: str, body: PromptUpdate):
    await _get_config(agent_id)
    pm = get_global_prompt_manager()

    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        config = result.scalar_one_or_none()
        if config:
            config.system_prompt = body.prompt
            await session.commit()

    version = None
    if pm:
        try:
            r = await pm.update_prompt(agent_id, body.prompt)
            version = r.get("version")
        except Exception as e:
            logger.warning(f"PromptVersion update failed: {e}")

    return {"agent_id": agent_id, "message": "Prompt 已更新", "version": version}


@router.post("/agents/{agent_id}/prompt/reset")
async def reset_agent_prompt(agent_id: str):
    config = await _get_config(agent_id)
    return {"agent_id": agent_id, "prompt": config.system_prompt, "message": "已重置为默认"}


@router.get("/agents/{agent_id}/versions")
async def list_agent_versions(agent_id: str):
    await _get_config(agent_id)
    pm = get_global_prompt_manager()
    if not pm:
        return {"agent_id": agent_id, "versions": []}
    try:
        versions = await pm.list_versions(agent_id)
        return {"agent_id": agent_id, "versions": versions}
    except Exception as e:
        raise HTTPException(500, f"获取版本历史失败: {e}")


@router.post("/agents/{agent_id}/rollback")
async def rollback_agent_prompt(agent_id: str, body: dict):
    await _get_config(agent_id)
    target_version = body.get("version")
    if not target_version:
        raise HTTPException(400, "缺少 version 参数")

    pm = get_global_prompt_manager()
    if not pm:
        raise HTTPException(500, "PromptManager 不可用")

    try:
        result = await pm.rollback(agent_id, target_version)
        return {"agent_id": agent_id, "message": f"已回滚到版本 {target_version}", **result}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── 工具管理 ────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/tools")
async def get_agent_tools(agent_id: str):
    """获取 Agent 工具列表 (区分 Skill 和 Sub-Agent)"""
    from app.tools import TOOL_REGISTRY
    from app.skills.registry import get_skill_registry, get_tool_schema

    config = await _get_config(agent_id)
    current_tools = config.available_tools or []
    children = await _get_children(agent_id)
    child_ids = {c.id for c in children}

    registry = get_skill_registry()
    tools_list = []

    for name in current_tools:
        if name in child_ids:
            child = next(c for c in children if c.id == name)
            tools_list.append({
                "name": name,
                "type": "agent",
                "title": child.name,
                "description": child.description,
                "tools": child.available_tools or [],
            })
        elif name in TOOL_REGISTRY:
            skill = registry.get(name)
            schema = get_tool_schema(name) or {}
            tools_list.append({
                "name": name,
                "type": "skill",
                "title": skill.title if skill else "",
                "description": skill.description if skill else schema.get("description", "").split("\n")[0],
                "trigger": skill.trigger if skill else [],
            })
        else:
            tools_list.append({"name": name, "type": "unknown", "title": name, "description": ""})

    return {"agent_id": agent_id, "current_tools": current_tools, "tools": tools_list}


@router.put("/agents/{agent_id}/tools")
async def update_agent_tools(agent_id: str, body: ToolsUpdate):
    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        config.available_tools = body.tools
        await session.commit()

    pm = get_global_prompt_manager()
    if pm:
        try:
            await pm.update_tools(agent_id, body.tools, editor="admin")
        except Exception:
            pass

    return {"agent_id": agent_id, "tools": body.tools, "message": "工具列表已更新"}


@router.get("/tools")
async def list_tools():
    from app.tools import TOOL_REGISTRY
    tools = []
    for name, func in TOOL_REGISTRY.items():
        doc = getattr(func, "__doc__", "") or ""
        tools.append({"name": name, "description": doc.strip().split("\n")[0]})
    return {"tools": tools, "count": len(tools)}


# ── 路由规则管理 ────────────────────────────────────────────────

def _get_route_manager():
    try:
        from app.graph.workflow import get_route_manager
        return get_route_manager()
    except Exception:
        return None


@router.get("/routes")
async def list_routes():
    rm = _get_route_manager()
    if not rm:
        return {"rules": []}
    try:
        return {"rules": await rm.get_all_rules()}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/routes")
async def create_route(body: RoutingRuleCreate):
    rm = _get_route_manager()
    if not rm:
        raise HTTPException(500, "RouteManager 不可用")
    try:
        return await rm.create_rule(body.model_dump())
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/routes/{rule_id}")
async def update_route(rule_id: int, body: RoutingRuleUpdate):
    rm = _get_route_manager()
    if not rm:
        raise HTTPException(500, "RouteManager 不可用")
    try:
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        rule = await rm.update_rule(rule_id, updates)
        if not rule:
            raise HTTPException(404, f"规则 {rule_id} 不存在")
        return rule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.patch("/routes/{rule_id}/toggle")
async def toggle_route(rule_id: int, body: RoutingRuleToggle):
    rm = _get_route_manager()
    if not rm:
        raise HTTPException(500, "RouteManager 不可用")
    try:
        rule = await rm.toggle_rule(rule_id, body.enabled)
        if not rule:
            raise HTTPException(404, f"规则 {rule_id} 不存在")
        return rule
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.put("/routes/reorder")
async def reorder_routes(body: RoutingRuleReorder):
    rm = _get_route_manager()
    if not rm:
        raise HTTPException(500, "RouteManager 不可用")
    try:
        await rm.reorder_rules(body.rule_ids)
        return {"message": "排序已更新"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/routes/{rule_id}")
async def delete_route(rule_id: int):
    rm = _get_route_manager()
    if not rm:
        raise HTTPException(500, "RouteManager 不可用")
    try:
        deleted = await rm.delete_rule(rule_id)
        if not deleted:
            raise HTTPException(404, f"规则 {rule_id} 不存在")
        return {"message": "已删除", "id": rule_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Skill 管理 ──────────────────────────────────────────────────

@router.get("/skills")
async def list_skills():
    from app.skills.registry import get_skill_registry
    return {"skills": get_skill_registry().list_all()}


@router.get("/skills/{skill_name}")
async def get_skill(skill_name: str):
    from app.skills.registry import get_skill_registry
    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")
    return skill.to_dict()


@router.get("/skills/{skill_name}/content")
async def get_skill_content(skill_name: str):
    from app.skills.registry import get_skill_registry
    import os
    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")
    skill_path = os.path.join(skill.path, "SKILL.md")
    if not os.path.exists(skill_path):
        raise HTTPException(404, "SKILL.md not found")
    with open(skill_path, "r", encoding="utf-8") as f:
        return {"skill_name": skill_name, "content": f.read(), "path": skill_path}


class SkillContentUpdate(BaseModel):
    content: str


@router.put("/skills/{skill_name}/content")
async def update_skill_content(skill_name: str, body: SkillContentUpdate):
    from app.skills.registry import get_skill_registry
    import os
    registry = get_skill_registry()
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")
    skill_path = os.path.join(skill.path, "SKILL.md")
    with open(skill_path, "w", encoding="utf-8") as f:
        f.write(body.content)
    registry.scan()
    return {"skill_name": skill_name, "message": "SKILL.md 已更新，SkillRegistry 已热更新"}


class SkillCreateRequest(BaseModel):
    name: str
    title: str = ""
    description: str = ""
    trigger: list[str] = ["always"]


@router.post("/skills")
async def create_skill(body: SkillCreateRequest):
    from app.skills.registry import get_skill_registry, SKILLS_DIR
    import os
    dir_name = body.name
    skill_dir = os.path.join(SKILLS_DIR, dir_name)
    if os.path.exists(skill_dir):
        raise HTTPException(400, f"Skill 目录已存在: {dir_name}")
    os.makedirs(skill_dir)
    trigger_yaml = "\n".join(f'  - "{t}"' for t in body.trigger)
    content = f"""---
name: {body.name}
title: {body.title or body.name}
description: {body.description or '自定义 Skill'}
trigger:
{trigger_yaml}
---

{body.description or '自定义 Skill'}
"""
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)
    get_skill_registry().scan()
    return {"skill_name": body.name, "message": "Skill 已创建"}


@router.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str):
    from app.skills.registry import get_skill_registry
    import shutil
    registry = get_skill_registry()
    skill = registry.get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")
    shutil.rmtree(skill.path, ignore_errors=True)
    registry.scan()
    return {"skill_name": skill_name, "message": "Skill 已删除"}


@router.post("/skills/reload")
async def reload_skills():
    from app.skills.registry import get_skill_registry
    registry = get_skill_registry()
    registry.scan()
    return {"message": "Skills reloaded", "count": len(registry.list_all())}


# ── Skill 文件管理 (scripts/references/assets) ───────────────────

@router.get("/skills/{skill_name}/files")
async def list_skill_files(skill_name: str):
    """列出 Skill 目录下的所有文件 (分 scripts/references/assets) + 内置 tool_source 代码"""
    from app.skills.registry import get_skill_registry
    import os, inspect, importlib

    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")

    result = {"scripts": [], "references": [], "assets": [], "tool_source": None}

    for subdir in ("scripts", "references", "assets"):
        dir_path = os.path.join(skill.path, subdir)
        if os.path.isdir(dir_path):
            for f in sorted(os.listdir(dir_path)):
                full = os.path.join(dir_path, f)
                if os.path.isfile(full):
                    result[subdir].append({
                        "name": f,
                        "size": os.path.getsize(full),
                        "path": f"{subdir}/{f}",
                    })

    if skill.tool_source:
        try:
            mod = importlib.import_module(skill.tool_source)
            source_file = inspect.getfile(mod)
            with open(source_file, "r", encoding="utf-8") as f:
                source_code = f.read()
            result["tool_source"] = {
                "module": skill.tool_source,
                "file": os.path.basename(source_file),
                "content": source_code,
                "readonly": True,
            }
            if not result["scripts"]:
                result["scripts"].append({
                    "name": f"_source ({os.path.basename(source_file)})",
                    "size": len(source_code),
                    "path": f"_tool_source/{os.path.basename(source_file)}",
                    "readonly": True,
                })
        except Exception as e:
            logger.warning(f"Failed to load tool_source for {skill_name}: {e}")

    return {"skill_name": skill_name, **result}


@router.get("/skills/{skill_name}/files/{subdir}/{filename}")
async def read_skill_file(skill_name: str, subdir: str, filename: str):
    """读取 Skill 子目录中的文件内容 (含 _tool_source 虚拟路径)"""
    from app.skills.registry import get_skill_registry
    import os, inspect, importlib

    if subdir not in ("scripts", "references", "assets", "_tool_source"):
        raise HTTPException(400, f"Invalid subdir: {subdir}")

    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")

    if subdir == "_tool_source" and skill.tool_source:
        try:
            mod = importlib.import_module(skill.tool_source)
            source_file = inspect.getfile(mod)
            with open(source_file, "r", encoding="utf-8") as f:
                return {"skill_name": skill_name, "path": f"_tool_source/{filename}", "content": f.read(), "readonly": True}
        except Exception as e:
            raise HTTPException(500, f"Failed to load source: {e}")

    file_path = os.path.join(skill.path, subdir, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {subdir}/{filename}")

    with open(file_path, "r", encoding="utf-8") as f:
        return {"skill_name": skill_name, "path": f"{subdir}/{filename}", "content": f.read()}


class SkillFileUpdate(BaseModel):
    content: str


@router.put("/skills/{skill_name}/files/{subdir}/{filename}")
async def write_skill_file(skill_name: str, subdir: str, filename: str, body: SkillFileUpdate):
    """写入/更新 Skill 子目录中的文件"""
    from app.skills.registry import get_skill_registry
    import os

    if subdir not in ("scripts", "references", "assets"):
        raise HTTPException(400, f"Invalid subdir: {subdir}")

    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")

    dir_path = os.path.join(skill.path, subdir)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(body.content)

    return {"skill_name": skill_name, "path": f"{subdir}/{filename}", "message": "文件已保存"}


@router.delete("/skills/{skill_name}/files/{subdir}/{filename}")
async def delete_skill_file(skill_name: str, subdir: str, filename: str):
    """删除 Skill 子目录中的文件"""
    from app.skills.registry import get_skill_registry
    import os

    if subdir not in ("scripts", "references", "assets"):
        raise HTTPException(400, f"Invalid subdir: {subdir}")

    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")

    file_path = os.path.join(skill.path, subdir, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(404, f"File not found: {subdir}/{filename}")

    os.remove(file_path)
    return {"message": f"File {subdir}/{filename} deleted"}


@router.get("/skills/{skill_name}/metadata")
async def get_skill_metadata(skill_name: str):
    """获取 Skill 的结构化元数据 (YAML frontmatter)"""
    from app.skills.registry import get_skill_registry

    skill = get_skill_registry().get(skill_name)
    if not skill:
        raise HTTPException(404, f"Skill '{skill_name}' not found")

    return {
        "name": skill.name,
        "title": skill.title,
        "description": skill.description,
        "trigger": skill.trigger,
        "readme": skill.readme,
    }


# ── 执行记录 (占位) ─────────────────────────────────────────────

@router.get("/runs")
async def list_runs():
    return {"runs": []}
