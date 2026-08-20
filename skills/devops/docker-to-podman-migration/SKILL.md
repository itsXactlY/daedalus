---
name: docker-to-podman-migration
description: Migrate Docker to Podman (CLI, Containerfile, compose, GPU/CDI, platform pinning).
---

# Docker → Podman Migration

Convert a Docker-based stack to Podman so it runs on the Podman OCI runtime
instead of the Docker daemon. Podman 6.x is a drop-in CLI for most cases, but
a handful of flags and image-format behaviors differ and will bite you.

## When this applies
- User wants a docker-compose / Dockerfile / `docker run` stack on Podman.
- User says "make this PODMAN", "kill DOCKER AIDS", "install the pod".
- Repo already has Dockerfiles + compose.yaml you must keep working under podman.

## Core steps

1. **Verify podman is installed** (`podman --version`). If absent, install it
   (`pacman -S podman` on Arch/Garuda). Podman is rootless by default and needs
   no daemon.
2. **Convert Dockerfiles → Containerfiles.** `cp Dockerfile Containerfile`.
   Podman reads `Containerfile` or `Dockerfile` automatically, but naming them
   `Containerfile` is the OCI convention and signals intent. Keep the old
   Dockerfile for backward compat if the repo builds elsewhere. Podman's
   buildah/`podman build` accepts the same Dockerfile syntax.
3. **Pin the platform explicitly.** This is the #1 trap (see Pitfalls).
   ```bash
   podman build --platform linux/amd64 -f Containerfile -t name:local .
   ```
   And/or in compose.yaml under the service's `build:`:
   ```yaml
   build:
     context: .
     dockerfile: Containerfile
     platforms: [linux/amd64]
   ```
4. **Swap the GPU flag.** Docker uses `--gpus all` / `--gpus device=N`.
   Podman exposes GPUs via CDI or device nodes: `--device nvidia.com/gpu`
   (CDI device; fails with "stat nvidia.com/gpu: no such file or directory"
   unless the NVIDIA Container Toolkit registers the CDI spec) OR pass the raw
   nodes explicitly:
   ```bash
   podman run --rm \
     --device /dev/nvidia0:/dev/nvidia0 \
     --device /dev/nvidiactl:/dev/nvidiactl \
     --device /dev/nvidia-modeset:/dev/nvidia-modeset \
     --device /dev/nvidia-uvm:/dev/nvidia-uvm \
     --device /dev/nvidia-uvm-tools:/dev/nvidia-uvm-tools \
     --device /dev/nvidia-caps:/dev/nvidia-caps \
     ...
   ```
   Confirm which the host supports: `ls /dev/nvidia*` and check CDI with
   `podman info | grep -i cdi`. If `nvidia-ctk` isn't configured, run
   `sudo nvidia-ctk runtime configure --runtime=podman` (Docker path uses
   `--runtime=docker`).
5. **Convert compose.** `podman compose up --build -d` delegates to the
   external `docker-compose` provider (noise line
   "Executing external compose provider ... docker-compose" is expected, not an
   error). Set `dockerfile: Containerfile` in the build block. `network_mode:
   host`, `volumes`, `environment`, `restart: unless-stopped` all work as-is.
   **GPU in compose:** a Docker-Swarm-style `deploy.resources.reservations.devices`
   block is SILENTLY IGNORED by podman-compose — the container starts but has no
   GPU. Replace it with the podman/CDI form:
   ```yaml
   services:
     app:
       devices:
         - nvidia.com/gpu
   ```
   (Note: `devices: [nvidia.com/gpu]` is the compose-spec CDI form. **In practice the
   external docker-compose provider often still fails even with CDI configured** — see the
   `=all` qualifier pitfall below. When it fails, deploy the GPU container via direct
   `podman run --device nvidia.com/gpu=all` instead of `podman compose up`.)
6. **Convert `docker` CLI calls in scripts/app code.** Replace `docker run/rm/
   pull/logs/image inspect` with `podman ...` AND swap `--gpus all` →
   `--device nvidia.com/gpu`. If app code may run under either, auto-detect:
   ```python
   runtime = "podman" if shutil.which("podman") else "docker"
   GPU_FLAG = "--device nvidia.com/gpu" if runtime == "podman" else "--gpus all"
   ```
