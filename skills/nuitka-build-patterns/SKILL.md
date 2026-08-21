---
name: nuitka-build-patterns
category: devops
description: Build, debug, and deploy Nuitka --onefile / --module compiled Python binaries across the mazemaker stack — host binaries, container images, Quadlet Exec paths, registry push.
---

# Nuitka Build Patterns — Mazemaker Closed-Source Pipeline

When to load: any task involving Nuitka compilation of mazemaker Python code,
build-host-binaries.sh, Containerfile.nuitka modifications, Quadlet Exec path
fixes after compilation, or registry push/size issues.

## Architecture Overview

```
Python source (.py)
  → sync-engine.sh (for container builds) or direct path
  → Nuitka compile (--onefile for host binaries, --module for container)
    → .so / binary
      → Containerfile.nuitka (multi-stage, .so only) OR host-binaries dir
        → registry.mazemaker.dev push (via localhost:5000, NOT CF tunnel)
          → install.sh / Quadlet pulls on customer machines
```

Three compilation targets exist:

| Target | Build Tool | Output | Deployment |
|--------|-----------|--------|------------|
| Host binaries | `bin/build-host-binaries.sh` | `--onefile` ELF in `dist/host-binaries/` | Copied via install.sh to `~/.local/bin/` |
| Container images (CPU) | `Containerfile.nuitka` | `.so` modules in python:3.12-slim | Registry push → Quadlet pull |
| Container images (GPU) | `Containerfile.gpu.nuitka` | `.so` modules on pytorch/pytorch:cuda base | Registry push → Quadlet pull |
| Legacy GPU (pre-fix) | `Containerfile.gpu` | Raw `.py` on pytorch/pytorch base — **avoid** | Was pushed accidentally; lacks Nuitka obfuscation |

## Common Pitfalls

### 1. Missing pip dependencies in builder

The builder container (python:3.12-slim) has a minimal pip install. If the
source code imports a package at module level (not inside a try/except),
Nuitka compiles it into the binary — but the package must be PIP-INSTALLED
in the builder stage, not just present at runtime.

**Symptom:** `ImportError` or `RuntimeError("PyYAML not installed")` at
runtime, even though the .so file exists.

**Fix:** Add the missing package to the pip install line in the build script.
For `build-host-binaries.sh` this is the line:
```bash
pip install --no-cache-dir nuitka==2.5.4 setuptools wheel ordered-set \
    httpx tomli requests pyyaml > /dev/null
```
For `Containerfile.nuitka` it's in the Stage 1 `requirements.txt`.

**Detection:** Run the compiled binary with `--help` or a smoke test. If it
crashes with a missing module error, the pip install line was too narrow.

### 2. File path changes after compilation

Nuitka --module compiles `foo.py` → `foo.cpython-311-x86_64-linux-gnu.so`.
The .so lands at the **same directory** the .py was in during compilation,
NOT necessarily at the path the Quadlet Exec line referenced.

**Symptom:** `can't open file '/app/core/dream_worker.py': No such file or
directory` in container logs, followed by restart loop (restart counter
climbs into the hundreds).

**Root cause:** The old Quadlet had `Exec=python -u /app/core/dream_worker.py`.
After Nuitka, the file is `/app/dream_worker.cpython-311-*.so` (different
directory AND extension).

**Fix:** Change Exec to use `python3 -c` with module import:
```ini
Exec=python3 -c "import sys; sys.path.insert(0, '/app'); sys.argv = ['dream_worker','--arg1','val1']; import dream_worker; dream_worker.main()"
```

The key: `sys.path.insert(0, '/app')` and `sys.argv = [...]` to pass CLI args
before importing the module (argparse reads from sys.argv at import time).

### 3. Quadlet AddDevice=nvidia on non-GPU machines

The Quadlet template includes `AddDevice=nvidia.com/gpu=all`. On machines
without NVIDIA GPUs, this causes immediate container start failure.

**Symptom:** `unresolvable CDI devices nvidia.com/gpu=all`

**Fix (permanent):** install.sh should sed-strip the line on no-GPU hosts:
```bash
nvidia-smi &>/dev/null || sed -i '/AddDevice=nvidia/d' ~/.config/containers/systemd/*.container
```

**Fix (manual):** `sed -i '/AddDevice=nvidia/d' ~/.config/containers/systemd/mazemaker-dream-worker.container`

### 4. Registry push through CF tunnel (413 Payload Too Large / 502 Bad Gateway)

