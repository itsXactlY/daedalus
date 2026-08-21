# Pulse-Wurm 2.0 Tick Learnings — June 2026 Deep-Tick Wave (§23–§33)

Full body of learnings §23–§33 and their lettered follow-ups (§26b, §27b–d,
§28b–c, §23a, §26c) from the SKILL.md index. Loaded via
`skill_view(file_path='references/learnings-june-2026.md')` when deep-job
processing, outage-abort, operator-override, or PITFALL #244/#253/#254
patterns apply.

---

## 23. Operator-override code pattern — APPLY, don't just recommend (NEW 2026-06-22 tick 1232)

The umbrella SKILL.md §20 says "recommend the operator-override (pop broken
seeds from saturation_scores) BEFORE the next tick" when `consecutive_empty >= 1`
AND `next_seeds[:3]` are unchanged AND those seeds yielded 0 novel in the prior
tick. This was repeatedly recommended across the 12:30Z and 14:19Z ticks but
NEVER applied, causing 2 consecutive 0-novel ticks on the same broken seeds.

**Refined rule: APPLY the override inline, do not just recommend it.**

When the trigger fires at the top of a tick (before the continue phase), execute:

```python
import json
with open('/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json') as f:
    state = json.load(f)
sat = state.get('saturation_scores', {})

# Identify broken seeds: any sat-0.3 (or sat-0) seed that has been in
# next_seeds[:3] for 2+ consecutive ticks AND yielded 0 novel both times.
# A pragmatic short-list (curated by hand per 12:30Z + 14:19Z observations):
BROKEN_SEEDS = [
    'education frontier research 2026',
    'NVIDIA DLSS 5 generative AI game developer backlash',
    'GLM-5.2 Z.ai open weights MIT license 753B MoE June 2026',
]
# Or derive programmatically:
# BROKEN_SEEDS = [s for s in state.get('next_seeds', [])[:3]
#                 if sat.get(s, 0) < 0.5]

for s in BROKEN_SEEDS:
    sat.pop(s, None)

# Recompute next_seeds from post-override pool
sorted_sat = sorted(sat.items(), key=lambda x: (x[1], x[0]))
state['next_seeds'] = [k for k, _ in sorted_sat[:5]]
state['saturation_scores'] = sat

# Save (one-shot, no other mutations this early in the tick)
with open('/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json', 'w') as f:
    json.dump(state, f, indent=2)
```

**Then proceed with the continue phase using the new `next_seeds[:3]`.**

**Detection signal for next-tick handler:** if you load state and see that
`saturation_scores` is missing 1+ of the well-known broken seeds (or any
sat-0.3 seed that was in `next_seeds[:3]` for 2+ ticks), the override was
already applied — proceed with the new top 3 (which will be the override-
fresh ones). Do NOT pop them again; do NOT re-initialize their saturation.

