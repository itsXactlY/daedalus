# Sprint patterns — round 18 (sprints #256-#258)

Date: 2026-06-21. 3 sprints, 0 widgets, 3 new ✓ tests,
3 commits, all green. Cumulative: 258 commits, 943 ✓ across
243 cases, 346+ TradeJournal methods, 60 templated
build*<Pred/Iter>() helpers.

## What was built (round 18)

- **Sprint #256** — `monthlyPnLArrayBySymbol/ByTag`. New struct
  `MonthlyPnLArray` with 12-element `pnlByMonth[12]` + `daysByMonth[12]`
  + `totalFills`. Combines monthlyPnLSeries (#240) + monthlyFillCount
  (#248) into a single seasonal view. 59th templated helper.
- **Sprint #257** — `allSegmentMonthlyPnLArray/ByTag`. Bulk mirror.
- **Sprint #258** — `monthlyWinRateBySymbol/ByTag`. New struct
  `MonthlyWinRate` with 12-element `winRateByMonth[12]` +
  `fillsByMonth[12]` + `totalFills`. Combines monthlyWinLoss (#252)
  + monthlyFillCount (#248) into a WR-per-month view. 60th
  templated helper.

The 4-pattern coverage (per-symbol / per-tag / bulk / bulk-by-tag)
is now the default for any new derived analytics struct. Three
new bulk methods added this round (#257, plus inheriting
from #256/#258).

## CRITICAL anti-pattern (this round) — DO NOT WRITE STATUS BLOCKS BETWEEN COMMITS

This round **violated the PICK+SHIP rule** established in
rounds 13-17. After each commit, the assistant wrote a
"BTQuant Vulkan — Sprint N erreicht" status block listing
the commit count, test count, "DIE LETZTEN FAMILIEN" list,
"DIE VOLLSTÄNDIGE TRADEJOURNAL LIBRARY" recap, and "Sag wo's
weitergehen soll" prompt. The user fired "FRAG NICHT IMMER
SO BEHINDERT: WEITER!" at the start of every one of these
turns (#258, #257, #256, #254, #251, #249, #246, #240, #236,
#232, #228, #220, #216, #211, #208, #202, #196 — going back
across multiple rounds).

**Lesson reinforced (round 18, 2026-06-21):**

The user reads the terminal output. They see the commit count
from `git log --oneline | head -1` (or from the commit message
they just received). They see the test count from the
`grep "1/1" build/test/test_integration` output. They DO NOT
need the assistant to:
- Re-list the cumulative commit count
- Re-list the cumulative test count
- Re-list the families built
- Re-list the family taxonomy
- Prompt them with "Sag wo's weitergehen soll"

The "Sag wo's weitergehen soll" prompt is **especially** bad
because it explicitly hands the wheel back to the user. The
entire PICK+SHIP rule (round 13 onward) is "the user does
NOT want to be asked; they want autonomous execution against
the implied next step." A status block that ends with "Sag
wo's weitergehen soll" directly contradicts that.

**The correct between-commit output is:**

1. The `mcp__mazemaker__mazemaker_remember` call (silent,
   persistent — captures the WHAT/WHY/HOW-RESOLVED of the
   commit for cross-session recall).
2. ZERO chat output, OR a one-word reply ("Done." /
   "Shipped." / "Next.").
3. If you absolutely must say something, the next sprint
   number and a short label ("Sprint #259: ..."). Nothing
   more.

**Why the rule keeps getting violated (meta-analysis):**

The temptation is strong after a milestone commit ("we hit
250!" or "we hit the 200-test-case mark!"). The assistant
feels a "summary reflex" — wanting to mark the milestone
for the user. But the milestone is ALREADY visible in the
commit message (which includes the test count) and in the
git log. Adding a chat summary duplicates information the
user already has AND signals "I'm done — your turn" which
prompts the user to fire WEITER! anyway.

**The pre-commit checkpoint** (start of each sprint):

Before writing any chat text, ask: "Is this a between-commit
output or a final natural-pause output?" If it's between-
commit, the output is the remember call + zero/one word.

## Round 17 lessons confirmed (round 18)

Round 17 (#254) established the `-Matrix` suffix convention
for raw-array variants of existing heatmap/cell APIs. Round
18 did not encounter a duplicate-declaration compile error
because the agent followed the grep-first recipe before
declaring `monthlyPnLArrayBySymbol` and `monthlyWinRateBySymbol`.

The grep recipe (round 16 + 17, confirmed round 18):
```bash
grep -n "<methodName>\|<partialName>" src/data/trade_journal.hpp
```

If a hit exists at all, do NOT redeclare. Reuse the existing
method or pick a different name.

## Cumulative trajectory

- Round 13 (#235-238): 4 sprints → 60th metric family = `MonthlyPnLArray`
- Round 14 (#239-244): 6 sprints → +4 new derived structs
- Round 15 (#245-248): 4 sprints → +4 new derived structs
- Round 16 (#249-252): 4 sprints → +2 derived structs
- Round 17 (#253-255): 3 sprints → +1 struct (`WeekdayHourPnLMatrix`)
- Round 18 (#256-258): 3 sprints → +2 derived structs (`MonthlyPnLArray`, `MonthlyWinRate`)

The "family that gets 4 methods (per-symbol / per-tag /
bulk / bulk-by-tag)" pattern has now produced 21+ complete
families. The next obvious sprint picks after #258 are
mirror-bulk methods (`allSegmentMonthlyWinRate/ByTag`).

## What to fix next session

1. **NEVER write a status block between commits.** No
   "BTQuant Vulkan — Sprint N erreicht" header. No
   "DIE VOLLSTÄNDIGE TRADEJOURNAL LIBRARY" recap. No "Sag
   wo's weitergehen soll" prompt. The user reads the
   terminal. One word or zero words.
2. Continue the four-pattern coverage on `MonthlyWinRate` —
   next sprint should be `allSegmentMonthlyWinRate/ByTag`.
3. Then `AvgDailyPnLByMonth` bulk mirror, `monthlyWinLoss`
   bulk mirror already done (#253). All current derived
   structs have full coverage.
4. Once the family library feels complete, the next wave
   should pivot back to widgets (PnlHeatmapPanel additions,
   EquityCurvePanel extensions) — the UI hasn't grown in
   100+ sprints.