The `registry.mazemaker.dev` endpoint routes through a Cloudflare tunnel
(separate from the API tunnel — this one uses a local config.yml, not
TUNNEL_TOKEN). CF enforces a ~100MB upload limit on the tunnel. GPU images
based on pytorch/pytorch are several GB — each uncompressed layer is ~5.6GB,
which times out even with bumped tunnel timeouts (connectTimeout 300s,
proxyTimeout 600s), returning 413 or 502.

**Fix:** The registry container also listens on `localhost:5000`. Push to
localhost (no tunnel, no size limit), and the same content is served at
`registry.mazemaker.dev` via the tunnel for pull operations:

```bash
# On desk: build + save + scp
podman build -t registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu \
  -f client/pod/mazemaker/Containerfile.gpu.nuitka \
  client/pod/mazemaker/
podman save registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu -o /tmp/mcp-gpu.tar
scp /tmp/mcp-gpu.tar mazemaker-prod:/tmp/mcp-gpu.tar

# On prod: load, retag if needed, push to localhost:5000 (NOT registry.mazemaker.dev)
ssh mazemaker-prod 'su - mazemaker -c "
  podman load -i /tmp/mcp-gpu.tar && \
  podman push --tls-verify=false localhost:5000/mazemaker-mcp:1.0.0-rc1-gpu && \
  rm -f /tmp/mcp-gpu.tar
"'
```

The `--tls-verify=false` is needed because the registry uses a self-signed
cert (registry:2 default). The push to `localhost:5000` avoids the Cloudflare
tunnel entirely — the registry container is on the same machine.

**Tunnel config** (Hetzner, separate from the API tunnel):
```
File: /home/mazemaker/mazemaker-registry-pod/cloudflared/config.yml
Key values: connectTimeout: 300s, proxyTimeout: 600s, keepAliveTimeout: 120s
Managed via: Cloudflare Zero Trust dashboard (separate tunnel from API)
```

If you need to bump tunnel timeouts (e.g. for extreme large layers):
```bash
ssh mazemaker-prod 'su - mazemaker -c "
  sed -i \"s/connectTimeout:.*/connectTimeout: 300s/\" ~/mazemaker-registry-pod/cloudflared/config.yml
  sed -i \"s/proxyTimeout:.*/proxyTimeout: 600s/\" ~/mazemaker-registry-pod/cloudflared/config.yml
  systemctl --user restart mazemaker-registry-cloudflared.service
"'
```

### 5. PUBLISH GATE blocking intentional .py files

The `install-backend.sh` PUBLISH GATE blocks ALL `.py` files from shipping.
Hermes plugins (`.py` files that install to `~/.hermes/plugins/`) are
intentional exceptions.

**Fix:** Add rsync include rules BEFORE the *.py exclude:
```bash
RSYNC_EXCLUDES+=(--include='*/' --include='__init__.py' --exclude='*.py' ...)
```

And exempt the plugin path from the PUBLISH GATE find command:
```bash
BAD_FILES=$(find "$SRC_TMP" \
  \( -name '*.py' ... \) \
  -not -path '*/client/hermes-plugins/*' \
  -print ...)
```

### 6. Busy binary on install (running service blocks cp)

When install.sh runs `cp new-binary ~/.local/bin/mazemaker-hermes-bridge`,
it fails if the bridge service is running (the inode is mapped into the
running process on some filesystems).

**Fix:** Stop the service + rm -f before cp:
```bash
systemctl --user stop mazemaker-hermes-bridge.service 2>/dev/null || true
rm -f "$HOME/.local/bin/mazemaker-hermes-bridge"
cp "$SOURCE" "$HOME/.local/bin/mazemaker-hermes-bridge"
```

### 7. build-all-locked.sh missing GPU variant

The `build-all-locked.sh` script has a `SERVICES[]` array where each entry
lists the service name, source dir, Containerfile, and optional GPU extra-tag.
If the GPU variant is missing from this array, only the CPU image gets built.

**Symptom:** `registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu` exists but
was built from `Containerfile.gpu` (raw .py) instead of
`Containerfile.gpu.nuitka` (compiled .so). Or worse — the :gpu tag doesn't
exist at all.

**Fix per service entry:**
```bash
SERVICES=(
  "engine|client/pod/mazemaker|Containerfile.nuitka|Containerfile.gpu.nuitka:gpu"
  "embedding-worker|client/pod/embedding-worker|Containerfile.nuitka|Containerfile.gpu.nuitka:gpu"
)
```

The format is `Containerfile.variant:suffix` where:
- `Containerfile.gpu.nuitka` = the Nuitka GPU build file
- `gpu` = the tag suffix (`:TAG-gpu`)

