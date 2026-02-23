"""GenericAgent — 数据驱动的通用 Agent 执行器

从 DB AgentConfig 读取配置 (prompt/tools/llm_config)，动态组装 ReAct Agent 或纯 LLM 调用。
available_tools 里可以是 Skill 名 (TOOL_REGISTRY) 或 Sub-Agent id (agent_configs)。
Sub-Agent 自动包装为 @tool 函数 (Agent-as-a-Tool 模式)。

执行模式 (execution_mode):
  - react (默认): 父 Agent LLM 通过 ReAct 逐个决定调用子 Agent (串行)
  - parallel: 所有子 Agent 并发执行, 结果合并后交给父 Agent 总结
"""

import json
import logging
import asyncio

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import get_settings
from app.tools import TOOL_REGISTRY
from app.graph.callbacks import push_agent_status, push_log_entry, StreamingWSCallback

logger = logging.getLogger(__name__)


async def get_agent_config(agent_id: str):
    """从 DB 读取 AgentConfig"""
    from app.models.database import AgentConfig, get_session_factory
    from sqlalchemy import select

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.id == agent_id)
        )
        return result.scalar_one_or_none()


async def get_child_agents(parent_id: str):
    """获取子 Agent 列表"""
    from app.models.database import AgentConfig, get_session_factory
    from sqlalchemy import select

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(AgentConfig).where(AgentConfig.parent_id == parent_id, AgentConfig.enabled == True)
        )
        return result.scalars().all()


