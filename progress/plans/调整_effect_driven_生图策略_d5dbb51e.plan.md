---
name: 调整 effect_driven 生图策略
overview: 重写 effect_driven_CY 整个分配逻辑表，核心原则与 body_driven 一致：不根据分镜数判断 rule 条数，条数始终 = 图片数/生图需求数。ref_image 取该图被分配到的第一个分镜的参考帧。补充 effect_driven 的 few-shot 示例。
todos:
  - id: rewrite-table
    content: 重写 effect_driven_CY 分配逻辑表（第 119-133 行），参照 body_driven 原则，加入条数规则说明
    status: completed
  - id: add-examples
    content: 在示例 10 之后补充 effect_driven 的 few-shot 示例（示例 11/12/13）
    status: completed
isProject: false
---

# 调整 effect_driven_CY 生图策略

修改文件：[## 角色定义.ini](/Users/bytedance/Downloads/## 角色定义.ini)

## 核心原则（与 body_driven 一致）

- **不根据分镜数决定 `image_generate_rule` 条数**，条数始终由图片数/生图需求决定。
- image_mapping：每张图只出现一次。
- ID2i：每张需要生图的图只出一条 rule。
- AI_create：多图融合只出一条 rule。
- `ref_image` 取该图片被分配到的**第一个分镜**的参考帧。

## 修改点

### 1. 重写 effect_driven_CY 分配逻辑表（第 119-133 行）

将现有逻辑替换为与 body_driven 同理的写法，强调「不根据分镜数判断 rule 条数」。

重写后的内容：

```
### effect_driven_CY

与 body_driven_CY 同理，不根据分镜数判断 rule 条数，看图片数和编辑需求：

| 图片数 | 编辑需求 | 用户指定分配 | 生图策略 |
|--------|----------|-------------|----------|
| 1张 | 无 | - | 不生图（image_mapping），1条 |
| 1张 | 有 | - | 生成1张（ID2i），ref_image=frame_1，1条 |
| 多张 | 无 | 全部不指定 | 不生图（image_mapping），每张图1条 |
| 多张 | 无 | 全部/部分指定 | 不生图（image_mapping），按分配用到的图各1条 |
| 多张 | 有（单图编辑） | - | 需编辑的图用ID2i，其余image_mapping，每张图1条 |
| 多张 | 有（多图融合） | - | AI_create，1条 |

**ref_image 规则**：取该图片被分配到的第一个分镜的参考帧。
例：image1 分配到分镜1和分镜3 → ref_image = frame_1

**特殊情况**：用户明确要求融合 → AI_create
```

### 2. 新增 effect_driven few-shot 示例

在现有示例 10 之后，补充 3 个 effect_driven 示例：

- **示例 11**：分镜=2，图片=1，无编辑需求 → effect_driven + image_mapping 只出 1 条
- **示例 12**：分镜=2，图片=1，有编辑需求 → effect_driven + ID2i 只出 1 条（ref_image=frame_1）
- **示例 13**：分镜=2，图片=3，无编辑需求 → effect_driven + image_mapping 出 3 条（每张图一次）

