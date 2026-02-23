---
name: color_correct_video
title: 色彩校正
description: 调整亮度、对比度、饱和度
trigger:
  - "raw_clips 数量 > 1"
---

调整视频色彩参数，保持多个片段之间的色彩一致性。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 进行色彩校正。
