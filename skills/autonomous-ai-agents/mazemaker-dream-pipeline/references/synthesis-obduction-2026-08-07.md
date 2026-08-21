# Synthesis-Obduktion & Dream-Timeline — Audit 2026-08-07

Forensic detail behind the SKILL.md defect registry. All timestamps container-local (host was +2h).

## The 4/4 synthesis runs (journalctl --user -u mazemaker-dream-worker)

| # | Run (container time) | PID | Evidence | Result |
|---|---|---|---|---|
| 1 | 19:10:11 | 201189 | `WARNING SYNTHESIS: window 86400s exceeds the derived:cluster TTL of 300s — Clamping`; AFE: 8 sources, 3 facts (A=3 C=0) | 30 seen, 0 synthesised, 0 proposals |
| 2 | 19:31:48 | 238399 | Insight: communities=9603 bridges=45194 **insights=29639** derived=50, **flush=244.06s**; AFE: 1 source, 0 facts | 30 seen, 0 synthesised, 0 proposals |
| 3 | 20:21:27 | 351426 | Insight flush=275.54s; AFE: 0 sources; run took **8.4 s** → `_model_present` fast-path (missing model → immediate `return []`, no HTTP) | 30 seen, **2 synthesised**, 0 proposals |
| 4 | 21:04:08 | 503953 | new compute_config code deployed: `[LEGACY] MAZEMAKER_SYNTHESIS_ENABLED ... IGNORED`; compute.toml `stage_s_enabled=false` | phase skipped (no summary line) |

Also visible: worker killed with status=137 (OOM/SIGKILL) between runs; container-file mtimes 22:25 (AFTER runs 1–3) → during those runs `MAZEMAKER_SYNTHESIS_MODEL` was NOT set → dream_engine.py:3556 default `alibayram/smollm3` → smollm3 absent from host ollama (16 models installed, verified) → `_model_present()=False`.

## Root-cause chain (all four runs)
1. **Window vs TTL:** MAZEMAKER_SYNTHESIS_WINDOW_S=86400 (quadlet env; mcp.container still has it) vs derived:cluster TTL 300 s → anchors enumerated from `dream_insights` but their `derived:cluster` memories already pruned → `_drop_no_derived`.
2. **min_facts gate:** `min_facts=3` (dream_engine `_cc_get("dream","synthesis_min_facts",3)`) against members with label `%::afe::C%`; Stage C off by default (`MAZEMAKER_AFE_LLM_FALLBACK=0`, dream_engine.py:3012) → whole corpus carries ~123 Stage-C facts (8082 Stage-A fragments) → 0–2 clusters pass.
3. **Model default:** `llm_model = env("MAZEMAKER_SYNTHESIS_MODEL", "alibayram/smollm3")` (dream_engine.py:3555–3557, unchanged since 41ad53a). 932cb76 (07.08. 19:41) fixed only `synthesis._DEFAULT_MODEL` → qwen2.5:3b; the engine line still overrides it. Worker survives only via container env; mcp pod has no such env.
4. **Never succeeded anywhere:** journalctl keeps exactly 4 `SYNTHESIS:` lines ever, none >0; `logs/` and `benchmarks/logs/` contain no Stage-S lines. The "ssp-lift 2704 facts 0.2667→0.3333" comment in synthesis.py refers to a direct `synthesize_cluster` bench call on the host (ollama present), NOT the engine phase. Engine phase additionally was `skipped: no_store` on PG until 0c4ed60 (store unwrap).

## Residual bugs after the 07.08. fixes
- dream_engine.py:3556 still defaults to smollm3 (fix 932cb76 missed the caller).
- compute.toml dead keys: `synthesis_model`, `synthesis_min_conf`, `synthesis_min_evidence`, `synthesis_timeout_s`, `[afe].model` — written by license-client, read by nobody (engine reads env only).
- mcp.container: `MAZEMAKER_SYNTHESIS_ENABLED=1` + `WINDOW_S=86400` still set.
- `stage_s_enabled=false` in compute.toml → synthesis disabled by policy until flipped on mazemaker.dev.
- Embedding-parse failure in synthesis (`fact_embeds=[]`, dream_engine.py:3652) silently sets `similarity_mean=1.0` → INFLATES confidence.
- Bridge-insight rows in `_phase_insights` (dream_engine.py:2475–2487) have no anchor/dedup → 29.6k rows/cycle ≈ 8.5M/day at ~95% duplication; `dream_insights` has no retention (only `dream_sessions` pruned).

