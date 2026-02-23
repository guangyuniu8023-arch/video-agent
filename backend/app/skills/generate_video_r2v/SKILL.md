---
name: generate_video_r2v
title: 参考视频生成
description: 用参考视频控制运镜和风格
trigger:
  - "uploaded_assets 包含 video"
  - "scenes 中有 generation_mode=r2v"
  - "scenes 中有 transition_strategy=camera_ref"
---

用参考视频 + prompt 生成视频，复用参考视频的运镜和风格。
适用于用户上传了参考视频或 camera_ref 衔接策略。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 Seedance 2.0 API 进行参考视频到视频生成。
