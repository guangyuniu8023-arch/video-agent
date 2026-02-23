---
name: evaluate_video_transition
title: 衔接质量评估
description: VLM 评估两段视频的衔接质量
trigger:
  - "raw_clips 数量 > 1"
---

对相邻两段视频调用 VLM 截帧评分 (0-100)。
评分决定后续策略：>80 直接拼接，50-80 裁剪+过渡，<50 标记重新生成。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 VLM 评估两段视频的衔接质量。