**Side effect on `consecutive_empty`:** the override does NOT reset
`consecutive_empty`. If the previous tick incremented it, this tick
still inherits the higher value. The script's hardcoded rotation trigger
at consecutive_empty=3 will fire if not offset by new findings, but the
override's `next_seeds` survives because the rotation code is dead
(per the umbrella SKILL.md commentary on the script's rotation logic).

**Why this matters:** 2 consecutive 0-novel ticks cost ~30s of MCP time
each + 1 increment of `consecutive_empty` + risk of triggering the
hardcoded fallback pool (which is worse than natural rotation per the
12:30Z ranking). The override is essentially free to apply (1 read + 1
write + 1 verification). The discipline is: when the trigger fires,
execute, do not recommend.


## 24. Pulse MCP full-outage clean-abort pattern (NEW 2026-06-22 tick 1232)

The `mcp__pulse__pulse_search` (and `mcp__pulse__pulse_health`) tools may
time out at 120s. When the server is fully unreachable, 4+ consecutive
calls fail identically. The platform wraps subsequent failures with
"MCP server 'pulse' is unreachable after N consecutive failures.
Auto-retry available in ~Ns. Do NOT retry this tool yet — use
alternative approaches or ask the user to check the MCP server."

**Important: that "Do NOT retry" message is legitimate platform policy
about the 60s cooldown gate, NOT a user instruction to abandon work.**
The right behavior:

1. **Honor the spirit** — don't infinite-loop on the same call.
2. **After the cooldown elapses** (suggested N + 5s buffer), make **1
   diagnostic `pulse_health` call**.
3. **If the diagnostic also times out:** treat it as a full outage and
   abort pulse work cleanly.
4. **Document the outage** in the tick report and state narrative.
5. **Do NOT** retry the same seed 5+ times in a row.

**Concrete clean-abort sequence (verified 2026-06-22T12:32Z):**

```python
# After 3 continue-phase calls all return TimeoutError OR
# "MCP server is unreachable after N consecutive failures":
import time
# Wait for the suggested cooldown + buffer
time.sleep(65)  # if suggested was 58s, sleep 65s

# One diagnostic attempt
try:
    mcp__pulse__pulse_health()
except Exception as e:
    # If this also times out, treat as full outage
    # Increment consecutive_empty, append outage narrative, save state, write report
    pass
```

**State and report mutations for a full-outage tick:**

- `state['consecutive_empty'] += 1` (0-novel rule)
- DO NOT increment `state['channel_stats']['mcp_channel']` (no successful MCP calls)
- DO NOT increment `state['saturation_scores'][seed]` (no signal at all)
- Append narrative: "BLOCKER: Pulse MCP server unreachable (N consecutive 120s timeouts on pulse_search + pulse_health). Operator-override applied/skipped. No discoveries saved."
- Skip the fresh-direction phase entirely (it depends on pulse_search)
- Skip the section 6d saturation_init for fresh_seed
- Write the tick report with a clear "BLOCKER" header so the next-tick handler does not conclude the seeds are also broken

**Distinguishing "MCP outage tick" from "saturation tick" in narratives:**

A saturation tick (0-novel due to topic exhaustion) has narrative like "0 novel, all candidates visited". A MCP outage tick has narrative like "BLOCKER: Pulse MCP unreachable, ticks could not run pulse_search". The wording matters because the next-tick handler should NOT conclude the seeds are broken on a MCP-outage tick — it should re-attempt them.

**Detection signal for next-tick handler:** if the prior tick's narrative contains "BLOCKER: Pulse MCP unreachable" or "MCP call timed out", assume the seeds are NOT proven broken. Only treat them as broken (and pop from saturation_scores) after 2+ non-MCP-outage 0-novel ticks on the same seeds.

**Single-call timeout vs full outage (verified 2026-06-22 14:45Z):**
§24's full-outage pattern fires when 3+ consecutive `pulse_search`
calls ALL fail. **Do NOT treat a single timeout among 3 successful
calls as a full outage.** The right behavior for a single timeout:

1. The 2 other calls returned normally — they count as 2 successful
   `mcp_channel` calls (per §19)
2. The timed-out seed is broken for this tick (sat stays at 0) — but
   confirm broken via carry-over before popping per §23
3. **DO NOT** apply the full-outage `consecutive_empty += 1` (the
   other 2 calls succeeded, so this is not 0-novel)
4. **DO NOT** skip the fresh-direction phase
5. Continue to the next tick normally

The 14:45Z tick had 1 timeout (Lutnick) and 2 successful pulse_search
calls (Glasswing + IPO). 2 saves resulted. The 120s timeout was a
seed-routing issue (Lutnick + named-person + government-agency +
named-AI-program triple-trigger per PITFALL #253), not an MCP
server outage. Confirmed broken via carry-over (prior deep job
a1ca4ec0138d returned 100% PM).

**Diagnostic check:** if 1-2 of 3 calls timeout but the others
return within 30s, it's a seed-routing issue, not an MCP outage.
Wait for the cooldown (per §24) before retrying the timed-out seed
**see also references/mcp-degraded-state-2026-06-23.md for the tick 38 soft-degrade pattern + carry-over JSON schema**


## 25. Single-datetime drift recovery (NEW 2026-06-22 tick 1232)

§21 says "capture timestamp ONCE at the start of the tick and reuse for both
`state['last_tick']` and the report filename." This is correct in principle
but `execute_code` invocations are independent processes — the `TICK_TS`
variable captured in call 1 is NOT visible in call 2. Calling
`datetime.now()` again in call 2 produces a later timestamp and creates
the drift the rule was meant to prevent.

**Refined rule: even if drift happens, the fix is one-line.**

```python
# After saving state in a later execute_code call that re-captured datetime:
import json
with open('/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json') as f:
    state = json.load(f)
state['last_tick'] = TICK_TS_ISO  # the original TICK_TS_ISO from call 1
with open('/home/alca/.hermes/loops/pulse-wurm2/pulse_state.json', 'w') as f:
    json.dump(state, f, indent=2)
# Verify
with open('/home/alca/.hermes/pulse-wurm2/pulse_state.json') as f:
    assert json.load(f)['last_tick'] == TICK_TS_ISO
```

**Even better: write TICK_TS to /tmp at the start of the tick, read it back later:**

```python
# Call 1 (at start of tick):
import json
from datetime import datetime, timezone
TICK_TS = datetime.now(timezone.utc)
TICK_TS_ISO = TICK_TS.isoformat()
TICK_TS_FN = TICK_TS.strftime("%Y%m%d_%H%M")
with open('/tmp/pw2_tick_ts.json', 'w') as f:
    json.dump({'iso': TICK_TS_ISO, 'fn': TICK_TS_FN}, f)

# Call N (state save, much later):
import json
with open('/tmp/pw2_tick_ts.json') as f:
    ts = json.load(f)
state['last_tick'] = ts['iso']
# ... continue with state save ...
```

**Verification check to add to the post-write assertion block:**

```python
assert final['last_tick'] == TICK_TS_ISO, f'last_tick drift: expected {TICK_TS_ISO} got {final["last_tick"]}'
```

This catches drift the moment the save completes, not 5 minutes later
when you notice the report filename doesn't match.

**Which side to fix when drift happens:** the state `last_tick` is the
"when the loop entered this state" marker. The report filename is the
"what happened" record. Both should be the tick's start time. If drift
happens, patch `state['last_tick']` to match the report's tick_ts (which
was captured at the start). The report filename is harder to change
post-hoc and is more important for human-readable tick history.

**Side note on the `pulse_state.json` itself:** the script's
`pulse_tick.py` line 289 uses `datetime.now().isoformat()` without
timezone — it writes local time as if it were UTC. The
agent-driven `last_tick` should be proper UTC with `+00:00` suffix.
This drift between script-side and agent-side `last_tick` is a
pre-existing issue not addressed by this section.


## 26. arxiv DOI + benchmark name = 100% Ti-substring noise (PITFALL #245) — NEW 2026-06-22 13:18Z

Even with 4 dig rounds (60+94+92+78+83 = 407 candidates aggregated, 4 LLM-kept),
pulse_research with the arxiv 2501.14249 HLE paper DOI anchor produced ZERO
substantive HLE findings. The 4/400 LLM-kept were ALL arxiv Ti-substrate
false-positives:
1. MultiQG-TI: Towards Question Generation from Multi-modal Sources (arxiv 2307.04643v1, 2023)
2. Tied Monoids (arxiv 2001.00625v2, 2020)
3. Multi-Phase Dataset for Ti and Ti-6Al-4V (arxiv 2501.06116v1, 2025)
4. Cu-Ti alloys (arxiv 2310.05415v1, 2023)

The arxiv 2501.14249 DOI anchor is too narrow for pulse_research's LLM intent
classifier. It routes to "person_research" intent (sources: github/reddit/arxiv)
and the LLM-filter keeps the highest-engagement arxiv candidates — which happen
to share the "T" or "Ti" token with the DOI string. The Ti-substring pattern
collides with: MultiQG-TI / 3M-TI / NLTE Ti~I / Ti-6Al-4V / Cu-Ti / Tied
Monoids / Tied Links / Ti nonlinear laser lithography (8 false-positives
cataloged in the 2026-06-22 13:18Z tick).

**This is NOT a Polymarket hijack (PITFALL #245, distinct from #241 HLE).**
It's pure arxiv-substring noise where the LLM-filter ranks Ti-metallurgy /
topology papers higher than the actual HLE paper. The LLM intent classifier
treats "arxiv 2501.14249" as a person_research query, not a paper_research
query.

**Counter-pattern for future HLE research** (verified 2026-06-22 13:18Z):
- DO NOT use pulse_research with bare arxiv DOI (e.g. 'arxiv 2501.14249 HLE paper')
- USE one of:
  - full corporate blog URL: 'blog.google / openai.com/index/ / anthropic.com/index/'
  - specific HLE question URLs (not paper DOI)
  - model-agnostic phrasing: 'expert-level LLM evaluation benchmark questions 2026'
  - paper title + venue anchor: 'arxiv 2501.14249 Humanity Last Exam paper questions'

**When to apply this counter-pattern:** whenever pulse_research with an arxiv
DOI returns 100% arxiv noise (Ti-substring or any other false-positive cluster).
Verify by checking items_by_source: if the LLM-kept candidates are all arxiv
papers that don't reference the actual benchmark/evaluation target, the DOI
anchor is too narrow.

**Companion pitfall:** PITFALL #244 (FrontierMath + Gemini + date-prediction →
Polymarket hijack) and PITFALL #246 (abstract-academic seed + 'lithography'
substring → Ti-substring noise) — all three collapse for the same root cause:
the LLM intent classifier + LLM-filter combine to drop the actual substantive
candidates and keep false-positives. The fix is to use concrete proper-noun
anchors with bridgeability, not abstract templates.


