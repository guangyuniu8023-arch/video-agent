"""SQLAlchemy 模型 - Agent 配置 + 画布节点/边 + MCP 服务 + Prompt 版本 + 路由规则"""

import datetime
from sqlalchemy import (
    Column, Integer, Float, String, Text, Boolean, DateTime, JSON,
    create_engine,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


class PromptVersion(Base):
    """Agent Prompt 版本表 — 支持版本历史 + 回滚"""
    __tablename__ = "prompt_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    system_prompt = Column(Text, nullable=False)
    available_tools = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    editor = Column(String(64), nullable=False, default="admin")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentConfig(Base):
    """Agent 配置表 — 支持层级 (Sub-Agent) + 数据驱动"""
    __tablename__ = "agent_configs"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    agent_type = Column(String(32), nullable=False, default="react")
    execution_mode = Column(String(16), nullable=False, default="react")  # react | parallel
    parent_id = Column(String(64), nullable=True, index=True)
    system_prompt = Column(Text, nullable=False, default="")
    available_tools = Column(JSON, nullable=False, default=list)
    llm_config = Column(JSON, nullable=False, default=dict)
    bypass = Column(Boolean, nullable=False, default=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class CanvasNode(Base):
    """画布节点 — 所有可视化节点的位置和类型"""
    __tablename__ = "canvas_nodes"

    id = Column(String(64), primary_key=True)
    node_type = Column(String(16), nullable=False)   # agent | skill | mcp | trigger | skillgroup | subagentgroup | mcpgroup
    ref_id = Column(String(64), nullable=False)
    position_x = Column(Float, nullable=False, default=0)
    position_y = Column(Float, nullable=False, default=0)
    config = Column(JSON, nullable=False, default=dict)     # 容器内容: {"items": [...]}
    parent_canvas = Column(String(64), nullable=True)       # 所属画布 (null=主画布)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class CanvasEdge(Base):
    """画布连线 — 节点间的关系 (执行流 / 工具绑定)"""
    __tablename__ = "canvas_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(64), nullable=False, index=True)  # canvas_nodes.id
    target_id = Column(String(64), nullable=False, index=True)  # canvas_nodes.id
    edge_type = Column(String(16), nullable=False, default="tool")  # "flow" | "tool"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class McpServer(Base):
    """MCP 服务注册表 — 外部 MCP 服务连接配置和状态"""
    __tablename__ = "mcp_servers"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    transport = Column(String(16), nullable=False, default="sse")  # "sse" | "stdio"
    url = Column(Text, nullable=True)                               # SSE: http://...
    command = Column(Text, nullable=True)                            # stdio: "npx ..."
    env_vars = Column(JSON, nullable=False, default=dict)
    status = Column(String(16), nullable=False, default="disconnected")
    discovered_tools = Column(JSON, nullable=False, default=list)
    last_health_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class WorkflowVersion(Base):
    """工作流版本快照 — 保存画布配置用于发布"""
    __tablename__ = "workflow_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(32), nullable=False)
    description = Column(Text, nullable=False, default="")
    is_published = Column(Boolean, nullable=False, default=False)
    snapshot = Column(JSON, nullable=False)  # {canvas_nodes, canvas_edges, agent_configs}
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class RoutingRule(Base):
    """路由规则表 — 可配置的意图路由"""
    __tablename__ = "routing_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True)

    target_type = Column(String(32), nullable=False, default="full_pipeline")
    target_skill = Column(String(128), nullable=True)
    skip_agents = Column(JSON, nullable=False, default=list)

    match_description = Column(Text, nullable=False, default="")

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


_async_engine = None
_async_session_factory = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(settings.database_url, echo=False)
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _async_session_factory


async def init_db():
    """创建所有表（开发环境用，生产环境用 Alembic）"""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