7. **Convert a `kind: "docker"` discriminator in config/JSON.** If app config
   or recipe data tags components as `"kind": "docker"` vs `"process"`, replace
   with `"kind": "podman"` everywhere, INCLUDING the Python comparisons that
   branch on it (recipes.py / registry.py / backend.py / runtime scripts) and
   the test assertions. Miss one branch and the container path silently takes
   the process path or raises.
8. **Scope judgment — don't over-reach.** When a repo vendors a third-party
   subtree (e.g. `engine/llama-cpp-turboquant/` with its own docs), LEAVE its
   internal docs alone — they describe upstream's own Docker build; rewriting
   them is noise and misattributes the tooling. Similarly LEAVE `CHANGELOG.md`
   historical entries that record commands as they were actually run at the
   time — a changelog is a record, not current instructions. Convert only the
   current-command files: Dockerfiles/Containerfiles, compose, README "quick
   start"/build sections, and live operational docs (setup/persistence/run
   guides).
9. **Verify.** Build, run, then hit the health endpoint and confirm the runtime
   is actually the target (see `scripts/verify-podman-deploy.sh`).

## Pitfalls

- **PLATFORM PINNING (worst):** `podman build` WITHOUT `--platform` on an x86_64
  host pulled the arm64 variant of the base image (`python:3.12-slim`) when the
  manifest had no local arch, and produced a working-but-wrong image. Symptom:
  `WARNING: image platform (linux/arm64/v8) does not match the expected
  platform (linux/amd64)`. ALWAYS pass `--platform linux/amd64` (or `$(uname -m)`
  mapping) at build and/or set `build.platforms` in compose. Verify with
  `podman inspect name --format '{{.Architecture}} {{.Os}}'` → expect `amd64 linux`.
- **HEALTHCHECK ignored under OCI format.** `HEALTHCHECK ... will be ignored.
  Must use docker format`. A container with HEALTHCHECK shows `Up` but never
  `(healthy)` under podman unless built `--format docker`. Cosmetic for basic
  deploys but breaks anything that gates on `podman ps` healthy status.
- **`--device nvidia.com/gpu` fails if CDI not configured.** Errors
  "stat nvidia.com/gpu: no such file or directory". Configure the NVIDIA
  Container Toolkit for podman (`nvidia-ctk runtime configure --runtime=podman`)
  or fall back to explicit `/dev/nvidia*` node mounts.
- **CDI is configured yet `--device nvidia.com/gpu` STILL fails — use the `=all`
  qualifier (and prefer `podman run`, not compose).** Even with `/etc/cdi/nvidia.yaml`
  present and `podman info` listing `nvidia.com/gpu=all` (CDI registered), the
  bare form fails:
  - `podman run --device nvidia.com/gpu <img>` → `stat nvidia.com/gpu: no such file or directory`
  - compose `devices: [nvidia.com/gpu]` via the external docker-compose provider → same error
  The form that WORKED: `podman run --device nvidia.com/gpu=all <img>`. The
  `=all` qualifier maps to the registered CDI device name. If compose keeps
  failing, bypass it — deploy the GPU container with a direct `podman run
  --device nvidia.com/gpu=all -p ... <img>` (the compose file still documents
  the config; the run command is what actually boots it). Verify the GPU is
  actually in the container with `podman exec <name> nvidia-smi -L`.
- **`docker-compose` provider noise.** `podman compose` prints
  "Executing external compose provider" every invocation. Not an error; suppress
  only if you want to.
- **Duplicate image/pod accumulation.** Rebuilding the same tag repeatedly with
  `--platform` differences leaves stale images and multiple `pod_container` pods.
  Clean before rebuild: `podman compose down`, `podman rm -f <name>`,
  `podman rmi <image>`. Verify exactly one pod + one container afterward.
