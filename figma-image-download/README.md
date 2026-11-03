# Figma 图片下载 Skill — 使用指南

通过 Figma REST API 将设计稿中的节点导出为 PNG / SVG / JPG，自动压缩并写入本仓库 `src/assets/`。可在 **Cursor 对话** 中 `@figma-image-download` 调用，也可在终端直接运行脚本。

---

## 目录

- [能做什么](#能做什么)
- [环境依赖](#环境依赖)
- [安装步骤](#安装步骤)
- [配置 Token](#配置-token)
- [在 Cursor 中使用](#在-cursor-中使用)
- [命令行使用](#命令行使用)
- [完整演示：从 Figma 到页面引用](#完整演示从-figma-到页面引用)
- [工作流程](#工作流程)
- [环境变量一览](#环境变量一览)
- [CLI 参数一览](#cli-参数一览)
- [常见问题](#常见问题)

---

## 能做什么

| 能力                  | 说明                                                                           |
| --------------------- | ------------------------------------------------------------------------------ |
| 按 URL + node-id 下载 | 粘贴 Figma 链接，指定图层节点，一键导出                                        |
| 批量下载              | 多个 node-id 逗号分隔，或 `--all` 扫描全文件 Frame/Component                   |
| 写入仓库 assets       | 默认 `src/assets/img`，可用 `-a entry` 等指定子目录                            |
| PNG 自动压缩          | 下载后用 pngquant 并行压缩，显著减小体积                                       |
| 语义化重命名（可选）  | 开启 `FIGMA_AI_RENAME` 后，用 AI 将 `12313_2066.png` 重命名为 `biker-pony.png` |
| 安全 staging          | 先在临时目录处理，再复制到目标目录，**不会误改已有素材**                       |

---

## 环境依赖

| 依赖                            | 是否必须 | 用途                                    |
| ------------------------------- | -------- | --------------------------------------- |
| **Python 3**                    | 必须     | 运行 `scripts/figma_download.py`        |
| **requests**                    | 必须     | 调用 Figma API、下载图片                |
| **pngquant**                    | 推荐     | PNG 压缩（可用 `--no-compress` 跳过）   |
| **Node.js + pnpm**              | 可选     | 仅在使用语义化重命名时需要 `ai-renamer` |
| **Figma Personal Access Token** | 必须     | 访问 Figma API                          |

---

## 安装步骤

在仓库根目录执行（路径以本 skill 目录为准）：

```bash
cd .cursor/skills/figma-image-download
```

### 1. Python 依赖

```bash
pip3 install requests
# 或
python3 -m pip install requests
```

### 2. PNG 压缩工具（推荐）

```bash
brew install pngquant
```

验证：

```bash
pngquant --version
python3 -c "import requests; print(requests.__version__)"
```

### 3. 语义化重命名（可选）

仅在 `.env` 中设置 `FIGMA_AI_RENAME=true` 时需要：

```bash
pnpm install
# 会在 node_modules/.bin/ 安装 ai-renamer
```

---

## 配置 Token

```bash
cp .env.example .env
```

编辑 `.env`，填入 Figma Token：

```bash
FIGMA_TOKEN=figd_xxxxxxxxxxxxxxxx
```

**获取 Token：**

1. 打开 [figma.com](https://www.figma.com)
2. 点击头像 → **Settings**
3. 滚动到 **Personal Access Tokens**
4. 点击 **Generate new token**，复制保存

> `.env` 已在 `.gitignore` 中，**切勿提交到 Git**。更多变量说明见 [`.env.example`](./.env.example)。

---

## 在 Cursor 中使用

在 Cursor 对话里 attach 本 skill，或直接输入：

```
/figma-image-download
https://www.figma.com/design/n7SAVRN4voKggUIcOExk8b/w2期?node-id=12313-2066
下载图片到 assets/entry 里
```

Agent 会自动：

1. 解析 URL 中的 `fileKey` 与 `node-id`
2. 在 skill 目录读取 `.env` 中的 `FIGMA_TOKEN`
3. 执行下载脚本，输出到 `src/assets/entry/`
4. 返回生成的文件名，便于在代码中 `import`

**node-id 格式说明：** URL 里是 `12313-2066`，API 使用 `12313:2066`，脚本会自动转换，无需手动改。

---

## 命令行使用

脚本路径：

```
.cursor/skills/figma-image-download/scripts/figma_download.py
```

以下命令均在**仓库根目录**执行。

### 模式 1：Figma URL + node-id（推荐）

```bash
python3 .cursor/skills/figma-image-download/scripts/figma_download.py \
  -u "https://www.figma.com/design/n7SAVRN4voKggUIcOExk8b/w2期?node-id=12313-2066" \
  -n "12313:2066" \
  -a "entry"
```

### 模式 2：file-key + 多个 node-id

```bash
python3 .cursor/skills/figma-image-download/scripts/figma_download.py \
  -f n7SAVRN4voKggUIcOExk8b \
  -n "12313:2066,10028:3361" \
  -a "entry"
```

### 模式 3：下载文件中所有 Frame / Component

```bash
python3 .cursor/skills/figma-image-download/scripts/figma_download.py \
  -f n7SAVRN4voKggUIcOExk8b \
  --all \
  -a "img"
```

### 常用选项

```bash
# 导出 SVG、1x（矢量或不需要 2x 时）
python3 .../figma_download.py -u "..." -n "1:234" --format svg --scale 1

# 跳过压缩（调试或 pngquant 未安装时）
python3 .../figma_download.py -u "..." -n "1:234" --no-compress

# 临时覆盖 Token（不写进 .env）
python3 .../figma_download.py -k "figd_xxx" -f abc123 -n "1:234"
```

---

## 完整演示：从 Figma 到页面引用

以下是一次真实可用的端到端流程。

### 步骤 1：在 Figma 中准备导出

1. 打开设计稿，选中要导出的图层（Frame / Component / 带 Export 的 Group）
2. 右侧 **Export** → 点击 **+** 添加导出格式（如 PNG @2x）
3. 复制浏览器地址栏链接，或右键 **Copy link to selection**

示例链接：

```
https://www.figma.com/design/n7SAVRN4voKggUIcOExk8b/w2期?node-id=12313-2066
```

### 步骤 2：下载到 `src/assets/entry`

```bash
python3 .cursor/skills/figma-image-download/scripts/figma_download.py \
  -u "https://www.figma.com/design/n7SAVRN4voKggUIcOExk8b/w2期?node-id=12313-2066" \
  -n "12313:2066" \
  -a "entry"
```

预期终端输出（节选）：

```
Figma 图片下载工具
  File Key: n7SAVRN4voKggUIcOExk8b
  格式: png, 缩放: 2x
  目标目录: .../src/assets/entry
  ...
  ✓ 12313:2066 → 12313_2066.png (81 KB)
  ↳ 压缩 12313_2066.png: 81 KB → 15 KB (-82%)
已复制 1 个文件 → .../src/assets/entry/
  → biker-pony.png
总耗时: 8.0s
```

> 若未开启 `FIGMA_AI_RENAME`，文件名默认为 `12313_2066.png`（node-id 中 `:` 替换为 `_`）。

### 步骤 3：在 React 页面中引用

```tsx
import bikerPony from '@/assets/entry/biker-pony.png';

<img src={bikerPony} alt="" className="w-200px h-200px" />;
```

与项目约定一致：静态资源放在 `src/assets/<模块>/`，通过 `@/` 别名引用。

---

## 工作流程

```
Figma URL / file-key + node-id
        │
        ▼
  GET /v1/images/:file_key     ← Figma API 返回临时下载 URL
        │
        ▼
  .tmp/run-<timestamp>/        ← 并行下载到临时目录
        │
        ├── pngquant 压缩 PNG（可关闭）
        ├── ai-renamer 语义重命名（可选）
        │
        ▼
  src/assets/<subdir>/           ← 复制成品，删除临时目录
```

**设计意图：** 压缩和重命名只在临时目录进行，避免误伤目标目录里已有的同名或历史素材。

---

## 环境变量一览

完整注释见 [`.env.example`](./.env.example)。

| 变量                       | 默认值           | 说明                                     |
| -------------------------- | ---------------- | ---------------------------------------- |
| `FIGMA_TOKEN`              | （必填）         | Figma Personal Access Token              |
| `FIGMA_ASSETS_DIR`         | `img`            | 未传 `-a` 时，输出到 `src/assets/<此值>` |
| `FIGMA_OUTPUT_DIR`         | `src/assets/img` | 完整输出路径（`-a` 未传时的兜底）        |
| `FIGMA_COMPRESS_PNG`       | `true`           | 是否 pngquant 压缩                       |
| `FIGMA_PNG_QUALITY`        | `65-80`          | 压缩质量区间                             |
| `FIGMA_PNGQUANT_SPEED`     | `4`              | 压缩速度 1–11                            |
| `FIGMA_DOWNLOAD_WORKERS`   | `8`              | 并行下载线程数                           |
| `FIGMA_COMPRESS_WORKERS`   | `4`              | 并行压缩线程数                           |
| `FIGMA_AI_RENAME`          | `false`          | 是否语义化重命名                         |
| `FIGMA_AI_RENAME_BIN`      | `ai-renamer`     | 重命名 CLI                               |
| `FIGMA_AI_RENAME_ARGS`     | （空）           | 传给重命名 CLI 的参数                    |
| `FIGMA_AI_RENAME_API_KEY`  | （空）           | 重命名 API Key                           |
| `FIGMA_AI_RENAME_MANIFEST` | （空）           | 重命名对照 JSON 文件名                   |

---

## CLI 参数一览

| 参数                  | 说明                              |
| --------------------- | --------------------------------- |
| `-k` / `--token`      | Figma Token（覆盖 `.env`）        |
| `-u` / `--url`        | Figma 完整链接                    |
| `-f` / `--file-key`   | 文件 key                          |
| `-n` / `--node-ids`   | 节点 ID，逗号分隔                 |
| `--all`               | 下载全部 Frame/Component          |
| `--format`            | `png` / `svg` / `jpg`，默认 `png` |
| `--scale`             | 缩放倍数，默认 `2`                |
| `-a` / `--assets-dir` | `src/assets` 下子目录，如 `entry` |
| `-o` / `--output`     | 完整输出目录（覆盖 `-a`）         |
| `--no-compress`       | 跳过 PNG 压缩                     |
| `--png-quality`       | 覆盖压缩质量                      |
| `--workers`           | 下载线程数                        |
| `--compress-workers`  | 压缩线程数                        |
| `--pngquant-speed`    | pngquant 速度                     |

---

## 常见问题

### 下载失败 / 某个节点没有 URL

**原因：** 该图层在 Figma 中未配置 **Export**。

**解决：** 选中图层 → 右侧 Export → 添加 PNG（或所需格式）→ 重新运行脚本。

### 报错「未找到 Figma Token」

确认已创建 `.env` 且 `FIGMA_TOKEN` 有值，或使用 `-k` 临时传入。

### pngquant 找不到

```bash
brew install pngquant
```

或单次跳过压缩：`--no-compress`。

### 与 Framelink MCP 的区别

| 方式                     | 适用场景                                      |
| ------------------------ | --------------------------------------------- |
| **本 skill（REST API）** | 批量导出、写入 `src/assets`、压缩、AI 重命名  |
| **Framelink MCP**        | Cursor 内按节点切图、需 `imageRef` 的栅格资源 |

页面还原优先用官方 Figma MCP 的 `get_design_context`；**落盘素材**优先本 skill 或 Framelink，不要用 curl 下载 MCP 临时 URL 作为最终资源。

### 语义化重命名不生效

1. `.env` 中设置 `FIGMA_AI_RENAME=true`
2. 在 skill 目录执行 `pnpm install`
3. 配置 `FIGMA_AI_RENAME_ARGS` 与 `FIGMA_AI_RENAME_API_KEY`

---

## 相关文件

| 文件                                                           | 说明                              |
| -------------------------------------------------------------- | --------------------------------- |
| [`SKILL.md`](./SKILL.md)                                       | Agent 技能定义（Cursor 自动读取） |
| [`.env.example`](./.env.example)                               | 环境变量模板（中文注释）          |
| [`scripts/figma_download.py`](./scripts/figma_download.py)     | 主下载脚本                        |
| [`scripts/ai_rename_images.js`](./scripts/ai_rename_images.js) | 语义重命名桥接                    |
| [`package.json`](./package.json)                               | `ai-renamer` devDependency        |
