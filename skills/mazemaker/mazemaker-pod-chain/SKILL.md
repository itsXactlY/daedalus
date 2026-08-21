---
name: mazemaker-pod-chain
description: "Use when auditing or debugging the Mazemaker pod chain."
---

# Mazemaker Pod Chain (Build→Image→Unit→Pod→Runtime)

Curator-maintained companion to the user-owned `mazemaker` / `mazemaker-ops` skills
(both `created_by=None` — adopt them with `hermes curator adopt <name>` to merge).
Covers the LOCAL operator-box pod chain (Pro tier) and its autonomy units.

## Chain map (where everything lives)

| Step | Location |
|---|---|
| Engine source (deployed) | `~/projects/mazemaker-pro/python` (Pro; free repo only for `mcp-free`) |
| Build | `mazemaker-v2-stack/backend/bin/build-all-locked.sh` (rsync→`client/pod/mazemaker/core/`, Nuitka, `--build-arg ENGINE_SHA`) |
| Image label | `org.mazemaker.engine_sha`; helper `client/pod/mazemaker/bin/engine-sha.sh` |
| Quadlet templates | `mazemaker-v2-stack/backend/client/quadlet/` |
| Live quadlets | `~/.config/containers/systemd/` (generated units in `~/.config/systemd/user/`) |
| Runtime gate | `~/.local/bin/mazemaker-mcp-preflight` (ExecStartPre of mcp.service) |
| Autonomy | `~/.local/bin/mazemaker-update`, `mazemaker-refresh-images`, `mazemaker-selftest` + their timers/watches |
| State files | `~/.mazemaker/`: `desired.image_tag`, `installed.image_tag`, `installed.version`, `update.conf`, `db.toml`, `compute.toml`, `runtime.env`, `image-refresh.log` |
| CLI | `~/.local/bin/mazemaker {on|off|dream|status}` |

## Verification commands (run before assuming anything)

```bash
systemctl --user is-enabled mazemaker-selftest.timer mazemaker-update.timer \
  mazemaker-image-refresh-watch.path mazemaker-update-watch.path \
  mazemaker-compute-watch.path mazemaker-db-watch.path mazemaker-upgrade-watch.path
# enabled-but-inactive and disabled are BOTH convergence stalls that look healthy
cat ~/.mazemaker/desired.image_tag ~/.mazemaker/installed.image_tag; cat backend/VERSION
podman image inspect localhost/mazemaker-v2-mcp:latest \
  --format '{{index .Config.Labels "org.mazemaker.engine_sha"}}'
~/.mazemaker/bin/engine-sha.sh ~/projects/mazemaker-pro/python
mazemaker-selftest --since -24h     # capability assertions + log sweep
```

## Pitfalls (code-verified 2026-08-08; full map in references/chain-audit-findings.md)

0. **engine-sha.sh two silent-constant-hash traps (fixed db432d8)**: (a) the
   DEFAULT ENGINE_SRC was the FREE tree (`~/projects/mazemaker/python`) while
   builds hash the PRO tree — a bare call hashed the unmodified free repo and
   the fingerprint looked constant; default is now `~/projects/mazemaker-pro/python`.
   (b) Under `set -euo pipefail`, a `while read` filter ends with exit 1 →
   pipefail kills the pipeline BEFORE xargs/sha256sum see input → the outer
   hash of the empty-input hash text, again a CONSTANT. Also `printf "%s\0"`
   under dash does NOT emit NULs (NUL separation silently vanishes). Use
   `git ls-files | LC_ALL=C sort | grep -vE "$EXCLUDE_RE" | xargs -d '\n' sha256sum | sha256sum`.
   Always verify CONTENT-SENSITIVITY (touch a tracked file → hash must move,
   revert → back) — determinism alone proves nothing.
1. **Autoupdater re-introduces `AddDevice=nvidia.com/gpu=all` on CPU pods** —
   FIXED (update path now strips the line on CDI-less hosts, same condition
   as install.sh: `ls /etc/cdi /var/run/cdi` empty → strip).
2. **`mazemaker off` leaves units running**: cmd_off stops only POD_MEMBERS + MASTER_UNITS +
   `mazemaker.target`. NOT stopped: `mazemaker-llm` (~6.5 GB), `mazemaker-apk-gateway(.mdns)`,
   all watch.path/timer units, hermes-compress-guard. And refresh-images.sh has NO STOPPED-guard:
   the nightly update (03:30) drops an image-refresh.request that **reanimates an off pod**.
   FIXED for llm: off-list now includes mazemaker-llm.service.
3. **engine_sha is a git-tree hash of the PRO tree** (`git ls-files` + sync-engine
   excludes; the old find-based version hashed UNTRACKED files and drifted from
   sync_engine). **Chain invariant: Image-Label == Live-Baum-Hash == Preflight-expected.**
   A commit DURING a build breaks the chain: the label carries the build-start
   tree, the preflight (fail-closed since the 08-08 hardening) computes the
   live tree → restart is refused with "refusing to start (fail-closed)". Fix:
   rebuild after the final commit; verify `podman image inspect ... engine_sha`
   == `engine-sha.sh` output == `[mcp-preflight] engine-sha OK` line.