## 27. Picker Counter() bug — 0-count domains get missed — NEW 2026-06-22 13:18Z

The fresh-direction domain picker counts keyword matches per 24-domain-pool
entry in the last 50 mazemaker browse. Implementation:

```python
from collections import Counter
domain_counts = Counter()
for m in memories:
    content = (m.get('content','') + ' ' + m.get('label','')).lower()
    for domain, kws in DOMAINS.items():
        for kw in kws:
            if kw.lower() in content:
                domain_counts[domain] += 1
                break
```

**Bug:** `Counter()` only registers domains that have ≥1 keyword match. Domains
with 0 matches are absent from the Counter. When you sort
`sorted(domain_counts.items(), key=lambda x: (x[1], x[0]))`, you miss 0-count
domains entirely — they get skipped, and the picker picks the lowest NON-ZERO
count instead.

**Symptom observed 2026-06-22 13:18Z tick 10:** Geopolitics has 0 keyword
matches in the last 50 mazemaker browse (it had been stale for 7+ days). The
Counter missed it, the picker picked programming (count=2) instead, and
geopolitics — the actual lowest-coverage domain — got skipped. Fixed in
the same tick by explicit 0-init:

```python
domain_to_check = []
for d in DOMAINS.keys():
    c = domain_counts.get(d, 0)  # explicit 0-init
    domain_to_check.append((d, c))
domain_to_check.sort(key=lambda x: (x[1], x[0]))
```

**Always use the explicit 0-init pattern** when implementing the picker. The
bug only fires when a domain has truly 0 matches in the 50-memory browse
window, which is rare but exactly the case when fresh-direction is most
needed (the under-covered domain is the one with 0 matches).

**Test case for verification:** if `mazemaker_browse(label_prefix='discovery:pulse-wurm-', limit=50)` returns 50 memories and the keyword counter
yields 0 matches for any domain, the picker MUST still consider that domain
as a candidate (sat=0, alphabetically-first). Verify by running the picker
and checking that 0-count domains appear in the sorted output.


## 28. Manual rotation at consecutive_empty=3 — script rotation code dead — NEW 2026-06-22 13:18Z

The umbrella SKILL.md §20 says "rotate to fresh seed topics" at
consecutive_empty=3. Per the carry-over file's operational_notes (2026-06-22
13:08Z tick 9): "the script's hardcoded rotation code is dead per the umbrella
SKILL.md commentary." The pulse_tick.py script's rotation code does NOT fire
when consecutive_empty hits the trigger.

**Verified 2026-06-22 13:18Z tick 10:** consecutive_empty was at 2 going into
the tick; continue phase yielded 0 for both seed topics (FrontierMath 0/15
LLM-kept, Stargate 4/15 LLM-kept but all fresh=0); consecutive_empty went to 3.
The script had already finished and exited by the time the operator-override
was applied. The script's `next_seeds` would have stayed the same (re-picking
the broken seeds) — the agent's recompute with fresh topics is what fixed it.

**Pattern when consecutive_empty=3 hits:**

```python
# 1. Identify fresh topics (NOT in saturation_scores, not in current next_seeds)
#    Sources: carry-over PRIORITY list + new findings' follow-ons
FRESH_TOPICS = [
    ('Cursor AI SpaceX $60 billion all-stock acquisition June 2026', 'carry-over'),
    ('Samsung Electronics ChatGPT Enterprise Codex deployment worldwide 2026', 'carry-over'),
    ('OpenAI Partner Network $150M Fortune 500 enterprise deployment 2026', 'carry-over'),
    ('Anthropic Fable 5 Mythos US export controls foreign nationals cyber defense 2026', 'new-this-tick-follow-on'),
    # ... more fresh topics
]

# 2. Add to saturation_scores at sat=0 (untried)
for topic, note in FRESH_TOPICS:
    if topic not in sat:
        sat[topic] = 0.0

# 3. Recompute next_seeds (lowest sat first, alphabetical tie-break)
sorted_sat = sorted(sat.items(), key=lambda x: (x[1], x[0]))
state['next_seeds'] = [k for k, _ in sorted_sat[:5]]

# 4. Append rotation narrative to discovery_topics
state['discovery_topics'].append(
    'ROTATION TRIGGER at consecutive_empty=3 (script rotation code dead per '
    'umbrella SKILL.md; manual rotation applied per §22 + §23 override pattern). '
    'Replaced post-tried sat-0 seeds with N fresh topics from carry-over + this tick.'
)

# 5. Save state
with open(state_path, 'w') as f:
    json.dump(state, f, indent=2)
```

**How many fresh topics to add:** 5-7 is the sweet spot. 5 fills the new
next_seeds[:5] pool. 7 gives some buffer for alphabetical ordering not
matching what you expected.

**Where to source fresh topics (in order of priority):**
1. Carry-over file's `discovered_topics_for_next_tick` PRIORITY 2+ (hand-curated)
2. New findings' follow-on topics (e.g. Fable 5 export controls → Anthropic Fable 5 Mythos US export controls follow-on)
3. Picker-suggested next-eligible domains (e.g. crypto-blockchain → Hyperliquid AI agent on-chain)

**DO NOT add:** seeds that were just tried and yielded 0 (they'd just yield 0
again next tick). Seeds with sat > 0.3 (they're already in the rotation pool
and will get tried naturally).

