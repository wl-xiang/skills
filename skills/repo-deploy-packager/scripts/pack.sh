#!/usr/bin/env bash
# pack.sh <repo_name> <compose_project_dir> [--profile <name>]
#
# Run FROM the workspace root (the directory containing results/, repos/, logs/).
# Produces, under results/<repo_name>/:
#   <repo_name>_docker-images.tgz   (all compose images, gzip)
#   <repo_name>_source-code.tgz     (source, excludes .git and node_modules)
# and prints their sizes + sha256sum.
#
# Designed to be called by the repo-deploy-packager skill Phase 3.
set -euo pipefail

repo="${1:?usage: pack.sh <repo_name> <compose_project_dir> [--profile <name>]}"
compose_dir="${2:?usage: pack.sh <repo_name> <compose_project_dir> [--profile <name>]}"
shift 2

profile=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) profile="${2:-}"; shift 2 ;;
    *) shift ;;
  esac
done

# Resolve compose_project_dir to an absolute, script-friendly path.
compose_dir="$(cd "$compose_dir" && pwd)"
workspace_root="$(pwd)"

results_dir="$workspace_root/results/$repo"
log_dir="$workspace_root/logs"
mkdir -p "$results_dir" "$log_dir"

img_tgz="$results_dir/${repo}_docker-images.tgz"
src_tgz="$results_dir/${repo}_source-code.tgz"
profile_arg="${profile:+--profile $profile}"

echo "=== [3] packaging repo: $repo ==="
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