4. **Local build+retag does not stamp `installed.image_tag`** → tag drift lies (VERSION=rtm.5
   while installed says rtm.4). Check `mazemaker status` after local rebuilds. The
   `desired.image_tag` file is the last SERVER response — a local-only build legitimately
   differs; stamp it to silence the selftest tag-drift check.
5. **Test traps — FIXED 1dfb868 + 19b6234**: `tests/test_suite.py` no longer opens the production
   db (isolated tmp DB + hash backend; its cleanup block previously targeted the
   production path and could delete real memories); `test_upside_down.py` sources list no
   longer requires the deleted `cpp_dream_backend.py`; auto-connections test skips
   honestly on hosts whose backend falls back to hash; the sentence_transformers singleton
   test skips honestly when torch is absent (the old skip only checked the model dir, then
   died on `No module named 'torch'` during instantiation). All three suites green
   (44/44, 171/171, 5/5) — first green run since the PG migration. New regression
   test guards the streaming arm (bit-exact blob decode).
6. **Free repo CI is dead — FIXED 2b92a6d**: triggers now include `main-v2`.
7. **memprobe/probe deaths on the GPU arm**: `Mazemaker.__init__` is NOT lazy —
   HttpEmbeddingBackend fires a 1-token probe POST at construction (10s default timeout), and
   the GPU-arm AUTO-BUILD path (gpu_cache empty) materialises the whole corpus via
   `store.get_all()` (~12.9 GB before 94cdc80; SQLite now streams via iter_for_gpu_arm).
   Probing with the embedding worker down dies in the constructor.
8. **User journal can be volatile** → early selftest/update runs become forensic dead ends.
   Capture selftest output promptly; don't rely on journalctl for pre-restart evidence.
9. **`_lib_finder.__file__` breaks under Nuitka**: `Path(__file__).resolve().parent.parent`
   resolves to `/` in compiled .so; the C++ bridge only loads via candidate #3
   (`/usr/local/lib/libmazemaker.so`).
10. **`sync.sh` is legacy and dangerous**: copies 7 files only; `_lib_finder.py` +
    `lstm_knn_bridge.py` missing → plugin import breaks and C++ silently falls back.
    Use install.sh v2 (symlinks) or rsync --delete of the whole python/.
11. **compute.toml is RENDERED**: the license-client re-renders it from the JWT claim —
    hand-edited keys are overwritten on the next render. Policy defaults belong in
    `compute_config.DEFAULTS` (e.g. insights_keep_days), not the toml.
12. **GPU-STRICT contract**: `MM_RECALL_GPU_STRICT=1` (both prod quadlets) makes CUDA-less
    recall a hard RuntimeError and refuses the whole-corpus get_all() brute-force;
    `MM_ALLOW_CPU_RECALL=1` is the explicit opt-in for dev boxes/tests/bakes. Never set
    STRICT without a working GPU or the arm raises at every init.
13. **Restart cascade self-kills ("das Ding killt sich selbst")**: restarting ONE pod member
    (e.g. `systemctl --user restart mazemaker-mcp`) refreshes the whole pod → the
    embedding-worker restarts with it (~36 s BGE load) → in that window every
    `EMBED_BACKEND=http` client (dream-worker, bakes) gets "Connection refused" → the
    worker unit fails twice and systemd restart-loops while the old cycle still holds RAM
    → swap pressure. Sequence restarts so the embedding endpoint is never down while a
    client starts; or stop clients first, restart the pod, then start clients.
14. **Lean-core envs (quadlets f477b19, operator directive)**: `MAZEMAKER_DAE_ENABLED=0`
    (dream-worker) is the STABLE off-switch for the full-corpus DAE recompute — the toml
    `dae_enabled=false` is NOT stable (license-client re-renders it from the claim);
    `MM_COLBERT_ENABLED=0` (mcp + worker) kills the duplicate bge copies — mcp went from
    3116 MiB to 0 MiB VRAM. Comment/warn lines must match behaviour: the old
    `warn_ignored_env("MM_DAE_ENABLED")` printed "set but IGNORED" while the code reads
    the env (fixed 388cae2).
15. **Push-gap trap — customers run the tree BEFORE the whole fix series**: commits made
    and never pushed leave origin/master frozen at the last push. Measured 2026-08-08:
    mazemaker-pro had 16 unpushed commits (last push 21:48 the previous day), v2-stack/backend
    had 7 — so customers had the state BEFORE the entire fix series while local runs looked
    current. The operator's suspicion ("kunden haben und bekommen 1:1 selbe stack") was
    FALSE in the other direction — local was AHEAD and nothing had been pushed. **Close a work
    session with `git rev-list --count @{upstream}..HEAD` per repo and push both
    (mazemaker-pro master + v2-stack/backend main; note the v2 remote is
    `mazemaker-v2-backend.git`, NOT mazemaker-pro.git).** Verify divergence AFTER pushing:
    both counters at 0. The engine-sha chain (Image-Label == Live-Baum == Preflight) can
    still lag the pushed tree until the next build.

## Support files

- `references/chain-audit-findings.md` — full 2026-08-07 audit: every break point with
  file:line + fix + introduction commit, silent-death inventory (selftest/update/watcher/
  memprobe), full repo timelines (mazemaker-pro + v2-stack), cross-repo divergence table.
