---
name: pulse-pro-research
description: "Drive pulse-pro Pod deep/wurm; avoid llm_filter collapse."
category: devops
---

# pulse-pro Pod research (this host)

Production research engine for this host. Source `/home/alca/projects/pulse-pro`,
served as a license-gated FastAPI app on `http://127.0.0.1:8770` (rootless
Podman, encrypted store, the Worm). A stdio MCP adapter
(`pod/pulse_mcp_adapter.py`) proxies Hermes MCP → REST. The Community CLI in the
`pulse` skill dir is the WEAK twin — use the Pod.

## Why not the Community CLI
Same query: Community CLI → 6 sources, ArXiv noise, no wurm. Pro-Pod
`/research/start` + wurm → 483 candidates over 6 recursive dig rounds. The
`wurm` mode (dig → re-seed → dig deeper) is the whole point and does NOT exist
in the CLI.

## Async flow (MANDATORY for deep / --wurm)
Deep/wurm dives run 30–120 min; the MCP client kills synchronous calls at ~120s.
Never call research synchronously — use the job flow:
```
POST /research/start  {topic, depth, wurm, max_wurm_rounds, lookback_days, llm_filter, n}
   → {job_id, state:"running"}
GET  /research/jobs/{job_id}         # state / phases[] / heartbeat_age_seconds
GET  /research/jobs/{job_id}/result  # full ranked candidates when state=done
```
Start it, then **accompany the run** with a backgrounded poll-loop: poll every
~120s, extract candidates per phase, deliver the result. The operator explicitly
demanded "begleite den vollen run" — do not hand off and disappear.

## Field gotchas (burned real runs)
- **Use `topic`, NOT `query`.** Schema rejects `query` with 422 `Field required: topic`.
- **Set `llm_filter: false`.** The Pod's Ollama on/off-topic filter COLLAPSES:
  - Run A (wurm 6, filter ON): 483 aggregated → kept 7 / dropped 476. All 7 were
    GitHub-Copilot *localization* pages — off-topic, wrong cluster survived.
  - Run B (narrower seed, filter ON): search 44, `dig-1` growth 0% → kept 0 /
    dropped 44 → returned 0.
  - With `llm_filter:false` the raw ranked candidates survive and YOU do the
    relevance call.
- `max_wurm_rounds`: 1–6. Watch `growth_pct` per dig phase; if it drops below
  ~20% the dig plateaued or drifted off-topic — stop.
- Recovery after a bad filter is IMPOSSIBLE via API: `/lineage/{run_id}` returns
  only `edges`, `/history` was empty. Capture candidates DURING the run (poll
  loop), not post-hoc.

## Reusable start
```bash
curl -s -X POST http://127.0.0.1:8770/research/start -H "Content-Type: application/json" \
  -d '{"topic":"...","depth":"deep","wurm":true,"max_wurm_rounds":6,
       "lookback_days":100,"llm_filter":false,"n":50}' > /tmp/job.json
JOB=$(python3 -c "import json;print(json.load(open('/tmp/job.json'))['job_id'])")
```
Then run a poll-loop on `$JOB` (see `hermes-mcp-visibility` for the poll
pattern; adapt result paths to `/home/alca/.hermes/pulse-${JOB}-*.md`).

## Phase shapes (good run)
```
search-start
search            candidates: 43
dig-1  new: 87  growth_pct: 202.3
dig-2  new: 97  growth_pct: 111.5
dig-6  new: 14  growth_pct: 15.7   <- plateau, stop
```
