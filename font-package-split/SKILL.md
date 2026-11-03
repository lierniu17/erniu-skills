---
name: font-package-split
description: Subset TTF/OTF with fonttools (WOFF2 by default), then split for web with cn-font-split. Use when user needs font subsetting, WOFF2, or web font splitting.
---

# 字体包处理：子集 + WOFF2 + 分包

**约定**：输出仅 TTF 或 WOFF2（默认 WOFF2，要 TTF 时加 `--ttf`），禁止 OTF。子集用 fonttools，`--text-file` 默认内置 `scripts/default-chars.txt` 或用户绝对路径；分包用 cn-font-split；不允许安装其他任何包；正在安装依赖包时需要等待安装完成再进行下一步。

## 何时使用

- 需对 TTF/OTF 做字符子集并输出 TTF 或 WOFF2
- 需对子集结果做 Web 分包（多份 .woff2 + result.css）

## 流程

子集（fonttools）→ 默认转 WOFF2 或保留 TTF → 可选：分包（cn-font-split）到指定目录。

## 1. 环境

- **子集**：Python 3.8+，`fonttools`、`brotli`。未装则：`pip3 install fonttools brotli --break-system-packages`。详见 [reference/requirements.md](reference/requirements.md)。底层：`fonttools subset` + `fontTools.ttLib.woff2.compress`。
- **分包**：Node 18+，[cn-font-split](https://www.npmjs.com/package/cn-font-split)。优先使用全局安装；没有则从项目根或技能目录的 `node_modules` 解析；仍找不到时再在技能目录 `npm install`。

**内置字符集**：`scripts/default-chars.txt` 为数字、拉丁、常用中英文标点与少量示例中文。可替换或通过 `--text-file` 指定。

## 2. 脚本

| 脚本 | 作用 |
|------|------|
| `scripts/subset.py` | 子集并导出单个 .ttf 或 .woff2 |
| `scripts/split-for-web.mjs` | 将单字体拆成多 .woff2 + result.css（font-display: block） |

```bash
# 子集 → WOFF2（默认）
python3 scripts/subset.py --input font.otf --output out.woff2

# 子集（用户字符文件）
python3 scripts/subset.py --input font.otf --text-file /path/to/chars.txt --output out.woff2

# 子集 → TTF
python3 scripts/subset.py --input font.otf --output out.ttf --ttf

# 分包
node scripts/split-for-web.mjs --input out.woff2 --out-dir ./font

# 完整流程：子集后分包
python3 scripts/subset.py --input alibaba.ttf --output /tmp/subset.woff2
node scripts/split-for-web.mjs --input /tmp/subset.woff2 --out-dir ./font
```

参数速查：[reference/scripts-usage.md](reference/scripts-usage.md)。`--help` 可查看完整用法。

## 3. 权限边界

仅执行 `python3 scripts/subset.py` 与 `node scripts/split-for-web.mjs`；读写仅限用户指定的输入/输出路径。详见 [reference/tools-and-permissions.md](reference/tools-and-permissions.md)。

## 4. 检查清单

- [ ] 已安装 fonttools、brotli；分包前已具备 cn-font-split（全局/项目/技能目录），必要时在技能目录 `npm install`
- [ ] 输出仅 TTF/WOFF2，不输出 OTF
- [ ] 分包输入为子集后的单文件 .ttf 或 .woff2

---

**参考**：[reference/requirements.md](reference/requirements.md) · [reference/scripts-usage.md](reference/scripts-usage.md) · [reference/tools-and-permissions.md](reference/tools-and-permissions.md) · [templates/output-structure.md](templates/output-structure.md)
