"""Pydantic schemas — API 请求/响应模型"""

from pydantic import BaseModel, Field


class PromptUpdate(BaseModel):
    prompt: str = Field(..., description="新的 system prompt")


class ToolsUpdate(BaseModel):
    tools: list[str] = Field(..., description="可用工具名称列表")


class PromptVersionInfo(BaseModel):
    version: int
    system_prompt: str
    available_tools: list[str]
    is_active: bool
    editor: str
    created_at: str


class RoutingRuleCreate(BaseModel):
    name: str = Field(..., description="规则名称")
    description: str = Field("", description="规则说明")
    priority: int = Field(100, description="优先级 (越小越先)")
    enabled: bool = Field(True, description="是否启用")
    target_type: str = Field("full_pipeline", description="路由目标类型")
    target_skill: str | None = Field(None, description="direct_skill 时指定的技能名")
    skip_agents: list[str] = Field(default_factory=list, description="跳过的 Agent 列表")
    match_description: str = Field("", description="匹配描述 (供 LLM 判断)")


class RoutingRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    target_type: str | None = None
    target_skill: str | None = None
    skip_agents: list[str] | None = None
    match_description: str | None = None


class RoutingRuleToggle(BaseModel):
    enabled: bool


class RoutingRuleReorder(BaseModel):
    rule_ids: list[int] = Field(..., description="规则 ID 列表，按新的优先级顺序排列")
