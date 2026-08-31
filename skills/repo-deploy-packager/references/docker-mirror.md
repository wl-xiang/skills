# Docker 国内镜像源加速（China / slow pulls）

Summary compiled from the Tencent Cloud article
"Docker国内镜像源加速列表" — https://cloud.tencent.com.cn/developer/article/2528445
(article updated 2025-07-24; mirror availability changes over time — re-check the source
if a mirror stops working).

Use this when the build machine is in a region where pulling from Docker Hub is slow or
fails (e.g. mainland China). Configure it BEFORE Phase 2 (pulls/builds) so images like
`node:24`, `nginx:stable-alpine-slim`, `postgres:15` download quickly.

> ⚠️ The one-click method uses `sudo` and modifies the host's Docker daemon. The agent
> must NOT run it automatically — present it to the user and let them execute it
> (e.g. `bash skills/repo-deploy-packager/scripts/setup-docker-mirror.sh`).

## Method A — One-click config script (recommended, simplest)

The `scripts/setup-docker-mirror.sh` runs exactly this:

```bash
# pull the helper
curl -fsSL --connect-timeout 10 --retry 3 \
  https://linuxmirrors.cn/docker.sh -o /tmp/docker.sh

# execute with sudo (user-confirmed)
sudo bash /tmp/docker.sh \
  --source mirrors.tencent.com/docker-ce \
  --source-registry docker.1ms.run \
  --protocol https \
  --install-latested true \
  --close-firewall false \
  --ignore-backup-tips
```

It sets the Tencent docker-ce mirror + the `docker.1ms.run` registry mirror over HTTPS,
without changing firewall rules and without prompting for backup tips.

## Method B — Manual `daemon.json` (no third-party script)

Pick one or more mirror URLs, write `/etc/docker/daemon.json`, then reload/restart Docker:

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<'EOF'
{
    "registry-mirrors": [
        "https://docker.1ms.run",
        "https://mirror.ccs.tencentyun.com",
        "https://docker.m.daocloud.io"
    ]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```

Adjust the URL list to whatever is currently reachable.

## Currently-listed mirror sources (as of article date)

| Address | Operator | Notes |
|---------|----------|-------|
| `https://docker.1ms.run` | 毫秒镜像 (1ms) | Free, fast, stable; confirmed available. Good default. |
| `https://mirror.ccs.tencentyun.com` | Tencent Cloud | Recommend only on Tencent Cloud servers (intra-region CDN). |
| `https://docker.m.daocloud.io` | DaoCloud | Forwarded; whitelist + rate limit. |
| `https://docker.1panel.live` | 1Panel | Cloudflare; some regions unreachable. |
| `https://hub.rat.dev` | 耗子面板 | Uses 1ms mirror; some regions unreachable. |
| `https://docker.anye.in` | Anye (1Panel) | Cloudflare; some regions unreachable. |

Mirror availability drifts — `docker.1ms.run` and the Tencent mirror are the most reliable
at time of writing. Re-verify from the article before relying on others.

## Verify acceleration works

```bash
docker pull docker.1ms.run/library/mysql
```

A successful pull through the mirror (or a faster `docker pull` of any image afterwards)
confirms the registry mirror is active.

## Notes

- Mirrors accelerate Docker Hub pulls only; they do not replace building local images.
- After enabling, `docker compose pull` / `docker pull` in Phase 2 will be much faster.
- If a mirror later 403/times out, remove it from `registry-mirrors` and restart Docker.
