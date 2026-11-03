#!/usr/bin/env node
/**
 * ai_rename_images.js
 *
 * A thin wrapper to invoke an external `ai-rename` CLI for semantic renaming.
 * - Collects image files under a directory (default: non-recursive)
 * - Spawns `ai-rename` via subprocess and forwards stdout/stderr
 * - Optionally writes a rename manifest by diffing before/after directory snapshots
 *
 * This file intentionally does NOT assume a specific `ai-rename` argument schema.
 * It supports:
 * - passing files list:   ai-rename <files...>
 * - passing directory:    ai-rename <dir>
 * - passing through args: everything after `--` is forwarded to ai-rename
 *
 * Usage:
 *   node ai_rename_images.js --dir src/assets/word
 *   node ai_rename_images.js --dir src/assets/word --recursive
 *   node ai_rename_images.js --dir src/assets/word --bin ai-rename -- --dry-run
 *   node ai_rename_images.js --dir src/assets/word --manifest rename-manifest.json -- --provider openai
 *
 * Exit codes:
 *   0: success
 *   2: bad arguments / dir not found
 *   127: ai-rename not found
 *   other: propagated from ai-rename
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

function resolveLocalBin(binName) {
  // Prefer local project bin so PATH isn't required.
  // Works for pnpm/npm/yarn installs that create node_modules/.bin/<name>.
  //
  // We search upward because callers may run from a nested directory
  // (e.g. `.cursor/skills/...`), while dependencies live at repo root.
  const suffixes = [binName, `${binName}.cmd`, `${binName}.ps1`];
  let cur = process.cwd();
  for (let i = 0; i < 20; i++) {
    for (const s of suffixes) {
      const p = path.join(cur, 'node_modules', '.bin', s);
      if (fs.existsSync(p)) return p;
    }
    const parent = path.dirname(cur);
    if (parent === cur) break;
    cur = parent;
  }
  return binName;
}

function parseArgs(argv) {
  const args = {
    dir: '',
    recursive: false,
    // Default to the locally installed `ai-renamer` (via pnpm add -D ai-renamer).
    // You can override with --bin to use any other CLI.
    bin: 'ai-renamer',
    // For a generic renamer, directory mode is safer (no argv length limits).
    mode: 'dir', // 'files' | 'dir'
    exts: ['.png', '.jpg', '.jpeg', '.webp', '.svg'],
    manifest: '',
    fileList: '',
    passthrough: [],
  };

  const doubleDashIdx = argv.indexOf('--');
  const main = doubleDashIdx >= 0 ? argv.slice(0, doubleDashIdx) : argv;
  args.passthrough = doubleDashIdx >= 0 ? argv.slice(doubleDashIdx + 1) : [];

  for (let i = 0; i < main.length; i++) {
    const v = main[i];
    if (v === '--dir' || v === '-d') {
      args.dir = main[++i] ?? '';
    } else if (v === '--recursive' || v === '-r') {
      args.recursive = true;
    } else if (v === '--bin') {
      args.bin = main[++i] ?? args.bin;
    } else if (v === '--mode') {
      const m = main[++i];
      if (m === 'files' || m === 'dir') args.mode = m;
    } else if (v === '--exts') {
      const raw = (main[++i] ?? '').trim();
      if (raw) {
        args.exts = raw
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
          .map((s) => (s.startsWith('.') ? s.toLowerCase() : `.${s.toLowerCase()}`));
      }
    } else if (v === '--manifest' || v === '-m') {
      args.manifest = main[++i] ?? '';
    } else if (v === '--file-list') {
      args.fileList = main[++i] ?? '';
    } else if (v === '--help' || v === '-h') {
      return { ...args, help: true };
    }
  }

  return args;
}

function collectImages(dir, { recursive, exts }) {
  /** @type {string[]} */
  const out = [];

  const walk = (cur) => {
    const entries = fs.readdirSync(cur, { withFileTypes: true });
    for (const e of entries) {
      const full = path.join(cur, e.name);
      if (e.isDirectory()) {
        if (recursive) walk(full);
        continue;
      }
      if (!e.isFile()) continue;
      const ext = path.extname(e.name).toLowerCase();
      if (exts.includes(ext)) out.push(full);
    }
  };

  walk(dir);
  out.sort();
  return out;
}

