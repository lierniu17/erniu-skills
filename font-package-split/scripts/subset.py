#!/usr/bin/env python3
"""
Subset a font with fonttools. Output is always TTF or WOFF2 (never OTF).
Default: WOFF2. Use --ttf only when TTF output is explicitly needed.

  python subset.py --input "思源黑体.otf" --output final-font.woff2   # default WOFF2
  python subset.py --input "思源黑体.otf" --output subset.ttf --ttf  # explicit TTF

Uses built-in default-chars.txt or --text-file (absolute path).
Requires: fonttools and brotli. If missing: pip3 install fonttools brotli --break-system-packages
"""

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEXT_FILE = SCRIPT_DIR / "default-chars.txt"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="子集字体并导出为 TTF 或 WOFF2（仅此一事）。默认 WOFF2，禁止输出 OTF。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --input font.ttf --output font/subset.woff2
  %(prog)s --input font.otf --output font/subset.woff2 --text-file /path/to/chars.txt
  %(prog)s --input font.ttf --output font/subset.ttf --ttf
        """.strip(),
    )
    ap.add_argument(
        "--input",
        type=Path,
        required=True,
        metavar="PATH",
        help="输入字体文件路径（.ttf 或 .otf）",
    )
    ap.add_argument(
        "--output",
        type=Path,
        required=True,
        metavar="PATH",
        help="输出文件路径，扩展名须为 .ttf 或 .woff2（默认行为为 WOFF2）",
    )
    ap.add_argument(
        "--text-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="保留字符的 UTF-8 文本文件路径；不传则使用内置 default-chars.txt",
    )
    ap.add_argument(
        "--ttf",
        action="store_true",
        help="显式输出为 TTF；不传则输出 WOFF2",
    )
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"Error: input not found: {args.input}", file=sys.stderr)
        return 1

    text_file = args.text_file if args.text_file is not None else DEFAULT_TEXT_FILE
    if not text_file.is_file():
        print(f"Error: text file not found: {text_file}", file=sys.stderr)
        return 1

    out_path = Path(args.output)
    suf = out_path.suffix.lower()
    if suf == ".otf":
        print("Error: output format must be .ttf or .woff2, not .otf", file=sys.stderr)
        return 1
    if suf not in (".ttf", ".woff2"):
        out_path = out_path.with_suffix(".woff2")

    want_ttf = args.ttf or (out_path.suffix.lower() == ".ttf")
    want_woff2 = not want_ttf
    if want_ttf and out_path.suffix.lower() != ".ttf":
        out_path = out_path.with_suffix(".ttf")

    # Subset to same format as input first
    if want_woff2:
        intermediate = out_path.with_suffix(".ttf")
    else:
        intermediate = out_path
    subset_out = intermediate.with_suffix(args.input.suffix.lower())

    cmd = [
        sys.executable,
        "-m",
        "fontTools.subset",
        str(args.input),
        "--text-file=" + str(text_file),
        "--output-file=" + str(subset_out),
    ]
    if subprocess.run(cmd).returncode != 0:
        return 1
    print(f"Subset written: {subset_out}")

    # Convert to TTF if input was OTF (final output must be TTF or WOFF2 only)
    if subset_out.suffix.lower() == ".otf":
        from fontTools.ttLib import TTFont
        font = TTFont(subset_out)
        font.save(intermediate)
        font.close()
        subset_out.unlink(missing_ok=True)
        print(f"Converted to TTF: {intermediate}")
    else:
        if subset_out != intermediate:
            subset_out.rename(intermediate)
        print(f"Subset TTF: {intermediate}")

    if want_woff2:
        try:
            from fontTools.ttLib.woff2 import compress
        except ImportError:
            print("Error: brotli required for WOFF2. Install: pip3 install fonttools brotli --break-system-packages", file=sys.stderr)
            return 1
        compress(str(intermediate), str(out_path))
        intermediate.unlink(missing_ok=True)
        print(f"WOFF2 written: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
