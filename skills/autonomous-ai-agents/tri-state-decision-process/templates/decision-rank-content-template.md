# decision-rank-content-template.md

Copy this template into each `mazemaker_remember` call's `content` field for the
top-3 ranked decisions in a DECIDE phase. Substitute `<PLACEHOLDERS>` with the
candidate's specifics. Keep the section order and the CYCLE CONTEXT line at the
end — the line-pairing convention is what the ACT phase and future DECIDE
cycles follow.

---

```
DECISION (DECIDE phase <YYYYMMDD>_<HHMM> UTC, RANK #N of M):

Discovery Memory ID: <DISCOVERY_ID> (discovery:pulse-wurm-<DATE>_<short-name>)
Discovery source: Pulse-Wurm 2.0 tick <DATE> ~<HH:MM>Z
Discovery URL: <URL>

Why it matters (<PRIORITY>):
<2-4 sentence summary of the discovery, the concrete contribution, and why it
matters for Hermes / the operator. For CRITICAL items, include: "This discovery
is significant because it introduces a threat/risk vector that is NOT yet
covered by the existing hermes-mcp-security-audit defensive-primitive
registry. The combination of (a) a fresh attack primitive or unverified-
assumption break and (b) the absence of paired defensive primitives in the
agent-security cluster motivates immediate research_watchlist action and (for
the critical-priority items) a skill_update that adds the threat/risk to the
audit's coverage matrix.">

Score breakdown:
- Graph connectedness: <X.XX>/1.0 (<K> of top 10 topic-recall results are fact:*/decision:* — <list the specific fact:*/decision:* IDs that landed in top 10>, all in the <cluster-name> cluster)
- Novelty: <X.XXX> (1 - similarity <Y.YYYY> to closest existing memory <MEMORY_ID>; <one-sentence novelty framing>)
- Recency weight: <X.XX> (created today within last ~<N.N>h)
- Base score: <C> + <N> + <R> = <BASE>
- <PRIORITY> priority boost: +<0.20 for critical | 0.10 for important | 0.00 for nice_to_know>
- Total score: <TOTAL>

Suggested action type: <skill_update | code_fix | config_change | research_watchlist | fact_memory> — <one-sentence description of the action>.

ACT phase action items:
(1) ADD a research_watchlist entry in mazemaker for <URL / arxiv ID>.
(2) <One specific update to a Hermes skill — e.g. UPDATE hermes-mcp-security-audit: add a new section "..." that ...>
(3) CROSS-REFERENCE with rank #<X> (<neighbor label>, memory id <NEIGHBOR_ID> — <one-line cluster pairing>) and rank #<Y> (<neighbor label>, memory id <NEIGHBOR_ID> — <one-line cluster pairing>) — together: <one-sentence cluster-arc summary>.
(4) ADD pulse-wurm seed: "<seed text>" — <rationale for tracking follow-on work>.
(5) <Optional: research gap / additional action / no-action statement>

Cluster context:
<2-4 sentences on how this rank fits into the cycle's overall theme.>

Label: decision:rank-<YYYYMMDD>-<priority>-<short-kebab-name>

CYCLE CONTEXT: <Nth> of <M> ranks from <YYYY-MM-DD> <HH:MM> UTC DECIDE. Pairs with rank #<X> (memory id <NEIGHBOR_ID>, <neighbor label>) and rank #<Y> (memory id <NEIGHBOR_ID>, <neighbor label>). Together these <M> trace <one-sentence arc summary across the M ranks>.
```

---

## Field-by-field guidance

### Label
- Format: `decision:rank-<YYYYMMDD>-<priority>-<short-kebab-name>`
- Date is **compact with NO dashes** (`20260619`, not `2026-06-19`). The dashed form breaks downstream label-prefix filters.
- Priority is one of: `critical`, `important`, `nice_to_know`
- Short kebab-name: a 3-5 word slug from the discovery label suffix (e.g. `building-browser-agents-arch-security`, `webmcp-tool-surface-poisoning`, `sop-agentic-browsers`). Lowercase, hyphens, no spaces.

### Discovery Memory ID
- Always include the numeric memory ID. Format: `822528 (discovery:pulse-wurm-20260619_building-browser-agents-arch-security-2511.19477)`.
- This is the line future DECIDE cycles will parse to build the covered-set — keep it on a single line with the discovery label in parentheses.

### Score breakdown
- `Graph connectedness`: count fact:*/decision:* labels in the topic `mazemaker_recall(limit=10)` result. Format: `0.30/1.0 (3 of top 10 topic-recall results are fact:*/decision:* — <list IDs>, all in the <cluster-name> cluster)`.
- `Novelty`: `1 - max(similarity)` from the same recall. Always ≥ 0.0 and ≤ 1.0.
- `Recency weight`: `1.0` for discoveries <1h old, decaying roughly linearly over 24h. Format: `0.99 (created today within last ~0.2h)`.
- `Base score` = connectedness + novelty + recency.
- Priority boost: critical=+0.20, important=+0.10, nice_to_know=+0.00.
- `Total score` = base + boost.

### CYCLE CONTEXT line — REQUIRED at end
- Without this line, the rank is malformed and breaks downstream linking.
- Format: `CYCLE CONTEXT: <Nth> of <M> ranks from <YYYY-MM-DD> <HH:MM> UTC DECIDE. Pairs with rank #<X> (memory id <NEIGHBOR_ID>, <neighbor label>) and rank #<Y> (memory id <NEIGHBOR_ID>, <neighbor label>). Together these <M> trace <one-sentence arc>.`
- For N=1 of 3: list ranks #2 and #3. For N=3 of 3: list ranks #1 and #2.
- The "together these <M> trace <arc>" sentence is the single most valuable
  part — it summarizes what the cycle collectively decided to act on.

## Verification (per skill pitfall)
After writing, call `mazemaker_get(memory_id=<NEW_ID>)` and assert:
1. The label matches `^decision:rank-\d{8}-(critical|important|nice_to_know)-`
2. The content ends with the `CYCLE CONTEXT:` line

If either fails, the write is malformed — patch the content with `mazemaker_remember` and re-verify before reporting success.
