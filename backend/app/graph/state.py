"""LangGraph State 定义 - 全局数据总线"""

from typing import TypedDict, Optional


class VideoProjectState(TypedDict):
    # 用户输入
    user_request: str
    uploaded_assets: list[dict]       # [{type, path, url}]
    conversation_history: list[dict]

    # Router 输出
    route_decision: str               # full_pipeline | skip_to_producer | skip_to_editor | direct_skill
    matched_rule_id: Optional[int]
    direct_skill_name: Optional[str]

    # Planner 输出
    plan: Optional[dict]              # 完整制作计划 (characters, world_setting, scenes, music)
    needs_clarification: bool
    clarification_question: str

    # Producer 输出
    raw_clips: list[dict]             # [{scene_id, video_url, local_path, quality_score}]
    generation_errors: list[dict]
    scenes_to_regenerate: list[int]

    # Editor 输出
    final_video_path: Optional[str]
    edit_log: list[dict]

    # 流程控制
    current_phase: str                # routing | planning | producing | editing | complete | error
    project_id: str
    retry_count: int
    max_retries: int
