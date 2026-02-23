---
name: transition_videos
title: 过渡效果
description: 在两段视频之间添加过渡效果
trigger:
  - "raw_clips 数量 > 1"
---

在相邻两段视频之间添加过渡效果 (fade/dissolve/wipeleft/slideright)。
适用于衔接评分 50-80 的片段。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 添加视频过渡效果。