- **Rootless podman bind-mounts resolve the host file at container start.** Editing
  a host file that is bind-mounted into the container (`./state.json:/var/lib/...:ro`)
  does NOT propagate while the container runs — rootless podman snapshots the file
  when the container starts. After editing the mounted host file, you MUST recreate
  the container: `podman compose down && podman compose up -d`, then confirm with
  `podman exec <name> cat <mounted-path>` (reads the file the process actually sees,
  not the host copy). `podman inspect <name> --format '{{json .Mounts}}'` shows the
  mount exists but not whether the content is current — always check via `exec cat`.
- **A "control-plane" container that 503s "no active backend" is a proxy with no
  backend configured — not a podman problem.** The control plane forwards `/v1/*`
  to whatever its routing `state.json` points at; if that file is empty (`{}`) or
  absent, `/v1/models` still returns 200 (with a dummy id) but `/v1/completions`
  POST returns `503 {"type":"backend_unavailable"}`. Diagnose the partial-failure
  signal: 200 on models + 503 on completions = routing state empty, not the
  container. Point `state.json` at a real OpenAI-compatible backend
  (e.g. `"base_url": "http://127.0.0.1:11434"` for a local Ollama), recreate the
  pod (see bind-mount pitfall above), then verify a real completion. Note that
  Ollama `*:cloud` models require a paid subscription — use a local model
  (`qwen2.5:3b`) for an end-to-end proxy smoke test.
- **llama.cpp-derived engine builds fail offline on the embedded-UI download.**
  Building a self-contained image that compiles vendored llama.cpp from source
  (a `Containerfile.engine-src`-style build) fails at the `llama-server` link
  step when the build env has no network/npm: `UI: download dist.tar.gz from
  b0 failed` / `llama-ui-embed failed (1)` / `missing required asset(s):
  loading.html`. Root cause: `tools/ui/CMakeLists.txt` provisions the embedded
  web UI, and with `LLAMA_USE_PREBUILT_UI=ON` (DEFAULT) it tries to fetch
  `dist.tar.gz` from a HuggingFace bucket; offline that fails, then the
  fallback `emit_files` runs `llama-ui-embed`, which errors on the missing
  assets — and the server target links `llama-ui` unconditionally, so the whole
  `llama-server` build dies. FIX: disable BOTH cmake flags on the `cmake -B
  build` invocation:
  ```bash
  -DLLAMA_BUILD_UI=OFF \
  -DLLAMA_USE_PREBUILT_UI=OFF \
  ```
  With both OFF, nothing is downloaded/extracted, `DIST_DIR` stays empty, embed
  produces an empty UI, and the compile proceeds. Do this when the manager has
  its OWN committed frontend (`src/frontend/dist`) and talks to llama-server
  only via API — the embedded UI is redundant. Apply to every llama.cpp-derived
  Containerfile (engine-src, cuda-multi, prism-bonsai) that compiles from source.

## Verification
Run `scripts/verify-podman-deploy.sh <compose_dir> <service_name> <port>` to
assert: compose.yaml parses, platform pinned, image arch is amd64, exactly one
container, health endpoint 200.

**Repo test runners can be script-style, not pytest-style.** Some repos declare
their tests as standalone scripts (`tests/test_x.py` with a docstring
`Run: PYTHONPATH=src python3 tests/test_x.py`) that call `sys.exit()` at import
and `print("ALL PASS")`. Running them via `pytest` crashes the collector with
`INTERNALERROR ... SystemExit` — a HARNESS mismatch, not a test failure and not
your regression. Run them the way the repo intends:
```bash
for t in tests/test_*.py; do PYTHONPATH=src python3 "$t"; done
```
Also, `podman build` has NO `--dry-run`/`--check` flag (up to 6.x) — a
syntax-only check isn't available. To validate a Containerfile actually builds
without a heavy/expensive stage, run `podman build` on the LIGHTEST variant
(e.g. the slim python/node one, not the CUDA-engine build) and treat "reached
a pre-existing source compile error" as proof the Containerfile itself is valid
(compare `git diff` on the failing source file to confirm it's not your edit).
