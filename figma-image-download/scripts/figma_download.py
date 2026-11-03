#!/usr/bin/env python3
"""
Figma 图片批量下载工具

支持两种模式:
  1. 单张/批量下载: 传入 node-id（逗号分隔多个）
  2. 自动提取: 传入 Figma 链接，自动下载页面所有可导出节点

用法:
  python3 figma_download.py -k <token> -u <baseurl> -n "1:234,5:678"
  python3 figma_download.py -k <token> -f <file_key> -n "1:234,5:678"

Token 获取: Figma → 头像 → Settings → Personal Access Tokens
"""

import argparse
import os
import re
import shutil
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests  # pip install requests
from requests.adapters import HTTPAdapter

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(SKILL_ROOT, ".env")
TEMP_DIR_BASE = os.path.join(SKILL_ROOT, ".tmp")
DEFAULT_ASSETS_SUBDIR = "img"
DEFAULT_PNG_QUALITY = "65-80"
DEFAULT_DOWNLOAD_WORKERS = 8
DEFAULT_COMPRESS_WORKERS = 4
DEFAULT_PNGQUANT_SPEED = 4


def load_dotenv(path=ENV_FILE):
    """从 .env 文件加载环境变量（不覆盖已存在的值）"""
    if not os.path.isfile(path):
        return

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def resolve_token(cli_token=None):
    """优先使用 CLI 参数，其次读取 FIGMA_TOKEN 环境变量"""
    return cli_token or os.environ.get("FIGMA_TOKEN")


def find_project_root():
    """向上查找含 src/assets 的仓库根目录；找不到则退回当前工作目录"""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(12):
        if os.path.isdir(os.path.join(cur, "src", "assets")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, "src", "assets")):
        return cwd
    return cwd


def assets_output_path(subdir):
    """src/assets/<subdir> 的绝对路径"""
    root = find_project_root()
    normalized = subdir.strip().strip("/").strip("\\")
    return os.path.join(root, "src", "assets", normalized)


def resolve_output_dir(cli_output=None, cli_assets_dir=None):
    """解析输出目录：-o 全路径 > -a/FIGMA_ASSETS_DIR > FIGMA_OUTPUT_DIR > src/assets/img"""
    if cli_output:
        return os.path.abspath(os.path.expanduser(cli_output))

    if cli_assets_dir is not None or os.environ.get("FIGMA_ASSETS_DIR"):
        subdir = (cli_assets_dir or os.environ.get("FIGMA_ASSETS_DIR") or DEFAULT_ASSETS_SUBDIR).strip()
        return assets_output_path(subdir or DEFAULT_ASSETS_SUBDIR)

    env_output = os.environ.get("FIGMA_OUTPUT_DIR")
    if env_output:
        return os.path.abspath(os.path.expanduser(env_output))

    return assets_output_path(DEFAULT_ASSETS_SUBDIR)


def env_flag(name, default=True):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def resolve_ai_rename_args():
    """解析下载后语义化重命名相关配置（用于调用 Node wrapper）"""
    enabled = env_flag("FIGMA_AI_RENAME", False)
    if not enabled:
        return None

    bin_name = os.environ.get("FIGMA_AI_RENAME_BIN", "ai-renamer").strip() or "ai-renamer"
    api_key = (os.environ.get("FIGMA_AI_RENAME_API_KEY") or "").strip()
    manifest = (os.environ.get("FIGMA_AI_RENAME_MANIFEST") or "").strip()

    # Space-separated args string, e.g.
    #   --provider openai --model gpt-4o-mini --language English --case kebabCase --chars 40
    raw_args = (os.environ.get("FIGMA_AI_RENAME_ARGS") or "").strip()
    # Use shell-like splitting to support quotes/spaces, e.g. --custom-prompt "Only describe ..."
    passthrough = shlex.split(raw_args) if raw_args else []
    if api_key:
        passthrough += ["--api-key", api_key]

    return {
        "bin": bin_name,
        "manifest": manifest,
        "passthrough": passthrough,
    }


def create_temp_work_dir():
    """在 skill/.tmp 下创建本次运行的隔离工作目录"""
    os.makedirs(TEMP_DIR_BASE, exist_ok=True)
    work_dir = os.path.join(TEMP_DIR_BASE, f"run-{int(time.time() * 1000)}")
    os.makedirs(work_dir, exist_ok=True)
    return work_dir


