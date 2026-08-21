# AFE DeepSeek-Bake — one-off whole-corpus Stage C catch-up (2026-08-07)

Goal: run the real A→B→C chain over ALL long conversational sources ONCE with
deepseek-v4-flash as the Stage C extractor, so the corpus returns to a real
production state; afterwards the local llama path takes over again (the
`mazemaker-afe-window.service` keeps its local settings — this bake is a
manual one-off, never the default).

## Why this exists

Stage B/C historically never really ran on the production corpus: B=0 for
months (spaCy was missing from the image, fixed 84fea5b/394e456), C produced
filler with the small local models (Bonsai/qwen) or was gated off. The engine
phases now work; the one-off bake catches the corpus up with a strong cloud
extractor.

## Transport (afe.py, commit b0184d2)

`_stage_c_completion` is OpenAI-compatible HTTP. Two modes:
- Local (no `MAZEMAKER_AFE_API_KEY`): Bearer-less, sends the llama.cpp-native
  `repeat_penalty` + frequency/presence penalties (llama-server/ollama).
- Cloud (`MAZEMAKER_AFE_API_KEY` set): sends `Authorization: Bearer <key>`,
  DROPS `repeat_penalty` (cloud APIs 400 on it), keeps frequency/presence.

Determinism env (operator directive — no invented facts):
- `MAZEMAKER_AFE_LLM_REASONING=0` — hard off; auto-detect only matches
  "hermes" in the model name, but force it so a model rename can't flip it.
- `MAZEMAKER_AFE_LLM_TEMP=0.0` — deterministic; cloud models do not
  degenerate at temp 0 the way the local 3B did.

## Parallel bake mechanics

The engine phase supports sharding + idempotency:
- `MAZEMAKER_AFE_WORKER_ID` / `MAZEMAKER_AFE_N_WORKERS` → round-robin shard
  `id % N`, so N parallel workers split the corpus without contention.
- `meta('afe_processed_ids')` tracks processed source ids — restarts and
  loop rounds never re-process a source.
- `MAZEMAKER_AFE_SKIP_CHUNKS=1` — skip ColBERT chunk memories (duplicate the
  session content, 2-3x the LLM calls).
- Each worker loops `--phase afe --once` until its log shows `AFE: 0 sources`.

Do NOT use `benchmarks/bake_afe_stageC_api.py` for production: it targets the
`mm10m_bench` DB with an `::api::C` label namespace (bench ablation), not the
production corpus.

## Recipe

1. Key file (0600), read at runtime by the bake script — never hardcode:
   ```bash
   python3 - <<'EOF'
   import yaml, os
   cfg = yaml.safe_load(open('/home/alca/.hermes/config.yaml'))
   key = cfg['providers']['deepseek']['api_key']
   open('/home/alca/.mazemaker/afe-deepseek.env', 'w').write(f'MAZEMAKER_AFE_API_KEY={key}\n')
   os.chmod('/home/alca/.mazemaker/afe-deepseek.env', 0o600)
   EOF
   ```
2. Bake workers (per worker: `MAZEMAKER_AFE_WORKER_ID=0..N-1`,
   `MAZEMAKER_AFE_N_WORKERS=N`), mirroring `mazemaker-afe-window.service`
   podman flags (pod, GPU device, mounts, `--secret mazemaker_pg_password`,
   `EMBED_BACKEND=http`, `MM_RECALL_GPU_STRICT=1`) plus:
   ```
   --env MAZEMAKER_AFE_LLM_FALLBACK=1
   --env MAZEMAKER_AFE_LLM_URL=https://api.deepseek.com/v1/chat/completions
   --env MAZEMAKER_AFE_API_KEY=<from env-file>
   --env MAZEMAKER_AFE_MODEL=deepseek-v4-flash
   --env MAZEMAKER_AFE_LLM_REASONING=0
   --env MAZEMAKER_AFE_LLM_TEMP=0.0
   --env MAZEMAKER_AFE_SESSION_MAX_CHARS=32000
   --env MAZEMAKER_AFE_MAX_PER_CYCLE=3000
   --env MAZEMAKER_AFE_WORKER_ID=$wid
   --env MAZEMAKER_AFE_N_WORKERS=$N
   --env MAZEMAKER_AFE_SKIP_CHUNKS=1
   localhost/mazemaker-v2-mcp:gpu  python3 -c "import sys; sys.path.insert(0,'/app'); sys.argv=['dream_worker','--phase','afe','--once','--log-level','INFO']; from dream_worker import main; main()"
   ```
   Worker loop: run → grep log for `AFE: 0 sources` → done, else sleep 5 →
   next round. Scale N by API budget; 8 workers × 61k sources ≈ hours.
3. Prereqs: the image must contain the afe.py cloud transport (rebuild +
   retag + preflight chain — see engine-sha section in the main SKILL.md);
   the deepseek env-file must exist; the bake runs against the PRODUCTION
   DB via db.env + the pod secret.

## Verification (before trusting the bake)

- Transport: mock HTTP server captures the request — with the key: Bearer
  header present, `repeat_penalty` ABSENT; without: `repeat_penalty` present,
  no Authorization.
- Determinism: with `REASONING=0` + `TEMP=0.0`, the captured body has
  `temperature == 0.0` and NO system/deep-think message, exactly one user
  message, plain-path stop `["\n\n"]`.
- `_reasoning_mode("deepseek-v4-flash")` is False in auto mode.
- Progress: watch `SELECT count(*) FROM memories WHERE label LIKE '%::afe::C%'`
  grow; workers' logs show `AFE: <sources> sources, <n> facts (A=.. B=.. C=..)`.

## After the bake

`mazemaker-afe-window.service` stays local (DeepHermes, llama-server sidecar,
`MAZEMAKER_AFE_LLM_REASONING=1`) — the bake is one-off by design. Do not
leave the cloud env in the quadlets; the afe-window unit is the ongoing
path.
