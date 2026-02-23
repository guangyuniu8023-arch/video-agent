---
name: generate_video_t2v
title: 文生视频
description: 纯文本 prompt 生成视频，最基础的视频生成模式
trigger:
  - always
---

最基础的视频生成模式，仅需文本 prompt。适用于无参考素材的纯创意生成、
硬切衔接策略的分镜、以及首个分镜（无前一镜可参考时）。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 Seedance 2.0 API 进行文本到视频生成。
