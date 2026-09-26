# Workflow Design — `docker-images-tgz-action`

Internals of the generated GitHub Actions workflow, decision rationale, and
known pitfalls. Read this when the generated workflow needs to be explained,
debugged, or hand-adjusted.

## Inputs (workflow_dispatch)

| Input | Type | Default (baked by the generator) | Used by |
|---|---|---|---|
| `platform` | choice `linux/amd64` / `linux/arm64` | user-confirmed | both modes |
| `build_mode` | choice `build` / `pull` | user-confirmed | selects the step branch |
| `dockerfile` | string | e.g. `Dockerfile` | build mode |
| `compose_file` | string | e.g. `docker-compose.yml` | pull mode |
| `compose_profiles` | string (space-separated) | `""` | pull mode |
| `image_name` | string | repo name, lowercased | naming of built/unnamed images |
| `image_tag` | string | `latest` | naming of built/unnamed images |

All inputs stay editable in the **Run workflow** dialog, so one workflow can
serve both modes and both platforms without editing YAML.

## Cross-architecture strategy

Runner `ubuntu-latest` is amd64.

- **Build mode**: `docker buildx build --platform <target> --load`. QEMU is
  registered when `platform == linux/arm64` (`docker/setup-qemu-action`).
  `--load` exports a single-platform image — that is exactly what we want
  (one platform per run; run twice for both platforms).
- **Pull mode, image-only services**: `docker pull --platform <target> <img>`.
  Pulling a foreign-arch image needs no QEMU (no execution happens).
  `docker compose pull` cannot pin a platform reliably, hence the per-image
  loop over `docker compose config --images`-equivalent JSON.
- **Pull mode, build services**: `DOCKER_DEFAULT_PLATFORM=<target>
  docker compose build` (+ QEMU for arm64). Classic builder + binfmt handles
  the cross-arch build.

## Pull mode — the three service classes

`docker compose config --format json` resolves the compose model; the workflow
uses `jq` on it (`PROJECT = .name`, services under `.services`).

1. **image-only** (`build == null`): image name from `.services[$s].image`,
   pulled per image with `--platform`, saved under its own name.
2. **build + declared image**: `docker compose build` tags it with the declared
   `image:`; kept under that name.
3. **build-only** (no declared name): compose names the built image
   `<project>-<service>`. The workflow re-tags it:
   first → `<image_name>:<image_tag>`, then `<image_name>:<image_tag>-1`,
   `-2`, … on collision (user-confirmed rule).

**Why the jq guard `image == null or image == "$project-$service"`**: some
compose versions inject the generated image name into `config` output for
build-only services, others leave it absent. The guard treats BOTH forms as
"unnamed" so the auto-fill rule applies consistently.

`.env` handling: if a `.env` sits next to the compose file, the workflow adds
`--env-file <dir>/.env` (compose only auto-reads `.env` from the working
directory, which is the repo root, not the compose file's directory).

Profiles: `compose_profiles` input adds `--profile <p>` args to every
`docker compose` call, including `config` (so service discovery and
build/pull see the same active service set).

## Artifacts

- File: `<repo>_<amd64|arm64>_docker-images.tgz` = `docker save <all images> | gzip`.
  Integrity is smoke-checked with `gzip -t`.
- `<repo>_<arch>_docker-images.tgz.sha256` = `sha256sum` of the TGZ.
- Two **separate** `actions/upload-artifact@v4` uploads (user-confirmed).
- Artifact *names* replace `.`→`-` (v4 forbids dots), e.g. repo `user.app` →
  artifact `user-app_amd64_docker-images` / `...-sha256`, while the file
  inside keeps the original repo name.

## Action Summary sections (in order)

1. **Configuration** — mode, platform, path, image name/tag (validated step).
2. **Compose services** (pull mode) — three service classes as a table.
3. **Packaging result** — archive name, size, SHA256, image count; per-image
   size table (`docker image inspect` + `numfmt`).
4. **Artifacts & restore guide** — what to download, then
   `sha256sum -c` → `docker load -i` → `docker images`.

## Pitfalls & fixes

- **Private registry images** (`ghcr.io/…`, internal registries): pulls/builds
  fail with `denied`. Fix: insert
  `docker/login-action@v3` (with `secrets.REGISTRY_*`) before the build/pull
  step. The generator does not add this automatically.
- **Compose requires env vars** that are undefined in CI: `docker compose
  config` fails. Fix: commit a CI-safe `.env` next to the compose file, or
  add `env:` entries to the pull step.
- **Inactive compose profiles**: a service under a non-default profile is
  invisible unless the profile is enabled — pass it via the
  `compose_profiles` input (space-separated).
- **buildx `--load` is single-platform**: never try to build both platforms in
  one run; run the workflow twice instead.
- **Cross-arch `docker compose build` fails** for exotic base images without
  arm64 binaries: add `platform: linux/arm64` to that service in the compose
  file, or build it in Build mode separately.
- **Huge TGZ**: images pile up layer-wise; the summary's per-image size table
  shows the offenders. Multi-arch is not saved — exactly one platform per run.
- **`timeout-minutes: 120`**: big builds (QEMU-emulated arm64 builds are ~5-10×
  slower) may need a bump.

## Regenerating / editing

The file header states it was generated by this skill. Hand edits are fine;
to regenerate deterministically, re-run
`scripts/generate_workflow.py` with the same arguments (+ `--force` to
overwrite). All repo-specific values live in the `default:` fields of the
inputs — everything else is generic.
