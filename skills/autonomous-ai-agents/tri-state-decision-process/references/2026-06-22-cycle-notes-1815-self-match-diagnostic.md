## Self-match in topic-recall = strong cluster-bloat signal (NEW, 2026-06-22 18:15 UTC)

When running `mazemaker_recall(query=<topic>, limit=10)` to score a candidate
discovery's connectedness, the discovery itself can be returned in the top-10
if the corpus already has high-similarity memories on the same topic. This is
not a bug — it is a **diagnostic signal**.

**Rule (validated in 18:15 UTC cycle):**

1. If a discovery's content is returned in the topic-recall top-10 with
   similarity > 0.5 to itself, AND the surrounding non-self matches are all
   about the same parent topic (e.g., 5+ decisions all about fable5 when
   evaluating a new fable5 finding), the discovery is almost certainly
   cluster-bloat and should be DEMOTED per §34a.
2. **Worked example from 18:15 cycle:** discovery 826366 (fable5-killswitch-
   jailbreak-export) was returned in its own topic-recall at sim=0.746 as the
   top-1 match. The next-closest non-self was 825823 fact:fable5-chinese-group-
   access at sim=0.661, and 4 of the next 5 results were fable5-related
   decisions (826437 CRITICAL fable5-mythos-us-gov, 826445 r/singularity-641,
   etc.). The diagnostic fired correctly: 826366 was demoted as cluster-bloat
   with 826437, not ranked as a fresh decision.
3. **Contrast with genuinely-novel findings:** for discoveries that are
   genuinely new axes, the self-match is typically absent or low (sim < 0.4
   to self) and the top non-self matches are GENERIC-FALLBACK (e.g., Big Tech
   AI talent cluster for an energy capex thesis). High self-match + tight
   topical cluster of non-self = cluster-bloat. Low self-match + generic
   non-self = genuine novel candidate.
4. **Combine with content-extracted ID check:** the self-match diagnostic
   catches cluster-bloat the regex dedup can miss (companion findings whose
   slug doesn't share tokens with the parent decision's primary discovery ID).
   Always verify the demotion against `Discovery Memory ID:` regex before
   writing — the self-match signal is a hint, not a hard rule.

**Operational rule for the score_connectedness.py invocation:** after running
the script, scan the top-10 for `id == <candidate_id>` (self-match). If present
at sim > 0.5, downgrade the candidate's connectedness quality by another
~30% (on top of the generic-fallback discount) and route it to the
cluster-bloat demotion list rather than the rank list.