def cleanup_temp_work_dir(work_dir):
    """删除临时工作目录（仅允许删除 skill/.tmp 下的路径）"""
    if not work_dir:
        return
    abs_work = os.path.abspath(work_dir)
    abs_base = os.path.abspath(TEMP_DIR_BASE)
    if not abs_work.startswith(abs_base + os.sep):
        return
    if os.path.isdir(abs_work):
        shutil.rmtree(abs_work, ignore_errors=True)


def list_image_files(directory, fmt="png"):
    """列出目录内指定格式的图片文件（不含隐藏文件）"""
    ext = f".{fmt}".lower()
    paths = []
    for name in os.listdir(directory):
        if name.startswith("."):
            continue
        path = os.path.join(directory, name)
        if os.path.isfile(path) and name.lower().endswith(ext):
            paths.append(path)
    paths.sort()
    return paths


def publish_from_temp(temp_dir, output_dir):
    """将临时目录中的文件复制到目标 assets 目录"""
    os.makedirs(output_dir, exist_ok=True)
    copied = []
    for name in sorted(os.listdir(temp_dir)):
        if name.startswith("."):
            continue
        src = os.path.join(temp_dir, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(output_dir, name)
        shutil.copy2(src, dst)
        copied.append(dst)
    return copied


def process_temp_and_publish(
    temp_dir,
    output_dir,
    fmt="png",
    compress=True,
    png_quality=DEFAULT_PNG_QUALITY,
    compress_workers=DEFAULT_COMPRESS_WORKERS,
    pngquant_speed=DEFAULT_PNGQUANT_SPEED,
    ai_rename_cfg=None,
):
    """在临时目录内压缩、重命名，再复制到目标目录并清理临时目录"""
    try:
        if compress and fmt == "png":
            png_paths = list_image_files(temp_dir, "png")
            if png_paths:
                compress_pngs(
                    png_paths,
                    quality=png_quality,
                    enabled=True,
                    workers=compress_workers,
                    speed=pngquant_speed,
                )

        if ai_rename_cfg and fmt in ("png", "jpg", "svg"):
            run_ai_rename(
                temp_dir,
                new_files=None,
                recursive=False,
                exts=[f".{fmt}"],
                cfg=ai_rename_cfg,
            )

        copied = publish_from_temp(temp_dir, output_dir)
        if copied:
            print(f"\n已复制 {len(copied)} 个文件 → {output_dir}/")
            for path in copied:
                print(f"  → {os.path.basename(path)}")
        else:
            print(f"\n提示: 临时目录无文件可复制 → {output_dir}/", file=sys.stderr)
        return copied
    finally:
        cleanup_temp_work_dir(temp_dir)


def run_ai_rename(output_dir, new_files=None, recursive=False, exts=None, cfg=None):
    """调用 Node 脚本批量语义化重命名（subprocess）"""
    if not cfg:
        return

    script = os.path.join(SKILL_ROOT, "scripts", "ai_rename_images.js")
    if not os.path.isfile(script):
        print(f"\n提示: 未找到重命名脚本: {script}，已跳过语义化重命名", file=sys.stderr)
        return

    # Important: run from skill root so this skill's local node_modules/.bin can be resolved.
    # This makes the skill self-contained and avoids depending on repo root deps.
    skill_root = SKILL_ROOT
    cmd = ["node", script, "--dir", output_dir, "--bin", cfg["bin"], "--mode", "dir"]
    tmp_list_path = None
    if new_files:
        # Legacy: restrict rename to explicit file list (prefer temp-dir workflow instead).
        tmp_list_path = os.path.join(output_dir, ".__figma_new_files__.txt")
        try:
            with open(tmp_list_path, "w", encoding="utf-8") as f:
                for p in new_files:
                    f.write(str(p) + "\n")
            cmd += ["--file-list", tmp_list_path]
        except Exception as e:
            print(f"提示: 无法写入 new files 列表（{e}），将跳过语义化重命名", file=sys.stderr)
            return
    if recursive:
        cmd.append("--recursive")
    if exts:
        cmd += ["--exts", ",".join(exts)]
    if cfg.get("manifest"):
        cmd += ["--manifest", os.path.join(output_dir, cfg["manifest"])]
    if cfg.get("passthrough"):
        cmd.append("--")
        cmd += cfg["passthrough"]

    print("\n语义化重命名 (ai-rename)...")
    try:
        subprocess.run(cmd, check=True, cwd=skill_root)
    except subprocess.CalledProcessError as e:
        print(f"提示: 语义化重命名失败（exit={e.returncode}），已跳过", file=sys.stderr)
    finally:
        if tmp_list_path:
            try:
                os.remove(tmp_list_path)
            except Exception:
                pass

def resolve_png_quality(cli_quality=None):
    return cli_quality or os.environ.get("FIGMA_PNG_QUALITY") or DEFAULT_PNG_QUALITY


def resolve_int_env(name, default):
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return max(1, int(val))
    except ValueError:
        return default


def resolve_pngquant_speed(cli_speed=None):
    if cli_speed is not None:
        return max(1, min(11, int(cli_speed)))
    return max(1, min(11, resolve_int_env("FIGMA_PNGQUANT_SPEED", DEFAULT_PNGQUANT_SPEED)))


def make_session(pool_size=DEFAULT_DOWNLOAD_WORKERS):
    """复用 TCP 连接，提升并行下载效率"""
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def normalize_node_ids(node_ids_str):
    """支持 11873-2083 或 11873:2083 两种 node-id 格式"""
    ids = []
    for raw in node_ids_str.split(","):
        nid = raw.strip().replace("-", ":")
        if nid:
            ids.append(nid)
    return ids


def compress_png(filepath, quality=DEFAULT_PNG_QUALITY, speed=DEFAULT_PNGQUANT_SPEED):
    """使用 pngquant 原地压缩 PNG，返回 (成功, 消息)"""
    if not shutil.which("pngquant"):
        return None, "pngquant missing"

    before = os.path.getsize(filepath)
    result = subprocess.run(
        [
            "pngquant",
            f"--quality={quality}",
            f"--speed={speed}",
            "--force",
            "--output",
            filepath,
            filepath,
        ],
        capture_output=True,
    )

    name = os.path.basename(filepath)
    if result.returncode == 0:
        after = os.path.getsize(filepath)
        if before > 0:
            pct = (1 - after / before) * 100
            msg = f"  ↳ 压缩 {name}: {before / 1024:.0f} KB → {after / 1024:.0f} KB (-{pct:.0f}%)"
        else:
            msg = f"  ↳ 压缩 {name}"
        return True, msg

    if result.returncode == 99:
        return True, f"  ↳ 跳过（已最优）: {name}"

    return False, f"  ↳ 压缩失败: {name} (exit {result.returncode})"


def compress_pngs(
    paths,
    quality=DEFAULT_PNG_QUALITY,
    enabled=True,
    workers=DEFAULT_COMPRESS_WORKERS,
    speed=DEFAULT_PNGQUANT_SPEED,
):
    """并行压缩已下载的 PNG 文件"""
    if not enabled or not paths:
        return 0, 0

    if not shutil.which("pngquant"):
        print("\n提示: 未安装 pngquant，已跳过 PNG 压缩。安装: brew install pngquant", file=sys.stderr)
        return 0, 0

    workers = min(workers, len(paths))
    print(f"\n压缩 PNG ({quality}, speed={speed}, {workers} 线程)...")
    ok = fail = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(compress_png, path, quality, speed): path for path in paths
        }
        for future in as_completed(futures):
            success, msg = future.result()
            if success is None:
                continue
            print(msg, file=sys.stderr if not success else sys.stdout)
            if success:
                ok += 1
            else:
                fail += 1

    print(f"压缩完成: {ok} 成功, {fail} 失败")
    return ok, fail


