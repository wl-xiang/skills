#!/usr/bin/env bash
# verify.sh <repo_name> [--arch <x64|arm>]
#
# Run FROM the workspace root. Performs Phase 4 restore/extract acceptance checks:
#   - [4-3] docker load the image archive (uses a RELATIVE path on purpose — see note)
#   - [4-4] extract source-code.tgz to a temp dir, count files, confirm no .git
#
# Designed to be called by the ship-repo-offline skill Phase 4. --arch must match
# the value passed to pack.sh (amd64/x86_64 -> x64, arm64/aarch64 -> arm).
set -euo pipefail

repo="${1:?usage: verify.sh <repo_name> [--arch <x64|arm>]}"
shift 1

arch=""
while [ $# -gt 0 ]; do
  case "$1" in
    --arch) arch="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

# Detect arch NOTE: x64 -> amd64/x86_64, arm -> arm64/aarch64.
detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64|x64|i686|i386) echo "x64" ;;
    aarch64|arm64|armv7*|armv8*|arm*) echo "arm" ;;
    *) echo "x64" ;;
  esac
}
[ -z "$arch" ] && arch="$(detect_arch)"

workspace_root="$(pwd)"
results_dir="$workspace_root/results/$repo"
img_tgz="$results_dir/${repo}_${arch}_docker-images.tgz"
src_tgz="$results_dir/${repo}_${arch}_source-code.tgz"

if [ ! -f "$img_tgz" ]; then echo "ERROR: missing $img_tgz" >&2; exit 1; fi
if [ ! -f "$src_tgz" ]; then echo "ERROR: missing $src_tgz" >&2; exit 1; fi

# ---- [4-3] docker load restore test ----
# GOTCHA: On Windows Git Bash, passing an absolute /d/... path to docker.exe fails with
# "The system cannot find the path specified". cd into the file's directory and use the
# relative filename to make `docker load` reliable.
echo "=== [4-3] docker load restore test (relative path) ==="
( cd "$results_dir" && docker load --input "${repo}_${arch}_docker-images.tgz" ) 2>&1 | tail -5

# ---- [4-4] source-code.tgz extract test ----
echo "=== [4-4] source-code.tgz extract test ==="
tmp="/tmp/${repo}_verify"
rm -rf "$tmp" && mkdir -p "$tmp"
tar -xzf "$src_tgz" -C "$tmp"
file_count="$(find "$tmp" -type f | wc -l | tr -d ' ')"
git_count="$(tar -tzf "$src_tgz" | grep -c '^\.git' || true)"
echo "extracted files : $file_count"
echo "contains .git?  : $git_count (0 = good)"
echo "top-level entries:"
ls -1 "$tmp" | head -10
echo "=== verify done ==="
