# Nuitka Deployment Pitfalls

Patterns discovered while maintaining the mazemaker-v2-stack's Nuitka-compiled
host binaries (`build-host-binaries.sh`) and their Quadlet/service integration.

## Compiled .so replaces .py — paths change

Nuitka `--module` compiles `foo.py` → `foo.cpython-3XX-x86_64-linux-gnu.so`.
The `.so` lands in the output directory, **not** necessarily at the same path
as the original `.py`. Common outcomes:

| Before (source .py) | After (compiled .so) | Problem |
|---|---|---|
| `python /app/core/dream_worker.py --args` | File gone: `.so` at `/app/dream_worker.*.so` | **Exec no longer resolves** |
| `python my_script.py` | `my_script.*.so` exists but `python my_script.so` is wrong | Use `python3 -c "import my_script; my_script.main()"` |

### Fix pattern

Replace `Exec=python -u /app/core/dream_worker.py --flag value` with:

```
Exec=python3 -c "import sys; sys.path.insert(0, '/app'); sys.argv = ['name','--flag','value']; import dream_worker; dream_worker.main()"
```

Key details:
- `sys.path.insert(0, '/app')` — the `.so` lives at `/app/`, not a subdir
- `sys.argv` — set before the import so `argparse` sees the CLI flags
- The module name is the **original filename without `.py`** (e.g. `dream_worker`, not `dream_worker.py`)
- Use `python3` not `python` inside containers (slim images have `python3`)

## Running binary cannot be overwritten with cp

When a Nuitka `--onefile` binary is currently executing, `cp new_bin target`
fails with **"Text file busy"** (Linux: `ETXTBUSY`) because the inode is mapped
into the running process's text segment.

### Fix pattern in install scripts

```bash
# Stop service before replacing binary
systemctl --user stop my-service.service 2>/dev/null || true
rm -f "$HOME/.local/bin/my-binary"
cp "$SOURCE/my-binary" "$HOME/.local/bin/my-binary"
chmod 755 "$HOME/.local/bin/my-binary"
# Restart later (or let the service auto-restart)
```

Key details:
- `rm -f` first (removes the old inode — the running process keeps its reference)
- THEN `cp` the new binary (creates a fresh inode)
- Stop before replace so the new binary is ready when the service restarts

## Builder container needs ALL Python deps the source imports

`build-host-binaries.sh` runs inside a `python:3.12-slim` container.
The pip install in the builder must include every import the source code uses.
Missing imports compile fine (Nuitka silently skips failed imports inside
`try/except ImportError` blocks) but the resulting binary raises `RuntimeError`
at runtime.

### Fix pattern

```bash
pip install --no-cache-dir nuitka==2.5.4 setuptools wheel \
  httpx tomli requests pyyaml \
  # ^ add any missing dep here
```

Check the source for `try: import X / except ImportError` blocks — those are
the silent-fail candidates that won't break the build but will break at runtime.

## Rsync excludes + publish gate block intentionally-shipped .py files

The lockdown rsync excludes `--exclude='*.py'` to prevent Python source from
leaking into the customer tarball. But `__init__.py` files in
`client/hermes-plugins/` and `client/hermes-skills/` are **intentional** —
they're Hermes plugins, not pod code.

### Fix pattern

Add `--include='*/' --include='__init__.py'` BEFORE `--exclude='*.py'`:

```bash
RSYNC_EXCLUDES+=(\
  --include='*/' \
  --include='__init__.py' \
  --exclude='*.py' \
  --exclude='*.pyx' \
  --exclude='*.pyi' \
  ...)
```

The publish gate's `find` needs a matching exemption:

```bash
BAD_FILES=$(find "$STAGEDIR" \
  \( -name '*.py' ... \) \
  -not -path '*/client/hermes-plugins/*' \
  -print ...)
```

Key detail: rsync processes `--include`/`--exclude` as **first-match wins**.
Without `--include='*/'`, rsync won't even descend into directories and the
`--include='__init__.py'` never matches.

## Quadlet `AddDevice=nvidia.com/gpu=all` fails on non-GPU hosts

When a Quadlet has `AddDevice=nvidia.com/gpu=all` and the machine has no NVIDIA
GPU, `podman run` fails with `unresolvable CDI devices nvidia.com/gpu=all`.

### Fix pattern in install scripts

```bash
if ! nvidia-smi &>/dev/null; then
  sed -i '/AddDevice=nvidia/d' "$QUADLET_FILE"
fi
```

Or strip unconditionally in the Quadlet template and let the GPU-variant image
handle device detection at runtime.

