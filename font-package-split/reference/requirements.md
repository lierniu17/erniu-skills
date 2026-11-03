# Python 依赖（子集 + WOFF2）

本技能子集脚本 `scripts/subset.py` 依赖以下 Python 包：

| 包名 | 最低版本 | 用途 |
|------|----------|------|
| fonttools | ≥ 4.0.0 | 子集提取、TTF 读写、WOFF2 压缩 |
| brotli | ≥ 1.0.0 | WOFF2 压缩所需 |

## 安装方式

不建虚拟环境时（如 Homebrew 等 externally-managed 环境需加 `--break-system-packages`）：

```bash
pip3 install fonttools brotli --break-system-packages
```

或指定版本：

```bash
pip3 install "fonttools>=4.0.0" "brotli>=1.0.0" --break-system-packages
```

使用虚拟环境时无需 `--break-system-packages`：

```bash
python3 -m venv .venv-font
source .venv-font/bin/activate  # Windows: .venv-font\Scripts\activate
pip install fonttools brotli
```

安装后可用 `python3 scripts/subset.py --help` 验证。
