#!/usr/bin/env bash
# pack.sh <repo_name> <compose_project_dir> [--arch <x64|arm>] [--profile <name>]
#
# Run FROM the workspace root (the directory containing results/, repos/, logs/).
# Produces, under results/<repo_name>/:
#   <repo_name>_<x64|arm>_docker-images.tgz   (all compose images, gzip)
#   <repo_name>_<x64|arm>_source-code.tgz     (source, excludes .git and node_modules)
# and prints their sizes + sha256sum.
#
# Designed to be called by the ship-repo-offline skill Phase 3. Pass --arch from
# the target deployment architecture determined in Phase 0 (amd64/x86_64 -> x64,
# arm64/aarch64 -> arm). Defaults to the build machine's arch when omitted.
set -euo pipefail

repo="${1:?usage: pack.sh <repo_name> <compose_project_dir> [--arch <x64|arm>] [--profile <name>]}"
compose_dir="${2:?usage: pack.sh <repo_name> <compose_project_dir> [--arch <x64|arm>] [--profile <name>]}"
shift 2

arch=""
profile=""
while [ $# -gt 0 ]; do
  case "$1" in
    --arch) arch="${2:-}"; shift 2 ;;
    --profile) profile="${2:-}"; shift 2 ;;
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

# Resolve compose_project_dir to an absolute, script-friendly path.
compose_dir="$(cd "$compose_dir" && pwd)"
workspace_root="$(pwd)"

results_dir="$workspace_root/results/$repo"
log_dir="$workspace_root/logs"
mkdir -p "$results_dir" "$log_dir"

img_tgz="$results_dir/${repo}_${arch}_docker-images.tgz"
src_tgz="$results_dir/${repo}_${arch}_source-code.tgz"
profile_arg="${profile:+--profile $profile}"

echo "=== [3] packaging repo: $repo (arch=$arch) ==="
echo "compose dir : $compose_dir"
echo "results dir : $results_dir"

# ---- 3-A: save all compose images ----
echo "=== [3-A] docker compose images ==="
( cd "$compose_dir" && docker compose $profile_arg images ) || true

# Collect distinct repo:tag references from the compose images table.
mapfile -t image_list < <( (cd "$compose_dir" && docker compose $profile_arg images --format '{{.Repository}}:{{.Tag}}') | grep -vE '^:$' | grep -vE '^<none>' | sort -u )

if [ "${#image_list[@]}" -eq 0 ]; then
  echo "ERROR: no images resolved from 'docker compose images'. Check the compose/project dir." >&2
  exit 1
fi
echo "Images to save (${#image_list[@]}): ${image_list[*]}"

( cd "$compose_dir" && docker save "${image_list[@]}" | gzip > "$img_tgz" )
echo "Saved $img_tgz ($(du -h "$img_tgz" | cut -f1))"

# ---- 3-B: tar source (exclude .git; exclude node_modules when present) ----
echo "=== [3-B] tar source ==="
( cd "$compose_dir"
  if [ -d node_modules ]; then
    tar --exclude='.git' --exclude='node_modules' -czf "$src_tgz" .
  else
    tar --exclude='.git' -czf "$src_tgz" .
  fi
)
echo "Saved $src_tgz ($(du -h "$src_tgz" | cut -f1))"

# ---- checksums ----
echo "=== SHA256 ==="
sha256sum "$img_tgz" "$src_tgz"
echo "=== done ==="
