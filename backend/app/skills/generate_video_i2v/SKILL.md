---
name: generate_video_i2v
title: 图生视频
description: 用角色参考图生成视频，保持角色一致性
trigger:
  - "uploaded_assets 包含 image"
  - "scenes 中有 generation_mode=i2v"
  - "scenes 中有 transition_strategy=first_frame_ref"
---

用角色参考图 + prompt 生成视频。适用于需要保持角色外观一致的场景，
或使用前一镜末帧作为参考的 first_frame_ref 衔接策略。

## 执行脚本
实际执行代码在 scripts/tool.py 中，调用 Seedance 2.0 API 进行图片到视频生成。
