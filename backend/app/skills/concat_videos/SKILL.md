---
name: concat_videos
title: 视频拼接
description: 按顺序拼接多段视频
trigger:
  - "raw_clips 数量 > 1"
---

将多段视频按顺序无缝拼接为一个完整视频。
适用于衔接评分 >80 的相邻片段。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 进行视频拼接。
