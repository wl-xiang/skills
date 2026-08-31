#!/usr/bin/env bash
# verify.sh <repo_name>
#
# Run FROM the workspace root. Performs Phase 4 restore/extract acceptance checks:
#   - [4-3] docker load the image archive (uses a RELATIVE path on purpose — see note)
#   - [4-4] extract source-code.tgz to a temp dir, count files, confirm no .git
#
# Designed to be called by the repo-deploy-packager skill Phase 4.
set -euo pipefail

repo="${1:?usage: verify.sh <repo_name>}"
workspace_root="$(pwd)"
results_dir="$workspace_root/results/$repo"
img_tgz="$results_dir/${repo}_docker-images.tgz"
src_tgz="$results_dir/${repo}_source-code.tgz"

if [ ! -f "$img_tgz" ]; then echo "ERROR: missing $img_tgz" >&2; exit 1; fi
if [ ! -f "$src_tgz" ]; then echo "ERROR: missing $src_tgz" >&2; exit 1; fi

# ---- [4-3] docker load restore test ----
# GOTCHA: On Windows Git Bash, passing an absolute /d/... path to docker.exe fails with
# "The system cannot find the path specified". cd into the file's directory and use the
# relative filename to make `docker load` reliable.
echo "=== [4-3] docker load restore test (relative path) ==="
( cd "$results_dir" && docker load --input "${repo}_docker-images.tgz" ) 2>&1 | tail -5

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
