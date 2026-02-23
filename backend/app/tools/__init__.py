"""全局工具注册表

TOOL_REGISTRY 只由 SkillRegistry._auto_register_scripts() 填充 (从 skills/*/scripts/ 自动注册)。
底层 API 模块 (tools/seedance.py 等) 仅作为 Python 函数库被 Skill 脚本 import 调用，不注册到 TOOL_REGISTRY。
"""

TOOL_REGISTRY: dict = {}


def register_tool(name: str):
    """装饰器: 保留兼容性但不再注册到 TOOL_REGISTRY (底层函数由 Skill scripts/ 包装后注册)"""
    def decorator(func):
        return func
    return decorator


def _ensure_modules_loaded():
    """预导入底层模块，确保 Skill scripts/ import 时不会报错"""
    import importlib
    for mod in ["app.tools.seedance", "app.tools.ffmpeg_tools", "app.tools.analysis", "app.tools.file_ops"]:
        try:
            importlib.import_module(mod)
        except Exception:
            pass


_ensure_modules_loaded()
