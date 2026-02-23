---
name: stabilize_video
title: 视频稳定化
description: 视频稳定化去抖
trigger:
  - "raw_clips 数量 >= 1"
---

对视频进行稳定化处理，消除画面抖动。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 进行视频稳定化去抖处理。