function snapshotDir(dirAbs, { recursive, exts }) {
  const files = collectImages(dirAbs, { recursive, exts });
  /** @type {Record<string, { size: number; mtimeMs: number }>} */
  const meta = {};
  for (const f of files) {
    const st = fs.statSync(f);
    meta[f] = { size: st.size, mtimeMs: st.mtimeMs };
  }
  return meta;
}

function diffSnapshots(before, after) {
  const beforeSet = new Set(Object.keys(before));
  const afterSet = new Set(Object.keys(after));

  /** @type {string[]} */
  const removed = [];
  /** @type {string[]} */
  const added = [];

  for (const f of beforeSet) if (!afterSet.has(f)) removed.push(f);
  for (const f of afterSet) if (!beforeSet.has(f)) added.push(f);

  removed.sort();
  added.sort();

  // Best-effort pairing: match removed→added by identical size, then closest mtime.
  const addedBySize = new Map();
  for (const f of added) {
    const size = after[f]?.size;
    if (typeof size !== 'number') continue;
    if (!addedBySize.has(size)) addedBySize.set(size, []);
    addedBySize.get(size).push(f);
  }
  for (const arr of addedBySize.values()) arr.sort();

  /** @type {{ oldPath: string; newPath: string; reason: string }[]} */
  const paired = [];
  /** @type {string[]} */
  const unpairedRemoved = [];
  /** @type {string[]} */
  const usedAdded = new Set();

  for (const oldPath of removed) {
    const size = before[oldPath]?.size;
    if (typeof size !== 'number' || !addedBySize.has(size)) {
      unpairedRemoved.push(oldPath);
      continue;
    }
    const candidates = addedBySize.get(size).filter((p) => !usedAdded.has(p));
    if (candidates.length === 0) {
      unpairedRemoved.push(oldPath);
      continue;
    }
    if (candidates.length === 1) {
      const newPath = candidates[0];
      usedAdded.add(newPath);
      paired.push({ oldPath, newPath, reason: 'size' });
      continue;
    }

    const oldM = before[oldPath]?.mtimeMs ?? 0;
    let best = candidates[0];
    let bestDist = Math.abs((after[best]?.mtimeMs ?? 0) - oldM);
    for (const c of candidates.slice(1)) {
      const dist = Math.abs((after[c]?.mtimeMs ?? 0) - oldM);
      if (dist < bestDist) {
        best = c;
        bestDist = dist;
      }
    }
    usedAdded.add(best);
    paired.push({ oldPath, newPath: best, reason: 'size+mtime' });
  }

  const unpairedAdded = added.filter((p) => !usedAdded.has(p));

  return { removed, added, paired, unpairedRemoved, unpairedAdded };
}

function printHelp() {
  process.stdout.write(
    [
      'ai_rename_images.js',
      '',
      'Usage:',
      '  node .cursor/skills/figma-image-download/scripts/ai_rename_images.js --dir <dir> [options] [-- <ai-rename args...>]',
      '',
      'Options:',
      '  -d, --dir <dir>         Directory containing images (required)',
      '  -r, --recursive         Recurse into subdirectories',
      '  --bin <cmd>             Renamer executable name/path (default: ai-renamer)',
      '  --mode <files|dir>      Call ai-rename with files list or with directory (default: dir)',
      '  --exts <csv>            Extensions filter (default: png,jpg,jpeg,webp,svg)',
      '  -m, --manifest <path>   Write rename manifest JSON (optional)',
      '  --file-list <path>      Newline-delimited file paths to rename (optional)',
      '  -h, --help              Show help',
      '',
      'Examples:',
      '  node .../ai_rename_images.js -d src/assets/word',
      '  node .../ai_rename_images.js -d src/assets/word --mode dir -- --profile ui --dry-run',
      '  node .../ai_rename_images.js -d src/assets/word -m rename-manifest.json -- --dry-run',
      '  node .../ai_rename_images.js -d src/assets/word --file-list /tmp/new-files.txt -- --dry-run',
      '',
    ].join('\n'),
  );
}