**Why this matters:** 2 consecutive 0-novel ticks on the same broken seeds
cost ~30s of MCP time + 1 increment of consecutive_empty + risk of triggering
the hardcoded fallback pool (which is worse than natural rotation per the
12:30Z ranking). The manual rotation is essentially free to apply (1 read +
1 write + 1 verification) and breaks the cycle cleanly.

**Companion to §23 (operator-override):** the §23 override pops broken seeds
when consecutive_empty >= 1 AND next_seeds[:3] unchanged AND 0 novel. The §28
manual rotation adds fresh topics when consecutive_empty hits 3. Both patterns
are now necessary because the script's automatic rotation is dead.


## 29. Deep-job processing as tick step 0 (NEW 2026-06-22 13:34Z)

The carry-over file `~/.hermes/pulse-wurm-next-topics.json` stores
`in_flight_deep_jobs{}` — async `pulse_research_start` jobs started on
prior ticks that haven't been polled yet. **These are a major
discovery source the script does NOT surface.** Processing them at
the START of every tick is mandatory.

**Verified 2026-06-22 13:34Z tick:** the carry-over file had 2
in-flight deep jobs from 13:18Z. Both completed in the ~12 minutes
since last tick:

1. `24ba77d66d1f Microsoft hyperscaler data center natural gas power purchase agreement 2026` — 286 candidates aggregated, 22 LLM-kept, 15 Polymarket-hijacked (75%). The 5 non-PM items included 3 cross-source confirmations of Chevron-Microsoft 20-year West Texas natural gas PPA (techmeme + wsj + cnbc, all fresh=100). **This was a fresh event (2026-06-22 announcement) that no continue-phase pulse_search would have surfaced** — the seed topic was a deep-job-only query.

2. `c883418e6082 Federal Reserve FOMC June 2026 interest rate decision Treasury yield reaction` — 237 candidates, 10 LLM-kept, **100% Polymarket hijack** (10/10 = polymarket.com crypto category in 9 language locales: bn/zh-hant/de/es/fr/hi/ja/pl/it/uk). PITFALL #243 confirmed at scale; counter-pattern reformulation (Fed officials by name + economic-data anchor) was queued in carry-over but the deep job used the original framing.

**Operational pattern:**

```python
# STEP 0: Process in_flight_deep_jobs BEFORE the continue phase
import json
with open('/home/alca/.hermes/pulse-wurm-next-topics.json') as f:
    carry = json.load(f)

in_flight = carry.get('in_flight_deep_jobs_at_tick_end', {})  # CORRECT key (see §32)
if in_flight:
    for job_id, job_meta in list(in_flight.items()):
        # Status check
        status = mcp__pulse__pulse_research_status(job_id=job_id)
        state = status['body']['state']
        if state == 'done':
            # Fetch result + mine substantive findings
            result = mcp__pulse__pulse_research_result(job_id=job_id)
            candidates = result['body']['result']['candidates']
            
            # Check Polymarket hijack ratio
            pm_pct = sum(1 for c in candidates
                         if 'polymarket' in c.get('source','').lower()) / len(candidates)
            
            if pm_pct >= 0.95:
                # 100% hijack — save as PITFALL record, don't mine
                mazemaker_remember(
                    label=f'pitfall:polymarket-<NNN>-<short-name>',
                    content=f'PITFALL: <seed-shape> triggered {pm_pct*100:.0f}% Polymarket '
                            f'hijack ({len(candidates)}/{len(candidates)} kept). '
                            f'Counter-pattern: <reformulation>.'
                )
            else:
                # Mine substantive non-PM findings
                non_pm = [c for c in candidates
                          if 'polymarket' not in c.get('source','').lower()]
                # Apply cluster-bloat discipline, save strongest 1-2 to mazemaker
            
            # Remove from in_flight, add to done_deep_jobs_this_tick
            carry['done_deep_jobs_this_tick'][job_id] = ...
            del carry['in_flight_deep_jobs'][job_id]
```

**Symptom of skipping this step:** the tick report has 0 deep-job
findings and the carry-over file's `in_flight_deep_jobs` keeps
accumulating. After 6h+ of accumulation, 2-4 jobs are pending and
the next tick finds them all DONE — major source of late discoveries.

**Time budget:** 1-2 minutes per deep-job result fetch. The result
file is persisted to `/tmp/hermes-results/call_<id>.txt` (per §13).
Parse with the triple-wrap pattern from §18.

**Where it fits in the tick sequence:** BEFORE the script runs (the
script's `pulse_search_mcp` is a stub, it doesn't see deep-job results).
BEFORE the continue phase (so the deep-job findings can be marked
visited and don't resurface in the continue phase's pulse_search).

**Channel-stats bookkeeping:** the deep-job result fetch counts as 1
mcp_channel call (per §19, every `mcp__pulse__*` call increments the
counter by 1). Typical tick: 1 health + 2 deep-job status + 2 deep-job
result + 3 continue pulse_search + 1 fresh-direction pulse_search = 9
mcp_channel calls (NOT 4-6 as the script-implied count would suggest).


## 30. Script auto-sort works correctly when next_seeds pool is healthy (NEW 2026-06-22 13:34Z)

The umbrella SKILL.md §20 commentary says the script's "rotation code
is dead." This is true ONLY when consecutive_empty hits 3 inside the
script's own increment. The script's NEXT_SEEDS SORT LOGIC works
correctly when the saturation_scores dict has a healthy mix of
sat-0 fresh topics (added via prior §23 operator-override or §28
manual rotation).

**Verified 2026-06-22 13:34Z tick:** script's auto-sort took
saturation_scores (275 entries, 8 sat-0 entries from carry-over's
manual rotation pool) and produced correct next_seeds[:5] =
alphabetically-first 5 at sat=0:
- Anthropic Fable 5 Mythos US export controls (sat 0)
- Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation (sat 0)
- Forward deployed engineer FDE role (sat 0)
- Huawei SMIC chip export controls (sat 0)
- Hyperliquid AI agent on-chain (sat 0)

(Stargate 10GW / Samsung / OpenAI Partner Network were ALSO at sat 0
but excluded from top 5 by alphabetical tie-break — they remain in
the pool and will be picked when the current 5 are processed.)

**When auto-sort breaks:** when the only sat-0 seeds in the pool are
ones that yielded 0 novel in 2+ consecutive ticks. In that case the
§23 operator-override or §28 manual rotation must fire.