## GPU VRAM grows unbounded in long-running CUDA daemons

Continuous PyTorch daemons (dream worker, embedding worker) accumulate CUDA
caching-allocator blocks across iterations. Different tensor sizes per cycle →
fragmented cache → VRAM grows over hours/days → eventual OOM even though no
individual tensor leaks.

nvidia-smi shows high usage but `torch.cuda.memory_allocated()` reports near
zero — the allocator holds freed blocks in reserve, not as live tensors.

### Fix pattern in source code

```python
# After each work cycle in the long-running loop:
import gc, torch
gc.collect()
before = torch.cuda.memory_reserved()
torch.cuda.empty_cache()
after = torch.cuda.memory_reserved()
if after < before:
    logger.debug("freed %d MB GPU cache", (before - after) // (1024*1024))
```

### Emergency band-aid (cron when source can't be rebuilt)

```bash
# cron every 5 min inside the container:
podman exec <container-name> python3 -c "
import torch, gc; gc.collect(); torch.cuda.empty_cache()
"
```

Set as a `no_agent=True` cron script so it runs silently and only emits output
when memory was actually freed.

## Multi-target deployment: always ship to all machines

Changes must reach three targets before the fix is "done":

| Target | What | How |
|--------|------|-----|
| **Desk** | Local dev machine | Direct edit + service restart |
| **Tpad** | Secondary machine | `scp` binary/plugin/fix + service restart |
| **Backend repo** | `git push origin main` | The source of truth — future installs pick it up |
| **Hetzner VM** | Production API server | `git pull + install-backend.sh` regenerates source.tar.gz |

Order matters: Desk → Tpad → Repo → Hetzner. The repo push comes AFTER the
ad-hoc deploy so the commit and the live fix are in sync.

### Pipeline components

| Component | Purpose |
|-----------|---------|
| `bin/build-host-binaries.sh` | Nuitka-compile 4 host binaries inside a `python:3.12-slim` container |
| `installer/linux/install.sh` | Customer-side installer — copies binaries, plugins, skills, sets config |
| `scripts/install-backend.sh` | Hetzner publisher — builds API image, stages tarball, runs publish gate |
| `source.tar.gz` | The shipped payload — everything a customer needs to install the pod |

### What goes in source.tar.gz

Always check `scripts/install-backend.sh` and its `RSYNC_EXCLUDES` when adding
a new component to the shipped payload. The publish gate aborts if it finds
aborts if it finds blacklisted artefacts (`.py`, `Containerfile*`, `.hermes`, `.wrangler`, etc.)
— exemptions must be explicit with `-not -path` in the find command.

## build-all-locked.sh GPU variant trap

The `build-all-locked.sh` script orchestrates multi-stage builds for all 4
closed-source images. Its `SERVICES[]` array has an `extra-tag` field for GPU
variants. If a service lacks the GPU entry, only the CPU image is built — the
`:gpu` tag either doesn't exist or (worse) falls back to the raw `.py`
Containerfile without Nuitka compilation.

### Pattern to check

```bash
SERVICES=(
  "wonderland|...|Containerfile.nuitka|"                    # no GPU variant
  "engine|...|Containerfile.nuitka|Containerfile.gpu.nuitka:gpu"  # HAS GPU variant
  "license-client|...|Containerfile.nuitka|"                # no GPU variant
  "embedding-worker|...|Containerfile.nuitka|Containerfile.gpu.nuitka:gpu"  # HAS GPU
)
```

Every service that ships a `:gpu` image must have the extra-tag entry.
Missing entries cause silent deployment of unhardened images.

### Remediation

```bash
# Add the GPU variant: Containerfile.<variant>:<tag-suffix>
# engine/mcp was missing this — embedding-worker had it correctly
"engine|client/pod/mazemaker|Containerfile.nuitka|Containerfile.gpu.nuitka:gpu"
```

## GPU VRAM fragmentation in long-running CUDA daemons

Hermes memory provider plugins go in `client/hermes-plugins/<name>/__init__.py`.
Hermes skills go in `client/hermes-skills/<name>/SKILL.md`.

The install.sh must:
1. Copy `__init__.py` to `~/.hermes/plugins/<name>/`
2. Copy `SKILL.md` to `~/.hermes/skills/<category>/<name>/`
3. Set `memory.provider: <name>` in `~/.hermes/config.yaml`
4. The MCP tools are auto-discovered — no explicit MCP server entry needed

Do NOT ship operator-only skills (bulk-insert, gpu-duplication-debug,
visuals-iteration, prod-ssh-backup) with the customer installer.
