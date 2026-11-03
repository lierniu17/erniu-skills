# 分包输出结构（标准化）

执行 `split-for-web.mjs` 后，`--out-dir` 目录内将包含以下文件，便于前端统一引用。

## 文件说明

| 文件/模式 | 说明 |
|-----------|------|
| `*.woff2` | 多个字体分片，按 Unicode 区块拆分，浏览器按需加载 |
| `result.css` | 含 `@font-face` 与 `unicode-range`，所有 `@font-face` 的 `font-display` 均为 `block`，页面直接 `<link>` 引用即可 |
| `index.html` | 本地预览页，用于检查字体显示 |
| `index.proto` / `reporter.bin` | cn-font-split 元数据，一般无需直接使用 |

## 前端引用方式

```html
<link rel="stylesheet" href="font/result.css" />
```

或复制 `result.css` 中的 `@font-face` 到项目样式。字体族名称以 cn-font-split 输出为准（可在脚本或 cn-font-split 的 `css` 选项中配置）。本技能分包脚本固定使用 `font-display: block`。

## 与子集输出的关系

- 子集脚本 `subset.py` 仅输出**单个** `.ttf` 或 `.woff2` 文件。
- 分包脚本 `split-for-web.mjs` 读取该单文件，在 `--out-dir` 下生成上述多文件结构。
