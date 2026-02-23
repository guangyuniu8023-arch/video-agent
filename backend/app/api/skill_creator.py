"""Skill Creator — LLM 驱动的对话式 Skill 生成器

用户描述需求 → LLM 生成 SKILL.md + scripts/ 等文件 → 预览 → 确认保存
"""

import json
import logging
import os
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

SKILL_CREATOR_SYSTEM_PROMPT = """\
你是一个 AI Agent Skill 创建专家。你的任务是帮助用户创建符合 Agent Skills 规范的 Skill。

## Skill 结构

一个 Skill 是一个目录，包含:
- SKILL.md (必需): YAML frontmatter 元数据 + Markdown 指令
- scripts/ (可选): 可执行脚本 (Python)
- references/ (可选): 参考文档
- assets/ (可选): 模板资源

## SKILL.md 格式

```
---
name: skill_name
title: 人类可读名称
description: 功能描述
trigger:
  - "触发条件"
---

这里是 Skill 的详细指令，告诉 Agent 如何使用这个工具...
```

## 你的工作流程

1. 询问用户想要什么功能的 Skill
2. 了解清楚后，生成完整的 Skill 定义
3. 输出时使用特定格式，方便系统解析

## 输出格式

当你准备好生成 Skill 时，使用以下格式 (严格遵守):

```skill-definition
{
  "name": "skill_name",
  "files": {
    "SKILL.md": "---\\nname: ...\\n---\\n\\n指令内容",
    "scripts/tool.py": "Python 代码内容"
  }
}
```

注意:
- 不是所有 Skill 都需要 scripts，简单的 Skill 只需要 SKILL.md
- name 只能包含小写字母、数字和下划线
- 如果 Skill 需要调用外部 API，在 scripts/ 中写 Python 代码
- 如果只是给 Agent 提供指令/策略，只需要 SKILL.md
- 用中文回复用户
"""


class SkillGenerateRequest(BaseModel):
    message: str
    history: list[dict] = []


class SkillSaveRequest(BaseModel):
    name: str
    files: dict[str, str]


@router.post("/skills/generate")
async def generate_skill(body: SkillGenerateRequest):
    """LLM 对话式 Skill 生成"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    settings = get_settings()
    llm_key = settings.ark_llm_api_key or settings.ark_api_key

    if llm_key and settings.ark_llm_endpoint_id:
        llm = ChatOpenAI(
            model=settings.ark_llm_endpoint_id,
            api_key=llm_key,
            base_url=settings.ark_llm_base_url,
            temperature=0.7,
            max_tokens=4096,
        )
    elif settings.openai_api_key:
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=4096,
        )
    else:
        raise HTTPException(500, "No LLM configured")

    messages = [SystemMessage(content=SKILL_CREATOR_SYSTEM_PROMPT)]
    for msg in body.history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=body.message))

    result = await llm.ainvoke(messages)
    content = result.content

    skill_def = _extract_skill_definition(content)

    return {
        "reply": content,
        "skill_definition": skill_def,
    }


@router.post("/skills/save-generated")
async def save_generated_skill(body: SkillSaveRequest):
    """保存 LLM 生成的 Skill 到文件系统"""
    from app.skills.registry import get_skill_registry, SKILLS_DIR

    skill_dir = os.path.join(SKILLS_DIR, body.name)
    if os.path.exists(skill_dir):
        raise HTTPException(400, f"Skill '{body.name}' already exists")

    os.makedirs(skill_dir, exist_ok=True)

    for file_path, content in body.files.items():
        full_path = os.path.join(skill_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    get_skill_registry().scan()

    return {
        "name": body.name,
        "message": f"Skill '{body.name}' created with {len(body.files)} files",
        "files": list(body.files.keys()),
    }


def _extract_skill_definition(content: str) -> dict | None:
    """从 LLM 输出中提取 skill-definition 代码块"""
    pattern = r'```skill-definition\s*\n(.*?)\n```'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        try:
            text = match.group(1)
            text = text.replace('\\\n', '\\n')
            return json.loads(text)
        except json.JSONDecodeError:
            return None
