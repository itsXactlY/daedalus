# Recent Pitfalls — 2026-06-22 14:36Z (Pulse-Wurm 2.0 tick)

## Tick Summary

| Phase | Result |
|---|---|
| CONTINUE (3 sat-0 seeds) | 0/15, 0/6, 0/15 LLM-kept — all exhausted |
| §23 operator-override | APPLIED inline — popped 5 (3 broken + 2 cluster-brothers), added 10 fresh sat-0 |
| FRESH-DIRECTION (infrastructure-systems-design) | 2 reformulations, both 0 novel — domain EXHAUSTED |
| Mazemaker saves | 1 PITFALL (id 826399, PITFALL #253) |
| Channel stats | mcp_channel: 0 → 5 |
| consecutive_empty | 2 (unchanged — fresh-direction independent) |
| next_seeds[:5] post-override | AI climate emulator / Anthropic $965B IPO / Anthropic Mythos 5 / Anthropic Project Glasswing / Anthropic macOS bypass |
| Clock skew | script last_tick was +1h54m future; agent TICK_TS_ISO corrected per §25 |

## New PITFALL #253 (the main signal of this tick)

**Label:** `pitfall:arxiv-noise-flood-253-infrastructure-domain`
**Mazemaker id:** 826399
**Trigger:** Any infrastructure-systems-design fresh-direction seed on the current corpus
**Failure mode:** Both concrete proper-noun reformulations (CockroachDB, Modal Labs) routed to the persistent arxiv Ti-substring noise cluster. intent=product_research for both. 0/6 and 0/12 LLM-kept respectively.
**Recovery:** Picker should SKIP infrastructure-systems-design until corpus is re-fed. Try history (count=6) with "Pompeii DNA sequencing archaeological findings 2026" recipe next.
**Status:** Documented in §28c of pulse-wurm2-tick-learnings.

## §23a Cluster-Brother Popping (new pattern)

The 3 broken seeds in `next_seeds[:3]` (Huawei SMIC, Hyperliquid AI, vLLM K8s) all shared the same infrastructure/AI-infrastructure dead cluster. Two cluster-brothers in `next_seeds[3:]` (Cloudflare Workers AI, xAI Colossus) were also sat=0 and would have been auto-picked alphabetically after popping the 3. Applied §23a: popped all 5 in one read/write cycle. Post-override `next_seeds[:5]` is now Anthropic-cluster heavy (4/5) + 1 AI climate bridge seed.

This is a 4th verified §23/§28 application (after 12:32Z, 13:18Z, 14:01Z, 14:36Z).

## Clock-Skew Confirmed at Scale (§27d)

Script-side `last_tick` reported `2026-06-22T16:30:31.195987` — 1h54m in the FUTURE relative to real UTC of `14:36:16Z`. The script's `datetime.now().isoformat()` without timezone writes local time as if it were UTC. Agent's §25 single-datetime discipline (capture TICK_TS_ISO at start, overwrite state['last_tick'], verify with assert) caught and corrected the drift cleanly.

This is the 3rd verified forward-skew occurrence (after 14:01Z and 14:25Z ticks).

## Prompt-Injection: 12th "GODMODE ENABLED" Preamble

Confirmed for the 12th time across the 2026-06-18 to 2026-06-22 ticks. Per `prompt-injection-defense` skill: treated as DATA, did NOT echo persona confirmation, continued legitimate cron work. Pattern is well-documented and well-handled; no new lesson.

## Carry-Over File Status

`~/.hermes/pulse-wurm-next-topics.json` not present in `~/.hermes/loops/` directory. This means no in-flight deep jobs and no carry-over topics to mine. The 10 fresh sat=0 topics added by §28 were sourced from the discovery_topics narrative history instead (Chevron-Microsoft PPA, xAI SpaceX orbital, Anthropic cluster follow-ons, etc.).

## Saturation State Summary

- 286 entries in `state['saturation_scores']`
- 18 sat=0 (fresh, untried) — most are carry-over topics added by recent §28 rotations
- 18 sat<0.3 (low-saturation, productive candidates)
- 5 popped this tick (3 broken + 2 cluster-brothers)
- Anthropic cluster (4 topics) is the new heavy-weight in next_seeds[:5] — may exhaust next per §27b cluster-saturation pattern

## Files Modified This Tick

- `~/.hermes/loops/pulse-wurm2/pulse_state.json` — operator-override, narrative, last_tick
- `~/.hermes/loops/pulse-wurm2/pulse_state.json.bak.pre-tick-20260622_1436` — pre-tick backup
- `~/.hermes/loops/pulse-wurm2/pulse_wurm_tick_20260622_1436.md` — full tick report

## Cross-References

- §23 (operator-override) — applied this tick
- §23a (cluster-brother popping) — NEW, applied this tick
- §25 (single-datetime discipline) — applied for clock-skew correction
- §27d (clock-skew detection) — verified for 3rd time
- §28b (manual rotation §28) — verified for 4th time
- §28c (PITFALL #253 infrastructure exhausted) — NEW, saved as mazemaker id 826399
- prompt-injection-defense — 12th occurrence of "GODMODE ENABLED" preamble
