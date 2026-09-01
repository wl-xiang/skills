# Common Pitfalls (repo-deploy-packager)

Recurring failure modes observed while deploying/packaging real repos
(excalidraw, hoppscotch, …). Read this when a phase fails unexpectedly.

## 1. `docker load` "The system cannot find the path specified" (Windows Git Bash)

**Symptom:** `docker load --input /d/desktop2/b/results/x/x_x64_docker-images.tgz`
fails with a Windows error 3, even though the file exists and `sha256sum` read it fine.

**Cause:** The Windows build of `docker.exe` does not understand Git Bash's
`/d/...` POSIX path style when passed via `--input`.

**Fix:** `cd` into the directory holding the archive and pass a **relative** path:
```bash
cd results/<repo> && docker load --input <repo>_<x64|arm>_docker-images.tgz
```
`scripts/verify.sh` already does this. `docker save` does not have this problem
because its output goes through a shell redirect, not a docker flag.

## 2. Front-end build aborts on PWA / Workbox precache size limit

**Symptom:** `vite build` / `vite-plugin-pwa` fails at `generateSW` with:
```
Error: Configure "workbox.maximumFileSizeToCacheInBytes" to change the limit:
       the default value is 2 MiB.
Assets exceeding the limit: ... is 2.68 MB, and won't be precached.
```
The JS/CSS/font assets themselves built fine — only the service-worker precache step died.

**Fix:** In the project's Vite/PWA config, raise `maximumFileSizeToCacheInBytes`
above the largest chunk (e.g. `6 * 1024 ** 2`). This is a build-config-only change;
record it and note it is reversible via `git checkout`.

## 3. Compose has no `image:` name → nothing to `pull`

**Symptom:** `docker compose pull` reports `Skipped - No image to be pulled`.

**Fix:** Skip pull and go straight to build: `docker compose up -d --build`.
The resulting image gets a generated name like `<dir>_<service>:latest`.

## 4. Multi-service apps need `.env` and/or `--profile`

**Symptom:** `docker compose up` errors because `env_file: ./.env` is missing, or only
some services start.

**Fix:**
- If `.env.example` exists, generate `.env` from it. For secret/encryption vars
  (e.g. `DATA_ENCRYPTION_KEY`), inject a freshly generated 32-char value:
  ```bash
  python - <<'PY'
  import secrets, pathlib
  ex = pathlib.Path('.env.example').read_text()
  key = secrets.token_hex(16)  # 32 hex chars
  pathlib.Path('.env').write_text(ex.replace('PLACEHOLDER', key))
  PY
  ```
- If the compose uses Compose **profiles** (e.g. hoppscotch `--profile default`),
  discover and confirm the profile with the user before deploying, and pass the same
  `--profile` flag to every `ps` / `down` / `images` command afterward.

## 5. Build log truncation hides the root cause

**Symptom:** Piping `docker compose build` through `| tail -N` buffers output, so on
failure only the tail (often just the stack trace) shows and the real error is lost.

**Fix:** Redirect full output to a log file instead:
`docker compose up -d --build > logs/<repo>_build.log 2>&1`,
then `grep -niE 'error|fail' logs/<repo>_build.log` to find the first root-cause line.

## 6. Migrating the compose directory after deployment

**Symptom:** After moving the cloned repo (e.g. from workspace root into `repos/`),
the running container's bind-mount path becomes stale.

**Fix:** If the image bakes built assets in at build time (e.g. nginx serving a static
`build/` folder), the service is unaffected. To make mount paths consistent again,
re-run `docker compose up -d` from the new location.
