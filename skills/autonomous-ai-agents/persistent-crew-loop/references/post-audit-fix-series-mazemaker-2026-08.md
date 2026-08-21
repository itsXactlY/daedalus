# Post-audit fix series — mazemaker 2026-08-07 (worked example)

Concrete instance of the point-by-point fix method. The deep audit produced a
10-point fix list; each point was processed as audit → fix → verify → commit.

## The core bottleneck found (why the whole series existed)

`get_all()` materialises the corpus as Python floats: 215k × 1024d =
**7-8 GB of Python objects (vs 0.88 GB raw)**. Every corpus-scaled path that
did not run through the armed GPU tensor paid it:
- HNSW full rebuild — memory_client.py `_ensure_hnsw` → `get_all()` (in code
  since 717589b, 2026-04-30; never touched by any 08-07 fix until P5)
- GPU-arm fallback — gpu_recall.py (12.3 GB measured; introduced 1e0d590,
  2026-05-18, latent 81 days)
- DAE-CPU path — dae.py:671
- Worker steady state was 12.9 GB (two anon blocks 5741+5199+815 MB) and
  systemd-oomd killed it (user-slice pressure >80%, OOMScoreAdjust=500) —
  NOT the kernel, NOT the 16G container cap.

The fix (P5): SQLiteStore got `count_all()` + `iter_for_gpu_arm()` yielding
blob bytes tagged with endianness (`"le"` for native struct.pack floats,
`"be"` for pgvector wire), and `_ensure_hnsw_streaming()` builds the index
from `np.frombuffer` into a preallocated float32 array (~0.9 GB instead of
11-12 GB). Verification: bit-exact decode vs `get()` on a 12-row corpus;
torch/hnswlib paths run in the container (host python lacks both).

## The three refuted CRITICALs (verification phase)

- "FTS5 MATCH injection" — refuted: `_sanitize_fts_query` tokenizes with
  `re.findall(r"[A-Za-z0-9_][A-Za-z0-9_/\-]{1,}")` first; FTS5 metacharacters
  never reach MATCH; quoted phrases are literal.
- "tsquery injection" — refuted: same regex strips `& | ! <-> :`; `-` is not
  a tsquery operator (unlike FTS5).
- "NUL-byte truncation" — refuted: the c_char_p boundary with the NUL check
  is the only truncating path; SQLite stores NUL in TEXT intact.

Real HIGHs survived: canonicalization sweep swapping directed edges
(edge_type filter missing), PG backend without `sample_for_dream` override
(3-slice sampling dead), hnswlib ef=64 vs PG 500.

## Sequence/timing pitfalls (concrete numbers)

- **engine-sha change + fail-closed preflight**: new git-based hash was
  `66de2458` vs image label `f4ecb993…` — if the new preflight had been
  deployed before the rebuild, the next mcp start would have been BLOCKED.
  Rule: deploy check binaries together with the image they verify.
- **Commit after build start**: `1ba43bc` (insights_keep_days default) landed
  after the build's `COPY . /build/` step → the image would carry a hash that
  no longer matches the live tree → second rebuild required. Rule: freeze the
  tree before starting the build.
- **compute.toml is rendered by the license-client** from the JWT claim —
  hand-edited `insights_keep_days = 30` vanished on the next render. The
  durable location is `compute_config.DEFAULTS["dream"]`.
- **present()-guard**: only keys actually in the toml may override
  constructor defaults, else a documented default shadows explicit caller
  values (broke the test suite's expectations).

## Latent bug found via pyright

`_phase_synthesis` used `_cc_get` at three lines but only imported `_cc_flag`
— a NameError that would fire the moment `stage_s_enabled=true`; masked
because the policy gate returned before those lines. LSP diagnostics
(reportUnboundVariable) surfaced it while wiring the synthesis model default.

## Test repair (P7)

- test_upside_down [15] demanded `cpp_dream_backend.py` (excised 93e6b91) —
  red since 2026-05-01, nobody noticed.
- tests/test_suite.py ran against the production SQLite DB (0 bytes since
  the PG migration) and its cleanup block connected to the PRODUCTION path —
  could delete real memories. Fixed: isolated tmp DB + hash backend, honest
  skips for semantic-only tests (hash cannot create connections).
- Result: 44/44 green — the first documented green run since 2026-04-21.

## Commit chain (mazemaker-pro unless noted)

be2ae07 (v2-stack quadlets: MemoryHigh sum 31.15→28.25G) · b530abb ([recall]
wiring) · b66fd5f (synthesis model + NameError) · f276260/eb8267d (mcp/worker
quadlet env) · 1c99921 (streaming arm + HNSW) · abf738c (DEGRADED warnings) ·
1dfb868 (test repair) · 9e321d6 (v2-stack: engine-sha/preflight/update/off) ·
146a157 (bridge dedup + insights retention) · 1c7849b (free-repo port) ·
2b92a6d (free CI trigger) · 1ba43bc (DEFAULTS fix).