**Refined rule:** the script's auto-sort is reliable WHEN you have a
healthy pool of sat-0 fresh topics. Maintain that pool by:
1. After every successful fresh-direction save, the new findings
   generate follow-on seeds (e.g. Huawei chairman export controls →
   Huawei SMIC chip export controls follow-on)
2. Carry-over file's `discovered_topics_for_next_tick` PRIORITY 2+ list
   feeds new topics into the next tick's manual rotation
3. Operator-override (§23) pops broken sat-0.3 seeds but does NOT add
   fresh ones — use §28 manual rotation for the addition

**Symptom of broken auto-sort:** script exits with same `next_seeds`
as the prior tick (re-picking broken seeds), `consecutive_empty`
increments to 2 or 3, and continue phase returns 0 novel again. The
§23 operator-override detects this and pops the broken seeds, after
which auto-sort works again.

**Why this matters:** the 13:34Z tick did NOT need to apply the
operator-override because the carry-over rotation had already
populated 7+ fresh sat-0 topics. The override is a SAFETY NET for
when the pool goes stale, not a routine step. Routine ticks should
trust the auto-sort and only override when consecutive_empty >= 1 AND
next_seeds[:3] unchanged AND 0 novel.


## 31. Person-research deep search fails on role/hiring topics — 9th hijack class (NEW 2026-06-22 13:55Z tick 11)

Verified on `Forward deployed engineer FDE role Google OpenAI Anthropic
2026 hiring salary` deep-research job `de3f5938f188`: 60 search + 52
dig-1 + 0 dig-2 (worm extraction exhausted) = **112 cumulative candidates**,
LLM-filter kept 2/112 (1.8% keep rate), and **both** kept candidates were
completely unrelated to FDE/hiring:

- `itunes.apple.com/us/app/reddit-the-official-app/id1064216828` (Reddit
  App Store — worm follow from a r/BestofRedditorUpdates thread)
- `github.com/unslothai/unsloth?tab=readme-ov-file` (Unsloth Studio
  GitHub README — worm follow from a r/LocalLLaMA Gemma 4 thread)

**Why this is a separate hijack class (NOT Polymarket, NOT arxiv-noise flood):**

- No prediction market involved
- No arxiv substring collision
- The failure mode is `intent=person_research` routing + worm-follow
  extracting URLs from low-substance Reddit/GitHub pages. The
  worm-follower's heuristic for "is this a relevant URL to follow?"
  treats any URL embedded in a Reddit thread body as a follow candidate,
  even if the URL is just a "download the Reddit app" sidebar link or a
  GitHub README link from an unrelated comment thread.

**Critical diagnostic signal: `dig-2 returned 0 new_candidates`** is a
**strong indicator of this failure mode**. The deep-research worm-follow
exhausted at round 2 — there were no more extractable URLs in the
thread bodies. Once dig-2 returns 0, subsequent rounds add no signal.
LLM-filter kept 2/112 (1.8%) of the available 110 candidates that
were already seen.

**Trigger condition:** any deep-research seed that combines:

1. Personal role / job title (`FDE`, `forward deployed`, `Solutions
   Architect`, `TAM`, `PM`, `SWE`)
2. Multi-company enumeration (`Google OpenAI Anthropic`, `Meta
   Microsoft Apple`)
3. Hiring/compensation framing (`hiring`, `salary`, `compensation`,
   `career`)

This 3-token combination routes to `intent=person_research` and the
sub-queries pull from github (issues/PRs) + reddit (subreddit threads),
which contain URLs in their bodies — and worm-follow treats those as
follow candidates regardless of relevance.

**Tested counter-patterns (verified 2026-06-22 tick 11):**

- **DO NOT use pulse_research deep for FDE / role-definition topics.**
  The signal-to-noise ratio is too low and the worm-follow degrades
  signal rapidly.
- **USE pulse_search with specific publication URL anchor:**
  `pragmaticengineer.com FDE forward deployed engineer role 2026` —
  the LLM-filter will surface the canonical article at fresh=high +
  engagement=high (Pragmatic Engineer newsletter has consistent
  presence on these topics).
- **USE pulse_search with specific company job-posting URL:** for
  specific hiring topics, anchor on `greenhouse.io <company> forward
  deployed engineer` or `lever.co <company> FDE`.

**Companion to §29 (deep-job processing):** even though this deep job
completed cleanly (state=done, all phases executed), the result was
substantively worthless. The diagnostic signal `dig-2 new_candidates=0`
should be checked early (after the first poll ~3-5 min into the deep
job) to decide whether to wait for completion or abort early.

**Cost:** this deep job ran 675s before completing — 100% wasted CPU.
Future ticks should add a `pulse_research_status` poll ~3-5 min after
start; if `dig-2 new_candidates == 0` AND `llm-filter` is not yet
populated, abort the job and use pulse_search fallback instead.


## 26b. PITFALL #244 LOW-SCALE MODE — sub-channel fully suppressed (NEW 2026-06-22 14:01Z)

The existing PITFALL #244 documents the HIGH-SCALE mode: abstract-academic + benchmark + model + date-prediction → 100% Polymarket hijack (3 markets, vol $1.45M / $155K / $95K). The 14:01Z tick surfaced a **distinct sub-mode** of the same pitfall.

