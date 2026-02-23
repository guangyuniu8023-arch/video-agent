---
name: Skill 自包含 + 搜索增强
overview: "Skill 文件夹完全自包含: 执行代码从外部迁入 scripts/, SKILL.md 写明调用规则。搜索列表增加删除/定位/加载操作。移除 tool_source 间接引用。"
todos:
  - id: done-prev
    content: "已完成: tool_source 字段 + SkillRegistry scripts/ 自动注册 + API 源码展示"
    status: completed
  - id: migrate-scripts
    content: "迁移: 14 个内置 Skill 的执行代码迁入各自 scripts/ 目录, 移除 tool_source, SKILL.md 写明调用规则"
    status: completed
  - id: cleanup-old-tools
    content: "清理: 从 tools/*.py 和 agents/producer.py 中移除已迁移的工具函数, 让 TOOL_REGISTRY 完全由 scripts/ 自动注册驱动"
    status: completed
  - id: search-enhance
    content: "搜索增强: 搜索结果支持点击定位画布节点 + 删除节点 + 未在画布的可添加"
    status: completed
isProject: false
---

# Skill 自包含 + 搜索增强

## 1. Skill 文件夹自包含迁移

### 问题

14 个内置 Skill 的执行代码散落在 `tools/seedance.py`、`tools/ffmpeg_tools.py`、`agents/producer.py` 等外部文件中，Skill 文件夹不自包含。用户在 UI 的脚本 Tab 看不到实际代码。

### 方案

将每个 Skill 的执行代码迁移到 `skills/{name}/scripts/` 目录内:

```
skills/generate_video_t2v/
├── SKILL.md          # 元数据 + 指令 (写明何时调用 scripts/tool.py)
└── scripts/
    └── tool.py       # 从 agents/producer.py 迁入的 generate_video_t2v 函数
```

**SKILL.md 指令部分**写明调用规则:

```markdown
## 使用方式
当需要纯文本生成视频时，调用 scripts/tool.py 中的 generate_video_t2v 函数。
参数: prompt(必填), duration(默认15), ratio(默认16:9)
```

迁移映射:


| Skill                     | 源文件                                                         | 迁移到                                              |
| ------------------------- | ----------------------------------------------------------- | ------------------------------------------------ |
| web_search                | tools/web_search.py → web_search()                          | skills/web_search/scripts/tool.py                |
| generate_video_t2v        | agents/producer.py → generate_video_t2v()                   | skills/generate_video_t2v/scripts/tool.py        |
| generate_video_i2v        | agents/producer.py → generate_video_i2v()                   | skills/generate_video_i2v/scripts/tool.py        |
| generate_video_r2v        | agents/producer.py → generate_video_r2v()                   | skills/generate_video_r2v/scripts/tool.py        |
| generate_video_extend     | agents/producer.py → generate_video_extend()                | skills/generate_video_extend/scripts/tool.py     |
| evaluate_video_quality    | tools/analysis.py → evaluate_video()                        | skills/evaluate_video_quality/scripts/tool.py    |
| evaluate_video_transition | tools/analysis.py → evaluate_transition()                   | skills/evaluate_video_transition/scripts/tool.py |
| trim_video                | tools/ffmpeg_tools.py → ffmpeg_trim()                       | skills/trim_video/scripts/tool.py                |
| concat_videos             | tools/ffmpeg_tools.py → ffmpeg_concat()                     | skills/concat_videos/scripts/tool.py             |
| transition_videos         | tools/ffmpeg_tools.py → ffmpeg_transition()                 | skills/transition_videos/scripts/tool.py         |
| normalize_video           | tools/ffmpeg_tools.py → ffmpeg_normalize()                  | skills/normalize_video/scripts/tool.py           |
| color_correct_video       | tools/ffmpeg_tools.py → ffmpeg_color_correct()              | skills/color_correct_video/scripts/tool.py       |
| stabilize_video           | tools/ffmpeg_tools.py → ffmpeg_stabilize()                  | skills/stabilize_video/scripts/tool.py           |
| mix_audio                 | tools/ffmpeg_tools.py → ffmpeg_audio_mix() + tools/music.py | skills/mix_audio/scripts/tool.py                 |


迁移后:

- 移除 SKILL.md 中的 `tool_source` 字段 (不再需要间接引用)
- 从原文件中删除已迁移的函数
- `tools/__init__.py` 的 `_auto_register()` 减少模块列表
- `SkillRegistry._auto_register_scripts()` 自动注册所有 scripts/

## 2. 搜索增强

NodePicker 的搜索 Tab 增加操作:

- 点击已在画布的节点 → 画布定位到该节点 (fitView)
- 已在画布的节点显示 [删除] 按钮
- 未在画布的 Skill → 显示 [添加到画布] 按钮

