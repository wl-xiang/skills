---
name: repo-deploy-packager
description: This skill should be used when the user wants to deploy a GitHub/Git repository via Docker Compose and package the deployment into offline-restoreable TGZ archives (Docker image(s) plus source code) with SHA256 checksums. It encodes a strict 5-phase SOP (environment/arch detection then clone then compose deploy then pack then acceptance), enforces fixed workspace conventions (repos/, results/repo_name/, logs/ with repo_name_ prefixed files), and prompts for cleanup after packaging. Use it for any "deploy and package a repo URL" request.
agent_created: true
---

# Repo Deploy & Packager

Deploy any Git repository via Docker Compose, then package the result (built image(s)
plus source code) into verifiable TGZ archives following a fixed workspace layout.

## When To Use

- The user asks to "deploy and package" a project and provides a GitHub/Git URL (or asks
  you to deploy a repo and produce offline-restoreable artifacts).
- The task implies a runnable container plus `<repo_name>_<x64|arm>_docker-images.tgz` /
  `<repo_name>_<x64|arm>_source-code.tgz` with
  recorded SHA256 checksums, organized under a fixed folder structure.
- A strict, phase-by-phase workflow with a confirmation gate between phases is expected.

## Workspace Conventions (MANDATORY)

Apply these for every project processed by this skill:

- `repos/<repo_name>/` — target directory for `git clone`.
- `results/<repo_name>/` — output directory for packaged TGZs.
- `logs/` — every log file (build, save, tar, verify) goes here.
- File naming: **all** logs and result files use the `<repo_name>_` prefix, and result
  TGZs additionally encode the **target architecture** as `<x64|arm>`:
  - Logs: `logs/<repo_name>_build.log`, `logs/<repo_name>_save.log`, `logs/<repo_name>_tar.log`, etc.
  - Results: `results/<repo_name>/<repo_name>_<x64|arm>_docker-images.tgz`,
    `results/<repo_name>/<repo_name>_<x64|arm>_source-code.tgz`.
- Architecture token map (from Phase 0): `amd64`/`x86_64` → `x64`;
  `arm64`/`aarch64` → `arm`. Every TGZ carries the target-arch token
  (`<repo_name>_<x64|arm>_<docker-images|source-code>.tgz`).
- Derive `<repo_name>` from the repo URL's last path segment, stripped of `.git`
  (e.g. `https://github.com/excalidraw/excalidraw.git` → `excalidraw`).

## General Constraints

- State intent before every command. For destructive operations (`rm`, `prune`, `down -v`,
  image removal) obtain explicit confirmation first.
- On build/deploy errors: print the full error log → diagnose root cause → propose a fix →
  apply only after the user confirms.
- **Pause and ask for confirmation at the end of every phase** before proceeding to the next.
- If the project has special dependencies (`.env`, database init, secret keys), proactively
  ask the user to provide or approve auto-generation before deploying.

---

## Phase 0 — Environment Detection & Arch Alignment

1. Detect the **build machine**: `uname -m`, `uname -srv`, and
   `docker info --format '{{.Architecture}} | {{.OSType}}'`.
2. Ask the user for the **target deployment server** CPU architecture + OS
   (use AskUserQuestion; offer `amd64/x86_64`, `arm64/aarch64`, `other/unsure`).
3. If build machine and target **differ** (e.g. amd64 → arm64):
   - Register QEMU: `docker run --rm --privileged multiarch/qemu-user-static --reset -p yes`
   - Create builder: `docker buildx create --name multiarch --driver docker-container --use`
   - Verify: `docker buildx inspect --bootstrap`
4. If they **match**, skip QEMU/buildx and use the default builder.

## Phase 0 (optional) — Docker Mirror Acceleration (China / slow pulls)

When the build machine is in a region where Docker Hub pulls are slow or fail (e.g.
mainland China), **offer** the user Docker Hub mirror acceleration BEFORE Phase 2, so
images like `node:24`, `nginx:*-alpine`, `postgres:15` download fast.

- This step is **optional** and **must NOT be executed automatically** — the one-click
  method uses `sudo` and rewrites the host Docker daemon config.
- Present `scripts/setup-docker-mirror.sh` to the user and let them run it manually, or
  show the one-liner from `references/docker-mirror.md`.