# ---- 核心函数 ----

def get_images(file_key, node_ids, token, fmt="png", scale=2):
    """调用 Figma API 获取节点导出 URL"""
    if isinstance(node_ids, list):
        ids_str = ",".join(node_ids)
    else:
        ids_str = node_ids

    resp = requests.get(
        f"https://api.figma.com/v1/images/{file_key}",
        params={"ids": ids_str, "format": fmt, "scale": scale},
        headers={"X-Figma-Token": token},
        timeout=30,
    )
    data = resp.json()

    if data.get("err"):
        print(f"Figma API 错误: {data['err']}", file=sys.stderr)
        sys.exit(1)

    if data.get("status") and data["status"] != 200:
        print(f"API 返回状态: {data['status']} - {data.get('err', '')}", file=sys.stderr)
        sys.exit(1)

    return data.get("images", {})


def _download_one(session, node_id, url, output_dir, fmt):
    """下载单张图片，返回 (node_id, filepath|None, error|None, size_kb, is_new_file)"""
    filename = f"{node_id.replace(':', '_')}.{fmt}"
    filepath = os.path.join(output_dir, filename)
    existed_before = os.path.isfile(filepath)
    try:
        r = session.get(url, timeout=60)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            f.write(r.content)
        is_new_file = not existed_before
        return node_id, filepath, None, len(r.content) / 1024, is_new_file
    except Exception as e:
        return node_id, None, str(e), 0, False


