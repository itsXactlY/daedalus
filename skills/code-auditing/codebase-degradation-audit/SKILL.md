---
name: codebase-degradation-audit
description: Audit a codebase's bottlenecks & silent degradations.
---

# Codebase Degradation Audit

Class of task: find the EXACT bottleneck at scale (N records/memories/users), enumerate ALL silent fallbacks/quality losses, and reconstruct WHEN an engine started silently degrading — with the introducing commit for every defect. Produces a ranking table, a degradation map, and a git timeline as the deliverable.

## Workflow

### 1. Inventory & scale
- `wc -l` the focus files; note line counts in the report.
- Get file histories first: `git log --follow --oneline --date=short --pretty=format:'%h %ad %s' -- <file>`
- Locate hot-path functions (`def ` in the core classes) before reading anything else; the constructor and the main entry points (recall/remember/batch) are where the story lives.

### 2. Git archaeology (dating defects)
- Symbol introduction: `git log --oneline -S "<symbol>" --date=short --pretty=format:'%h %ad %s' -- <file>` (pickaxe). Works for function names, env vars, config keys.
- Hot-spot attribution: `git blame -L <start>,<end> <file>`.
- **BEFORE-state of a function** — the single most valuable move for "when did the 12-GB path appear":
  `git show <commit>^:<file> | sed -n '/def funcname/,/def nextfunc/p'`
- Mine commit bodies: this codebase (and many like it) documents MEASURED values (12.3 GB, 57.8 s/query, 193.7 s/phase) in commit messages. Those numbers ARE the evidence.
- Env-var/config archaeology: `git log --all --oneline -S "<KEY>" --pretty=format:'%h %ad %s'`.
- Cross-repo: same commit MESSAGE with different hashes = cherry-picked fork lines that have diverged. `diff -q` reporting "differ" can mean the file is MISSING in the other repo — verify with `ls`.

### 3. Silent fallback hunting
- grep for `except Exception: pass`, bare `except:`, `return False`/`return []` right after try/except, and `except TypeError` (backend-flag compat shims).
- For EVERY fallback record: trigger condition, log level (**debug does NOT count as visible** — only warning/error), introducing commit.
- grep comments for "fallback|silent|degrad|cpu|numpy" — authors document their own sins; those comments carry the measured costs.
- Check `hasattr(store, "x")` dispatch: one backend gets the fast path, the other silently no-ops (e.g. `iter_for_gpu_arm` exists on PG only; SQLite keeps the whole-corpus path).

### 4. Config-chain verification (config lies)
- For every config key/env var the deployment sets: `grep -rn "<KEY>" <repo> --include="*.py"` and count READERS. **A key read by zero code is a lie**, no matter how authoritative the file looks.
- Trace the real chain: remote/cloud config → license client → generated .toml/.env → container mount (Quadlet `/etc/containers/systemd` or `~/.config/containers/systemd/*.container`) → code.
- Compare what the operator THINKS runs (config says "advanced") vs constructor DEFAULTS actually used (often "semantic").
- Operator history lives in artifacts: drop-in dirs (`*.container.d/`, `*.service.d/`) and backup tarballs (`dropin-backup-*.tar.gz`) — disabled/renamed configs (e.g. `dae-off.conf.disabled-20260806`) are only findable there. Extract to /tmp and read.

### 5. RAM cost math (Python) — do the arithmetic
- list[float]: **32 B/float** (24 B PyFloat object + 8 B list pointer) — the #1 silent killer at scale (215k×1024 → 7.05 GB).
- np.float32 array: 4 B/float. torch tensor: 4 B/float (GPU).
- dict row overhead ~600 B; content/label strings ~1–2 KB/row typical.
- hnswlib index @200k×1024: ~2.5–4 GB.
- Sum the copies in order (wire bytes → list → np.asarray → torch → index) and check against measured peaks in commit messages (7.05+0.88+0.88+0.5 ≈ 12.3 GB — matches).

### 6. Deliverable format (German, per operator convention)
- `## Flaschenhals-Ranking` — table: Rang | Operation | Komplexität | RAM | Datei:Zeile, top 10.
- `## Stille-Degradations-Karte` — table: Fallback | Auslöser | Log-Level | Seit-Commit | Datum.
- `## get_all()-Kosten-Analyse` — the RAM arithmetic written out.
- `## Git-Zeitlinie der Degradation` — Datum -> Commit -> was brach.
- `## JEDER Einzelbefund` — Datei:Zeile | Severity | Bug | Fix | Einführungs-Commit.
- Always give the INTRODUCING commit, not just the fix commit.

## Pitfalls
- `pass` in an except block after a GPU call = permanent silent CPU fallback ("for the lifetime of this process") — the classic "OOM → restart → silently on CPU forever" chain.
- A feature can be ACTIVE (computing full-corpus every N cycles) yet UNWIRED (nobody reads the output, channel weight 0.0). Check the consumer side before calling it useful.
- Quality knobs differ per index: hnswlib `set_ef(64)` vs pgvector `hnsw.ef_search=500` — the smaller number silently misses top-K.
- get_all()/fetchall() of the whole table is the classic O(n) RAM bomb; look for `include_embeddings` flags and streaming variants (`iter_for_gpu_arm`, raw-wire-byte loaders) that exist on only ONE backend.
- The production pod/container may be DOWN at audit time — live logs unavailable. Rely on MEASURED values in code comments and commit bodies; say so in the report.
- NREM/dream dead-man switches and stats fields can LIE (e.g. "pairs_checked 17708, found 0" while the writer was a no-op). Cross-check stats against whether the writer exists.

## References
- `references/mazemaker-engine-kernel.md` — full 2026-08-07 audit of the mazemaker-pro engine kernel: bottleneck ranking @215k, silent-degradation map with commits, get_all() cost math, git timeline 2026-04-09→08-07, DAE config chain, cross-repo divergence (pro vs community fork), operator artifacts (Quadlet paths, drop-in backups).
