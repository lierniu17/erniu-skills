# 权限与工具边界

本技能遵循**权限最小化**：仅通过固定脚本完成子集与分包，不执行任意 shell 或未列出的命令。

## 允许执行的命令

| 命令 | 用途 | 脚本 |
|------|------|------|
| `python3` | 运行子集脚本 | `scripts/subset.py` |
| `node` | 运行分包脚本 | `scripts/split-for-web.mjs` |

## 允许的操作

- **读**：技能目录内 `scripts/`、`templates/`、`reference/`、用户指定的 `--input` 与 `--text-file`。
- **写**：用户指定的 `--output` 与 `--out-dir` 路径（应在工作区内或用户明确允许的目录）。

## 不应执行的操作

- 不执行 `pip install` / `npm install` 以外的任意包管理或系统命令（安装由文档指引用户自行执行）。
- 不读写技能未声明的系统路径或环境变量。
- 不调用未在 SKILL.md / 本页列出的脚本或二进制。

## 若使用方支持 allowed-tools

可将技能可调用的工具限制为：

- `run_terminal_cmd`：仅允许执行 `python3 <技能>/scripts/subset.py ...` 与 `node <技能>/scripts/split-for-web.mjs ...`（参数由技能文档规定）。
- `read_file` / `write`：仅限工作区及上述输入/输出路径。

这样实现**工具隔离**，降低误用或越权风险。
