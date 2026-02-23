---
name: normalize_video
title: 规格统一
description: 统一视频的分辨率和帧率
trigger:
  - "raw_clips 数量 > 1"
---

将视频统一为指定分辨率和帧率，确保所有片段规格一致。
在拼接前使用。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 统一视频规格。
