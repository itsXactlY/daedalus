---
name: pulse-pro-deep-research
description: Use the Pulse pod for deep/wurm research, not the CLI.
---

# Pulse-Pro Deep Research (foreground / `/pulse` requests)

## Trigger conditions
- User invokes `/pulse <topic>` or asks for deep multi-source research.
- User passes `--wurm`, `--deep`, `--n <days>`, `--emit md`, or "find 11/10 / best / cutting-edge techniques".
- Any request that should fan out across Reddit/HN/ArXiv/GitHub/Polymarket/etc with ranked, scored output.

## THE DECOY TRAP (most important lesson)
There are TWO pulse installs. The first one an agent finds is usually the wrong one:

- `~/.hermes/skills/devops/pulse/scripts/pulse.py` = **Community build**.
  Looks complete (18-source table, `--crew`, `--iterative`) but on deep topics it
  returns **weak/decoys** output: ≈6 sources active, ArXiv noise clusters
  ("Theories Quantum Editing Technological"), **no `--wurm` support**.
- `/home/alca/projects/pulse-pro/` = **Pro pod**. License-gated, encrypted store,
  the Worm (recursive dig). This is what `--wurm` actually means and what the
  operator expects.

If a `/pulse` run returns <8 sources or ArXiv junk clusters, you hit the decoy
CLI. STOP and use the Pro pod flow below. The operator has explicitly flagged
"community pulse is a decoy — use pulse-pro".

## Pro pod architecture
- FastAPI pod in rootless Podman, port **8770**.
  Alive check: `curl -s -m 6 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8770/healthz`
  (expect 200; container `systemd-pulse-api` / `pulse-infra`).
- stdio MCP adapter (`pod/pulse_mcp_adapter.py`) proxies Hermes MCP → pod REST,
  but you can call the REST surface directly from terminal (simpler, no MCP
  timeout).
- Pro endpoints are license-gated: `/research`, `/research/start`,
  `/research/jobs/{id}`, `/research/jobs/{id}/result`, `/diagnostics`.
- Safe non-gated diagnostics: `/healthz`, `/license`, `/stats`, `/sources`,
  `/trending`, `/history`.

## DEEP / --wurm RUNS ARE ASYNC — NEVER SYNCHRONOUS
The adapter documents this: deep/wurm dives run **30–120 minutes**; the MCP
client kills calls at ~120s. Even from terminal, do NOT block on it. Use the job
flow:
1. START  → `POST /research/start`  → `{job_id, state:"running"}`
2. POLL   → `GET  /research/jobs/{job_id}` → phases + `heartbeat_age_seconds`
3. RESULT → `GET  /research/jobs/{job_id}/result` → ranked candidates (md/json)

Run is "stuck" ONLY if `state=="running"` AND `heartbeat_age_seconds` > ~45 min
with no new phase. Otherwise report job_id + pod logs.

## ⚠️ DEEP-WURM IS NON-FUNCTIONAL ON THIS POD (learned 2026-08-17)
Deep-wurm on this pod has two fatal flaws:
1. **Anchor filter is too aggressive** — drops 90%+ of candidates (e.g. 59/60,
   49/60, 55/60 across three parallel jobs). The strict topic lock kills even
   relevant results instead of keeping them for manual curation.
2. **API doesn't expose candidate content** — `/research/jobs/{job_id}/result`
   returns "Not Found" even when jobs complete with `state:"done"`. The job
   pipeline runs internally (search→anchor-filter→dig) but never surfaces
   candidates through the REST API.

**Workaround: use iterative mode instead.** It actually returns usable content:
```bash
# Single topic, sequential rounds — works with single-slot llama-server
python3 -m pulse_cli.research --topic "<query>" --depth deep --emit md --iterative --max-rounds 3 --no-llm
```
Iterative mode gave us 65 items across three runs (WebGL SIMD 21, WebGPU Compute 19, Shader Opt 25) with actual content. Crew mode times out on single-slot setups.

**Bottom line:** For niche/technical topics on this pod, skip deep-wurm entirely.
Use iterative mode or the community CLI build. Deep-wurm is a dead end here.

## Verified invocation recipe
```bash
# 1. start — field is "topic", NOT "query"
curl -s -m 30 -X POST http://127.0.0.1:8770/research/start \
  -H "Content-Type: application/json" \
  -d '{"topic":"<query>","depth":"deep","wurm":true,
       "max_wurm_rounds":6,"lookback_days":100,"emit":"md"}'
# → {"job_id":"f1853f1e5dfe","state":"running",...}

# 2. status (poll every few min)
curl -s -m 10 http://127.0.0.1:8770/research/jobs/f1853f1e5dfe \
  | python3 -m json.tool   # phases[], heartbeat_age_seconds, candidates

# 3. result (when state=="done")
curl -s -m 30 http://127.0.0.1:8770/research/jobs/f1853f1e5dfe/result
```

## OPERATOR OUTPUT PREFERENCE — FACTS ONLY, NO DESIGN (corrected 2026-08-08)
The operator wants `/pulse` work to be: **dig, curate, compile facts** — and STOP
there. Do NOT add a "Design für Mazemaker" layer, "next step for our stack",
prioritisation-as-design, or "what we should build" proposals on top of the
research. Quote: *"was für design? du sollst nur graben, kuratieren, fakten
zusammentragen!"*
- Deliverable shape = a curated fact inventory per category: for each item the
  paper/tool, what it actually is/does (from the abstract, not title-guessing),
  source/ID, relevance score, freshness. A one-line "kuratierte Einordnung
  (Befund)" is OK; design recommendations are not.
- It's fine to fetch abstracts (`<meta name="citation_abstract">`) to ground each
  fact — that IS curation, not design.

