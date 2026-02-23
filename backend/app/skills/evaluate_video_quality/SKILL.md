---
name: evaluate_video_quality
title: 视频质量评估
description: VLM 评估单段视频质量
trigger:
  - always
---

对单段视频调用 VLM 评分 (0-100)，
可评估整体质量、视觉质量、运动流畅度、构图等维度。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 VLM 截帧评分进行视频质量评估。
