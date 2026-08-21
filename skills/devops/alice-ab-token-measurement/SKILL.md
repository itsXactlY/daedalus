---
name: alice-ab-token-measurement
description: "Measure real token cost of Alice-Router delegation vs without (A/B harness) — subprocess `hermes chat -q -v`, config-toggle route_mcp_through_router, parse STDERR for API calls + alice-server.log for router tokens. Includes the regex/stderr/idempotency pitfalls that silently zero out Alice numbers."
category: devops
version: 1.0
tags: [alice, router, ab-test, tokens, measurement, llama-server, hermes]
priority: high
---

# Alice A/B Token Measurement — MIT vs OHNE Router

## Trigger
- Need to prove whether Alice-Router delegation actually saves main-model tokens
- User asks "was kostet der Router wirklich" / "mis mal mit und ohne alice"
- Prototype reference: `~/projects/alice-ab-proto/alice_ab_proto.py` (proven 2026-08-11)

## What the harness does
Runs the SAME query set twice in subprocesses:
- Arm A (OHNE): `route_mcp_through_router: false` → main model talks to pod directly
- Arm B (MIT):  `route_mcp_through_router: true`  → Alice bridge consults :8801 first
Then compares main-model API tokens (the PAID ones, deepseek) vs Alice tokens (LOCAL, free).

Subprocess command (the only reliable way — isolates each arm in its own session):
```bash
hermes chat -q -v --quiet --pass-session-id "query" 2>>stderr.log
```
`-q` = one-shot answer, `-v` = verbose, `--quiet` = suppress banner, `--pass-session-id` = keep session stable.

## Measurement sources (WHERE the numbers live)
1. **Main-model API tokens**: parse `API call #N: ... in=... out=... total=...` lines.
   - WITH `-v` these lines go to **STDERR**, NOT stdout. If you capture only stdout you get 0 calls.
   - They do NOT land in `~/.hermes/logs/agent.log` — agent.log only logs the MAIN (parent) session, not subprocesses. Never read agent.log for subprocess costs.
2. **Alice tokens**: parse `~/.hermes/logs/alice-server.log` (llama-server stdout):
   ```
   ... prompt eval time =      22.75 ms /   107 tokens (...)
   ...        eval time =     541.37 ms /    61 tokens (...)
   ```
   Count `launch_slot` / task lines with a REQUEST, sum prompt+eval tokens.
   Small `prompt eval` values are NORMAL (KV cache: only new query tokens evaluated) — not a bug.

## THE THREE PITFALLS (all hit 2026-08-11, all silently produced zeros)
1. **Regex: llama-server pads with MULTIPLE spaces after `=`** — `prompt eval time =      22.75 ms /   107 tokens` (6 spaces!).
   `r"prompt eval time = [\d.]+ ms /\s*(\d+) tokens"` NEVER matches → Alice always 0.
   Fix: `r"prompt eval time = +\s*([\d.]+) ms / +\s*(\d+) tokens"` — and then group(2) is the TOKEN count, group(1) is ms. If you forget the group shift you sum milliseconds into the token column.
2. **Subprocess API lines are on STDERR** — `hermes chat` prints logs to stdout but debug/API lines to stderr. Split capture: `>>stdout.log 2>>stderr.log`, parse API_RE on stderr.
3. **Config toggle must be IDEMPOTENT** — if Arm A already set `false` and the toggle function raises when the target equals current, the first arm fails before measuring. Read current value, only write when different.

## Procedure
```bash
cd ~/projects/alice-ab-proto
# 1. sanity: alice must be live (health check, NOT systemd status — see below)
curl -s --max-time 5 http://127.0.0.1:8801/health   # {"status":"ok"}
# 2. run both arms (script toggles config between them, parses both logs)
python3 alice_ab_proto.py
```

## Result interpretation (measured 2026-08-11, 5 queries, deepseek-v4-flash)
```
Arm                  main-total  calls  alice  elapsed
OHNE Alice             246755      12      0    84.8s
MIT Alice              244336      12    953    90.0s
Main-Model Delta:      +2419 Tokens (+1.0%)
```
- **Alice saves ~1% on PAID main tokens** — the scope contract only delegates the TOOL-TYPE decision (query+limit come from parent), so the parent generates almost the same output anyway.
- Real value of Alice: LOCAL decision tokens (953 local vs what deepseek would charge for the same routing thought) + preventing recall_multi angle over-generation + consistency.
- If you want real main-token savings, extend the scope so Alice writes the QUERIES too, then re-measure.

## Production check: is the SERVICE running the right model? (bug found 2026-08-11)
After any model rollback (e.g. v4.3 → v4.2), the systemd service file is NOT auto-updated — it kept pointing at the overfitted `alice_qwen_lora_merged-Q4_K_S-v4.3.gguf` and crashed 467× with "couldn't bind HTTP server socket, port 8801" while a manual nohup llama-server held the port. Health check said OK (manual process) while the service was dead-looping.
```bash
systemctl --user list-units | grep alice
journalctl --user -u alice-router | grep -c "restart counter"   # hundreds = stale config loop
grep -n "gguf" ~/.config/systemd/user/alice-router.service      # verify model version
```
Fix: patch service to v4.2.gguf (backup first: `cp alice-router.service alice-router.service.bak-v43`), `systemctl --user daemon-reload`, keep the manual process running OR restart service. After ANY rollback: patch the service file in the same step as swapping the running model.

## Pitfalls
- Don't read agent.log for subprocess costs — only the parent session logs there.
- Don't trust `route_mcp_through_router: true` in config alone — verify the LLM actually calls the UNPREFIXED tool name (system prompt can force mcp__ names, bypassing Alice). See skill `alice-routing-debugging`.
- A single-space regex on llama-server logs yields silent zeros — always test the regex against a real log line before trusting output.
- Correlate Alice log timestamps with the run window: count only NEW lines (record line_count before the run, parse from there).
