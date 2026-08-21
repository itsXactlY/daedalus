# Build-Chain-Reproduzierbarkeits-Audit — mazemaker, verifiziert 2026-08-07

Read-only audit of the mazemaker-v2 build/deploy chain (THESIS D: "chain cannot produce
reproducible images, preflight dead, repo/production diverged"). All facts verified on the
operator box (alca@linux) 2026-08-07 ~23:15 CEST. Image state: rtm.5 built 22:25 CEST
(created 20:25 UTC), pod stopped 23:16. Verdict: thesis PARTIALLY confirmed — mechanisms
real, but the two headline "current-state" claims (label missing; :latest vs :gpu mismatch)
were FALSE at audit time.

## Chain map: Repo → Image → Label → Unit → Pod

| Step | Location | Detail |
|---|---|---|
| Fingerprint | `~/.mazemaker/bin/engine-sha.sh` (= repo `client/pod/mazemaker/bin/engine-sha.sh`, IDENTICAL) | `find . -type f` over ENGINE_SRC; excludes dirs `__pycache__ .git build .venv tests tools`; files `*.so *.bak *.cpp *.hpp *.cmake CMakeLists.txt setup_fast.py demo.py`. **NO git filter → untracked files inside `python/` change the sha.** |
| Label baked | `bin/build-all-locked.sh:307-312` → `--build-arg ENGINE_SHA`; `Containerfile(.gpu).nuitka:107-108` `ARG ENGINE_SHA=unknown` + `LABEL org.mazemaker.engine_sha="$ENGINE_SHA"` | Fallback `unknown` if helper fails or tier has no engine src (wonderland/license-client/embedding-worker) — script comment: "the preflight fail-opens" (commit `c8e02b2`). |
| Sync into context | `build-all-locked.sh:246-256` `sync_engine` (`rsync -a --delete`, pattern excludes only, **no git filter**); `:263-274` `sync_cpp` copies `CMakeLists.txt src include tests benchmarks` from Pro repo ROOT | Verified: untracked `client/pod/mazemaker/cpp/benchmarks/audit/upside-down-*.md` junk in build context — proof the rsync carries uncommitted files. |
| Preflight | `client/bin/mazemaker-mcp-preflight` (deployed `~/.local/bin/` IDENTICAL), wired ONLY via mcp quadlet `ExecStartPre=%h/.local/bin/mazemaker-mcp-preflight` | Block ONLY if `expected` AND `actual` non-empty AND `actual != unknown` AND differ (Z.129-133). **FAIL-OPEN**: no helper/source → Z.135-136; missing/`unknown` label → Z.137-138 "pre-stamp image — skipping staleness check (fail-open)". Commits `c8e02b2` (2026-06-18), tier-aware src `9c92d3c` (2026-07-08). Dream-worker has NO preflight. |
| Quadlet tags | live `~/.config/containers/systemd/mazemaker-mcp.container` `Image=localhost/mazemaker-v2-mcp:latest`; dream-worker `Image=localhost/mazemaker-v2-mcp:gpu` | Build tags `registry.mazemaker.dev/mazemaker-<svc>:<VERSION>[-gpu]` — retag to localhost names required (TAG-GAP pitfall, recurring blocker 2026-07-20). |
| install.sh | `installer/linux/install.sh:1387-1396` | GPU hosts: pull `mcp:<TAG>-gpu`, tag BOTH `localhost/mazemaker-v2-mcp:latest` AND `:gpu` (fixes `94c3de9`, `1a18e5a`). `latest==gpu==same ID` is the HEALTHY state on a GPU box. |

## Verified state 2026-08-07

- Labels: `localhost/mazemaker-v2-mcp:latest|gpu` AND `registry.mazemaker.dev/mazemaker-mcp:1.0.0-rtm.5[-gpu]` ALL = `f4ecb9938e5bc…` = `engine-sha.sh ~/projects/mazemaker-pro/python` computed NOW (match!). mcp-free rtm.5 = `d9af2e4b…` = free tree hash. rtm.4-gpu = `e0620d31…` (older, present).
- Pro `python/` tree CLEAN vs HEAD `b415570` (2026-08-07 21:48+0200, predates build). Untracked junk only at Pro repo ROOT (`.directory`, `benchmarks/audit/*.md`, `logs/`) — `git ls-files --others python/` empty in BOTH repos.
- Build context `client/pod/mazemaker/core/` == `python/` file-name-for-name. Image `/app`: 39 Nuitka `.so`, zero `.py` (lockdown `Containerfile*.nuitka:122-125`, fail-closed), no junk files.
- `build_nuitka.py` compiles ALL `*.py` except skips (`__init__.py demo.py test_*.py setup_fast.py embed-server.py build_nuitka.py`); `_lib_finder.py` explicitly MUST ship (Z.46-47) — present in image. Nuitka pinned `==2.5.4`; requirements mostly pinned (`uvicorn==0.32.1`, `fastembed==0.5.1`).
- Byte-non-determinism: floating FROM tags, no `@sha256:` pins (`docker.io/pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime`, `docker.io/python:3.12-slim`, `docker.io/library/ubuntu:22.04`).
- **sync.sh (pro + free repo roots, files IDENTICAL) is DEAD CODE**: copies `memory_client.py cpp_bridge.py embed_provider.py mssql_store.py dream_mssql_store.py dream_engine.py fast_ops.pyx`; `mssql_store.py` + `dream_mssql_store.py` DO NOT EXIST in either repo; `_lib_finder.py config.py __init__.py postgres_store.py gpu_recall.py dream_worker.py …` missing from list. Zero references in v2-stack scripts (only the junk audit .md files mention it). Free repo: untouched since initial "community" commit.
- ACTIVE Hermes memory provider: `~/.hermes/plugins/mazemaker/__init__.py` (config `memory.provider: mazemaker`), shipped from `client/hermes-plugins/mazemaker-memory-provider/__init__.py` by `install.sh:1081-1086`; verified IDENTICAL to repo. Engine-repo `install.sh` v2 (symlink ALL `*.py`) NOT wired into the pod chain; `plugins/memory/neural` does not exist on this box.
- Drift at audit time: 6 quadlet files uncommitted in v2-stack (62 insertions: `MM_EMBED_TIMEOUT=120`, `MM_COLBERT_ENABLED=1`, `Pull=never`, ExecStartPost warmup-restart, dream-worker GPU lines); live == worktree ≠ HEAD. `~/.mazemaker/installed.image_tag` = `1.0.0-rtm.4` while rtm.5 built/tagged locally. `release/digests.json` consistent with rtm.5 (incl. mcp:1.0.0-rtm.5-gpu sha256:629fb47d…). Historical: rc6/rc8 tag drift 2026-07-05→08-01 (documented in `build-all-locked.sh:35-47`, fixed by `df23df9` VERSION single-source-of-truth).

## Verdict

Reproducibility TODAY: **7/10**. HEAD of both repos + build-all-locked.sh reproduces the current `:gpu` image functionally 1:1 (same engine_sha label, same module set, zero `.py`). Gaps: floating base tags (byte-level), engine-sha sensitivity to untracked files inside `python/` (latent), preflight fail-open on missing/unknown label (by design, `c8e02b2`), preflight covers mcp only, uncommitted quadlet drift.

**THE ONE FIX**: engine-sha.sh + sync_engine/sync_cpp operate on git-tracked files only (`git ls-files` hashing / `git archive` extraction) → fingerprint becomes a pure function of committed HEAD; then digest-pin base images.

## Reusable one-liners

```bash
# Label-vs-tree staleness check (Pro tier)
podman image inspect localhost/mazemaker-v2-mcp:latest --format '{{index .Config.Labels "org.mazemaker.engine_sha"}}'
bash ~/.mazemaker/bin/engine-sha.sh ~/projects/mazemaker-pro/python
# Free tier: use ~/projects/mazemaker/python — Pro vs free hash differently
# Image content lockdown check
podman run --rm --entrypoint sh localhost/mazemaker-v2-mcp:gpu -c 'ls /app'
```
