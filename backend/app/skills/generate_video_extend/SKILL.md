---
name: generate_video_extend
title: 视频续拍
description: 从上一镜末尾续拍，保持最佳连续性
trigger:
  - "scenes 中有 generation_mode=extend"
  - "scenes 中有 transition_strategy=extend"
  - "raw_clips 数量 >= 1"
---

从上一镜的末尾直接续拍，利用 Seedance 模型内置的连续性能力。
适用于连续动作场景，需要前一镜已生成。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 Seedance 2.0 API 进行视频续拍生成。
