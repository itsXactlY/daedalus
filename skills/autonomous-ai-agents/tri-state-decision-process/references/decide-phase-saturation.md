# DECIDE phase — saturation mode + large-response parsing

Session reference: 2026-06-22 22:00 UTC, 30+ decisions already written earlier
that day, 13/16 candidates in the 24h discovery pool were dedup-eligible.

## When the corpus is saturated, write what's available — don't fabricate

**Symptom:** A DECIDE cycle in a saturated corpus typically produces 0–2 unranked
candidates instead of the canonical TOP 3. Trying to force 3 leads to
manufactured work or, worse, re-ranking items the ACT phase has already handled.

**Correct behavior (verified in 2026-06-22 22:00 cycle):**

1. Run dedup against recent `decision:rank-*` (extend the 2h window by spirit
   when an item is already ranked as CRITICAL or IMPORTANT — re-ranking the
   same discovery 3h later is wasted ACT work, even if strict 2h would
   technically allow it).
2. If only 0–2 candidates survive, write those.
3. Report the saturation in the final response — explicitly state how many
   candidates were dedup'd and which prior decisions covered them. The ACT
   phase + operator use this to understand signal-vs-noise for the cycle.
4. Do NOT promote noise items to "TOP 3" just to hit the quota. Better to
   acknowledge saturation than write a low-quality decision.

**Why this matters:** The loop runs every 60 min; if saturated cycles
manufacture 3 decisions per cycle, the ACT phase at 6AM gets buried in
re-rank noise. Honest "only 2 unranked items, here's the saturation context"
is the load-bearing signal.

## Use mazemaker_browse with label_prefix, NOT mazemaker_recall, for the discovery pool

**Symptom:** `mazemaker_recall` with query like `discovery:pulse-tick-*` returns
600K+ characters of semantically-mixed content (it ignores the label filter and
returns decisions that mention those terms). This is unusable for finding
the actual discovery pool.

**Correct pattern:**

1. Use `mazemaker_browse(label_prefix='discovery:', limit=30)` to get the
   chronological list of recent discoveries. Returns ~30 in order, predictable
   size, easy to parse.
2. Use `mazemaker_browse(label_prefix='decision:rank-', limit=30)` for
   the dedup-target list.
3. THEN use `mazemaker_recall` only for the small number of surviving
   candidates, with topic-specific queries for connectedness scoring.

## Parsing huge JSON responses from mazemaker_browse / mazemaker_recall

**Symptom:** `mazemaker_recall` and `mazemaker_browse` can return 100K–600K
characters. The read_file tool's line-number prefix + chunked reading
truncates mid-string, breaking JSON parsing.

**Correct pattern (terminal + python, not execute_code):**

1. The tool result includes a `persisted-output` note: "Full output saved to:
   `/tmp/hermes-results/call_<id>.txt`" — use this path.
2. Read via `read_file` to confirm structure, then parse via terminal+python
   because `read_file` chunks at line boundaries and JSON is one giant line.
3. Strip the `N|` line-number prefix that `read_file` adds — every line
   in the persisted file is prefixed with `<line_num>|`.
4. Parse with `json.loads(clean)` → expect DOUBLE-encoded JSON
   (outer `{"result": "<stringified JSON>"}`, then `json.loads(outer["result"])`).

**Working snippet (save as script in /tmp first if > 20 lines, heredoc
may be blocked):**

```python
import json
with open('/tmp/hermes-results/call_<id>.txt') as f:
    raw = f.read()
lines = []
for line in raw.split('\n'):
    if '|' in line and line.split('|',1)[0].strip().isdigit():
        lines.append(line.split('|',1)[1])
    else:
        lines.append(line)
clean = '\n'.join(lines)
outer = json.loads(clean)
inner = json.loads(outer['result'])
mems = inner['memories']  # or inner depending on the call
```

## Connectedness + novelty scoring — practical short-form

For each surviving candidate after dedup, run one `mazemaker_recall` with
a 5–10 word topic query and limit=5–10. Compute:

- **Connectedness** = (count of fact:* / decision:* labels in top N) / N
  (excluding the self-discovery if it appears in results)
- **Novelty** = 1 − max(similarity) of any non-self result in top N
- **Recency weight** = 1.0 if <1h old, 0.95 if 1–2h, 0.85 if 2–3h, 0.50 if 3–6h
- **Base score** = connectedness + novelty + recency_weight
- **Priority boost:** CRITICAL +0.40, IMPORTANT +0.10, NICE_TO_KNOW +0.00

**Pitfall — cross-axis vs topic-related:** the recall may return decisions
that share graph-position but not topic. The previous DECIDE cycles' recent
outputs (last 1–2h) tend to dominate the recall regardless of topic. To avoid
overcounting, label each fact/decision hit as "TOPIC-RELATED" or "cross-axis"
when the label doesn't share the query topic. Discount connectedness by
~30% when most hits are cross-axis (typical pattern in saturated cycles).

## Saturated-cycle response template

When a cycle produces 0–2 decisions, the report should explicitly include:

1. **Dedup table** — each dedup'd candidate, the covering decision id,
   age of that decision.
2. **Surviving candidates** — with score, action type, and a note about
   why it's cluster-bloat (if applicable).
3. **Operator-stack observation** — call out the saturation explicitly so
   the operator knows the loop is in steady-state, not broken.

**Anti-pattern:** silently writing 3 NICE_TO_KNOW decisions to fill the
quota. Better: 1–2 decisions + clear saturation note.
