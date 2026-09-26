---
name: docker-images-tgz-action
description: This skill should be used when the user wants a GitHub Actions workflow (for ANY repository) that produces all Docker images for a target deployment platform (linux/amd64 or linux/arm64). Build mode builds one image from a Dockerfile path; Pull mode pulls every image-only service AND builds every build: service of a docker compose file (mixed pull+build), auto-naming unnamed builds as repo:latest with -1/-2 suffixes on collision. All resulting images are packed into ONE TGZ workflow artifact plus a separate SHA256 artifact, and the workflow renders a full Action Summary (configuration, image list with sizes, archive size, SHA256, offline restore guide). The skill inspects the target repo's context first, confirms configuration with the user, then renders the ready-to-commit workflow via a bundled generator script. Use it for any "create a GitHub Action to build/pull and package Docker images into a TGZ artifact" request.
agent_created: true
---

# Docker Images TGZ Action

Generate a GitHub Actions workflow for any repository that:

- targets a **deployment platform** (`linux/amd64` or `linux/arm64`),
- runs in **Build mode** (build one image from a Dockerfile path) or **Pull mode**
  (pull every `image:` service and build every `build:` service of a docker
  compose file — mixed pull+build),
- packs **ALL resulting images into a single TGZ** uploaded as a workflow
  artifact, with the SHA256 checksum as a **separate artifact**,
- and writes a full **Action Summary** (configuration, compose service classes,
  image list with sizes, archive size + SHA256, offline restore guide).

## When To Use

- The user asks to "create a GitHub Action / workflow" that builds or pulls
  Docker images for a target server platform and packages them as a TGZ
  artifact (typically for offline deployment to an intranet / air-gapped server).
- The user mentions: target platform `linux/amd64` / `linux/arm64`, build mode
  Build or Pull, Dockerfile path, docker-compose.yml, docker save, images TGZ
  artifact, or an Action Summary for the whole flow.
- The user points at ANY repository (local path or git URL) that needs this
  workflow generated based on its context.

## Naming & Artifact Rules (from confirmed requirements — MANDATORY)

- **Build mode** produces exactly one image: `<image_name>:<image_tag>`
  (defaults: repository name lowercased : `latest`; both overridable at every
  run via workflow inputs).
- **Pull mode** classifies compose services into three classes:
  1. **image-only** (has `image:`, no `build:`) → pulled as-is with
     `docker pull --platform <target>`.
  2. **build + declared `image:`** → built via `docker compose build`, kept
     under its declared image name.
  3. **build-only** (has `build:`, no usable image name) → built, then
     auto-named `<image_name>:<image_tag>`; on collision the suffix `-1`,
     `-2`, `-3`… is appended to the tag (`repo:latest-1`, `repo:latest-2`, …).
- **Artifacts** (two separate uploads, names sanitized `.`→`-` for artifact
  name rules):
  - `<repo>_<amd64|arm64>_docker-images.tgz` — ALL images of the run, one TGZ.
  - `<repo>_<amd64|arm64>_docker-images.tgz.sha256` — checksum file.
- The TGZ file name encodes the target arch token `amd64` / `arm64`.

## General Constraints

- Inspect the target repository **read-only**. The only write is the generated
  workflow file, and only after confirming an existing file may be replaced.
- Never push/commit to the target repo on the user's behalf unless asked.
- All configuration is baked in as workflow_dispatch input **defaults**, so the
  user can still override platform / mode / paths / image name / tag per run.
- Never guess a compose file's service structure — read it (Phase 1) and
  report what was detected before generating anything.

---

## Phase 0 — Locate the Target Repository

1. If the user gave a **local path**, work there directly.
2. If the user gave a **git URL**, clone it to a temp dir
   (`git clone --depth 1 <url>`) and use that as the working root.
3. `<repo_name>` = last path segment of the URL / directory name, stripped of
   `.git` (this drives artifact naming and the default image name).

## Phase 1 — Repository Context Detection (read-only)

Report ALL of the following before asking for configuration:

