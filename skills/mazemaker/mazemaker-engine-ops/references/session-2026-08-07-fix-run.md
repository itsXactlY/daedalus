# Session 2026-08-07 — the P1-P10 fix run

Context: two deep audits (3-stream basis + 5-thesis inception) found the
whole degradation map; then a point-by-point repair run on the Pro pod.
All commits landed in mazemaker-pro, mazemaker-v2-stack/backend (repo root
is backend/, NOT the top dir — frontend/ and shared/ have their own .git),
and the free repo ~/projects/mazemaker.

## Fix list (commits)

- P1 deploy: installed.image_tag + desired.image_tag stamped 1.0.0-rtm.5;
  pod up; worker RSS 1.06 GB after arm vs 10.4 GB old / 12.9 GB pre-fix.
- P2 limits: MemoryHigh sum 31.15G -> 28.25G (dream 12/16->10/14 incl.
  PodmanArgs --memory, pgvector 9/10->8/9). be2ae07. Live via
  `systemctl --user set-property` (no restart).
- P3 compute.toml recall wiring: `present()` API + guards in
  mazemaker.py / dream_worker.py / __init__.py. b530abb.
- P4 synthesis: smollm3 default -> compute.toml [dream].synthesis_model;
  found + fixed the _phase_synthesis NameError. b66fd5f, f276260, eb8267d.
- P5 SQLite streaming: count_all + iter_for_gpu_arm (LE endian tag) +
  _ensure_hnsw_streaming + DAE streaming. 1c99921. Bit-exact verified.
- P6 observability: CPU-arm DEGRADED warning, rerank warn-once, remote
  recall warn-once. abf738c.
- P7 tests: sources list (cpp_dream_backend gone), tmp-DB isolation, real
  cleanup target, honest hash skips, streaming regression test. 1dfb868.
  First green suites since the PG migration: 44/44, 171/171, 5/5.
- P8 chain: git-based engine-sha (9e321d6, db432d8), fail-closed preflight,
  CDI strip in update, llm in off-list, selftest re-enabled (16 pass /
  3 fail: tag-drift, stale image vs new tree, historical log errors).
- P9 bridge dedup cache + prune_old_insights both backends. 146a157,
  1ba43bc (DEFAULTS default — the toml render is volatile).
- P10 free-repo port of the OOM healing (1c7849b) + CI main-v2 (2b92a6d).
- GPU-STRICT: MM_RECALL_GPU_STRICT=1 in both quadlets; gpu arm raises
  without CUDA; get_all brute-force refused. 9e85e3c, 0d64272.
- DeepSeek Stage C transport: MAZEMAKER_AFE_API_KEY -> Bearer header,
  repeat_penalty dropped in cloud mode (cloud APIs 400 on it). b0184d2.

## Latent bugs found live (class lessons)

- NREM _cc_get NameError: 02fda91 added compute.toml reads to NREM but the
  import only bound _cc_flag -> NREM was a silent no-op (crashed 4 s after
  "NREM decay scaled"), the cycle continued, stats printed. Seen in the
  worker journal as "NREM phase error: name '_cc_get' is not defined".
  Fixed 9b2747a; whole-file AST scan now guards the class.
- engine-sha.sh default pointed at the FREE repo: the fingerprint looked
  constant because the wrong tree never changed. Plus two bash traps:
  `while read` pipeline stage under set -euo pipefail silently empties the
  pipeline (constant "empty-input" hash); `printf "%s\0"` under dash does
  not emit NULs (xargs -0 concatenates everything into one bogus name).
  Content-sensitivity test (touch tracked file -> hash changes) catches
  all of these.
- compute.toml is RENDERED by the license-client from the JWT claim —
  hand-edited keys disappear on the next render. Defaults live in
  compute_config.DEFAULTS.
- First rebuild had a label from a mid-build tree (a commit landed during
  the build) -> fail-closed preflight would have blocked the mcp. Rule:
  freeze the tree, note the hash, build, verify label == hash, THEN deploy
  the new preflight/engine-sha together with the image.

## Worker journal evidence (new image, hash d437e7f9 -> 5bf76274)

- Arm: "streamed 215306 vectors onto cuda, decoded on-device (no host-side
  float conversion)"; RSS 1.06 GB after arm, 2.3-3.5 GB through cycle #1
  (old code: 10.4 GB after 5 min).
- Cycle #1 (36 min): NREM 26043+/190526-/635 pruned; REM 1374 bridges;
  Insight 29370 rows (first run, dedup cache empty), flush 219 s;
  AFE B=4 (Stage B works — spaCy fix 84fea5b/394e456); DAE 215261 vectors
  in 87.3 s; no OOM. Synthesis skipped (stage_s_enabled=false).
- Maintenance first run: pruned 2616 sessions + 150 derived:cluster.

## Benchmark model history (reconstructed, saved to mazemaker id=1154023)

- EverMemBench (02-05.07.): answerer/judge = qwen2.5:3b over local Ollama
  (run_arms_ollama.sh; evermembench JSONs gen_model=qwen2.5:3b); the
  qwen2.5:3b-128k tag was pulled in that window but not hard-proven as the
  run model. Later runs: deepseek cloud, then free-model rerun.
- R@5 0.9000 = skynet RETRIEVAL, no LLM (README.md:188). Inception
  champion = E95 R@5 0.8426; E97 broke R@10 0.9000 (history.tsv).
- AFE Stage C production model = DeepHermes-3-Llama-3-3B-Preview ("GOATED",
  decision id=1153300). qwen2.5-3b-instruct-q6_k + Bonsai-4B-Q2_0 were the
  failed experiments. ssp-lift 0.2667->0.3333 (17.05.) = qwen2.5:3b via the
  parallel API baker.
- No published benchmark value is reproducible under normal ops config:
  champion = skynet+colbert+dae+rerank; production ran hybrid/semantic with
  DAE weight 0.0 and compute.toml [recall] unread. Fixed by P3.
