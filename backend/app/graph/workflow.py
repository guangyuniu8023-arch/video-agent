"""LangGraph 状态图 - Router → Planner → Producer → Editor → QualityGate

Sprint 1: Router(简化) + Planner + Producer 可用
Sprint 2: Editor + QualityGate 完善
Sprint 3: Human-in-the-loop (Planner 追问 → 挂起等待 → 用户回复 → 恢复)
Sprint 4: Router LLM 意图路由 + PromptManager 热更新
"""

import asyncio
import json
import logging
import os
import uuid

from langgraph.graph import StateGraph, END

from app.graph.state import VideoProjectState
from app.graph.callbacks import (
    push_agent_status,
    push_edge_active,
    push_log_entry,
)
from app.api.websocket import ws_manager
from app.agents.generic import GenericAgent, get_agent_config

logger = logging.getLogger(__name__)

_generic_agent = GenericAgent()

# Sprint 4: 路由管理器 (由 main.py lifespan 注入)
_route_manager = None


def set_route_manager(rm):
    global _route_manager
    _route_manager = rm


def get_route_manager():
    return _route_manager


ROUTER_SYSTEM_PROMPT = """\
你是一个意图路由器。根据用户的请求和可用的路由规则，判断应该走哪条执行路径。

## 可用路由规则
{active_rules_json}

## 判断标准
1. 逐条检查启用的路由规则（按优先级排序）
2. 如果用户请求明确匹配某条规则的 match_description，返回该规则的 target
3. 如果没有匹配任何规则，返回 "full_pipeline"（走完整链路）
4. 如果不确定，宁可走 full_pipeline 也不要误路由

## 输出格式
严格输出 JSON，不要任何其他文字:
{{"route": "full_pipeline", "rule_id": null, "reason": "简短理由"}}

route 可选值: full_pipeline | skip_to_producer | skip_to_editor | direct_skill
"""


def create_initial_state(
    user_request: str,
    project_id: str | None = None,
    uploaded_assets: list[dict] | None = None,
) -> VideoProjectState:
    """创建初始 State"""
    return VideoProjectState(
        user_request=user_request,
        uploaded_assets=uploaded_assets or [],
        conversation_history=[],
        route_decision="full_pipeline",
        matched_rule_id=None,
        direct_skill_name=None,
        plan=None,
        needs_clarification=False,
        clarification_question="",
        raw_clips=[],
        generation_errors=[],
        scenes_to_regenerate=[],
        final_video_path=None,
        edit_log=[],
        current_phase="routing",
        project_id=project_id or str(uuid.uuid4()),
        retry_count=0,
        max_retries=3,
    )


# ── Node functions ──────────────────────────────────────────────

async def router_node(state: VideoProjectState) -> dict:
    """Router 节点: LLM 意图路由 (有规则时) / 直走全链路 (无规则时)"""
    project_id = state.get("project_id", "default")
    await push_agent_status(project_id, "router", "running")
    await push_log_entry(project_id, "router", "路由分析中...")

    route_decision = "full_pipeline"
    matched_rule_id = None
    direct_skill_name = None

    rm = get_route_manager()
    if rm:
        try:
            rules = await rm.get_active_rules()
            if rules:
                decision = await _llm_route(state["user_request"], rules)
                route_decision = decision.get("route", "full_pipeline")
                matched_rule_id = decision.get("rule_id")
                if route_decision == "direct_skill":
                    matched = next((r for r in rules if r["id"] == matched_rule_id), None)
                    direct_skill_name = matched.get("target_skill") if matched else None

                await push_log_entry(
                    project_id, "router",
                    f"LLM 路由: {route_decision} (规则: {matched_rule_id}, 原因: {decision.get('reason', '')})"
                )
            else:
                await push_log_entry(project_id, "router", "无路由规则，走完整链路")
        except Exception as e:
            logger.warning(f"Router LLM failed, fallback to full_pipeline: {e}")
            await push_log_entry(project_id, "router", f"路由失败, 回退全链路: {e}")
    else:
        await push_log_entry(project_id, "router", "路由决策: full_pipeline (完整链路)")

    await push_edge_active(project_id, "router->planner", True)
    await push_agent_status(project_id, "router", "success")

    return {
        "route_decision": route_decision,
        "matched_rule_id": matched_rule_id,
        "direct_skill_name": direct_skill_name,
        "current_phase": "planning",
    }