**Check:** Verify both variants exist after build:
```bash
podman images registry.mazemaker.dev/mazemaker-$NAME:$TAG          # CPU
podman images registry.mazemaker.dev/mazemaker-$NAME:$TAG-gpu       # GPU
```

### 8. GPU VRAM grows unbounded in long-running daemons

Continuous PyTorch daemons (dream worker, embedding worker) accumulate CUDA
caching-allocator blocks across iterations. Different tensor sizes per cycle →
fragmented cache → VRAM grows over hours/days → eventual OOM even though no
individual tensor leaks. `nvidia-smi` shows high usage but
`torch.cuda.memory_allocated()` reports near zero — the allocator holds freed
blocks in reserve, not as live tensors.

**Fix in source code:** Add `torch.cuda.empty_cache()` after each work cycle
in the long-running loop:
```python
import gc, torch
gc.collect()
before = torch.cuda.memory_reserved()
torch.cuda.empty_cache()
after = torch.cuda.memory_reserved()
if after < before:
    logger.debug("freed %d MB GPU cache", (before - after) // (1024*1024))
```

**Emergency band-aid (when container can't be rebuilt):**
```bash
# cron every 5 min, no_agent=True, silent unless memory freed
podman exec <container> python3 -c "import torch, gc; gc.collect(); torch.cuda.empty_cache()"
```

### 9. Multi-target deployment order

Changes must reach all targets before the fix is done. Order matters:

| Step | Action | Example |
|------|--------|---------|
| 1 | **Desk** | Direct edit + service restart on local machine |
| 2 | **Tpad** | scp binary/plugin/fix + service restart |
| 3 | **Backend repo** | `git commit && git push origin main` |
| 4 | **Hetzner** | `git pull && bash scripts/install-backend.sh` regenerates source.tar.gz |
| 5 | **Registry push** | Build GPU variant OR deploy fixed image via build-all-locked.sh |

The repo push comes AFTER ad-hoc deploys so the commit and live fix are in sync.

### 10. Use uv instead of pip in Containerfiles

**Signal:** pip install times out on PyPI downloads (`ReadTimeoutError: HTTPSConnectionPool`),
especially on `--no-cache` builds that re-download everything. `uv` is ~10-100x faster
and avoids the timeout issue entirely.

**Fix:** Replace every `pip install` in the Containerfile with `uv pip install --system`:

```dockerfile
# BEFORE:
RUN pip install --no-cache-dir nuitka==2.5.4 setuptools wheel ordered-set
RUN pip install --no-cache-dir -r /build/requirements.gpu.txt

# AFTER:
# 1. Install uv (pip itself is fine for bootstrapping uv)
RUN pip install uv && uv pip install --system --no-cache nuitka==2.5.4 setuptools wheel ordered-set
# 2. uv for all subsequent pip installs
RUN uv pip install --system --no-cache -r /build/requirements.gpu.txt
```

**Key differences between pip and uv flags:**
| pip | uv equivalent | Why |
|-----|--------------|-----|
| `pip install` | `uv pip install --system` | uv needs `--system` in containers (no venv) |
| `--no-cache-dir` | `--no-cache` | Different flag name |
| `-r requirements.txt` | `-r /absolute/path/requirements.txt` | uv resolves paths differently; use absolute paths |

**Each build stage needs uv installed separately** — it's not inherited between stages:
- Stage 1 (builder): `RUN pip install uv && uv pip install --system ...`
- Stage 2 (runtime): `RUN pip install uv && uv pip install --system ...`

**Check**: After building, verify the image has the expected .so files:
```bash
podman run --rm <image> find /app -name '*.so' | head -10
```

### 11. sync-engine.sh requires full path

The `sync-engine.sh` script lives at `client/pod/mazemaker/bin/sync-engine.sh` relative
to the `mazemaker-v2-stack/backend` root. Running just `sync-engine.sh` from the backend
directory fails with "command not found" because it's not in PATH.

**Fix:** Always use the full relative path:
```bash
cd ~/projects/mazemaker-v2-stack/backend
bash client/pod/mazemaker/bin/sync-engine.sh
```

**Check:** After sync, verify the engine source was copied:
```bash
ls -la client/pod/mazemaker/core/dream_worker.py 2>/dev/null && echo "SYNC OK" || echo "SYNC FAILED"
```

### 12. Shipping Hermes plugins via install.sh

Hermes memory provider plugins go in `client/hermes-plugins/<name>/__init__.py`.
Hermes skills go in `client/hermes-skills/<name>/SKILL.md`.

The install.sh must:
1. Copy `__init__.py` to `~/.hermes/plugins/<name>/`
2. Copy `SKILL.md` to `~/.hermes/skills/<category>/<name>/`
3. Set `memory.provider: <name>` in `~/.hermes/config.yaml`
4. MCP tools are auto-discovered — no explicit MCP server entry needed

Do NOT ship operator-only skills (bulk-insert, gpu-duplication-debug,
visuals-iteration, prod-ssh-backup) with the customer installer.

## Canonical Build+Push: `build-all-locked.sh --push`

For engine images (mcp, embedding-worker, wonderland, license-client), the
**canonical** pipeline is `build-all-locked.sh`. It handles sync + build + push
in one command. Do NOT manually run sync-engine.sh + podman build + podman push
when `build-all-locked.sh` covers the same ground.

```bash
# Single command — syncs engine source, builds all Nuitka variants, pushes to registry
cd ~/projects/mazemaker-v2-stack/backend
bash bin/build-all-locked.sh --tag 1.0.0-rc1 --push

# Build only one service (skip push)
bash bin/build-all-locked.sh --tag 1.0.0-rc1 --only=engine

# Build + push one service with --skip-gpu (CPU only)
bash bin/build-all-locked.sh --tag 1.0.0-rc1 --only=engine --push --skip-gpu
```

**What `--only=` accepts** (from SERVICES[] array):
- `engine` — MCP + dream-worker container
- `embedding-worker` — embedding service
- `wonderland` — Wonderland proxy
- `license-client` — license verify daemon

**What `--push` does:**
1. Builds primary variant (Containerfile.nuitka → `registry.mazemaker.dev/mazemaker-<svc>:<TAG>`)
2. Builds GPU variant (Containerfile.gpu.nuitka → `registry.mazemaker.dev/mazemaker-<svc>:<TAG>-gpu`)
3. Pushes both to registry via `podman push`

**Why this matters:** The manual approach (sync-engine.sh → podman build → save → scp → load → push) is fragile, error-prone, and the user will correct you. `build-all-locked.sh --push` is the established pipeline.

**Pitfall:** The registry push goes through the Cloudflare tunnel. GPU images (>5GB) may hit 413/502. If that happens, fall back to the manual save+scp→localhost:5000 approach below.

### Manual fallback (when CF tunnel blocks large pushes)

Only use when `build-all-locked.sh --push` fails with 413/502:

```bash
# 1. Sync engine source
cd ~/projects/mazemaker-v2-stack/backend
bash client/pod/mazemaker/bin/sync-engine.sh

# 2. Build image (Nuitka-compiled, uv not pip)
podman build -t localhost/mazemaker-v2-mcp:gpu \
  -f client/pod/mazemaker/Containerfile.gpu.nuitka \
  client/pod/mazemaker/

# 3. Tag for registry
podman tag localhost/mazemaker-v2-mcp:gpu \
  registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu

# 4. Save + SCP to Hetzner (avoid CF 413 limit — 6.3 GB GPU image)
podman save registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu -o /tmp/mcp-gpu.tar
scp /tmp/mcp-gpu.tar mazemaker-prod:/tmp/mcp-gpu.tar

# 5. On Hetzner: load + push to localhost:5000 (NOT via CF tunnel — avoids 413/502 on large pytorch blobs)
ssh mazemaker-prod 'su - mazemaker -c "
  podman load -i /tmp/mcp-gpu.tar && \
  podman push --tls-verify=false localhost:5000/mazemaker-mcp:1.0.0-rc1-gpu && \
  rm -f /tmp/mcp-gpu.tar
"'

# 6. On desk/tpad: pull new image + restart
podman pull registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu
systemctl --user restart mazemaker-dream-worker.service
```

## Building Host Binaries (full workflow)

```bash
cd ~/projects/mazemaker-v2-stack/backend
bash bin/build-host-binaries.sh
# Output: dist/host-binaries/{peer_sync, mazemaker-hermes-bridge, mazemaker-mcp-socket-bridge, fingerprint}
```

To rebuild just one binary after a source change, edit the script logic
(no single-binary rebuild flag exists — run the full script).

## Verification After Deployment

```bash
# Host binary: check version/help
~/.local/bin/mazemaker-hermes-bridge --help 2>&1 | head -5

# Container: check .so exists
podman exec systemd-mazemaker-dream-worker ls /app/dream_worker*.so

# Service: check running
systemctl --user is-active mazemaker-dream-worker.service

# Registry: check image exists
podman pull registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc1-gpu
