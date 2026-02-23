# 开发进度与 Plan 文档

本目录存放 Video Agent 项目的开发总结与 Plan 文档。

## 目录结构

```
progress/
├── README.md           # 本文件
├── PROGRESS.md         # 开发进度总结（后端/前端状态、设计要点）
├── Sprint6_交接说明.md  # Sprint 6 交接说明
└── plans/              # Plan 文档（按主/前端/后端分类整合）
    ├── 01_主Plan_视频生成Agent系统.md   # 系统概述、架构、子 Agent 接入、外部调用
    ├── 02_前端Plan.md                   # 画布、面板、交互、层级导航
    └── 03_后端Plan.md                   # API、Skill、Agent、动态工作流
```

## 使用说明

- `PROGRESS.md`：当前开发状态、待修复问题、设计要点
- `plans/01_主Plan_*`：系统整体、子 Agent 接入机制、外部调用
- `plans/02_前端Plan.md`：画布、节点、面板、层级画布
- `plans/03_后端Plan.md`：数据模型、API、Skill、GenericAgent、动态 LangGraph
