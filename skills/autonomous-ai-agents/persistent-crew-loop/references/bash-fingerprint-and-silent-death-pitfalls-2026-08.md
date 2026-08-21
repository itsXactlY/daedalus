# Bash-Fingerprint, NameError-Class and oomd-Diagnosis — mazemaker 2026-08-07

Session detail behind the persistent-crew-loop pitfalls. All three bit during a
single post-audit fix series (P1-P10) on the mazemaker v2 stack.

## 1. engine-sha.sh — three silent killers in one rewrite

Goal: hash only git-tracked files of the engine source (pro repo), so an
uncommitted edit cannot silently change the image fingerprint.

Killer A — `while read` loop as a pipeline stage under `set -euo pipefail`:
```bash
git ls-files | sort | grep -vE "$EXCLUDE" \
  | while IFS= read -r f; do test -f "$f" && printf '%s\n' "$f"; done \
  | xargs -d '\n' sha256sum | sha256sum | awk '{print $1}'
```
The loop's last command (`read`) exits 1 at EOF → pipefail marks the whole
pipeline failed → `set -e` aborts the script BEFORE xargs consumes the stream.
Result: the inner sha256sum hashes EMPTY stdin; the outer sha256sum hashes
that constant text. The "fingerprint" was a constant — content changes never
moved it. Fix: no while filter at all; a deleted tracked file SHOULD fail
sha256sum loudly (broken tree = loud error is the right outcome).

Killer B — `printf "%s\0"` inside `xargs -I{} sh -c ...`:
dash's printf does not honour `\0` in the format string, so the NUL
separators silently vanish and all filenames concatenate into one argument.
Never build NUL-separated streams through `sh -c` printf. Use `xargs -d '\n'`
with newline-separated names (GNU xargs) or a `while` loop writing to a file.

Killer C — default source pointed at the WRONG repo:
`ENGINE_SRC="${1:-${MAZEMAKER_ENGINE_SRC:-$HOME/projects/mazemaker/python}}"`
defaulted to the FREE repo while build-all-locked.sh rsyncs the PRO repo.
Bare helper calls hashed the untouched free tree — constant hash again, and
the preflight chain would have compared the pro image against a free-tree
fingerprint. Default must be `~/projects/mazemaker-pro/python`; the preflight
already resolves tier-aware sources (`MAZEMAKER_PRO_ENGINE_SRC`).

Verification rule that caught all three: mutate a tracked file → hash must
move → revert → hash must return. A deterministic-but-constant fingerprint is
a dead check; "deterministic (2 runs)" alone proves nothing.

## 2. Config-wiring NameError class (silent no-op since the policy move)

Moving dream policy from env vars to compute.toml (commit 02fda91) added
`_cc_get("dream", ...)` reads to several phase functions. The NREM phase's
import only bound `_cc_flag`; the first `_cc_get` read crashed the phase with
`NameError: name '_cc_get' is not defined`. Because phase errors are caught
and the cycle continues, NREM ran as a silent no-op (no strengthen/weaken/
prune/retention) while the rest of the cycle completed. The live worker log
showed `NREM phase error` at 23:51:39 — the first place it was visible.
The same class hit `_phase_synthesis` (masked by `stage_s_enabled=false`
returning before the reads).

Closing move: a whole-file AST scan asserting every `_cc_*` name used inside
each function is bound in that scope (module-level or fn-level ImportFrom).
Run it after any config-wiring change; pyright catches it per-file, but the
AST scan is the regression net for the class.

## 3. systemd-oomd vs kernel OOM — read the journal, not the exit code

status=137 alone is ambiguous. oomd kills are provable only from
`journalctl --user`:
- "cgroup marked", "Memory Pressure Limit exceeded", pressure % (e.g.
  user@1000 84.49%) > 80% for > 20s (DurationSec via drop-in)
- the killed unit is the LARGEST consumer, preferred via OOMScoreAdjust=500
  (worker) vs 200 elsewhere; the worker's own 16G limit was never touched

The real cause was the SUM: MemoryHigh across concurrent units (dream 12 +
pgvector 9 + mcp 3 + embed 2.5 + llm 3 + wonderland 1.5 + license 0.25 =
31.2G) on a 31G host with a desktop. Lowering one container limit is the
wrong fix; bring the MemoryHigh SUM under physical RAM and fix what makes a
unit large.

Steady-state vs leak: the worker held 12.9G flat for minutes (two large anon
allocations, +61MB/75s) — that is LOADED STATE (get_all() materialising
215k x 1024d as Python floats: 24B/float + 8B pointer ≈ 7-9GB; Python heap
does not return freed blocks to the OS), not a cycle leak. The fix was lazy
graph loading + embedding-skip + a streaming arm (blob bytes → np.frombuffer
→ preallocated float32 array, ~0.9GB instead of 11-12GB), not "fewer cycles".