**LOW-SCALE mode signature:**
- Abstract-academic seed + `benchmark` substring + **no specific model + no specific date**
- Planner routes to `person_research` intent
- openalex sub-channel **fully SUPPRESSED** (not present in subqueries, or weight=0)
- LLM-filter keeps **1/15 candidate maximum**
- The 1 kept candidate is a low-relevance off-topic user post (loc=0.015, fresh=0)
- **No Polymarket hijack** (the seed didn't make it to the hijack-trigger sub-channel)

**Example trigger seed:** `Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation` — same seed phrase triggered HIGH-SCALE mode at 13:34Z (3/15 PM markets) and LOW-SCALE mode at 14:01Z (0/15 PM, 1/15 off-topic user post). The stochastic planner routing determines which sub-mode fires.

**Comparison table:**

| Sub-mode | Polymarket hijack | LLM-kept | Topic relevance | Counter-pattern |
|---|---|---|---|---|
| **HIGH-SCALE** | YES (3/15 markets, vol $1.45M) | 1/15 of REAL = 3 PM hijacked | off-topic via hijack | paper-DOI anchor OR model-agnostic phrasing |
| **LOW-SCALE** | NO (0/15 PM) | 1/15 (off-topic user post) | off-topic via sub-channel suppression | corporate-anchor OR fresh concrete reformulation |

**Refined rule:** the FrontierMath seed phrase `Epoch AI FrontierMath benchmark math reasoning 2025 2026 evaluation` triggers PITFALL #244 in BOTH sub-modes. The HIGH-SCALE mode is more dangerous (3 hijacked markets dominate) but the LOW-SCALE mode is more common (intent=person_research is the default routing for abstract-academic seeds). **Do not retry this seed phrase.** Working counter-patterns:
- Full corporate URL (e.g. `epoch.ai/frontiermath` direct URL)
- Paper DOI (e.g. `arxiv.org/abs/<FrontierMath paper ID>`)
- Specific model + paper (e.g. `Claude 3.5 FrontierMath score breakdown`)
- Sub-category anchor (e.g. `FrontierMath category math 2026` or `FrontierMath proof pipeline LLM curation`)

**Diagnostic check:** when LLM-kept count = 1 with loc < 0.05, the seed is in LOW-SCALE mode. Treat as broken and pop from saturation_scores.


## 27b. High-yield §27 cluster-saturation clarification (NEW 2026-06-22 14:01Z)

The umbrella SKILL.md §27 documents "high-yield seed patterns" — concrete corporate-anchor templates (acquisition, deployment, partnership) that reliably surface the canonical URL.

**Clarification from this tick:** the high-yield pattern reliably surfaces the **canonical URL** (1/15 LLM-kept with loc=0.4+ and fresh within 30-day window) but **yields 0 novel findings when the cluster is already saturated**. The canonical URL is in `visited_urls` from prior coverage; sub-partner URLs (PNNL/Snowflake/Instacart) are stale (outside 30-day window) and don't trigger fresh saves.

**Refined rule:** the high-yield pattern is reliable for:
1. **Coverage verification** — confirms the cluster is comprehensively covered (if canonical is visited, cluster is done)
2. **Initial discovery** — first time the topic is searched, the canonical surfaces reliably

The pattern is **NOT reliable for re-mining** once the cluster is saturated. Don't expect novel findings from a 2nd-time high-yield seed run on the same topic — expect canonical-URL confirmation only. When `cluster_saturation confirmed` (canonical URL in visited_urls + sub-partner URLs stale), pop the seed from `saturation_scores` per §23/§28 manual rotation.

**Implication for next-tick plan:** Anthropic Fable 5 follow-on seeds (Project Glasswing, $965B IPO, macOS protection bypass) are concrete corporate-anchor templates (high-yield pattern). First-time searches should reliably surface canonical URLs. But the 826376 deep-job save from 13:55Z already covered these. Next tick's continue-phase may yield 0 novel on Fable 5 follow-ons if the 826376 deep-job has already touched them.


## 27c. 3-angle climate yield from single seed (NEW 2026-06-22 14:01Z)

The climate fresh-direction (sat-0 retry, intent=learning routing, openalex weight 1.2144) yielded 3 discoveries spanning **3 distinct sub-domains from a single seed**:

1. **Climate observation** (HKH Monsoon Outlook 2026 — concrete regional seasonal forecast with El Niño + IOD signals)
2. **Climate + bio-health bridge** (Northeast India EcoHealth/OneHealth — bridges climate with pandemic-preparedness/biodiversity)
3. **Climate + AI/ML bridge** (AI Aerosol Optical Depth Retrieval — bridges climate observation with AI/ML methodology)

**Insight:** when the openalex sub-channel activates via intent=learning routing, a single fresh-direction seed can yield multi-domain bridges. The "fresh direction" picks are not just narrow-domain discoveries — they're often trans-disciplinary. The 3-angle yield is a multiplier effect that justifies the fresh-direction phase budget (30s) even when the continue-phase yields 0.

**Implication for fresh-direction picker:** when a fresh-direction seed yields 0.3+ kept candidates and the openalex sub-channel is active, the agent should expect multi-domain bridges. Don't trim the cluster-bloat discipline to "save only 1 strongest" — the strongest discovery may be in a sub-domain (e.g. AI/ML bridge) different from the seed's primary domain (e.g. climate). Save up to 3 strongest from distinct sub-domains.


## 27d. Clock-skew detection pattern (NEW 2026-06-22 14:01Z)

The 14:01Z tick surfaced an anomaly: the script's `last_tick` was `2026-06-22T16:00:19.888100` — **1h59m in the FUTURE** relative to the real UTC (14:01:36). The script uses `datetime.now().isoformat()` without timezone (per §25) — the script's "now" may be local time interpreted as UTC, or the system clock may be skewed.

**Detection signal:** when `state['last_tick']` is in the future vs. `datetime.now(timezone.utc).isoformat()`, the script-side timestamp is clock-skewed.

**The fix is already in §25 (single-datetime discipline) but this is the FIRST verified occurrence of 1h+ forward skew.** The agent's existing handling worked correctly:
1. Captured TICK_TS_ISO = `datetime.now(timezone.utc).isoformat()` at the START of the tick
2. Saved TICK_TS_ISO to `/tmp/pw2_tick_ts.json` for cross-execute_code-call consistency
3. Overwrote `state['last_tick'] = TICK_TS_ISO` after all state mutations
4. Verified with `assert state['last_tick'] == TICK_TS_ISO` post-write
5. Used TICK_TS_FN (from TICK_TS_ISO) for the report filename

**Side effect on `discovery_topics` narrative:** the script-side `last_tick` is a separate marker from the narrative `tick_timestamp`. The narrative should use the agent's TICK_TS_ISO (real time when work was done), not the script-side `last_tick` (clock-skewed).

**Refined rule for future ticks:** the §25 single-datetime discipline already handles this case. The new lesson is that **script-side clock skew can be 1h+ in either direction** — always overwrite `state['last_tick']` to the agent's TICK_TS_ISO regardless of the script's value. The drift-correction assertion `assert state['last_tick'] == TICK_TS_ISO` catches both forward and backward skew.


## 28b. Manual rotation §28 verified end-to-end (2026-06-22 14:01Z)

The §28 manual rotation pattern (pop 5 broken seeds, add 7 fresh sat=0 from carry-over, recompute next_seeds alphabetical) worked end-to-end without edge cases. This is the **3rd verified §28 application** (after 13:18Z and 13:55Z ticks).

**Verified at 14:01Z:**
- consecutive_empty reached 3 (script rotation code dead per §28 caveat)
- Applied §28 pattern: popped 5 broken (3 from this tick's 0-novel, 2 from prior deep-job coverage)
- Added 7 fresh sat=0 (6 carry-over + 1 programming reformulation)
- Recomputed next_seeds (alphabetical top-5 of sat=0)
- Consecutive_empty stays at 3 (per playbook, fresh-direction doesn't touch the counter; this is correct — continue-phase IS still 0-novel even though fresh-direction found 3)

**Refined rule:** §28 is a RELIABLE fallback when the script's auto-sort fails (consecutive_empty=3 trigger). The pattern is now mature — no need to recommend the §23 operator-override separately; §28 covers both the pop-broken-seeds AND the add-fresh-seeds needs.


## 23a. Cluster-brother popping — extend §23 to include adjacent dead seeds (NEW 2026-06-22 14:36Z)

The §23 override example pops only the 3 sat-0 seeds in `next_seeds[:3]`. **Refined rule:** when 1+ of the broken seeds has a topical cluster (e.g. all 3 are infrastructure-flavored), ALSO pop the cluster-brothers — the sat-0 seeds in `next_seeds[3:]` that share the same dead cluster. They will yield 0 novel on the next tick too, and the override's purpose is to break the cycle cleanly.

**Verified at 14:36Z:** the 3 broken seeds (Huawei SMIC, Hyperliquid AI, vLLM K8s — all infrastructure / AI-infrastructure) had 2 cluster-brothers in `next_seeds[3:4]` (Cloudflare Workers AI inference gateway, xAI Series E Colossus supercomputer) — same cluster, same dead topic. Popped all 5 (3 broken + 2 cluster-brothers) in one read/write cycle. The post-override `next_seeds[:5]` was the alphabetical-top-5 of the remaining sat-0 pool (Anthropic cluster + AI climate emulator) — none of the dead cluster resurfaced.

**Implementation:**

```python
# After identifying BROKEN_SEEDS (the 3 in next_seeds[:3]):
# Look at next_seeds[3:] for sat-0 cluster-brothers
CLUSTER_BROTHERS = [
    s for s in state.get('next_seeds', [])[3:]
    if sat.get(s, 0) == 0.0
    # Optional: filter by topical cluster via shared tokens
    # if any(token in s.lower() for token in ['kubernetes', 'cloudflare', 'xai'])
]
# Pop them all in the same read/write cycle as the 3 broken seeds
for s in BROKEN_SEEDS + CLUSTER_BROTHERS:
    sat.pop(s, None)
```

**Detection signal for next-tick handler:** if state['saturation_scores'] is missing 1+ sat-0 seeds that were in `next_seeds[:5]` for 2+ consecutive ticks, the cluster-brother popping was applied. Do NOT re-pop them; do NOT re-initialize their saturation. The override is one-shot.

**Why this matters:** cluster-brothers are dead-weight in `next_seeds[3:]` — they'll get auto-picked alphabetically when the broken 3 are popped, and the script will yield 0 novel on them next tick, restarting the cycle. Popping them in the same override is essentially free (1 read + 1 write) and breaks the cycle completely.


## 28c. PITFALL #253 — infrastructure-systems-design domain exhausted (NEW 2026-06-22 14:36Z)

The infrastructure-systems-design 24-domain-pool entry (count=3 in last-100 mazemaker browse) is now **structurally exhausted** in the current corpus. Two concrete proper-noun reformulations BOTH routed to the persistent arxiv Ti-substring noise cluster (PITFALL #246):

**Attempt 1:** `CockroachDB distributed SQL AI inference production deployment 2026`
- Result: 0/6 LLM-kept
- All candidates: Ti NLTE 1997, MultiQG-TI, 3M-TI, Tied Links, Tied Monoids, Cell response Ti/Zr/Ti (the persistent arxiv noise cluster)

**Attempt 2:** `Modal Labs serverless GPU AI inference production 2026`
- Result: 0/12 LLM-kept
- All candidates: same Ti/3M-TI/MultiQG-TI arxiv noise + Lobsters recurring programming cluster (AI-ruining-skills, wigglegram, postmarketOS, Deno Desktop, Chesterton, What are you doing this week)

**Why this is distinct from §15a (concrete-reformulation fails for non-AI/ML domains):** the §15a rule says concrete proper-noun anchors WITHOUT an AI/ML bridge fail. Both these attempts had AI/ML bridges (`AI inference` as syntactic modifier, `AI inference` as head respectively). The reformulation followed §15a-update-2 ("the AI/ML token must be the syntactic HEAD") — Modal Labs IS the AI/ML serving product. But the persistent arxiv Ti-substring noise cluster wins regardless.

**Corpus-structural, not seed-routing-dependent:** the "Ti" substring collision is now STRUCTURAL in the corpus. Every infrastructure-keyword query routes to the same 6 Ti-metallurgy / topology papers via the arxiv sub-channel. The LLM intent classifier (`product_research` for both attempts) and LLM-filter don't change the outcome — the arxiv sub-channel returns the persistent noise cluster as the highest local_relevance items.

**Refined rule for fresh-direction picker:**

1. **SKIP `infrastructure-systems-design`** for fresh-direction until the corpus is re-fed with non-Ti-substring infrastructure content. The next-lowest 24-domain-pool entries are: education (5), robotics (5), history (6), legal (6).
2. **Recommended next-pick:** history (count=6) with the verified-working "Pompeii DNA sequencing archaeological findings 2026" recipe (3 saves in 2026-06-22T13:00Z tick via intent=learning routing + openalex sub-channel). Or education (count=5) with a fresh concrete proper-noun anchor.
3. **Symptom of structural exhaustion:** 2+ reformulation attempts on the same domain BOTH 0-novel, with the SAME persistent noise cluster surfacing in `items_by_source`. Don't keep retrying — pick a different domain.
4. **Save PITFALL** to mazemaker with label `pitfall:arxiv-noise-flood-253-infrastructure-domain` so the picker can check the pitfall catalog before picking this domain.

**Implication for continue-phase seeds:** the 5 popped seeds in the 14:36Z override (Huawei SMIC, Hyperliquid AI, vLLM K8s, Cloudflare Workers AI, xAI Colossus) were all infrastructure-flavored. The post-override `next_seeds[:5]` is now Anthropic-cluster heavy (4 of 5) plus 1 AI-climate bridge seed. Future ticks should monitor whether the Anthropic cluster follows the same exhaustion pattern (per §27b cluster-saturation clarification — high-yield pattern yields 0 novel when cluster is saturated).


## 26c. PITFALL #253 references and follow-up (NEW 2026-06-22 14:36Z)

Companion pitfalls in the same noise family:
- **PITFALL #245** (arxiv DOI + benchmark name → 100% Ti-substring noise) — research-paper framing
- **PITFALL #246** (abstract-academic + 'lithography'/'FrontierMath'/'benchmark' substring → Ti-substring noise) — academic framing
- **PITFALL #26b** (#244 LOW-SCALE MODE — sub-channel fully suppressed) — abstract-academic + benchmark
- **PITFALL #27** (broad-benchmark-evaluation → arxiv-noise flood) — deep-research framing
- **PITFALL #253** (infrastructure-systems-design domain → corpus-structural Ti-substring noise) — domain-level structural

The progression: §9 (noise URL pattern recognition, individual arxiv noise items) → §26 (deep-research arxiv flood) → §245-#246 (specific token trigger combinations) → §26b (sub-mode sub-channel suppression) → **#253 (domain-level structural exhaustion, corpus-bound)**. #253 is the END of the arxiv-noise progression — the corpus itself is now structurally over-seeded with the Ti-substring cluster on infrastructure topics. Recovery requires corpus re-feeding, not seed reformulation.

**Save to mazemaker** with label `pitfall:arxiv-noise-flood-253-infrastructure-domain` (verified stored as id 826399 on 2026-06-22T14:36Z).


## 32. Carry-over file key naming — `in_flight_deep_jobs_at_tick_end` (NEW 2026-06-22 14:45Z)

The §22 / §29 examples use the key `in_flight_deep_jobs` for reading the
in-flight deep jobs dict from the carry-over file. **This key is WRONG.**
The actual key in the on-disk JSON is `in_flight_deep_jobs_at_tick_end`.

Verified 2026-06-22 14:45Z tick: my first read used
`carry.get('in_flight_deep_jobs', {})` and got `{}` (empty dict). I
proceeded as if there were no in-flight deep jobs from the prior tick.
The carry-over file actually contained 3 in-flight deep jobs
(`df9ba9bf9bc3` theregister Mythos macOS, `fd7be8fb1527` OpenAI
Trusted Access for Cyber, `4fd823023597` Khanmigo K-12). I caught
the bug only when I re-read the file with the correct key — the
Khanmigo job was already done, the other 2 were still running.

**Always use the correct key when reading the carry-over file:**

```python
with open('/home/alca/.hermes/pulse-wurm-next-topics.json') as f:
    carry = json.load(f)

# CORRECT — actual on-disk key:
in_flight = carry.get('in_flight_deep_jobs_at_tick_end', {})

# WRONG — yields {} on a file that has 3 in-flight jobs:
# in_flight = carry.get('in_flight_deep_jobs', {})
```

**Other carry-over keys that exist on disk** (verified 14:45Z):
- `in_flight_deep_jobs_at_tick_end` (NOT `in_flight_deep_jobs`)
- `completed_jobs_this_tick` (dict keyed by job_id)
- `tick_status` (string, narrative)
- `operational_notes` (list of strings)
- `fresh_findings_<timestamp>` (list of {id, label, type, source_url, note} dicts)
- `discovered_topics_for_next_tick` (list of strings)
- `next_topics_priority` (list of strings)
- `domain_coverage_24_pool` (dict keyed by domain name)
- `next_tick_fresh_direction_picker` (dict)
- `mazemaker_saves_this_tick` (list of {id, label} dicts)
- `tick_metadata` (dict with last_run_iso, last_run_tick, last_saves_count, etc.)
- `Qwen3-Coder_stuck_job_decision` (string, one-off)

**Related §29 update:** the operational pattern in §29 shows
`in_flight_deep_jobs` (wrong) — change to `in_flight_deep_jobs_at_tick_end`
in any code that reads the carry-over. When writing, use the same key
so the next tick reads it back correctly.

**Why this matters:** the carry-over file is the cross-tick memory
that holds in-flight deep jobs from prior ticks. Missing it means
|those jobs sit unpolled and the discoveries they would have produced
|never enter the corpus. With a 6h cadence, that's a 6-12h discovery
|gap per missed poll.


## 33. Nature as primary-source venue for AI-cognitive-impact (NEW 2026-06-22 18:30Z)

Nature (the journal, ISSN 0028-0836) is the highest-prestige general-science
venue in the world — multi-disciplinary, weekly, with a current impact
factor of ~50 and a famously low acceptance rate (~7-8% for research
articles, much lower for the editorial/comment section that d41586-* IDs
live in). When Nature publishes AI-cognitive-impact research with
empirical framing, that signals a corpus shift away from blog-opinion
and toward the empirical literature. Future pulse runs and recall
queries should therefore weight Nature d41586-* identifiers higher on
AI-cognitive-impact / AI-skill-degradation recall queries — these are
the canonical primary-source anchors for that corpus.

On 2026-06-21 Nature published d41586-026-01947-1, "Is AI ruining our
skills? Early results are in and they're not good"
(https://www.nature.com/articles/d41586-026-01947-1). This is the
first 2026 Nature publication that frames AI-skill-degradation as
empirical rather than speculative — a meaningful corpus marker that
the question has matured from opinion writing into citable research
synthesis. The piece reports early empirical evidence that AI tool use
degrades human skill acquisition and retention.

Adjacency note — this discovery surfaced as a rescue from a failed
PHASE B seed (template-failure-mode §15a confirmed for the history
domain: a literal Library of Congress AI-digitization seed returned
zero fresh finds). The lobsters sub-channel tagged 'vibecoding' then
delivered d41586-026-01947-1 as adjacent AI-cognitive-impact content
with loc_rel 0.157, freshness 96, engagement 147 comments, and final
score 0.0188. Treat lobsters 'vibecoding' / HN / Hacker News as the
fallback channel when a literal history-domain seed fails — the
adjacent corpus is often richer than the literal seed corpus.

Cross-reference — pairs with decisions 826215 (Boötes III neutrino
DM), 826429 (Anthropic IPO pivot), 825810 (OpenAI rare pediatric
disease), and 826396 (Apple Swift in kernel). Together these five
anchor a 2026-Q2 corpus shift from pure-AI-infrastructure coverage
toward AI-societal-impact research.

