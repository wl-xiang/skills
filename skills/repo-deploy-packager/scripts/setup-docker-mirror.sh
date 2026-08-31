#!/usr/bin/env bash
# setup-docker-mirror.sh
#
# ⚠️  IMPORTANT — DO NOT AUTO-RUN THIS SCRIPT ON THE USER'S BEHALF.
# This script downloads and executes a third-party config script with `sudo`, which
# modifies the host's Docker daemon (registry mirrors, possibly Docker itself). It must
# be run MANUALLY by the user, or shown to them as a one-liner, after they explicitly
# confirm. The agent should only present this file / command; never execute it silently.
#
# Purpose: configure Docker Hub mirror acceleration for faster / more reliable pulls
# from mainland China (or any region where Docker Hub is throttled).
#
# Source / background: https://cloud.tencent.com.cn/developer/article/2528445
# Upstream config script: https://linuxmirrors.cn/docker.sh
#
# What it does:
#   1. Pull the linuxmirrors.cn docker config helper into /tmp/docker.sh
#   2. Run it with sudo to set Tencent docker-ce mirror + 1ms.run registry mirror,
#      over https, without touching the firewall, skipping backup tips.
#
# Verify after running (as the user, manually):
#   docker pull docker.1ms.run/library/mysql

set -euo pipefail

# 1) Pull the config script
curl -fsSL --connect-timeout 10 --retry 3 \
  https://linuxmirrors.cn/docker.sh -o /tmp/docker.sh

# 2) Execute with sudo (requires user confirmation; needs root)
sudo bash /tmp/docker.sh \
  --source mirrors.tencent.com/docker-ce \
  --source-registry docker.1ms.run \
  --protocol https \
  --install-latested true \
  --close-firewall false \
  --ignore-backup-tips

echo "Done. Restart Docker if the script did not, then verify with:"
echo "  docker pull docker.1ms.run/library/mysql"
