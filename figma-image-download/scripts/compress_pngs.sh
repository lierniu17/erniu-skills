#!/usr/bin/env bash
# Recursively compress PNGs with pngquant (overwrites in place on success).
# Usage: compress_pngs.sh <directory> [quality_range]
set -euo pipefail

DIR="${1:?usage: compress_pngs.sh <directory> [quality_range e.g. 65-80]}"
QUAL="${2:-65-80}"

if ! command -v pngquant >/dev/null 2>&1; then
  echo "pngquant not found. Install: brew install pngquant" >&2
  exit 1
fi

if [[ ! -d "$DIR" ]]; then
  echo "Not a directory: $DIR" >&2
  exit 1
fi

find "$DIR" -type f -name '*.png' -print0 | while IFS= read -r -d '' f; do
  if pngquant --quality="$QUAL" --force --output "$f" "$f" 2>/dev/null; then
    echo "ok: $f"
  else
    code=$?
    if [[ "$code" -eq 99 ]]; then
      echo "skip (already optimal): $f"
    else
      echo "warn: $f (exit $code)" >&2
    fi
  fi
done
