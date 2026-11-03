#!/usr/bin/env python3
"""生成间隔重复复习排期表（遗忘曲线落地工具）。

用法：
    python3 review_schedule.py --start 2026-11-03 --topic "Rust 所有权"
    python3 review_schedule.py --topic "SQL 索引" --intervals 1,3,7,14,30 --out 07-review.md

输出 Markdown 表格，含节点、日期、星期、三列闭卷问题占位与结果列。
只依赖标准库。
"""

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DEFAULT_INTERVALS = "1,2,4,7,15,30"


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"日期格式错误：{value}，应为 YYYY-MM-DD（例如 2026-11-03）")


def parse_intervals(value: str) -> list[int]:
    try:
        items = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError:
        sys.exit(f"间隔格式错误：{value}，应为逗号分隔的整数（例如 1,2,4,7,15,30）")
    if not items:
        sys.exit("间隔列表为空")
    if any(i <= 0 for i in items):
        sys.exit("间隔必须是正整数（单位：天）")
    if items != sorted(items):
        sys.exit(f"间隔必须递增：{items}")
    if len(set(items)) != len(items):
        sys.exit(f"间隔有重复：{items}")
    return items


def build_rows(start: date, intervals: list[int]) -> list[dict]:
    rows = []
    for offset in intervals:
        d = start + timedelta(days=offset)
        rows.append(
            {
                "offset": offset,
                "label": f"D+{offset}",
                "date": d.isoformat(),
                "weekday": WEEKDAYS[d.weekday()],
            }
        )
    return rows


def render_markdown(topic: str, start: date, rows: list[dict]) -> str:
    lines = [
        f"# 复习排期：{topic}",
        "",
        f"- 起始日：{start.isoformat()}（{WEEKDAYS[start.weekday()]}）",
        f"- 节点：{' / '.join(r['label'] for r in rows)}",
        f"- 规则：闭卷先答，再对照；错题（❌）占下一轮一半题量；复习 ≠ 重读笔记。",
        "",
        "| 节点 | 日期 | 星期 | 闭卷问题 1 | 闭卷问题 2 | 闭卷问题 3 | 结果 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['date']} | {r['weekday']} |  |  |  |  |"
        )
    lines += [
        "",
        "## 出题要求",
        "",
        "1. 能闭卷口头回答，答案唯一，不用查资料。",
        "2. 三轮以上逐步升层：是什么 → 为什么 → 换场景怎么用。",
        "3. 错题簿里的 ❌ 项优先，占该轮一半题量。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="生成间隔重复复习排期")
    p.add_argument("--topic", default="未命名主题", help="学习主题名称")
    p.add_argument("--start", default=date.today().isoformat(), help="起始日期 YYYY-MM-DD，默认今天")
    p.add_argument("--intervals", default=DEFAULT_INTERVALS, help=f"天数间隔，默认 {DEFAULT_INTERVALS}")
    p.add_argument("--out", help="写入文件路径（.md 输出 Markdown，.json 输出 JSON）")
    args = p.parse_args()

    start = parse_date(args.start)
    intervals = parse_intervals(args.intervals)
    rows = build_rows(start, intervals)

    if args.out and args.out.lower().endswith(".json"):
        payload = {
            "topic": args.topic,
            "start": start.isoformat(),
            "intervals": intervals,
            "schedule": rows,
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        text = render_markdown(args.topic, start, rows)

    if args.out:
        out = Path(args.out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {out}（{len(rows)} 个复习节点）")
    else:
        print(text)


if __name__ == "__main__":
    main()