class GenericAgent:
    """数据驱动的通用 Agent 执行器

    execution_mode:
      - react: 父 Agent LLM 逐个决定调用子 Agent (串行, 默认)
      - parallel: 所有子 Agent 并发执行, 结果合并
    """

    async def run(self, config, state: dict, project_id: str = "default") -> dict:
        agent_id = config.id
        execution_mode = getattr(config, 'execution_mode', 'react') or 'react'

        await push_agent_status(project_id, agent_id, "running")
        await push_log_entry(project_id, agent_id, f"{config.name} 开始执行...")

        try:
            if execution_mode == "parallel":
                children = await get_child_agents(agent_id)
                if children:
                    output = await self._execute_parallel(config, children, state, project_id)
                else:
                    output = await self._execute_react(config, state, project_id)
            else:
                output = await self._execute_react(config, state, project_id)

            await push_log_entry(project_id, agent_id, f"{config.name} 执行完成")
            await push_agent_status(project_id, agent_id, "success")
            return output

        except Exception as e:
            logger.error(f"GenericAgent {agent_id} failed: {e}", exc_info=True)
            await push_agent_status(project_id, agent_id, "error", error=str(e))
            await push_log_entry(project_id, agent_id, f"{config.name} 执行失败: {e}")
            return {"current_phase": "error", "generation_errors": [{"error": str(e)}]}

    async def _execute_react(self, config, state: dict, project_id: str) -> dict:
        """ReAct 模式: LLM 逐个决定调用工具/子 Agent (串行)"""
        streaming_cb = StreamingWSCallback(project_id, config.id)
        llm = self._build_llm(config.llm_config, callbacks=[streaming_cb])
        tools = await self._resolve_all_tools(config.available_tools, state, project_id)

        system_prompt = config.system_prompt or ""
        user_message = self._build_user_message(state)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

        if config.agent_type == "llm" or not tools:
            result = await llm.ainvoke(messages)
            result = {"messages": [result]}
        else:
            agent = create_react_agent(llm, tools)
            result = await agent.ainvoke({"messages": messages})

        return self._parse_output(config, result)

    async def _execute_parallel(self, config, children, state: dict, project_id: str) -> dict:
        """并行模式: 所有子 Agent 同时执行, 结果合并后由父 LLM 总结"""
        active = [c for c in children if not c.bypass]

        await push_log_entry(project_id, config.id,
            f"并行执行 {len(active)} 个子 Agent: {[c.id for c in active]}")

        async def run_child(child_config):
            try:
                result = await GenericAgent().run(child_config, state, project_id)
                return child_config.id, result
            except Exception as e:
                logger.error(f"Parallel child {child_config.id} failed: {e}")
                return child_config.id, {"error": str(e)}

        results = await asyncio.gather(*(run_child(c) for c in active))
        child_outputs = {cid: out for cid, out in results}

        await push_log_entry(project_id, config.id,
            f"子 Agent 并行执行完毕, 开始汇总")

        streaming_cb = StreamingWSCallback(project_id, config.id)
        llm = self._build_llm(config.llm_config, callbacks=[streaming_cb])
        system_prompt = config.system_prompt or ""
        user_message = self._build_user_message(state)

        summary_block = "\n".join(
            f"[{cid}] 输出:\n```json\n{json.dumps(out, ensure_ascii=False, default=str)}\n```"
            for cid, out in child_outputs.items()
        )
        combined_message = f"{user_message}\n\n## 子 Agent 执行结果\n{summary_block}"

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=combined_message)]
        result = await llm.ainvoke(messages)
        output = self._parse_output(config, {"messages": [result]})
        output["_child_outputs"] = child_outputs
        return output

    async def _resolve_all_tools(self, tool_names: list[str], state: dict, project_id: str) -> list:
        """解析 available_tools: Skill → 函数, Sub-Agent → 包装为 Tool, MCP → 包装为 Tool"""
        from app.skills.registry import get_skill_registry

        if not tool_names:
            return []

        registry = get_skill_registry()
        resolved = []
        mcp_servers_loaded: dict[str, bool] = {}

        for name in tool_names:
            if name.startswith("mcp_"):
                parts = name.split("_", 2)
                if len(parts) >= 3:
                    server_id = parts[1]
                    if server_id not in mcp_servers_loaded:
                        mcp_tools = await self._load_mcp_tools(server_id)
                        resolved.extend(mcp_tools)
                        mcp_servers_loaded[server_id] = True
                continue

            if name in TOOL_REGISTRY:
                skill = registry.get(name)
                if skill and skill.trigger and "always" not in skill.trigger:
                    if not registry._check_triggers(skill.trigger, state):
                        continue
                resolved.append(TOOL_REGISTRY[name])
                continue

            sub_config = await get_agent_config(name)
            if sub_config and sub_config.enabled:
                wrapped = self._wrap_sub_agent(sub_config, state, project_id)
                resolved.append(wrapped)
                continue

            logger.warning(f"Tool/Agent '{name}' not found in TOOL_REGISTRY or agent_configs")

        return resolved

    async def _load_mcp_tools(self, server_id: str) -> list:
        """从 MCP 服务加载工具"""
        from app.models.database import McpServer, get_session_factory
        from app.services.mcp_client import get_mcp_manager
        from sqlalchemy import select

        sf = get_session_factory()
        async with sf() as session:
            result = await session.execute(select(McpServer).where(McpServer.id == server_id))
            server = result.scalar_one_or_none()

        if not server or not server.discovered_tools:
            return []

        manager = get_mcp_manager()
        return manager.wrap_tools_for_agent(server_id, server.discovered_tools)

    def _wrap_sub_agent(self, sub_config, parent_state: dict, project_id: str):
        """将 Sub-Agent 包装为 @tool 函数"""
        config_snapshot = sub_config
        desc = f"{sub_config.name}: {sub_config.description}" if sub_config.description else f"调用子 Agent: {sub_config.name}"

        @tool(description=desc)
        async def sub_agent_fn(task: str) -> str:
            """调用子 Agent 执行任务"""
            merged_state = {**parent_state, "sub_task": task}
            result = await GenericAgent().run(config_snapshot, merged_state, project_id)
            return json.dumps(result, ensure_ascii=False, default=str)

        sub_agent_fn.name = sub_config.id
        return sub_agent_fn

    def _build_llm(self, llm_config: dict | None, callbacks=None):
        settings = get_settings()
        config = llm_config or {}
        temperature = config.get("temperature", 0.5)
        max_tokens = config.get("max_tokens", 4096)
        model_override = config.get("model")

        extra = {"streaming": True}
        if callbacks:
            extra["callbacks"] = callbacks

        llm_key = settings.ark_llm_api_key or settings.ark_api_key
        model = model_override or settings.ark_llm_endpoint_id

        if llm_key and model:
            return ChatOpenAI(
                model=model,
                api_key=llm_key,
                base_url=settings.ark_llm_base_url,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
        if settings.openai_api_key:
            return ChatOpenAI(
                model=model_override or "gpt-4o",
                api_key=settings.openai_api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra,
            )
        raise RuntimeError("No LLM configured")

    def _build_user_message(self, state: dict) -> str:
        parts = []

        if state.get("sub_task"):
            parts.append(state["sub_task"])
        elif state.get("user_request"):
            parts.append(state["user_request"])

        if state.get("uploaded_assets"):
            asset_desc = ", ".join(
                f"{a['type']}: {a.get('url', a.get('path', ''))}"
                for a in state["uploaded_assets"]
            )
            parts.append(f"\n上传素材: {asset_desc}")

        if state.get("plan"):
            parts.append(f"\n制作计划:\n```json\n{json.dumps(state['plan'], ensure_ascii=False, indent=2)}\n```")

        if state.get("raw_clips"):
            parts.append(f"\n原始片段:\n```json\n{json.dumps(state['raw_clips'], ensure_ascii=False, indent=2)}\n```")

        return "\n".join(parts) if parts else "请处理当前任务"

    def _parse_output(self, config, result: dict) -> dict:
        """从 Agent 输出中解析结构化结果"""
        messages = result.get("messages", [])

        for msg in reversed(messages):
            content = getattr(msg, "content", None) or ""
            if not content or len(content) < 10:
                continue
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                parsed = json.loads(content[start:end])
                return parsed
            except (ValueError, json.JSONDecodeError):
                try:
                    start = content.index("[")
                    end = content.rindex("]") + 1
                    parsed = json.loads(content[start:end])
                    return {"results": parsed}
                except (ValueError, json.JSONDecodeError):
                    continue

        last_content = ""
        for msg in reversed(messages):
            c = getattr(msg, "content", None)
            if c and isinstance(c, str) and len(c) > 2:
                last_content = c
                break

        return {"text_output": last_content}