function readFileList(fileListPath) {
  const abs = path.resolve(process.cwd(), fileListPath);
  const content = fs.readFileSync(abs, 'utf8');
  return content
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((p) => path.resolve(process.cwd(), p));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    process.exit(0);
  }

  if (!args.dir) {
    process.stderr.write('Error: --dir is required\n');
    printHelp();
    process.exit(2);
  }

  const dirAbs = path.resolve(process.cwd(), args.dir);
  if (!fs.existsSync(dirAbs) || !fs.statSync(dirAbs).isDirectory()) {
    process.stderr.write(`Error: not a directory: ${dirAbs}\n`);
    process.exit(2);
  }

  const beforeSnap = args.manifest
    ? snapshotDir(dirAbs, { recursive: args.recursive, exts: args.exts })
    : null;

  const images = args.fileList
    ? readFileList(args.fileList)
    : collectImages(dirAbs, { recursive: args.recursive, exts: args.exts });
  if (images.length === 0) {
    process.stdout.write(`No images found under: ${dirAbs}\n`);
    process.exit(0);
  }

  const childArgs =
    args.mode === 'dir' ? [dirAbs, ...args.passthrough] : [...images, ...args.passthrough];

  const binResolved = resolveLocalBin(args.bin);
  process.stdout.write(
    `Running: ${binResolved} ${childArgs.map((s) => JSON.stringify(s)).join(' ')}\n`,
  );

  const child = spawn(binResolved, childArgs, {
    stdio: 'inherit',
    shell: false,
  });

  child.on('error', (err) => {
    // Common: ENOENT when bin not found
    if (err && typeof err === 'object' && 'code' in err && err.code === 'ENOENT') {
      process.stderr.write(`Error: '${args.bin}' not found (PATH or local node_modules/.bin)\n`);
      process.exit(127);
    }
    process.stderr.write(`Error: failed to start '${args.bin}': ${String(err)}\n`);
    process.exit(1);
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      process.stderr.write(`ai-rename terminated by signal: ${signal}\n`);
      process.exit(1);
    }
    const exitCode = code ?? 1;
    if (exitCode === 0 && args.manifest && beforeSnap) {
      try {
        const afterSnap = snapshotDir(dirAbs, { recursive: args.recursive, exts: args.exts });
        const diff = diffSnapshots(beforeSnap, afterSnap);
        const manifestAbs = path.resolve(process.cwd(), args.manifest);
        const payload = {
          tool: 'ai_rename_images.js',
          bin: args.bin,
          dir: dirAbs,
          recursive: args.recursive,
          exts: args.exts,
          ranAt: new Date().toISOString(),
          passthrough: args.passthrough,
          summary: {
            beforeCount: Object.keys(beforeSnap).length,
            afterCount: Object.keys(afterSnap).length,
            added: diff.added.length,
            removed: diff.removed.length,
            paired: diff.paired.length,
            unpairedAdded: diff.unpairedAdded.length,
            unpairedRemoved: diff.unpairedRemoved.length,
          },
          diff,
        };
        fs.writeFileSync(manifestAbs, JSON.stringify(payload, null, 2) + '\n', 'utf8');
        process.stdout.write(`Wrote manifest: ${manifestAbs}\n`);
      } catch (e) {
        process.stderr.write(`Warn: failed to write manifest: ${String(e)}\n`);
      }
    }
    process.exit(exitCode);
  });
}

void main();
