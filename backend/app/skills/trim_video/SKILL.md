---
name: trim_video
title: 视频裁剪
description: 裁剪视频片段，去除头尾不自然帧
trigger:
  - always
---

指定起止时间裁剪视频。主要用于去除 AI 生成视频头尾的不自然帧。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 进行视频裁剪。