async def _llm_route(user_request: str, rules: list[dict]) -> dict:
    """调用 LLM 做意图路由"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    from app.config import get_settings
    from app.agents.base import get_global_prompt_manager

    settings = get_settings()
    llm_key = settings.ark_llm_api_key or settings.ark_api_key

    if llm_key and settings.ark_llm_endpoint_id:
        llm = ChatOpenAI(
            model=settings.ark_llm_endpoint_id,
            api_key=llm_key,
            base_url=settings.ark_llm_base_url,
            temperature=0,
            max_tokens=256,
        )
    elif settings.openai_api_key:
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.openai_api_key,
            temperature=0,
            max_tokens=256,
        )
    else:
        return {"route": "full_pipeline", "rule_id": None, "reason": "无 LLM 配置"}

    # 获取 Router 的自定义 prompt (如有)
    pm = get_global_prompt_manager()
    router_prompt = ROUTER_SYSTEM_PROMPT
    if pm:
        try:
            config = await pm.get_active_prompt("router")
            if config and config.get("system_prompt"):
                router_prompt = config["system_prompt"]
        except Exception:
            pass

    rules_summary = [
        {"id": r["id"], "name": r["name"], "target_type": r["target_type"],
         "match_description": r["match_description"]}
        for r in rules
    ]
    prompt = router_prompt.format(
        active_rules_json=json.dumps(rules_summary, ensure_ascii=False, indent=2)
    )

    result = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=user_request),
    ])

    try:
        content = result.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except (json.JSONDecodeError, IndexError):
        logger.warning(f"Router LLM returned unparseable response: {result.content[:200]}")
        return {"route": "full_pipeline", "rule_id": None, "reason": "LLM 输出解析失败"}


async def planner_node(state: VideoProjectState) -> dict:
    """Planner 节点: 从 DB 读配置 → GenericAgent 执行"""
    project_id = state.get("project_id", "default")
    await push_edge_active(project_id, "router->planner", False)
    await push_edge_active(project_id, "planner->producer", False)

    config = await get_agent_config("planner")
    if not config:
        return {"plan": None, "current_phase": "error", "needs_clarification": False, "clarification_question": ""}

    if config.bypass:
        await push_log_entry(project_id, "planner", "已跳过 (bypass)")
        await push_agent_status(project_id, "planner", "success")
        await push_edge_active(project_id, "planner->producer", True)
        return {"current_phase": "producing", "needs_clarification": False, "clarification_question": ""}

    result = await _generic_agent.run(config, dict(state), project_id)

    if result.get("needs_clarification"):
        question = result.get("clarification_question", "")
        await push_edge_active(project_id, "planner->human_feedback", True)
        await ws_manager.broadcast(project_id, {
            "type": "clarification_needed",
            "question": question,
        })
    elif result.get("plan"):
        await push_edge_active(project_id, "planner->producer", True)
    elif result.get("scenes"):
        result = {"plan": result, "current_phase": "producing", "needs_clarification": False, "clarification_question": ""}
        await push_edge_active(project_id, "planner->producer", True)
    elif result.get("text_output"):
        result = {
            "plan": None, "current_phase": "planning",
            "needs_clarification": True,
            "clarification_question": result["text_output"],
        }
        await push_edge_active(project_id, "planner->human_feedback", True)
        await ws_manager.broadcast(project_id, {"type": "clarification_needed", "question": result["clarification_question"]})

    return result


async def producer_node(state: VideoProjectState) -> dict:
    """Producer 节点: 从 DB 读配置 → GenericAgent 执行"""
    project_id = state.get("project_id", "default")
    await push_edge_active(project_id, "planner->producer", False)

    config = await get_agent_config("producer")
    if not config:
        return {"raw_clips": [], "generation_errors": [{"error": "Producer 配置不存在"}], "current_phase": "error"}

    if config.bypass:
        await push_log_entry(project_id, "producer", "已跳过 (bypass)")
        await push_agent_status(project_id, "producer", "success")
        await push_edge_active(project_id, "producer->editor", True)
        return {"raw_clips": state.get("raw_clips", []), "generation_errors": [], "scenes_to_regenerate": [], "current_phase": "editing"}

    result = await _generic_agent.run(config, dict(state), project_id)

    raw_clips = result.get("raw_clips", result.get("results", []))
    if isinstance(raw_clips, list) and raw_clips:
        await push_edge_active(project_id, "producer->editor", True)

    return {
        "raw_clips": raw_clips if isinstance(raw_clips, list) else [],
        "generation_errors": result.get("generation_errors", []),
        "scenes_to_regenerate": [],
        "current_phase": "editing",
    }


async def editor_node(state: VideoProjectState) -> dict:
    """Editor 节点: 下载 raw_clips → GenericAgent 执行后期合成"""
    project_id = state.get("project_id", "default")
    await push_edge_active(project_id, "producer->editor", False)

    raw_clips = state.get("raw_clips", [])
    if not raw_clips:
        await push_agent_status(project_id, "editor", "error", error="无可编辑的视频片段")
        return {
            "final_video_path": None,
            "edit_log": [{"action": "error", "detail": "无视频片段"}],
            "current_phase": "error",
        }

    from app.tools.file_ops import download_video
    from app.config import get_settings

    settings = get_settings()
    clips_dir = os.path.join(settings.output_dir, project_id, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    await push_log_entry(project_id, "editor", f"下载 {len(raw_clips)} 个视频片段到本地...")

    for clip in raw_clips:
        video_url = clip.get("video_url", "")
        if not video_url:
            continue
        if clip.get("local_path") and os.path.exists(clip["local_path"]):
            continue
        try:
            local_path = os.path.join(clips_dir, f"scene_{clip['scene_id']}.mp4")
            dl_result = await download_video(video_url, local_path)
            clip["local_path"] = dl_result["local_path"]
            await push_log_entry(project_id, "editor", f"分镜 {clip['scene_id']} 下载完成")
        except Exception as e:
            logger.error(f"Failed to download clip {clip.get('scene_id')}: {e}")
            clip["local_path"] = ""

    state_copy = dict(state)
    state_copy["raw_clips"] = raw_clips

    config = await get_agent_config("editor")
    if not config:
        return {"final_video_path": None, "edit_log": [], "current_phase": "error"}

    if config.bypass:
        await push_log_entry(project_id, "editor", "已跳过 (bypass)")
        await push_agent_status(project_id, "editor", "success")
        fallback = raw_clips[0].get("local_path", raw_clips[0].get("video_url", "")) if raw_clips else ""
        return {"final_video_path": fallback, "edit_log": [{"action": "bypass"}], "scenes_to_regenerate": [], "current_phase": "complete"}

    result = await _generic_agent.run(config, state_copy, project_id)

    if result.get("final_video_path"):
        await push_edge_active(project_id, "editor->quality_gate", True)

    return {
        "final_video_path": result.get("final_video_path", ""),
        "edit_log": result.get("edit_actions", result.get("edit_log", [])),
        "scenes_to_regenerate": result.get("scenes_to_regenerate", []),
        "current_phase": "complete" if not result.get("scenes_to_regenerate") else "producing",
    }


async def quality_gate_node(state: VideoProjectState) -> dict:
    """质量门控: VLM 评估最终视频 → pass / regenerate / fail"""
    project_id = state.get("project_id", "default")
    await push_agent_status(project_id, "quality_gate", "running")
    await push_edge_active(project_id, "editor->quality_gate", False)
    await push_log_entry(project_id, "quality_gate", "VLM 质量评估中...")

    final_video = state.get("final_video_path", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if not final_video:
        await push_agent_status(project_id, "quality_gate", "error", error="无最终视频")
        return {"current_phase": "error"}

    from app.tools.analysis import evaluate_video

    try:
        eval_result = await evaluate_video(final_video, criteria="overall")
        score = eval_result.get("score", 0)
        reason = eval_result.get("reason", "")

        await ws_manager.broadcast(project_id, {
            "type": "quality_score",
            "score": score,
            "reason": reason,
            "retry_count": retry_count,
        })
        await push_log_entry(
            project_id, "quality_gate",
            f"质量评分: {score}/100 - {reason[:80]}"
        )

        if score >= 70:
            await push_agent_status(project_id, "quality_gate", "success",
                                    data={"quality_score": score})
            await push_log_entry(project_id, "quality_gate", "质量检查通过!")
            return {"current_phase": "complete"}

        if retry_count >= max_retries:
            await push_agent_status(project_id, "quality_gate", "error",
                                    data={"quality_score": score})
            await push_log_entry(
                project_id, "quality_gate",
                f"质量不达标 ({score}/100) 且已达最大重试次数 ({max_retries}), 强制完成"
            )
            return {"current_phase": "complete"}

        await push_agent_status(project_id, "quality_gate", "running",
                                data={"quality_score": score})
        await push_log_entry(
            project_id, "quality_gate",
            f"质量不达标 ({score}/100), 触发重新生成 (第 {retry_count + 1} 次重试)"
        )

        low_score_scenes = _identify_low_quality_scenes(state, score)

        return {
            "current_phase": "producing",
            "retry_count": retry_count + 1,
            "scenes_to_regenerate": low_score_scenes,
        }

    except Exception as e:
        logger.error(f"Quality gate evaluation failed: {e}", exc_info=True)
        await push_agent_status(project_id, "quality_gate", "success",
                                data={"quality_score": -1})
        await push_log_entry(
            project_id, "quality_gate",
            f"VLM 评估异常 ({e}), 跳过质量检查，视为通过"
        )
        return {"current_phase": "complete"}


def _identify_low_quality_scenes(state: VideoProjectState, overall_score: int) -> list[int]:
    raw_clips = state.get("raw_clips", [])
    if not raw_clips:
        return []

    low_quality = [
        clip["scene_id"] for clip in raw_clips
        if clip.get("quality_score", 0) < 60
    ]

    if not low_quality:
        return [clip["scene_id"] for clip in raw_clips]

    return low_quality


# ── Human-in-the-loop 挂起/恢复 ─────────────────────────────────

_pending_feedback: dict[str, asyncio.Event] = {}
_feedback_replies: dict[str, str] = {}


def submit_human_feedback(project_id: str, reply: str):
    _feedback_replies[project_id] = reply
    event = _pending_feedback.get(project_id)
    if event:
        event.set()


def has_pending_feedback(project_id: str) -> bool:
    return project_id in _pending_feedback


async def human_feedback_node(state: VideoProjectState) -> dict:
    """Human Feedback 节点: 挂起等待用户回复"""
    project_id = state.get("project_id", "default")
    question = state.get("clarification_question", "")

    await push_agent_status(project_id, "human_feedback", "waiting")
    await push_edge_active(project_id, "planner->human_feedback", False)
    await push_log_entry(project_id, "human_feedback", f"等待用户回复: {question[:80]}")

    event = asyncio.Event()
    _pending_feedback[project_id] = event

    try:
        await event.wait()
    except asyncio.CancelledError:
        _pending_feedback.pop(project_id, None)
        _feedback_replies.pop(project_id, None)
        await push_agent_status(project_id, "human_feedback", "error", error="已取消")
        raise

    user_reply = _feedback_replies.pop(project_id, "")
    _pending_feedback.pop(project_id, None)

    conversation_history = list(state.get("conversation_history", []))
    conversation_history.append({"role": "assistant", "content": question})
    conversation_history.append({"role": "user", "content": user_reply})

    await push_agent_status(project_id, "human_feedback", "success")
    await push_edge_active(project_id, "human_feedback->planner", True)
    await push_log_entry(project_id, "human_feedback", f"收到用户回复: {user_reply[:80]}")

    return {
        "user_request": f"{state['user_request']}\n\n用户补充: {user_reply}",
        "conversation_history": conversation_history,
        "needs_clarification": False,
        "clarification_question": "",
        "current_phase": "planning",
    }


# ── Routing functions ───────────────────────────────────────────

def route_after_router(state: VideoProjectState) -> str:
    decision = state.get("route_decision", "full_pipeline")
    if decision == "skip_to_producer":
        return "producer"
    if decision == "skip_to_editor":
        return "editor"
    if decision == "direct_skill":
        return "end"
    return "planner"


def route_after_planner(state: VideoProjectState) -> str:
    if state.get("needs_clarification"):
        return "human_feedback"
    if state.get("current_phase") == "error":
        return "end"
    return "producer"


def route_after_quality(state: VideoProjectState) -> str:
    scenes_to_regen = state.get("scenes_to_regenerate", [])
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    if scenes_to_regen and retry_count < max_retries:
        return "regenerate"
    return "pass"


# ── Node registry: agent_id → node function ────────────────────

NODE_FUNCTIONS = {
    "router": router_node,
    "planner": planner_node,
    "human_feedback": human_feedback_node,
    "producer": producer_node,
    "editor": editor_node,
    "quality_gate": quality_gate_node,
}


async def _generic_node_fn(state: VideoProjectState, agent_id: str) -> dict:
    """通用节点函数: 从 DB 读配置 → GenericAgent 执行"""
    project_id = state.get("project_id", "default")
    config = await get_agent_config(agent_id)
    if not config:
        return {"current_phase": "error"}
    if config.bypass:
        await push_log_entry(project_id, agent_id, "已跳过 (bypass)")
        await push_agent_status(project_id, agent_id, "success")
        return {}
    return await _generic_agent.run(config, dict(state), project_id)


# ── Dynamic Build Graph ─────────────────────────────────────────

CONDITIONAL_NODES = {
    "router": (route_after_router, {"planner": "planner", "producer": "producer", "editor": "editor", "end": END}),
    "planner": (route_after_planner, {"producer": "producer", "human_feedback": "human_feedback", "end": END}),
    "quality_gate": (route_after_quality, {"pass": END, "regenerate": "producer"}),
}

FIXED_EDGES = {
    "human_feedback": "planner",
}


async def _load_flow_edges() -> list[tuple[str, str]]:
    """从 canvas_edges 加载所有 flow 边"""
    from app.models.database import CanvasEdge, CanvasNode, get_session_factory
    from sqlalchemy import select

    sf = get_session_factory()
    async with sf() as session:
        result = await session.execute(
            select(CanvasEdge).where(CanvasEdge.edge_type == "flow")
        )
        edges = result.scalars().all()

        flow_edges = []
        for e in edges:
            src = e.source_id.replace("agent:", "") if e.source_id.startswith("agent:") else e.source_id
            tgt = e.target_id.replace("agent:", "") if e.target_id.startswith("agent:") else e.target_id
            flow_edges.append((src, tgt))

        return flow_edges


def build_workflow(flow_edges: list[tuple[str, str]]) -> StateGraph:
    """从 flow 边动态构建 LangGraph 工作流"""
    workflow = StateGraph(VideoProjectState)

    all_agents = set()
    for src, tgt in flow_edges:
        all_agents.add(src)
        all_agents.add(tgt)

    for fixed_src, fixed_tgt in FIXED_EDGES.items():
        all_agents.add(fixed_src)
        all_agents.add(fixed_tgt)

    for agent_id in all_agents:
        if agent_id in NODE_FUNCTIONS:
            workflow.add_node(agent_id, NODE_FUNCTIONS[agent_id])
        else:
            async def make_fn(aid=agent_id):
                async def fn(state: VideoProjectState) -> dict:
                    return await _generic_node_fn(state, aid)
                return fn
            import functools
            node_fn = functools.partial(_generic_node_fn, agent_id=agent_id)

            async def wrapper(state, _aid=agent_id):
                return await _generic_node_fn(state, _aid)
            workflow.add_node(agent_id, wrapper)

    in_degree = {a: 0 for a in all_agents}
    for src, tgt in flow_edges:
        in_degree[tgt] = in_degree.get(tgt, 0) + 1
    entry_candidates = [a for a in all_agents if in_degree.get(a, 0) == 0]
    entry_point = "router" if "router" in entry_candidates else (entry_candidates[0] if entry_candidates else "router")
    workflow.set_entry_point(entry_point)

    adjacency: dict[str, list[str]] = {}
    for src, tgt in flow_edges:
        adjacency.setdefault(src, []).append(tgt)

    connected_sources = set()

    for agent_id in all_agents:
        if agent_id in CONDITIONAL_NODES:
            route_fn, route_map = CONDITIONAL_NODES[agent_id]
            targets = adjacency.get(agent_id, [])
            final_map = dict(route_map)
            for t in targets:
                if t not in final_map.values():
                    final_map[t] = t
            workflow.add_conditional_edges(agent_id, route_fn, final_map)
            connected_sources.add(agent_id)

    for agent_id in all_agents:
        if agent_id in connected_sources:
            continue
        if agent_id in FIXED_EDGES:
            workflow.add_edge(agent_id, FIXED_EDGES[agent_id])
            connected_sources.add(agent_id)
            continue
        targets = adjacency.get(agent_id, [])
        if len(targets) == 1:
            workflow.add_edge(agent_id, targets[0])
            connected_sources.add(agent_id)
        elif len(targets) == 0:
            workflow.add_edge(agent_id, END)
            connected_sources.add(agent_id)

    return workflow


async def compile_workflow_async():
    flow_edges = await _load_flow_edges()
    if not flow_edges:
        flow_edges = [
            ("router", "planner"),
            ("planner", "producer"),
            ("producer", "editor"),
            ("editor", "quality_gate"),
        ]
    workflow = build_workflow(flow_edges)
    return workflow.compile()


def compile_workflow():
    """同步编译 (首次启动用, 使用默认拓扑)"""
    default_edges = [
        ("router", "planner"),
        ("planner", "producer"),
        ("producer", "editor"),
        ("editor", "quality_gate"),
    ]
    workflow = build_workflow(default_edges)
    return workflow.compile()


_compiled_app = None


def get_workflow_app():
    global _compiled_app
    if _compiled_app is None:
        _compiled_app = compile_workflow()
    return _compiled_app


async def rebuild_workflow():
    """重建工作流 (画布 flow 边变化时调用)"""
    global _compiled_app
    _compiled_app = await compile_workflow_async()
    logger.info("Workflow rebuilt from canvas_edges")
    return _compiled_app
