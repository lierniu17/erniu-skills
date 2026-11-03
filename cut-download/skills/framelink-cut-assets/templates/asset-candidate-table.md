# 切图字段对照表（可选）

整理 **Framelink `get_figma_data`** 结果时使用；**不落盘**，便于核对 `download_figma_images` 的 `nodes` 参数。

| # | 建议 fileName | 类型 | nodeId | 说明 |
|---|----------------|------|--------|------|
| 1 | | png / svg / gif | `12:34` | |
| 2 | | | | |

- `nodeId` 使用 API 形式（冒号）；若来自 URL，将 `12-34` 转为 `12:34`。
- 仅对需要的行组装 `download_figma_images` 的 `nodes`。
