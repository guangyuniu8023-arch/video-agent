"""SkillRegistry — 1 Skill = 1 Tool 通用协议

SKILL.md 字段: name, title, description, trigger, tool_source(可选)
Skill 不绑定 Agent，Agent-Skill 映射由 DB available_tools 管理。
支持 scripts/ 目录自动注册 @tool 函数到 TOOL_REGISTRY。
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent


class SkillInfo:
    __slots__ = ("name", "title", "description", "trigger", "tool_source", "path", "readme")

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k))

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


class SkillRegistry:
    def __init__(self, skills_dir: Path | str | None = None):
        self._skills: dict[str, SkillInfo] = {}
        self._dir = Path(skills_dir) if skills_dir else SKILLS_DIR

    def scan(self):
        self._skills.clear()
        if not self._dir.exists():
            return

        for child in sorted(self._dir.iterdir()):
            if not child.is_dir():
                continue
            skill_file = child / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                info = self._parse_skill_md(skill_file)
                if info and info.name:
                    self._skills[info.name] = info
            except Exception as e:
                logger.warning(f"Failed to parse {skill_file}: {e}")

        self._auto_register_scripts()
        logger.info(f"SkillRegistry: {len(self._skills)} skills loaded")

    def _auto_register_scripts(self):
        """扫描每个 Skill 的 scripts/ 目录，自动注册 @tool 函数到 TOOL_REGISTRY"""
        from app.tools import TOOL_REGISTRY
        import importlib.util
        import sys

        for skill in self._skills.values():
            scripts_dir = Path(skill.path) / "scripts"
            if not scripts_dir.exists():
                continue

            for py_file in sorted(scripts_dir.glob("*.py")):
                if py_file.name.startswith("_"):
                    continue

                module_name = f"skill_script_{skill.name}_{py_file.stem}"
                if module_name in sys.modules:
                    continue

                try:
                    spec = importlib.util.spec_from_file_location(module_name, str(py_file))
                    if not spec or not spec.loader:
                        continue
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)

                    for attr_name in dir(module):
                        if attr_name.startswith('_'):
                            continue
                        obj = getattr(module, attr_name)
                        type_name = type(obj).__name__
                        if type_name in ('StructuredTool', 'Tool') or (callable(obj) and hasattr(obj, 'name') and hasattr(obj, 'description')):
                            tool_name = getattr(obj, 'name', attr_name)
                            if tool_name not in TOOL_REGISTRY:
                                TOOL_REGISTRY[tool_name] = obj
                                logger.info(f"Auto-registered tool '{tool_name}' from {py_file}")
                except Exception as e:
                    logger.warning(f"Failed to auto-register {py_file}: {e}")

    def get(self, name: str) -> Optional[SkillInfo]:
        return self._skills.get(name)

    def list_all(self) -> list[dict]:
        return [s.to_dict() for s in self._skills.values()]

    def match_skills(self, tool_names: list[str], state: dict) -> list[SkillInfo]:
        """从给定的工具名列表中，根据 trigger 条件筛选需要加载的 Skill"""
        if not tool_names:
            return []

        all_skills = [self._skills[n] for n in tool_names if n in self._skills]

        if not state:
            return all_skills

        matched = []
        for skill in all_skills:
            if not skill.trigger or "always" in skill.trigger:
                matched.append(skill)
                continue
            if self._check_triggers(skill.trigger, state):
                matched.append(skill)

        return matched if matched else all_skills

    def get_skills_for_names(self, tool_names: list[str]) -> list[SkillInfo]:
        """根据工具名列表返回对应的 SkillInfo（不做 trigger 过滤）"""
        return [self._skills[n] for n in tool_names if n in self._skills]

    def _check_triggers(self, triggers: list[str], state: dict) -> bool:
        for trigger in triggers:
            if trigger == "always":
                return True
            if self._eval_trigger(trigger, state):
                return True
        return False

    def _eval_trigger(self, trigger: str, state: dict) -> bool:
        t = trigger.strip().lower()

        if "uploaded_assets" in t and "image" in t:
            assets = state.get("uploaded_assets", [])
            return any(a.get("type") == "image" for a in assets)

        if "uploaded_assets" in t and "video" in t:
            assets = state.get("uploaded_assets", [])
            return any(a.get("type") == "video" for a in assets)

        if "scenes" in t and "generation_mode=" in t:
            mode = t.split("generation_mode=")[1].strip().rstrip('"\'')
            plan = state.get("plan") or {}
            return any(s.get("generation_mode") == mode for s in plan.get("scenes", []))

        if "scenes" in t and "transition_strategy=" in t:
            strategy = t.split("transition_strategy=")[1].strip().rstrip('"\'')
            plan = state.get("plan") or {}
            return any(
                s.get("transition_from_prev", {}).get("strategy") == strategy
                for s in plan.get("scenes", [])
            )

        if "raw_clips" in t and "数量" in t:
            clips = state.get("raw_clips", [])
            if "> 1" in t:
                return len(clips) > 1
            if ">= 1" in t:
                return len(clips) >= 1

        if "plan.music.generate" in t and "true" in t:
            plan = state.get("plan") or {}
            music = plan.get("music") or {}
            return music.get("generate", False) is True

        return False

    def _parse_skill_md(self, path: Path) -> Optional[SkillInfo]:
        content = path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        meta = self._parse_yaml_simple(parts[1].strip())
        if not meta:
            return None

        trigger_raw = meta.get("trigger", [])
        if isinstance(trigger_raw, str):
            trigger_raw = [trigger_raw]

        return SkillInfo(
            name=meta.get("name", ""),
            title=meta.get("title", ""),
            description=meta.get("description", ""),
            trigger=trigger_raw,
            tool_source=meta.get("tool_source", ""),
            path=str(path.parent),
            readme=parts[2].strip(),
        )

    def _parse_yaml_simple(self, text: str) -> dict:
        result = {}
        current_key = None
        current_list = None

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("- ") and current_key:
                if current_list is None:
                    current_list = []
                    result[current_key] = current_list
                val = stripped[2:].strip().strip('"\'')
                current_list.append(val)
                continue

            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                current_key = key
                current_list = None

                if value.startswith("[") and value.endswith("]"):
                    items = value[1:-1].split(",")
                    result[key] = [i.strip().strip("'\"") for i in items if i.strip()]
                elif value:
                    result[key] = value
                continue

        return result


def get_tool_schema(tool_name: str) -> Optional[dict]:
    """从 TOOL_REGISTRY 提取工具的完整 schema"""
    from app.tools import TOOL_REGISTRY
    func = TOOL_REGISTRY.get(tool_name)
    if func is None:
        return None

    schema = {
        "name": getattr(func, "name", tool_name),
        "description": getattr(func, "description", "") or "",
    }

    args_schema = getattr(func, "args_schema", None)
    if args_schema:
        try:
            model_schema = args_schema.model_json_schema()
            props = model_schema.get("properties", {})
            required = set(model_schema.get("required", []))
            params = []
            for pname, pinfo in props.items():
                param = {"name": pname, "type": pinfo.get("type", "string"), "required": pname in required}
                if "default" in pinfo:
                    param["default"] = pinfo["default"]
                params.append(param)
            schema["parameters"] = params
        except Exception:
            pass

    return schema


_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.scan()
    return _registry
