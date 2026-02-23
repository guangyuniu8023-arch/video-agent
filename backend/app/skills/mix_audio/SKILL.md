---
name: mix_audio
title: 音频混合
description: 将背景音乐与视频混合
trigger:
  - "plan.music.generate == true"
---

将背景音乐轨道与视频原声混合，可调节两者音量比。
默认保留 Seedance 原生音频，仅在需要叠加 BGM 时使用。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 FFmpeg 进行音频混合。
