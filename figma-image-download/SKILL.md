---
name: figma-image-download
description: Download images from Figma files via the Figma REST API. Triggers when the user asks to download, export, or save Figma images, frames, or components to local files. Keywords include download Figma images, export Figma nodes, save Figma frames as png, batch download Figma images, or any request to export specific Figma node-ids to local image files.
---

# Figma Image Download

This skill provides a script to download images from Figma files using the Figma API.

> 人类可读完整指南（依赖安装、配置、Cursor 与命令行演示）：见 [README.md](./README.md)

## When to Use

Use this skill when the user:

- Asks to download or export images from a Figma file
- Provides a Figma URL and asks to save images locally
- Wants to batch-download multiple Figma nodes by node-id
- Mentions Figma image export, Figma picture download, or similar

## Setup

Store your Figma Personal Access Token in a local `.env` file (not committed to git):

```bash
cp .env.example .env
# Edit .env and set FIGMA_TOKEN=your_actual_token
# Optional: set FIGMA_OUTPUT_DIR=~/Downloads/figma_export
```

The script loads settings from `.env` automatically:

| Variable                   | Description                                        | Default          |
| -------------------------- | -------------------------------------------------- | ---------------- |
| `FIGMA_TOKEN`              | Figma Personal Access Token                        | (required)       |
| `FIGMA_ASSETS_DIR`         | Subfolder under `src/assets` (e.g. `extension/bg`) | `img`            |
| `FIGMA_OUTPUT_DIR`         | Full output path override (used when `-a` not set) | `src/assets/img` |
| `FIGMA_COMPRESS_PNG`       | Compress PNGs after download (`true`/`false`)      | `true`           |
| `FIGMA_PNG_QUALITY`        | pngquant quality range (e.g. `65-80`)              | `65-80`          |
| `FIGMA_PNGQUANT_SPEED`     | pngquant speed `1`–`11` (higher = faster)          | `4`              |
| `FIGMA_DOWNLOAD_WORKERS`   | Parallel download threads                          | `8`              |
| `FIGMA_COMPRESS_WORKERS`   | Parallel pngquant threads                          | `4`              |
| `FIGMA_AI_RENAME`          | Run semantic rename after download                 | `false`          |
| `FIGMA_AI_RENAME_BIN`      | Renamer CLI name/path                              | `ai-renamer`     |
| `FIGMA_AI_RENAME_ARGS`     | Pass-through args string for renamer               | (empty)          |
| `FIGMA_AI_RENAME_API_KEY`  | API key for renamer (mapped to `--api-key`)        | (empty)          |
| `FIGMA_AI_RENAME_MANIFEST` | Write manifest json under output dir               | (empty)          |

Requires **pngquant** for compression: `brew install pngquant`

Downloads and PNG compression run in parallel (previously sequential, which caused most of the slowness).

CLI flags `-k` and `-o` override the corresponding `.env` values when provided. Use `--no-compress` to skip compression for a single run.

## Quick Start

The main script is `scripts/figma_download.py`. It supports three modes:

### Mode 1: Download by URL plus node-ids (recommended)

```bash
python3 scripts/figma_download.py \
  -u "https://www.figma.com/file/abc123/..." \
  -n "1:234,5:678"
```

### Mode 2: Download by file-key plus node-ids

```bash
python3 scripts/figma_download.py \
  -f abc123 \
  -n "1:234,5:678,9:1011"
```

### Mode 3: Download all Frames and Components in a file

```bash
python3 scripts/figma_download.py \
  -f abc123 \
  --all
```

Override token inline when needed:

```bash
python3 scripts/figma_download.py -k "FIGMA_TOKEN" -f abc123 -n "1:234"
```

## Getting a Figma Token

1. Open Figma in browser
2. Click avatar -> Settings
3. Scroll to Personal Access Tokens
4. Click Generate new token
5. Copy and save the token securely

## How It Works

