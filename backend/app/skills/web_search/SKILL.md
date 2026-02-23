---
name: web_search
title: 网络搜索
description: 搜索互联网获取风格参考、场景描述等创作灵感
trigger:
  - always
---

搜索互联网获取与视频创作相关的参考信息。
Planner 自行判断是否需要搜索，System Prompt 中约定使用时机。

## 执行脚本
实际执行代码在 scripts/tool.py 中，使用 DuckDuckGo 免费搜索 API 进行网络搜索。