## Per-category parallel wurm (better than one broad seed)
A single broad `--deep --wurm` seed returns mostly ranking noise (Polymarket
volume skews rrf; arxiv Ti-substring junk). For a multi-facet question, launch
one focused wurm job PER category (`POST /research/start` ×N, all parallel) —
each anchored topic stays on-topic and the whole batch completes in minutes
(anchored worms plateau fast). Poll all job_ids, fetch each `/result`, then
curate per category with a junk filter (Ti-cluster, polymarket-non-agent,
epstein/jan-6/free-agent, wayback/donate/nitter, celebrity/sports noise).
Cross-reference the operator's `NO OLLAMA` / deepseek-curates directive — it
lives in `pulse-pro-pod-ops`.

## Flag → param mapping (operator uses CLI-style flags)
- `--wurm`     → `"wurm": true`   (recursive dig→re-seed→dig-deeper until plateau)
- `--deep`     → `"depth": "deep"`
- `--n 100`    → `"lookback_days": 100`   (the `-n` is the time window, NOT a count)
- `--emit md`  → `"emit": "md"`
- `max_wurm_rounds` caps outer rounds (1–6; default 3).

## Pitfalls
- **Field name**: body key is `topic`, not `query` — wrong key → 422
  `{"detail":[{"type":"missing","loc":["body","topic"]...}]}`.
- **Symlink warning**: `scripts/lib/` must NOT be a symlink to
  `pod/pulse_community/lib` — agents writing through it destroy work via git
  checkout. Verified absent in pulse-pro; safe to spawn agents.
- **"11/10" is NOT pulse's job**: pulse returns ranked candidates + sources +
  scores, not a curated quality verdict. The operator draws the "11/10" ranking
  from the result. Don't promise pulse will "deliver 11/10 techniques" — it
  delivers the evidence ratnest; the critic is the operator.
- **Correction pattern this session**: I first ran the community CLI; operator
  slammed `!!!!!!!!!!!!!!!!` and pointed at pulse-pro. Default to the pod on any
  deep/wurm request — don't try the community CLI first.

## LLM backend — VERIFY BEFORE TRUSTING OUTPUT (learned 2026-08-04)
The pod's planner + relevance filter need an LLM. It speaks **Ollama protocol
only** (`/api/tags`, `/api/generate`) and is wired (via quadlet env
`~/.config/containers/systemd/pulse-api.container`) to a local **llama.cpp**
model (Gemma-4-E4B Q8) through an Ollama-compat proxy on `:11435`. If that
chain is broken the pod either (a) falls back to a remote cloud model that
returns off-topic noise, or (b) the filter drops everything. **Symptom of a
broken backend:** dig rounds show `+0` growth, or the LLM filter keeps 0 of
hundreds. Always probe the real model path before blaming the search:
```bash
curl -s http://127.0.0.1:11435/api/tags        # should list Gemma
curl -s http://127.0.0.1:8080/v1/models          # llama.cpp must be up
```
If `8080` is empty the model is still loading — wait, don't run the job.
The bridge pattern lives in the `ollama-protocol-bridge` skill.

## `llm_filter:false` — avoid the filter collapse
The post-rank LLM relevance filter (`_llm_filter_candidates` in app.py) reuses
the same model. An "aggressive/uncensored" model often returns `none` and the
pod drops the ENTIRE pool (seen: 103 candidates → kept 0). **Fix:** start the
job with `"llm_filter": false` and curate the raw candidates yourself. The
worm dig is what matters; the filter is optional cleanup.

## Wurm drift + the `topic_anchor` patch (2026-08-04)
Stock `WormCrawler` (`scripts/lib/worm.py`) follows links from seed pages and
**drifts**: topic "GPU" → "GPU rental prices" (Polymarket) → "compute finance"
→ Reddit/AITA. A strict `topic_anchor` lock was added (filters harvested URLs
AND fetched page content against the topic's keywords + an allow-list of
tech-doc hosts). It is compiled into the pod image — verify it survived a
rebuild: `podman exec systemd-pulse-api grep -c topic_anchor /app/lib/worm.py`
(must be >0). If a deep run returns relationship-drama/Polymarket junk, the
anchor was lost in a rebuild — re-apply and redeploy.

## Quadlet-patch gotchas (cost a full debug cycle)
- The **real** quadlet is `~/.config/containers/systemd/pulse-api.container`.
  `pod/quadlet/pulse-api.container` in the repo is only a TEMPLATE — edits there
  do nothing.
- After editing the real quadlet: `systemctl --user daemon-reload`,
  `podman rm -f systemd-pulse-api`, `systemctl --user start pulse-api.service`.
  `systemctl restart` is NOT enough — the old container persists with stale env
  (verified: showed old `qwen2.5:3b` env after restart, only `rm`+`start` fixed it).

## MCP visibility prerequisite
The pod's MCP tools (`pulse_research*` etc.) are only in the agent's visible
toolset if `tools.tool_search.enabled = off` in `~/.hermes/config.yaml`.
Otherwise MCP tools are DEFERRED (stripped from the hot list, replaced by
`tool_search`/`tool_call` bridge tools) and you must steer them. Call the REST
surface directly from terminal to bypass this entirely — simpler and no timeout.

## See Also
- `ollama-protocol-bridge` — bridge llama.cpp (OpenAI-compat) to an Ollama-only service.
- `pulse-wurm-recon-tick` — the cron/tick variant (multi-wave autonomous runs).
- `pulse-wurm2-tick-learnings` — tick-specific learnings + hijack registry.
- Community skill `devops/pulse` is a DECORABLE decoy for deep runs; use pod.
