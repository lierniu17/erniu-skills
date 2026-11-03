#!/usr/bin/env node
/**
 * split-for-web：将单个字体文件拆分为多个分片，便于 Web 按需加载。
 * 仅做分包一件事，不修改字体内容。默认 .woff2；加 --ttf 则输出 .ttf。
 *
 * 用法:
 *   node split-for-web.mjs --input <字体文件> --out-dir <输出目录>
 *   node split-for-web.mjs --input <字体文件> --out-dir <输出目录> --ttf
 *
 * 参数:
 *   --input   必填。单个字体文件路径，支持 .ttf | .otf | .woff2（woff2 输入不推荐）
 *   --out-dir 必填。输出目录路径，将在此目录生成多个字体分片及 result.css、index.html 等
 *   --ttf     可选。输出 TTF 分片；不传则输出 WOFF2
 *
 * 示例:
 *   node split-for-web.mjs --input ./subset.ttf --out-dir ./font
 *   node split-for-web.mjs --input ./subset.ttf --out-dir ./font --ttf
 *
 * 依赖: cn-font-split（优先全局，否则项目根/技能目录 node_modules，最后找不到再在技能目录 npm install）
 */

import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";
import { fileURLToPath, pathToFileURL } from "url";
import { createRequire } from "module";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, "..");
const CN_FONT_SPLIT_PATH = path.join(SKILL_ROOT, "node_modules", "cn-font-split", "dist", "auto.mjs");
const require = createRequire(import.meta.url);

function printUsage() {
  console.log(`
split-for-web — 将字体拆分为 Web 分包（默认 .woff2 + result.css；--ttf 则 .ttf）

用法:
  node split-for-web.mjs --input <字体文件> --out-dir <输出目录> [--ttf]

参数:
  --input <path>   必填。输入字体文件（.ttf | .otf | .woff2）
  --out-dir <path> 必填。输出目录，将写入多个字体分片与 result.css、index.html 等
  --ttf            可选。输出 TTF 分片；不传则输出 WOFF2

示例:
  node split-for-web.mjs --input ./my-subset.ttf --out-dir ./font
  node split-for-web.mjs --input ./my-subset.ttf --out-dir ./font --ttf
`);
}

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { input: null, outDir: null, ttf: false };
  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--input" || args[i] === "-i") && args[i + 1]) {
      out.input = path.resolve(args[++i]);
    } else if ((args[i] === "--out-dir" || args[i] === "-o") && args[i + 1]) {
      out.outDir = path.resolve(args[++i]);
    } else if (args[i] === "--ttf") {
      out.ttf = true;
    } else if (args[i] === "--help" || args[i] === "-h") {
      printUsage();
      process.exit(0);
    }
  }
  return out;
}

async function loadCnFontSplit() {
  // Prefer skill-local install (complete native libs) over broken global installs.
  if (fs.existsSync(CN_FONT_SPLIT_PATH)) {
    return await import(pathToFileURL(CN_FONT_SPLIT_PATH).href);
  }
  try {
    return await import("cn-font-split");
  } catch (e) {
    try {
      const globalRoot = require("child_process")
        .execSync("npm root -g", { encoding: "utf8" })
        .trim();
      const globalEntry = path.join(globalRoot, "cn-font-split", "dist", "auto.mjs");
      if (fs.existsSync(globalEntry)) {
        return await import(pathToFileURL(globalEntry).href);
      }
    } catch (_) {
      /* fall through */
    }
    throw e;
  }
}

/**
 * cn-font-split 当前 FFI 实际固定产出 .woff2；--ttf 时用 fonttools 转为 .ttf，
 * 并同步改写 result.css / index.html 中的引用。
 */
function convertWoff2ShardsToTtf(outDir) {
  const py = `
import sys
from pathlib import Path
from fontTools.ttLib import TTFont

out = Path(sys.argv[1])
n = 0
for src in sorted(out.glob("*.woff2")):
    dst = src.with_suffix(".ttf")
    font = TTFont(str(src))
    font.flavor = None
    font.save(str(dst))
    font.close()
    src.unlink()
    n += 1

for name in ("result.css", "index.html"):
    p = out / name
    if not p.is_file():
        continue
    text = p.read_text(encoding="utf-8")
    text = text.replace(".woff2", ".ttf").replace('format("woff2")', 'format("truetype")').replace("format('woff2')", "format('truetype')")
    p.write_text(text, encoding="utf-8")

print(f"converted {n} shards to ttf")
`.trim();

  const r = spawnSync("python3", ["-c", py, outDir], { encoding: "utf8" });
  if (r.status !== 0) {
    console.error(r.stderr || r.stdout || "fonttools convert failed");
    process.exit(r.status || 1);
  }
  if (r.stdout) process.stdout.write(r.stdout);
}

async function main() {
  const { input, outDir, ttf } = parseArgs();
  if (!input || !outDir) {
    console.error("Error: 缺少 --input 或 --out-dir");
    printUsage();
    process.exit(1);
  }
  if (!fs.existsSync(input)) {
    console.error("Error: 输入文件不存在:", input);
    process.exit(1);
  }

  const buffer = new Uint8Array(fs.readFileSync(input));
  const mod = await loadCnFontSplit();
  const { fontSplit } = mod;

  await fontSplit({
    input: buffer,
    outDir,
    // Prefer native ttf when supported; older FFI may still emit woff2.
    targetType: ttf ? "ttf" : "woff2",
    css: { fontDisplay: "block" },
  });

  if (ttf) {
    const hasWoff2 = fs.readdirSync(outDir).some((f) => f.endsWith(".woff2"));
    const hasTtf = fs.readdirSync(outDir).some((f) => f.endsWith(".ttf"));
    if (hasWoff2 && !hasTtf) {
      convertWoff2ShardsToTtf(outDir);
    }
  }

  console.log(`Split output (${ttf ? "ttf" : "woff2"}) written to:`, outDir);
}

main().catch((err) => {
  if (err?.code === "ERR_FFI" || err?.message?.includes("dlopen")) {
    console.error(
      "Error: cn-font-split 需要原生库。请在技能目录执行 npm install 并允许 postinstall，或使用已配置好的环境。"
    );
  }
  console.error(err);
  process.exit(1);
});
