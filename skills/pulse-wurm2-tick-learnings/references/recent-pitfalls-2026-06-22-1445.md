# Tick 14 — 2026-06-22 14:45Z — Detailed log

## Tick summary
- 2 mazemaker saves (826405 simonwillison.net Fable 5 primary source + 826406 r/singularity 641-comment thread)
- 1 fresh-direction failure (bio-health frontier research 2026 — count=2 lowest non-AI/ML, §15 PITFALL)
- 3 broken seeds popped via §23/§23a (Anthropic $965B IPO + Howard Lutnick + macOS-brother)
- 5 fresh sat=0 seeds added
- 3 in-flight deep jobs polled (4fd823023597 done, df9ba9bf9bc3 + fd7be8fb1527 still running)
- consecutive_empty: 0 → 0
- 7 mcp_channel calls (3 continue pulse_search + 1 fresh-direction pulse_search + 3 deep job status)

## New patterns observed (already patched into SKILL.md)

### §32 — Carry-over file key naming bug (NEW pitfall)
- The actual key in `~/.hermes/pulse-wurm-next-topics.json` is `in_flight_deep_jobs_at_tick_end`, NOT `in_flight_deep_jobs` (which the §22/§29 examples use).
- Caught because my initial read used `in_flight_deep_jobs` and got `{}` — re-read with correct key revealed 3 in-flight deep jobs from prior tick.
- The §29 code example was patched to use the correct key.

### §20 — Pulse_search-bypass SECOND verification (Glasswing)
- Verified on `Anthropic Project Glasswing cyberdefender Mythos 5 deployment government collaboration 2026` (Mythos-themed seed)
- `pulse_research` (carry-over 262d555a0bd0) returned 100% PM
- `pulse_search` (this tick) returned 3/15 substantive non-PM URLs (Reddit cluster + simonwillison.net primary source)
- Saved 2 mazemaker memories from the bypass result
- Mechanism confirmed: raw source-weighted candidates WITHOUT dig-following or LLM-filter rerank

### §14 — Saturation value restoration bug pattern
- bio-health already had sat=3 in state (from prior attempts)
- I almost set it to 0 on 0-novel fresh-direction result
- Caught via assertion, restored to 3
- Per §14: "DO NOT increment further on 0-novel — leave existing value alone"
- Added clarification that `sat["<seed>"] = 0.0` is WRONG when the key already has a non-zero value

### §24 — Single-call timeout vs full outage distinction
- 1 timeout (Lutnick) + 2 successful pulse_search calls = NOT a full outage
- The 2 successful calls count as 2 mcp_channel calls
- The timed-out seed is broken for this tick but should be confirmed via carry-over before popping per §23
- DO NOT apply full-outage consecutive_empty += 1
- DO NOT skip fresh-direction phase

## Specific findings

### Fable 5 / Mythos 5 export control directive (June 13, 2026)
- US government (citing national security authorities) ordered Anthropic to suspend all access to Fable 5 and Mythos 5 by any foreign national (even within US, including Anthropic employees)
- Net effect: Anthropic disabled Fable 5 + Mythos 5 for ALL customers
- Coverage:
  - simonwillison.net 2026-06-13 (primary source, Anthropic's official statement)
  - r/singularity 1u4cxr8 (641 comments, 2026-06-13)
  - r/ClaudeAI 1u4oc1z (19 comments, "What really pulled Fable 5, and why it's bigger than Claude")
  - r/ClaudeCode 1u4pqyz (5 comments, "I Spent the Night Interviewing the AI the Government Just Recalled")
  - lucumr.pocoo.org 2026-06-13 (Armin Ronacher: "Dangerous Technology For Americans Only" — schadenfreude analysis)
  - simonwillison.net 2026-06-15 (Axios behind-the-scenes reporting: "They screwed us: Personality clashes sent Anthropic's models offline" — Logan Graham + Dave Orr + Nic)

## PITFALLS confirmed this tick
1. **#251 at pulse_search level**: Anthropic IPO 2/2 PM at pulse_search (counter-pattern from deep_research does NOT bypass at pulse_search level)
2. **§20 pulse_search-bypass for Glasswing** (second domain verification)
3. **§15 abstract-academic seed** for bio-health (0/15 first attempt)
4. **§26b LOW-SCALE mode** for Khanmigo deep job (1/267, kept item is stale 2023 OpenAI blog)

## In-flight deep jobs (will poll next tick)
- `df9ba9bf9bc3` (theregister Mythos macOS) — dig-4 complete (32 candidates, 71% growth), heartbeat 8s (FRESH)
- `fd7be8fb1527` (OpenAI Trusted Access for Cyber) — dig-3 complete (66 candidates, 81% growth), heartbeat 373s

## Recommendation for next tick
- PHASE A: Poll the 2 in-flight deep jobs
- PHASE A: Continue on `next_seeds[:5]`:
  - AI climate model emulator (concrete reformulation: Aurora / Pangu-Weather)
  - Anthropic Mythos 5 Tom Brown (try pulse_search — bypass proven)
  - Apple Swift in kernel (cluster-saturation risk per §27b)
  - Chevron-Microsoft Project Kilby PPA (high-yield §27 pattern)
  - CockroachDB distributed SQL (PITFALL #253 risk)
- PHASE B: Retry bio-health with §15a AI/ML bridge (AlphaFold 3 / AI drug discovery)
- Fallback: history with "Pompeii DNA sequencing" recipe
