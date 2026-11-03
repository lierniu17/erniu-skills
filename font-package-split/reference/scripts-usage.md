# 脚本参数速查（有意义的参数提示）

## subset.py — 子集并导出 TTF/WOFF2

**职责**：仅做一件事——按字符子集提取字体，并导出为单个 .ttf 或 .woff2 文件（默认 WOFF2，禁止 OTF）。

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `--input` | 是 | 输入字体路径（.ttf 或 .otf） | `--input ./font.ttf` |
| `--output` | 是 | 输出文件路径，扩展名须为 .ttf 或 .woff2 | `--output ./out/subset.woff2` |
| `--text-file` | 否 | 保留字符的 UTF-8 文本文件；不传则用内置 default-chars.txt | `--text-file /abs/path/chars.txt` |
| `--ttf` | 否 | 显式输出 TTF；不传则输出 WOFF2 | `--ttf` |

查看完整帮助：`python3 scripts/subset.py --help`

---

## split-for-web.mjs — Web 分包

**职责**：仅做一件事——将单个字体文件拆分为多个 .woff2 分片及 result.css 等，便于 Web 按需加载。

| 参数 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `--input` | 是 | 输入字体文件路径（.ttf 或 .woff2，通常为子集后的单文件） | `--input ./subset.woff2` |
| `--out-dir` | 是 | 输出目录，将在此生成多个 .woff2 与 result.css、index.html 等 | `--out-dir ./font` |

查看完整帮助：`node scripts/split-for-web.mjs --help`