1. **Dockerfiles**: root `Dockerfile`, `Dockerfile.*`, `*.dockerfile`, and
   shallow subdirectories (1–2 levels). List every candidate with its path.
2. **Compose files**: `docker-compose.yml`, `docker-compose.yaml`,
   `compose.yml`, `compose.yaml` (root and 1–2 levels deep).
3. If a compose file exists, **read it** and classify its services:
   - image-only services (list names + images)
   - build services with a declared `image:` (names + images)
   - build-only services (names only — these will be auto-named; call out
     collisions in advance, e.g. "2 build-only services → `repo:latest` and
     `repo:latest-1`")
   - any compose **profiles**, required `.env` / env vars, and private registry
     image references (e.g. `ghcr.io/...`, registry ports) — these need extra
     setup (see `references/workflow-design.md` → Pitfalls).
4. Propose defaults based on findings: mode = `build` if a root Dockerfile
   exists, else `pull` if a compose file exists; corresponding path defaults;
   image name = `<repo_name>` lowercased; tag = `latest`.

## Phase 2 — Confirm Configuration (AskUserQuestion)

Ask (skip any item the user already specified):

1. **Platform**: `linux/amd64` or `linux/arm64`.
2. **Build mode**: `build` or `pull`.
3. **Path**: Dockerfile path (build mode, default `./Dockerfile`) or compose
   file path (pull mode, default `./docker-compose.yml`) — default to what
   Phase 1 actually found.
4. **Image name / tag**: defaults `<repo_name>` / `latest` (used for the
   build-mode image, and for auto-naming build-only services in pull mode).

Then state the resolved configuration in one short summary block and proceed.

## Phase 3 — Generate the Workflow

Run the bundled generator (use the installed skill's directory):

```bash
python3 <skill_dir>/scripts/generate_workflow.py \
  --repo-name    "<repo_name>" \
  --build-mode   <build|pull> \
  --platform     <linux/amd64|linux/arm64> \
  --dockerfile   "<path>" \        # build mode
  --compose-file "<path>" \        # pull mode
  --image-name   "<name>" \
  --image-tag    "<tag>" \
  --output       "<target_repo>/.github/workflows/docker-images.yml"
```

- The script refuses to overwrite an existing `docker-images.yml` unless
  `--force` is passed — ask the user first in that case.
- The script validates paths are repo-relative and prints the baked-in
  defaults when done.
- After generation, show the user the key parts of the rendered workflow
  (inputs with defaults, and the steps for the chosen mode).

## Phase 4 — Delivery Notes

Tell the user (concise, in Chinese or the user's language):

1. **Commit & push** the workflow file to the target repository.
2. Trigger: repo → **Actions** → **Docker Images TGZ** → **Run workflow**;
   every input is pre-filled with the baked-in defaults and can be changed
   per run.
3. Artifacts land in the run's **Artifacts** section:
   `<repo>_<arch>_docker-images.tgz` (+ `.sha256`); restore offline with
   `sha256sum -c <file>.sha256` then `docker load -i <file>.tgz`.
4. Call out anything detected in Phase 1 that needs extra care (private
   registry login step, compose `.env`, profiles) and point to
   `references/workflow-design.md` → Pitfalls for the fix.

---

## Bundled Resources

- `scripts/generate_workflow.py` — renders the complete workflow YAML from the
  confirmed configuration (workflow_dispatch inputs with defaults, QEMU/buildx
  setup for cross-arch, build/pull mode steps, naming rules, TGZ + SHA256
  packaging, dual artifact upload, Action Summary). Run via
  `python3 <skill_dir>/scripts/generate_workflow.py --help` for all options.
- `references/workflow-design.md` — how the generated workflow works
  internally: input table, cross-arch strategy (QEMU + buildx +
  `DOCKER_DEFAULT_PLATFORM`), the three pull-mode service classes and naming
  rules, artifact naming, summary sections, and pitfalls (private registries,
  compose `.env`, profiles, buildx `--load` single-platform limit).
