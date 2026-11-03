---
name: framelink-cut-assets
description: Framelink Figma MCP slice export into the workspace plus pngquant PNG compression (bundled script). Use for Framelink cut-asset workflows, Figma URLs, per-node download_figma_images, and post-export PNG optimization—not for Figma REST Images API or non-Framelink export.
---

# Framelink 切图：MCP 下载 + PNG 压缩

## 概述

**Framelink MCP** 负责把切图写入工作区；**`scripts/compress_pngs.sh` + pngquant** 仅对目录内 **PNG** 做体积优化。本 Skill 不包含 Figma Images API / 自建下载脚本。拷贝到 `.cursor/skills/` 或 `.claude/skills/` 下即可用。

## 前置条件

- Cursor 已配置 **Framelink Figma MCP**（`get_figma_data`、`download_figma_images`）。
- 工作区对目标目录**可写**。
- 压缩：`pngquant` 在 PATH（如 `brew install pngquant`）。若无 pngquant，可只完成下载，跳过压缩步骤。

## 硬性规则

1. **`localPath`**：相对**工作区根**，正斜杠（例：`public/images/feature`）。
2. **单张下载，禁止批量**：调用 **`download_figma_images`** 时，**`nodes` 数组长度必须为 1**（只含一个 `{ nodeId, fileName, … }`）。多张切图需**拆成多次调用**，逐张下载。**禁止**在一次调用里传入多个 `nodes` 项做批量导出。
3. **SVG / GIF**：**不要**对 `.svg` / `.gif` 跑 pngquant；压缩仅针对 **PNG**。

## 流程

### 1. 解析 Figma URL

- **fileKey**：`figma.com/design/<fileKey>/...` 第一段。
- **nodeId**：`node-id=`；Framelink/API 常用 **冒号**（`7563:4482`），URL 常为 `7563-4482`，需替换。

### 2. 下载

按需调用 **`get_figma_data`** 获取节点树与栅格填充信息（如 **`imageRef` / `gifRef`**、`imageDownloadArguments` 等），为**每一张**待导出的图组装 **仅含一个元素** 的 **`nodes`**（`nodeId`、`fileName`、以及上述字段），然后调用 **`download_figma_images`**（`fileKey`、`nodes`、`localPath`、`pngScale` 按需）。**每成功导出一张 = 一次 MCP 调用**；不要在一次调用中堆多个节点。

### 3. 压缩 PNG

在**工作区根**执行（第二参数为 pngquant 质量区间，可选，默认 `65-80`；偏高保真可试 `70-85`）：

```bash
bash .cursor/skills/framelink-cut-assets/scripts/compress_pngs.sh public/images/feature 65-80
```

路径与上一步 **`localPath`** 一致（相对工作区根）。

**无 pngquant 时**：可单文件试 `pngquant --quality=65-80 --force --output out.png in.png`；批量自行 `find` 调用。

### 4. 收尾

列出已生成文件的**相对路径**；失败项单独说明。

## 目录结构

```
framelink-cut-assets/
  SKILL.md
  reference/overview.md
  templates/asset-candidate-table.md
  scripts/compress_pngs.sh
```

Skill 根路径常见为 `.cursor/skills/framelink-cut-assets/` 或 `.claude/skills/framelink-cut-assets/`；示例以前者为准。

**路由**：[templates/asset-candidate-table.md](templates/asset-candidate-table.md) · [reference/overview.md](reference/overview.md)

## 本 Skill 文件

- [scripts/compress_pngs.sh](scripts/compress_pngs.sh) — 递归 pngquant 目录内 PNG。
- [reference/overview.md](reference/overview.md) — 流程图、能力对照、安全说明。
