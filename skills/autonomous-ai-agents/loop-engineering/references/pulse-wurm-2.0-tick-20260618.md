# Pulse-Wurm 2.0 — 2026-06-18 Tick

## Why this reference exists

This is a per-tick log captured when the bypass pattern was first exercised end-to-end. It documents the exact state, the exact novel URLs found, and the exact maze memory IDs. Useful for future audits of "how did the bypass pattern actually work" and for the next time the script returns 0.

## State at tick start

- `visited_urls`: 858
- `consecutive_empty`: 2 (one more empty tick would trigger rotation)
- `next_seeds`: Anthropic Claude 5 / Linux kernel 6.19 / Quantum computing error correction / Healthcare AI / Geothermal energy
- `saturation_scores`: 117 entries, range 0–63

## Tick script run (legacy GitHub path)

```
PULSE-WURM 2.0 DISCOVERY RUN
Already visited URLs: 858
Consecutive empty: 1
=== Seed: Anthropic Claude 5 release enterprise features 2026 ===
  Novel results: 0
=== Seed: Linux kernel 6.19 LTS security patches 2026 ===
  Novel results: 0
=== Seed: Quantum computing error correction milestones 2026 ===
  Novel results: 0
SUMMARY: 0 discoveries, 2 consecutive_empty
```

## Bypass run (MCP path)

| Seed | Candidates | Unvisited | Dig yield | Saved |
|---|---|---|---|---|
| Anthropic Claude 5 release enterprise features 2026 | 28 | 5 | 0 (CVE was bare stub) | 1 (CVE-2026-42530) |
| Linux kernel 6.19 LTS security patches 2026 | 23 | 0 | n/a | 0 |
| Quantum computing error correction milestones 2026 | (truncated in transport) | n/a | n/a | 0 |

## The 5 unvisited URLs from the Claude 5 seed

| URL | Source | Saved? | Why |
|---|---|---|---|
| https://www.cve.org/CVERecord?id=CVE-2026-42530 | lobsters | ✅ memory 808740 | Concrete security finding (nginx HTTP/3 QUIC UAF) |
| https://old.reddit.com/r/accelerate/comments/1nkwuy9/... | reddit | ❌ | r/accelerate compilation, off-topic for Claude 5 enterprise |
| https://old.reddit.com/r/MachineLearning/comments/1px1agd/... | reddit | ❌ | Year-in-review digest, low concrete signal |
| https://old.reddit.com/r/microsoft_365_copilot/comments/1tkio2o/... | reddit | ❌ | Copilot Cowork workflow post, off-topic |
| https://old.reddit.com/r/accelerate/comments/1m72puu/... | reddit | ❌ | r/accelerate weekly digest, off-topic |

**Lesson:** not every novel URL is worth saving to mazemaker. The 4 Reddit posts were genuinely unvisited but off-topic for the seed. Saving them would dilute the graph. The test is: does this URL *change the graph* (new fact, new decision, new action) or does it just *add another row*? Only save rows that move the graph.

## Pulse dig result on the CVE URL

```
run_id: c408d0dbdcc16048
rounds_completed: 0
candidates: []
fetches_attempted: 1
fetches_succeeded: 0
fetches_failed: 0
new_candidates: 0
```

**Reason:** cve.org record pages are bare stubs with no embedded links to related advisories, vendor patches, or exploit write-ups. The dig agent has nothing to follow. This is a known pattern: bare stub URLs (cve.org, NVD, single-comment GitHub issues) dig to 0. **Do not retry pulse_dig on these.** Save the bare discovery and move on.

## mazemaker_remember call

```python
mcp__mazemaker__mazemaker_remember(
    content="""Discovery: CVE-2026-42530 — Use-after-free in nginx HTTP/3 QUIC module. Found via pulse-wurm2 tick on 2026-06-18 (seed: Anthropic Claude 5 enterprise features 2026). nginx HTTP/3 is widely deployed as a reverse proxy; QUIC UAF could enable RCE or DoS against servers with HTTP/3 enabled. pulse_dig returned 0 follow-up URLs (cve.org bare record). Action: monitor nginx security advisories, patch nginx against CVE-2026-42530 if HTTP/3 enabled in production. Source seed surfaced this via 30d lookback, depth=deep.""",
    label="discovery:pulse-wurm-20260618_cve-nginx-quic"
)
# → {"id": 808740, "status": "stored"}
```

A first call with longer content (the original 8-line variant) returned `{"error": "Internal tool execution error"}`. Re-call with a tighter 6-line payload succeeded. This is consistent with prior runs — the error is transient and a retry usually works. **Always retry once on this specific error.**

## State update applied

```python
visited = visited + [5 new URLs]                    # 858 → 863
consecutive_empty = 0                                # reset (not +1) — bypass path found yield
saturation_scores["Anthropic Claude 5 ..."] = 0 + 5  # was 0
saturation_scores["Linux kernel 6.19 ..."] = 0 + 0   # stays 0
saturation_scores["Quantum computing ..."] = 0 + 0   # stays 0
next_seeds = sorted(saturation_scores.items(), key=lambda x: x[1])[:5]
# → Linux kernel / Quantum / Healthcare AI / Geothermal / AISI OpenAI
```

## Files touched

- `~/.hermes/loops/pulse-wurm2/pulse_state.json` — updated
- `~/.hermes/loops/pulse-wurm2/discoveries_20260618_pulse-wurm-mcp.json` — created
- `~/.hermes/loops/pulse-wurm2/discoveries.log` — appended
- mazemaker memory 808739 (tick observation) + 808740 (CVE finding)

## Reuse checklist for next bypass

- [ ] State has > 800 visited URLs (script likely exhausted)
- [ ] consecutive_empty is 1 or 2 (one more empty = rotation, so this tick's bypass is the last easy win)
- [ ] MCP pulse license valid (check `mcp__pulse__pulse_license`)
- [ ] MCP pulse health ok (check `mcp__pulse__pulse_health`)
- [ ] mazemaker reachable (one `mcp__mazemaker__mazemaker_recall` smoke test)
- [ ] Sort next_seeds by lowest saturation after update
- [ ] Always include 1–2 fresh rotation seeds in next_seeds
