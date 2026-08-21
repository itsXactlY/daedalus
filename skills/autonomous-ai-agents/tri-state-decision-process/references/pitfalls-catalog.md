# Pitfalls Catalog — Tri-State DECIDE Phase

Session-agnostic pitfalls that every DECIDE cycle should pre-check before scoring.

## Label-Typo Prevention (mazemaker_remember `label` parameter)

When calling `mazemaker_remember` with `label: "decision:rank-<date>-<priority>-..."`, it is easy to type `decision:rank-rank-<date>-...` (double "rank") because the prefix is repeated naturally in the typed string. The API accepts the malformed label as-is and stores it in the `label` field — future searches by `decision:rank-YYYYMMDD-*` will MISS the entry.

**Pitfall:** Always construct the label string by CONCATENATION from explicit parts, not by typing the full string manually:

```python
# GOOD — parts concatenated, typo-free
prefix = "decision:rank"
date = "20260621"
priority = "important"
slug = "1-mhot-blockchain-state-commitment"
label = f"{prefix}-{date}-{priority}-{slug}"

# BAD — typed manually, typo-prone (e.g., "rank-rank")
label = "decision:rank-20260621-important-1-mhot-blockchain-state-commitment"
```

**Verification after storage:** For each of the 3 `mazemaker_remember` calls in a DECIDE cycle, fetch the stored memory back via `mazemaker_get(memory_id=...)` and confirm the label matches the expected pattern `decision:rank-YYYYMMDD-<priority>-<N>-<slug>`. A `decision:rank-rank-...` label is the most common typo (because of the "rank-rank" double-syllable).

**Detection:** If a typo slips through, the entry will not appear in `mazemaker_browse(label_prefix="decision:rank-YYYYMMDD-", limit=30)` because the prefix doesn't match. The entry WILL still appear in `mazemaker_recall(query="decision:rank-20260621")` if the typo preserves a substring match. Use both tools to cross-check.

**Cleanup:** There is no `mazemaker_update` API. The typo'd memory stays in the corpus until SUPERSEDES phase catches it. To prevent future cycles from inheriting the typo, the curate pass should add a fact memory documenting the bad label so future DECIDE cycles know to skip-or-rename on encounter.

**Real-world instance:** 08:45 UTC cycle, 2026-06-21 — memory id 825509 was stored with label `decision:rank-rank-20260621-nice_to_know-3-crypto-blockchain-is-research-cluster-ecis-arxiv` (double "rank"). Discovered via cross-check `mazemaker_get`. Content correct, only label malformed. Logged for next-cycle curation pass.

## See also

- `references/2026-06-21-cycle-notes.md` — Recall-glob pitfall, all-NICE_TO_KNOW validity, score formula recap
- `references/2026-06-21-cycle-notes-0800.md` — High-similarity-to-existing discovery, three-front synthesis pattern
- `references/2026-06-21-cycle-notes-0835.md` — Pool-thinness strategy, contradictory-decision-as-novelty, connectedness inflation
- `references/2026-06-21-cycle-notes-0845.md` — 95% saturation case study, single-tick orthogonal-academic-layers, fresh-direction three-attempt validation