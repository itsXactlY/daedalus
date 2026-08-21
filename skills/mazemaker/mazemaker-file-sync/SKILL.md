---
name: mazemaker-file-sync
category: devops
description: Mazemaker symlink deployment — single source of truth at python/, deployed via symlinks
version: 2.0.0
tags: [mazemaker, symlinks, deployment, architecture]
priority: critical
created: 2026-04-20
updated: 2026-04-21
---

# Mazemaker Deployment — Symlink Architecture

**SUPERSEDES the old 3-copy sync pattern. As of 2026-04-21, the architecture uses SYMLINKS, not copies.**

## Architecture (Current)

```
~/projects/mazemaker/python/       ← SINGLE SOURCE OF TRUTH (21 .py files)
~/.hermes/hermes-agent/plugins/memory/mazemaker/  ← SYMLINKS → python/
hermes-plugin/                                 ← Only metadata: plugin.yaml, neural_skin.yaml, README.md
```

**No more copies. No more sync. Edit python/ → immediately live in all deploy targets.**

## How It Works

The installer (`install.sh`) creates symlinks using `ln -s`:

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="$SCRIPT_DIR/python"

for f in "$PYTHON_DIR"/*.py; do
    ln -s "$f" "$TARGET_DIR/$(basename "$f")"
done
```

The `SCRIPT_DIR` resolves to wherever the installer lives — so it works regardless of where the repo is cloned.

## Deploy Targets

The installer auto-detects hermes-agent in this order:
1. `~/.hermes/hermes-agent`
2. `~/jack-in-a-box/hermes-agent` (jack-in-a-box installations)
3. `~/hermes-agent`
4. `~/.hermes/agent`
5. `/opt/hermes-agent`
6. `~/projects/hermes-agent`

## Commands

```bash
bash install.sh install    # Create symlinks, install deps, verify
bash install.sh update     # git pull + re-symlink + test
bash install.sh test       # Run test suite
bash install.sh verify     # Check imports, embeddings, DB, symlinks
bash install.sh uninstall  # Remove symlinks, preserve source
```

## Files That Stay in hermes-plugin/ (NOT symlinked)

- `plugin.yaml` — hermes plugin metadata
- `neural_skin.yaml` — CLI skin definition
- `README.md` — documentation
- `skills/` — skill definitions

These are per-install metadata, not shared code.

## Pitfalls

1. **Never `cp python/ hermes-plugin/`** — hermes-plugin only has metadata now
2. **Broken symlinks** = source files deleted or moved. Run `install.sh verify` to check
3. **Remote cloning** — symlinks are relative to SCRIPT_DIR, not hardcoded. Works from any path
4. **Git does NOT track symlinks** — the installer creates them at install time, they're not in the repo

## History

- v1 (2026-04-20): 3-copy sync pattern (python/ + hermes-plugin/ + deployed). Required manual `cp` after every edit.
- v2 (2026-04-21): Symlink architecture. python/ is source of truth, deployed via `ln -s`. Eliminated sync entirely.