def download_images(
    images,
    fmt="png",
    output_dir=None,
    compress=True,
    compress_inline=True,
    png_quality=DEFAULT_PNG_QUALITY,
    download_workers=DEFAULT_DOWNLOAD_WORKERS,
    compress_workers=DEFAULT_COMPRESS_WORKERS,
    pngquant_speed=DEFAULT_PNGQUANT_SPEED,
    session=None,
):
    """并行下载图片到本地。

    compress_inline=True 时在下载过程中并行压缩（旧行为）。
    compress_inline=False 时仅下载，压缩留给 process_temp_and_publish。
    """
    if output_dir is None:
        output_dir = assets_output_path(DEFAULT_ASSETS_SUBDIR)
    os.makedirs(output_dir, exist_ok=True)

    total = len(images)
    missing = [nid for nid, url in images.items() if not url]
    tasks = [(nid, url) for nid, url in images.items() if url]

    success = 0
    fail = len(missing)
    new_files = []

    for node_id in missing:
        print(f"  ✗ {node_id} → 无下载链接（节点可能缺少导出设置）")

    if not tasks:
        print(f"\n完成: 0 成功, {fail} 失败, 共 {total} 张 → {output_dir}/")
        return success, fail

    workers = min(download_workers, len(tasks))
    own_session = session is None
    session = session or make_session(workers)

    t_dl = time.perf_counter()
    compress_futures = []
    do_inline_compress = compress and compress_inline and fmt == "png" and shutil.which("pngquant")

    with ThreadPoolExecutor(max_workers=workers) as dl_pool:
        compress_pool = None
        cp_workers = min(compress_workers, len(tasks))
        if do_inline_compress:
            compress_pool = ThreadPoolExecutor(max_workers=cp_workers)

        futures = {
            dl_pool.submit(_download_one, session, node_id, url, output_dir, fmt): node_id
            for node_id, url in tasks
        }
        for future in as_completed(futures):
            node_id, filepath, err, size_kb, is_new_file = future.result()
            if err:
                print(f"  ✗ {node_id} → 下载失败: {err}")
                fail += 1
            else:
                suffix = ""
                if compress_inline and not is_new_file:
                    suffix = "（已存在，跳过压缩）"
                print(f"  ✓ {node_id} → {os.path.basename(filepath)} ({size_kb:.0f} KB){suffix}")
                success += 1
                if filepath and (is_new_file or not compress_inline):
                    new_files.append(filepath)
                if compress_pool and filepath and is_new_file:
                    compress_futures.append(
                        compress_pool.submit(compress_png, filepath, png_quality, pngquant_speed)
                    )

        if compress_pool:
            if compress_futures:
                print(f"\n压缩 PNG ({png_quality}, speed={pngquant_speed}, {cp_workers} 线程)...")
                ok = fail_cp = 0
                for future in as_completed(compress_futures):
                    success_cp, msg = future.result()
                    if success_cp is None:
                        continue
                    print(msg, file=sys.stderr if not success_cp else sys.stdout)
                    if success_cp:
                        ok += 1
                    else:
                        fail_cp += 1
                print(f"压缩完成: {ok} 成功, {fail_cp} 失败")
            else:
                print("\n目录内均为已有文件，已跳过 PNG 压缩")
            compress_pool.shutdown(wait=True)

    dl_secs = time.perf_counter() - t_dl
    phase = "下载+压缩" if do_inline_compress else "下载"
    print(f"\n{phase}: {success} 成功, {fail} 失败, 共 {total} 张 ({dl_secs:.1f}s) → {output_dir}/")

    if own_session:
        session.close()

    return success, fail, new_files


def collect_node_ids(file_key, token, depth=1):
    """递归提取文件中所有可导出节点的 ID"""
    resp = requests.get(
        f"https://api.figma.com/v1/files/{file_key}",
        params={"depth": depth},
        headers={"X-Figma-Token": token},
        timeout=30,
    )
    data = resp.json()

    if data.get("err"):
        print(f"读取文件失败: {data['err']}", file=sys.stderr)
        sys.exit(1)

    node_ids = []

    def walk(node):
        if node.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET"):
            node_ids.append(node["id"])
        for child in node.get("children", []):
            walk(child)

    walk(data["document"])
    return node_ids


