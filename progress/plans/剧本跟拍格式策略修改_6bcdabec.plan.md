---
name: 剧本跟拍格式策略修改
overview: 对 `剧本-跟拍.ini` 进行输入格式、输出格式、工具变更、生图策略和示例调整的全面修改，使其与舞蹈/唱歌 PE 的主体类型和工具体系保持一致。
todos:
  - id: input-format
    content: 修改输入格式：添加 IP/ID 字段和主体类型规则
    status: completed
  - id: strategy-rewrite
    content: 重写生图策略部分，去掉 group_photo/ID2i，改为 album_CY/IP_CY 策略
    status: completed
  - id: output-format
    content: 修改输出格式、工具表和工具补充说明
    status: completed
  - id: examples-update
    content: 调整全部 12 个示例（输入加 IP/ID、输出改字典、工具替换）
    status: completed
isProject: false
---

# 剧本-跟拍.ini 全面修改

文件：[/Users/bytedance/Downloads/## 剧本-跟拍.ini](/Users/bytedance/Downloads/## 剧本-跟拍.ini)

## 修改点1：输入格式（第93-104行）

添加 IP、ID 字段，与其他 PE 统一：

**当前**（第94-95行）：

```
"图片": ["user_image1", "user_image2", ...],  // 1-4张
```

**改为**：

```
"图片": ["user_image1", ...],  // 0-4张，图像主体
"IP": ["user_image2", ...],    // 0-3张，IP主体
"ID": ["user_image3", ...],    // 0-3张，ID主体
```

并在输入格式后增加**主体类型规则**说明（参考对口型-跟拍的第77-81行）。

## 修改点2：生图策略（第43-64行）

完全重写，去掉 group_photo 和 ID2i 引用，改为与舞蹈/唱歌 PE 一致的策略：

- 图像：单张+视频单人+图片单人 → album_CY，其他 → image_mapping，融合 → AI_create
- IP：单IP → IP_CY，多IP → image_mapping
- ID：所有 → image_mapping
- 混合主体：所有 → image_mapping

## 修改点3：输出格式（第117-139行）

### 3a. image_generate_rule 结构改为字典

**当前**（第122行）：

```
"image_generate_rule": [...]  // 按分镜顺序
```

**改为**：

```
"image_generate_rule": {
  "图片": [...],
  "IP": [...],
  "ID": [...]
}
```

### 3b. 工具表更新（第128-134行）

- 删除：`ID2i`、`group_photo`、`null`
- 新增：`album_CY`（图像生成，适用图片，参数 image/ref_image/prompt）、`IP_CY`（IP生成，适用IP，参数 image/ref_image/prompt）
- 保留：`AI_create`、`image_mapping`

### 3c. 多图prompt格式说明（第138行）

去掉 group_photo 引用，只保留 AI_create。

## 修改点4：工具补充说明（第142-148行）

- 删除 ID2i 和 group_photo 的说明
- 新增 album_CY 和 IP_CY 的说明（参考对口型-跟拍文件中的工具定义）

## 修改点5：示例调整（12个示例）

所有有 AI_movie_CY 输出的示例：

- 输入格式统一增加 `"IP": [], "ID": []`
- 输出 `image_generate_rule` 从扁平数组改为字典格式

逐个示例变更：


| 示例          | 输出变更                                                                                       |
| ----------- | ------------------------------------------------------------------------------------------ |
| 示例1（拍同款）    | `ID2i` -> `album_CY`，扁平数组 -> `{"图片": [...]}`                                               |
| 示例2（有编辑）    | `ID2i` -> `album_CY`，扁平数组 -> `{"图片": [...]}`                                               |
| 示例3（反差路由）   | 仅输入加 IP/ID 字段                                                                              |
| 示例4（舞蹈动作）   | 仅输入加 IP/ID 字段                                                                              |
| 示例5（唱歌路由）   | 仅输入加 IP/ID 字段                                                                              |
| 示例6（BGM动作）  | 仅输入加 IP/ID 字段                                                                              |
| 示例7（多图融合）   | 扁平数组 -> `{"图片": [...]}`，AI_create 保留                                                       |
| 示例8（创意互动）   | 仅输入加 IP/ID 字段                                                                              |
| 示例9（用户文本剧本） | 仅输入加 IP/ID 字段                                                                              |
| 示例10（兜底）    | `group_photo` -> `image_mapping`（3张图全部 image_mapping），扁平数组 -> `{"图片": [...]}`              |
| 示例11（不生图）   | 扁平数组 -> `{"图片": [...]}`                                                                    |
| 示例12（图片复用）  | 去掉复用逻辑，所有图用 `image_mapping`，分配文本移入 `video_prompt`，`是否修改文本` 改为 true，扁平数组 -> `{"图片": [...]}` |