1. `parse_figma_url()` extracts `file_key` from any Figma URL
2. `get_images()` calls `GET /v1/images/:file_key` with comma-separated node-ids
3. Figma API returns a map of `{ node_id: download_url }`
4. `download_images()` saves files to an isolated temp folder under `.cursor/skills/figma-image-download/.tmp/run-<timestamp>/` (never writes directly to the target assets folder first)
5. `process_temp_and_publish()` runs in the temp folder only:
   - **Compress** all PNGs in the temp folder (`pngquant`)
   - **Rename** all images in the temp folder when `FIGMA_AI_RENAME=true` (via `ai_rename_images.js` + `ai-renamer`)
   - **Copy** processed files into the target directory (`src/assets/<subdir>` or `-o`)
   - **Delete** the temp folder
6. For `--all` mode, `collect_node_ids()` walks the file tree to find all FRAME or COMPONENT nodes, then batches them (50 per request)

This staging workflow prevents compress/rename steps from touching **existing** files already present in the target assets directory.

## Important Notes

- **Nodes must have export settings**: In Figma, select a layer -> right sidebar -> Export section -> click `+` to add an export format. Without this, the API returns no download URL for that node.
- **Node ID format**: In Figma URLs, `node-id=1-234` uses `-`; in the API, use `:` -> `1:234`. The script handles this conversion automatically.
- **Batch limit**: The script processes `--all` mode in batches of 50 to avoid URL length limits.
- **Performance**: Use `FIGMA_DOWNLOAD_WORKERS` / `FIGMA_COMPRESS_WORKERS` to tune parallelism; raise `FIGMA_PNGQUANT_SPEED` (up to `11`) for faster compression.
- **Semantic rename args parsing**: `FIGMA_AI_RENAME_ARGS` is parsed with `shlex.split()` in Python, so quoted strings are supported.
- **Do not commit secrets**: `.env` contains tokens/keys and must NOT be committed.

## Output

Files are saved under `src/assets/img` by default (override with `-a extension/bg` or `-o`):

```
src/assets/img/
  1_234.png
  5_678.png
```

By default (without semantic rename), filenames are the node-id with `:` replaced by `_`.

If `FIGMA_AI_RENAME=true` is enabled, the semantic renamer runs on the **temp folder only** (before copy), so final filenames are **not forced** to follow the node-id pattern and existing assets in the target folder are never renamed in place.

## Parameters Reference

| Flag                  | Description                                                              | Default                       |
| --------------------- | ------------------------------------------------------------------------ | ----------------------------- |
| `-k` / `--token`      | Figma Personal Access Token (optional if `.env` or `FIGMA_TOKEN` is set) | from `.env`                   |
| `-f` / `--file-key`   | Figma file key (from URL)                                                | -                             |
| `-u` / `--url`        | Full Figma URL (auto-extracts file-key)                                  | -                             |
| `-n` / `--node-ids`   | Comma-separated node-ids (`1:234,5:678`)                                 | -                             |
| `--all`               | Auto-discover and download all FRAME or COMPONENT nodes                  | -                             |
| `--format`            | Export format: `png`, `svg`, `jpg`                                       | `png`                         |
| `--scale`             | Pixel density multiplier (1, 2, 3, 4)                                    | `2`                           |
| `-a` / `--assets-dir` | Subfolder under `src/assets`                                             | `img`                         |
| `-o` / `--output`     | Full output directory (overrides `-a`)                                   | `src/assets/img`              |
| `--no-compress`       | Skip PNG compression                                                     | compression on                |
| `--png-quality`       | pngquant quality range                                                   | from `FIGMA_PNG_QUALITY`      |
| `--workers`           | Parallel download threads                                                | from `FIGMA_DOWNLOAD_WORKERS` |
| `--compress-workers`  | Parallel compress threads                                                | from `FIGMA_COMPRESS_WORKERS` |
| `--pngquant-speed`    | pngquant speed 1–11                                                      | from `FIGMA_PNGQUANT_SPEED`   |