def parse_figma_url(url):
    """从 Figma URL 提取 file_key 和 node_id

    支持格式:
      https://www.figma.com/file/abc123/...?node-id=1-234
      https://www.figma.com/design/abc123/...?node-id=5%3A678
    """
    file_match = re.search(r"/(?:file|design)/(\w+)", url)
    if not file_match:
        return None, None

    file_key = file_match.group(1)

    node_match = re.search(r"node-id=([\d\-\%]+)", url)
    if node_match:
        # URL 里用 - 分隔，API 里用 : 分隔
        node_id = node_match.group(1).replace("%3A", ":").replace("-", ":")
        return file_key, node_id

    return file_key, None


# ---- 入口 ----

def main():
    parser = argparse.ArgumentParser(
        description="Figma 图片批量下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # baseurl + node-id 分开传（推荐）
  python3 figma_download.py -k <token> -u "https://www.figma.com/file/abc123/xxx" -n "1:234,5:678"

  # 也可以从完整链接一步下载（含 node-id 在 URL 里）
  python3 figma_download.py -k <token> -u "https://www.figma.com/file/xxx?node-id=1-234"

  # 用 file_key 代替 url
  python3 figma_download.py -k <token> -f abc123 -n "1:234,5:678,9:1011"

  # 下载整个页面的所有 Frame/Component
  python3 figma_download.py -k <token> -f abc123 --all

  # 自定义输出格式和缩放倍数
  python3 figma_download.py -k <token> -u "https://..." -n 1:234 --format svg --scale 1

  # 默认输出到仓库 src/assets/img；指定子目录
  python3 figma_download.py -k <token> -f abc123 -n 1:234 -a extension/bg

Token: 在技能目录 .env 中设置 FIGMA_TOKEN，或使用 -k 参数
        Figma → 头像 → Settings → Personal Access Tokens → 生成
        """,
    )

    parser.add_argument(
        "-k",
        "--token",
        help="Figma Personal Access Token（也可通过 .env 或 FIGMA_TOKEN 环境变量提供）",
    )
    parser.add_argument("-f", "--file-key", help="Figma 文件 key（从 URL 提取）")
    parser.add_argument("-u", "--url", help="Figma 链接（自动解析 file_key 和 node_id）")
    parser.add_argument("-n", "--node-ids", help="节点 ID，多个用逗号分隔（如 1:234,5:678）")
    parser.add_argument("--all", action="store_true", help="下载文件所有 Frame/Component 节点")
    parser.add_argument("--format", default="png", choices=["png", "svg", "jpg"], help="导出格式（默认 png）")
    parser.add_argument("--scale", type=float, default=2, help="缩放倍数（默认 2，导出 2x 清晰度）")
    parser.add_argument(
        "-a",
        "--assets-dir",
        help="输出到仓库 src/assets/<子目录>（默认 img；例: extension/bg）",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="输出目录全路径（优先于 -a；也可在 .env 设置 FIGMA_OUTPUT_DIR）",
    )
    parser.add_argument(
        "--no-compress",
        action="store_true",
        help="跳过 PNG 压缩（默认下载后使用 pngquant 压缩）",
    )
    parser.add_argument(
        "--png-quality",
        help="pngquant 质量区间，如 65-80（也可在 .env 设置 FIGMA_PNG_QUALITY）",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="并行下载线程数（也可在 .env 设置 FIGMA_DOWNLOAD_WORKERS）",
    )
    parser.add_argument(
        "--compress-workers",
        type=int,
        help="并行压缩线程数（也可在 .env 设置 FIGMA_COMPRESS_WORKERS）",
    )
    parser.add_argument(
        "--pngquant-speed",
        type=int,
        help="pngquant 速度 1-11，越大越快（默认 4，.env: FIGMA_PNGQUANT_SPEED）",
    )

    args = parser.parse_args()

    load_dotenv()
    t_start = time.perf_counter()
    token = resolve_token(args.token)
    final_output_dir = resolve_output_dir(args.output, args.assets_dir)
    temp_dir = create_temp_work_dir()
    ai_rename_cfg = resolve_ai_rename_args()
    compress_png_enabled = not args.no_compress and env_flag("FIGMA_COMPRESS_PNG", True)
    png_quality = resolve_png_quality(args.png_quality)
    download_workers = args.workers or resolve_int_env("FIGMA_DOWNLOAD_WORKERS", DEFAULT_DOWNLOAD_WORKERS)
    compress_workers = args.compress_workers or resolve_int_env(
        "FIGMA_COMPRESS_WORKERS", DEFAULT_COMPRESS_WORKERS
    )
    pngquant_speed = resolve_pngquant_speed(args.pngquant_speed)
    if not token:
        print(
            "错误: 未找到 Figma Token。请任选其一:\n"
            f"  1. 在 {ENV_FILE} 中设置 FIGMA_TOKEN=...\n"
            "  2. 导出环境变量 FIGMA_TOKEN\n"
            "  3. 使用 -k <token> 参数",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- 解析参数 ---
    file_key = args.file_key
    node_ids = None

    if args.url:
        key, url_nid = parse_figma_url(args.url)
        if not key:
            print("错误: 无法解析 Figma URL", file=sys.stderr)
            sys.exit(1)
        file_key = key
        # 如果用户没单独传 -n，才从 URL 中提取 node-id
        if not args.node_ids and url_nid and not args.all:
            node_ids = [url_nid]

    if not file_key:
        print("错误: 请提供 -f <file_key> 或 -u <url>", file=sys.stderr)
        sys.exit(1)

    if args.node_ids:
        node_ids = normalize_node_ids(args.node_ids)

    print(f"Figma 图片下载工具")
    print(f"  File Key: {file_key}")
    print(f"  格式: {args.format}, 缩放: {args.scale}x")
    print(f"  目标目录: {final_output_dir}")
    print(f"  临时目录: {temp_dir}")
    print(f"  并行: 下载 {download_workers} 线程", end="")
    if args.format == "png" and compress_png_enabled:
        print(f", 压缩 {compress_workers} 线程 (quality={png_quality}, speed={pngquant_speed})")
    else:
        print()

    dl_kwargs = dict(
        compress=compress_png_enabled,
        compress_inline=False,
        png_quality=png_quality,
        download_workers=download_workers,
        compress_workers=compress_workers,
        pngquant_speed=pngquant_speed,
    )

    publish_kwargs = dict(
        fmt=args.format,
        compress=compress_png_enabled,
        png_quality=png_quality,
        compress_workers=compress_workers,
        pngquant_speed=pngquant_speed,
        ai_rename_cfg=ai_rename_cfg,
    )

    # --- 模式 1: 下载所有节点 ---
    if args.all:
        print("  模式: 自动提取所有 Frame/Component")
        node_ids = collect_node_ids(file_key, token)
        if not node_ids:
            cleanup_temp_work_dir(temp_dir)
            print("未找到可导出的 Frame/Component 节点")
            sys.exit(1)
        print(f"  找到 {len(node_ids)} 个节点")
        try:
            # 分批处理，避免 URL 过长
            BATCH = 50
            with make_session(download_workers) as session:
                for i in range(0, len(node_ids), BATCH):
                    batch = node_ids[i : i + BATCH]
                    print(f"\n--- 批次 {i // BATCH + 1} ({len(batch)} 个) ---")
                    images = get_images(file_key, batch, token, args.format, args.scale)
                    download_images(
                        images,
                        args.format,
                        temp_dir,
                        session=session,
                        **dl_kwargs,
                    )
            process_temp_and_publish(temp_dir, final_output_dir, **publish_kwargs)
        except Exception:
            cleanup_temp_work_dir(temp_dir)
            raise
        print(f"\n总耗时: {time.perf_counter() - t_start:.1f}s")
        return

    # --- 模式 2: 指定节点下载 ---
    if not node_ids:
        print("错误: 请提供 -n <node_ids> 或 --all", file=sys.stderr)
        sys.exit(1)

    print(f"  节点: {len(node_ids)} 个 → {', '.join(node_ids)}")
    print()

    try:
        with make_session(download_workers) as session:
            images = get_images(file_key, node_ids, token, args.format, args.scale)
            download_images(images, args.format, temp_dir, session=session, **dl_kwargs)
        process_temp_and_publish(temp_dir, final_output_dir, **publish_kwargs)
    except Exception:
        cleanup_temp_work_dir(temp_dir)
        raise
    print(f"\n总耗时: {time.perf_counter() - t_start:.1f}s")


if __name__ == "__main__":
    main()