## RAM measurements (from commit bodies, pod was down during audit)
- 94cdc80: RssAnon 10.4 GB at 97.8% CPU inside `Mazemaker.__init__` → `_load_from_store` `_graph_nodes` (embedding+content for all 193k memories, ~7 GB retained) → fixed with lazy_graph → 1.43 GB.
- d8fa3d6: embedding-worker 2392 MiB (BGE-M3 over HTTP) vs dream worker 5668 MiB (own BGE-M3 + ColBERT); card 0.9 GB free, 850 HTTP embed calls that day; mcp+worker each ~2.5 GB recall tensor.
- Post-cycle survivors: `_gpu._emb_tensor` (~790 MB VRAM @ 193k×1024 float32) + `_gpu._ids/_labels/_contents` lists (~1–2 GB RAM), `_hnsw_index`, GPU PPR adjacency (deliberate, rebuild every 10 cycles), ColBERT own model copy (colbert_helper.py:18 — remaining unaddressed hog), `globals()["_RECALL_ONLY_SERVER"]` (references same `_gpu` object, no copy). `torch.cuda.empty_cache()` per cycle (271dc82) frees only caching-allocator blocks.

## Git timeline (introduction commits)
- 2026-04-17 0748c86 — Dream Engine (NREM/REM/Insight)
- 2026-05-08 d227d17 — `keep_seconds=5*60` derived-cluster prune (5-min TTL); EMBED_CLIENT_ONLY guard
- 2026-05-08 b0ffc3f — dream_worker.py born; a4e587f socket embed server; 61ddb3f GPU PPR
- 2026-05-09 afec238 — mixed sampling, defaults 100→2000 / 50→800
- 2026-05-10 3c63f96 — 6h anchor rotation
- **2026-05-17 41ad53a — SYNTHESIS introduced: window 3600 s against pre-existing 5-min TTL (mismatch born with the phase); smollm3 default; min_facts=3**
- 2026-05-17 aa9f2ab — DAE first-cycle (cycle_index==0) deliberately
- 2026-05-18 c99d038/d482451 — AFE Stage C + Stage S wiring
- 2026-05-20 66157d6 — HttpEmbeddingBackend WITHOUT env dispatch (EMBED_BACKEND=http dead value until d8fa3d6, 74 days)
- 2026-05-21 59b65d4 — synthesis HTTP-first transport
- 2026-06-03 0c4ed60 — synthesis/DAE revived on PG (store unwrap)
- 2026-08-05 66a70fb — cycle interval from compute.toml (was hardcoded 5 s → 5004 cycles/day, 9.1M conn_history + 1.6M dream_insights rows/day)
- 2026-08-06 24da5ab/eab7a9f — PG supersedes writer + curated-only gate (25k→515k edges in 90 min before gate)
- 2026-08-07 38a1848 — conn_history flood stopped (24k identical rows/cycle)
- 2026-08-07 baf369f/94cdc80/02fda91 — TTL/window unified with clamp (300 s); _graph_nodes RAM fix; compute.toml policy (stage_s_enabled=false)
- 2026-08-07 d8fa3d6/52e8e15 — EMBED_BACKEND=http dispatch fixed; recall server decoupled
- 2026-08-07 932cb76 — synthesis.py default → qwen2.5:3b (engine caller untouched)

## except-inventory highlights (dream_engine.py, 54 sites)
Silent deaths: 1718 (think_ids pass — killed a 1M-edge graph on 2026-07-09 via zombie decay), 1900 (whole maintenance block), 1958 (supersedes metadata fail → whole phase), 2652/2654 (derived-cluster dedup fail → duplicate memories), 2710 (derived_from edges), 2793/2859 (theme fallback), 3652 (embed parse → confidence inflation), 3694/3701 (synthesis_of edges). Loud/fine: phase-level warning+exc_info handlers at 1903/2131/2272/2510/2960/3423/3717.
