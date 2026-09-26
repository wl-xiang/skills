#!/usr/bin/env python3
"""sync_upstream.py — 把本仓库 skills/ 下登记为「同步上游」的 Skill 拉成上游最新内容。

设计目标
--------
* 本仓库里的某个 Skill 目录（如 `skills/git-commit/`）是从第三方仓库整体搬过来的，
  之后上游更新了，本地还停留在旧版本 —— 本脚本负责把它「重置」成上游的样子。
* 同步语义 = **丢弃该 Skill 目录的本地修改**：先清空目录（只保留白名单文件），
  再把上游目标目录下的全部文件原样写入。
* 哪些 Skill 参与同步、上游仓库地址、上游仓库内的子目录，全部由 `sync_config.json` 声明。

用法
----
    python skills/sync_upstream.py --list                 # 列出已登记的 Skill 及状态
    python skills/sync_upstream.py git-commit             # 同步单个（交互确认）
    python skills/sync_upstream.py git-commit -y          # 跳过确认
    python skills/sync_upstream.py git-commit --ref main  # 临时指定 ref
    python skills/sync_upstream.py --all -y               # 同步全部已登记 Skill
    python skills/sync_upstream.py git-commit --dry-run   # 只预览会变什么，不落盘
    python skills/sync_upstream.py --config path/to.json --list

上游抓取策略
------------
1. 上游是 GitHub（`github.com`）：走 GitHub API 拿 tree，再逐个 blob 走 raw 下载。
   可通过环境变量 `GITHUB_TOKEN` / `GH_TOKEN` 提高限流额度（私有仓库则必须给）。
2. 其他 Git 托管：退回 `git clone --depth 1 --filter=blob:none --sparse` + sparse-checkout。
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:  # Windows 控制台可能不是 UTF-8，避免中文输出炸掉
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

SCRIPT_DIR = Path(__file__).resolve().parent          # <repo>/skills
DEFAULT_CONFIG = SCRIPT_DIR / "sync_config.json"
DEFAULT_KEEP = [".upstream.json"]
METADATA_NAME = ".upstream.json"
UA = "skills-repo-sync-upstream/1.0"


# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
def load_config(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"[x] 配置文件不存在: {path}\n    可用 --config 指定路径。")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[x] 配置文件不是合法 JSON: {path}\n    {exc}")
    if not isinstance(cfg.get("skills"), dict) or not cfg["skills"]:
        raise SystemExit(f"[x] {path} 里没有 skills 条目。")
    return cfg


def normalize_entry(name: str, raw: dict) -> dict:
    """把配置条目整理成统一结构。"""
    if not isinstance(raw, dict):
        raise SystemExit(f"[x] skill '{name}' 的配置必须是一个对象。")
    up = raw.get("upstream")
    if not isinstance(up, dict) or not up.get("repo") or not up.get("path"):
        raise SystemExit(
            f"[x] skill '{name}' 缺少 upstream.repo / upstream.path（上游仓库地址与仓库内子目录）。"
        )
    keep = raw.get("keep", DEFAULT_KEEP)
    if not isinstance(keep, list):
        raise SystemExit(f"[x] skill '{name}' 的 keep 必须是数组。")
    return {
        "name": name,
        "enabled": bool(raw.get("enabled", True)),
        "repo": str(up["repo"]).rstrip("/"),
        "ref": up.get("ref") or raw.get("ref"),      # 缺省走上游默认分支
        "subpath": str(up["path"]).strip("/"),
        "keep": set(keep) | {METADATA_NAME},         # 元数据文件永远保留
        "local_dir": SCRIPT_DIR / name,
    }


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
RETRIES = 3
TIMEOUT = 30


def _open(url: str, headers: dict):
    """带重试的 urlopen；HTTPError 直接抛出交给上层处理。"""
    last: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
            last = exc
            if attempt < RETRIES:
                print(f"    [retry {attempt}/{RETRIES}] 网络波动，重试 {url}", file=sys.stderr)
                time.sleep(attempt * 2)
    raise SystemExit(f"[x] 网络请求失败（已重试 {RETRIES} 次）：{url}\n    {last}")


def http_json(url: str, token: str | None = None) -> dict:
    try:
        payload = _open(url, _headers(token, accept="application/vnd.github+json"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        hint = ""
        if exc.code in (401, 403):
            hint = "\n    提示：GitHub API 限流或需要 token，可设置 GITHUB_TOKEN 环境变量。"
        elif exc.code == 404:
            hint = "\n    提示：仓库/ref 不存在，或该仓库为私有（私有仓库需要 GITHUB_TOKEN）。"
        raise SystemExit(f"[x] 请求 {url} 失败：HTTP {exc.code} {exc.reason}\n    {body}{hint}")
    return json.loads(payload.decode("utf-8"))


def http_bytes(url: str, token: str | None = None, fatal: bool = True) -> bytes | None:
    """下载文件内容；fatal=False 时失败返回 None（供上层走备用通道）。"""
    try:
        return _open(url, _headers(token, accept="application/octet-stream"))
    except urllib.error.HTTPError as exc:
        if not fatal:
            return None
        raise SystemExit(f"[x] 下载失败：{url}\n    HTTP {exc.code} {exc.reason}")
    except SystemExit:
        if fatal:
            raise
        return None


def http_blob(api: str, sha: str, token: str | None) -> bytes | None:
    """备用通道：通过 GitHub git blobs API 取内容（base64）。"""
    try:
        data = http_json(f"{api}/git/blobs/{sha}", token)
        return base64.b64decode(data["content"])
    except SystemExit:
        return None


def _headers(token: str | None, accept: str) -> dict:
    h = {"User-Agent": UA, "Accept": accept}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# --------------------------------------------------------------------------- #
# 上游抓取
# --------------------------------------------------------------------------- #
def fetch_from_github(entry: dict, token: str | None) -> tuple[str, dict[str, bytes], dict[str, int]]:
    """返回 (commit_sha, {相对路径: 内容}, {相对路径: 权限位})。"""
    owner, repo = parse_github_repo(entry["repo"])
    api = f"https://api.github.com/repos/{owner}/{repo}"

    ref = entry["ref"] or http_json(api, token).get("default_branch") or "main"
    commit_sha = http_json(f"{api}/commits/{urllib.parse.quote(ref, safe='')}", token)["sha"]

    # 只按目标目录逐层拉取 contents（skill 目录通常很浅），避免整仓库 recursive tree 过大中断
    prefix = entry["subpath"] + "/"
    files: dict[str, bytes] = {}
    modes: dict[str, int] = {}
    _walk_contents(api, owner, repo, commit_sha, entry["subpath"], token, prefix, files, modes)

    if not files:
        raise SystemExit(
            f"[x] 上游 {owner}/{repo}@{ref} 的 '{entry['subpath']}' 下没找到任何文件，"
            f"请检查 sync_config.json 里的 path。"
        )
    return commit_sha, files, modes


def _walk_contents(api: str, owner: str, repo: str, commit_sha: str, path: str,
                   token: str | None, prefix: str,
                   files: dict[str, bytes], modes: dict[str, int]) -> None:
    """递归列出 GitHub 上某个目录，并下载其中所有文件。"""
    url = f"{api}/contents/{urllib.parse.quote(path, safe='')}?ref={commit_sha}"
    listing = http_json(url, token)
    if isinstance(listing, dict):        # 目标其实是个文件
        listing = [listing]
    for item in listing:
        if item.get("type") == "dir":
            _walk_contents(api, owner, repo, commit_sha, item["path"], token, prefix, files, modes)
            continue
        if item.get("type") not in ("file", "symlink"):
            continue                     # submodule 等类型跳过
        full = item["path"]
        rel = full[len(prefix):] if full.startswith(prefix) else item["name"]
        raw = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{urllib.parse.quote(full, safe='/')}"
        content = http_bytes(raw, token, fatal=False)
        if content is None:                                   # raw 抖动时走 blob API 兜底
            content = http_blob(api, item.get("sha", ""), token)
        if content is None:
            raise SystemExit(
                f"[x] 文件下载失败（raw 与 blob API 均失败）：{full}\n"
                f"    若持续失败，可设置 GITHUB_TOKEN 后重试。"
            )
        files[rel] = content
        modes[rel] = 0o755 if item.get("mode") == "100755" else 0o644


def fetch_by_git_clone(entry: dict) -> tuple[str, dict[str, bytes], dict[str, int]]:
    """非 GitHub 托管：浅克隆 + sparse-checkout 后读取文件。"""
    if not shutil.which("git"):
        raise SystemExit("[x] 非 GitHub 上游需要本机 git，但未找到 git 命令。")
    tmp = Path(tempfile.mkdtemp(prefix="skill-sync-"))
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", entry["repo"], str(tmp / "src")],
            check=True, capture_output=True, text=True,
        )
        src = tmp / "src"
        if entry["ref"]:
            subprocess.run(["git", "-C", str(src), "fetch", "--depth", "1", "origin", entry["ref"]],
                           check=True, capture_output=True, text=True)
            subprocess.run(["git", "-C", str(src), "checkout", entry["ref"]],
                           check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(src), "sparse-checkout", "set", entry["subpath"]],
                       check=True, capture_output=True, text=True)
        commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True).stdout.strip()
        root = src / entry["subpath"]
        if not root.is_dir():
            raise SystemExit(f"[x] 上游 {entry['repo']} 里找不到目录 '{entry['subpath']}'。")
        files, modes = {}, {}
        for file in root.rglob("*"):
            if file.is_file():
                files[str(file.relative_to(root))] = file.read_bytes()
                modes[str(file.relative_to(root))] = 0o755 if os.access(file, os.X_OK) else 0o644
        return commit, files, modes
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"[x] git 操作失败：{exc.stderr.strip()}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def parse_github_repo(repo: str) -> tuple[str, str]:
    """从 URL / owner/repo 形式里解析出 (owner, repo)。"""
    candidate = repo
    if "://" in candidate or candidate.startswith("git@"):
        if candidate.startswith("git@"):
            candidate = candidate.replace(":", "/", 1).replace("git@", "", 1)
        parsed = urllib.parse.urlparse(candidate if "://" in candidate else f"https://{candidate}")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
    else:
        parts = [p for p in candidate.split("/") if p]
    parts = [p[:-4] if p.endswith(".git") else p for p in parts]
    if len(parts) < 2:
        raise SystemExit(f"[x] 无法解析上游仓库地址：{repo}")
    return parts[-2], parts[-1]


def is_github(repo: str) -> bool:
    host = ""
    if "://" in repo:
        host = urllib.parse.urlparse(repo).netloc.lower()
    elif repo.startswith("git@"):
        host = repo.split("@", 1)[1].split(":", 1)[0].split("/", 1)[0].lower()
    return host in ("github.com", "www.github.com", "raw.githubusercontent.com")


# --------------------------------------------------------------------------- #
# 同步
# --------------------------------------------------------------------------- #
def local_files(directory: Path) -> dict[str, bytes]:
    if not directory.is_dir():
        return {}
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def diff_upstream(entry: dict, upstream: dict[str, bytes], keep: set[str]) -> tuple[list[str], list[str], list[str]]:
    current = local_files(entry["local_dir"])
    added = sorted(p for p in upstream if p not in current)
    updated = sorted(p for p in upstream if p in current and current[p] != upstream[p])
    removed = sorted(p for p in current if p not in upstream and p not in keep)
    return added, updated, removed


def confirm(entry: dict, added: list[str], updated: list[str], removed: list[str], assume_yes: bool) -> bool:
    print(f"\n==> {entry['name']}  <-  {entry['repo']} @ {entry['subpath']}")
    for path in added:
        print(f"    [+] {path}  (新增)")
    for path in updated:
        print(f"    [~] {path}  (覆盖本地修改)")
    for path in removed:
        print(f"    [-] {path}  (本地独有，将被删除)")
    if not (added or updated or removed):
        print("    [=] 与上游一致，无需改动")
        return False
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        raise SystemExit("[x] 非交互环境请显式加 -y/--yes 才会执行覆盖。")
    answer = input("    丢弃该 Skill 的本地修改并同步上游？[y/N] ").strip().lower()
    return answer in ("y", "yes")


def write_upstream(entry: dict, upstream: dict[str, bytes], modes: dict[str, int], keep: set[str]) -> None:
    target = entry["local_dir"]
    target.mkdir(parents=True, exist_ok=True)

    # 1) 清空本地（保留白名单）
    for item in sorted(target.iterdir(), key=lambda p: p.name):
        if item.name in keep:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # 2) 写入上游内容
    for rel, content in upstream.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        os.chmod(dest, modes.get(rel, 0o644))

    # 3) 记录来源元数据
    meta = {
        "skill": entry["name"],
        "repo": entry["repo"],
        "path": entry["subpath"],
        "ref": entry["ref"] or "(default branch)",
        "commit": entry.get("resolved_commit", ""),
        "synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": sorted(upstream),
    }
    (target / METADATA_NAME).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sync_entry(entry: dict, args: argparse.Namespace, token: str | None) -> int:
    if is_github(entry["repo"]):
        commit, upstream, modes = fetch_from_github(entry, token)
    else:
        commit, upstream, modes = fetch_by_git_clone(entry)
    entry["resolved_commit"] = commit

    added, updated, removed = diff_upstream(entry, upstream, entry["keep"])
    if not confirm(entry, added, updated, removed, args.yes):
        return 0
    if args.dry_run:
        print(f"    [dry-run] 跳过写入（{entry['name']}）")
        return 0

    write_upstream(entry, upstream, modes, entry["keep"])
    print(f"    [ok] 已同步 {len(upstream)} 个文件，上游 commit {commit[:12]}")
    return 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="把 skills/ 下登记的 Skill 同步成上游仓库的最新内容（丢弃本地修改）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("skills", nargs="*", help="要同步的 Skill 名（对应 skills/ 下的目录名）")
    parser.add_argument("--all", action="store_true", help="同步 sync_config.json 里所有 enabled 的 Skill")
    parser.add_argument("--list", action="store_true", help="列出已登记的 Skill 与同步状态")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help=f"配置文件路径（默认 {DEFAULT_CONFIG}）")
    parser.add_argument("--ref", help="覆盖配置里的 ref（分支 / tag / commit）")
    parser.add_argument("--dry-run", action="store_true", help="只预览差异，不写盘")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过交互确认")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    entries = [normalize_entry(name, raw) for name, raw in cfg["skills"].items()]
    if args.ref:
        for entry in entries:
            entry["ref"] = args.ref
    default_ref = cfg.get("defaults", {}).get("ref")
    if default_ref:
        for entry in entries:
            entry["ref"] = entry["ref"] or default_ref

    by_name = {e["name"]: e for e in entries}

    if args.list:
        print(f"配置文件: {Path(args.config).resolve()}\n")
        for entry in entries:
            state = "enabled" if entry["enabled"] else "disabled"
            exists = "本地已存在" if entry["local_dir"].is_dir() else "本地缺失"
            meta = entry["local_dir"] / METADATA_NAME
            last = ""
            if meta.is_file():
                try:
                    last = f" | 上次同步 {json.loads(meta.read_text(encoding='utf-8')).get('synced_at','?')}"
                except json.JSONDecodeError:
                    last = ""
            print(f"  {entry['name']:<24} {state:<9} {exists}{last}")
            print(f"      upstream: {entry['repo']} @ {entry['ref'] or '默认分支'} : {entry['subpath']}")
        return 0

    if args.all:
        selected = [e for e in entries if e["enabled"]]
    elif args.skills:
        unknown = [n for n in args.skills if n not in by_name]
        if unknown:
            raise SystemExit(f"[x] sync_config.json 里没有这些 Skill: {', '.join(unknown)}\n"
                             f"    已登记: {', '.join(by_name)}")
        selected = [by_name[n] for n in args.skills]
    else:
        parser.print_help()
        print("\n提示：用 --list 查看可同步的 Skill。")
        return 1

    if not selected:
        print("[!] 没有可同步的 Skill（可能全部 disabled）。")
        return 0

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    changed = 0
    for entry in selected:
        changed += sync_entry(entry, args, token)
    print(f"\n完成：{changed}/{len(selected)} 个 Skill 被更新。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