- For the full mirror list, the manual `daemon.json` method, and verification, read
  `references/docker-mirror.md` (background: Tencent Cloud article
  https://cloud.tencent.com.cn/developer/article/2528445).
- Never run `sudo`/root commands on the user's behalf without explicit confirmation.

## Phase 1 — Clone

1. `git clone <URL> repos/<repo_name>` (run in background; report the task id and wait for it).
2. Inspect the clone root for compose files: `docker-compose.yml`, `docker-compose.yaml`,
   `compose.yml`, `compose.yaml`.
3. If no official compose file exists:
   - If a `Dockerfile` exists, author a minimal `docker-compose.yml` (map a host port to the
     container's service port, build from the Dockerfile).
   - If neither compose nor Dockerfile exists, **pause and ask the user for instructions**.
4. Report what was found (compose present? Dockerfile present? single vs multi-service?).

## Phase 2 — Docker Compose Deploy

Use the priority order below:

1. **Pull first** if the compose declares a prebuilt `image:` name:
   `docker compose [--profile <p>] pull` then `docker compose [--profile <p>] up -d`.
2. **Otherwise build**: `docker compose [--profile <p>] up -d --build`
   (run in background; redirect full output to `logs/<repo_name>_build.log`).
3. Wait until all containers reach `running` / `healthy`.
4. Health check: `docker compose [--profile <p>] ps` and `curl` the exposed port(s);
   confirm the served page title to avoid trusting a 200 error page.
5. Report container list, port mappings, and access URLs.

Multi-service / profile notes: if the compose uses Compose **profiles** (e.g. hoppscotch
`--profile default` = aio + postgres + migrate), discover and confirm the profile with the
user. If an `.env` is required, generate it from `.env.example`, filling secret vars
(e.g. `DATA_ENCRYPTION_KEY`) with a randomly generated 32-char value; keep other defaults.

## Phase 3 — Package Artifacts

Run `scripts/pack.sh <repo_name> <compose_project_dir> [--arch <x64|arm>] [--profile <p>]` from the workspace root.
The script:

- **3-A** lists `docker compose images`, then `docker save <images...> | gzip >
  results/<repo_name>/<repo_name>_<x64|arm>_docker-images.tgz` (include base images such as
  `postgres:15` so the archive is self-restorable offline).
- **3-B** tars the source (exclude `.git`; also exclude `node_modules` when present) to
  `results/<repo_name>/<repo_name>_<x64|arm>_source-code.tgz`.
- Prints file sizes and `sha256sum` for both archives.

Pass `--arch <x64|arm>` from the **target** architecture chosen in Phase 0 (if omitted,
the script falls back to the build machine's arch via `uname -m`). Name → token:
`amd64`/`x86_64` → `x64`; `arm64`/`aarch64` → `arm`.

If buildx multi-arch was used, inspect the target platform with
`docker buildx imagetools inspect <image>` before exporting.

## Phase 4 — Acceptance & Cleanup Prompt

Verify each item (use `scripts/verify.sh <repo_name> --arch <x64|arm>` — match the same
arch passed to pack.sh — for the restore/extract checks):

| # | Check | Method |
|---|-------|--------|
| 1 | Containers `docker compose ps` healthy | `docker compose ps` |
| 2 | Service port reachable / health passes | `curl` the port(s) |
| 3 | `<repo_name>_<arch>_docker-images.tgz` loadable & restoreable | `docker load` (relative path!) |
| 4 | `<repo_name>_<arch>_source-code.tgz` extractable, complete | `tar -xzf` to temp, count files, ensure no `.git` |
| 5 | SHA256 of both TGZs recorded | from Phase 3 output |

After **all ✅**, ask the user (AskUserQuestion, multi-select) whether to:

- **Down** the compose service for this project (`docker compose [--profile <p>] down`,
  keeps volumes by default)?
- **Remove** the Docker images built for this project?
- **Remove** the logs generated while processing this project?

Do not auto-execute any of these; they are destructive. Default to offering them, then act
only on explicit confirmation.

---

## Bundled Resources

- `scripts/pack.sh` — Phase 3 packaging (save images + tar source + sha256; names files
  `<repo_name>_<x64|arm>_docker-images.tgz` / `..._source-code.tgz`). Run from the
  workspace root: `bash skills/repo-deploy-packager/scripts/pack.sh <repo> <compose_dir> [--arch <x64|arm>] [--profile <p>]`.
- `scripts/verify.sh` — Phase 4 restore/extract verification. Run from the workspace root:
  `bash skills/repo-deploy-packager/scripts/verify.sh <repo> [--arch <x64|arm>]`.
- `scripts/setup-docker-mirror.sh` — **Manual-only** Docker Hub mirror acceleration for
  China / slow pulls. Presents the one-click `linuxmirrors.cn` config; never auto-run
  (uses `sudo`). See `references/docker-mirror.md`.
- `references/common-pitfalls.md` — Recurring failure modes and fixes encountered across
  deployments (PWA/Workbox precache limit, `docker load` path quirk on Windows Git Bash,
  compose-without-image-name, multi-service `.env`/profile requirements).
- `references/docker-mirror.md` — Docker Hub mirror acceleration: one-click script, manual
  `daemon.json` method, current mirror list, and verification.
