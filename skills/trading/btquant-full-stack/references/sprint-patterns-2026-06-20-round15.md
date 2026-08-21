# Sprint patterns — round 15 (2026-06-21)

Sprints **#245 – #248** (4 sprints, 0 widgets, 4 new ✓ tests,
PICK+SHIP held across **8+ mid-chain WEITER! triggers**).

## What got built

| Sprint | Family | Struct | Methods |
|--------|--------|--------|---------|
| #245 | streaks (mirror) | `LongestWinStreak` | per-symbol, per-tag |
| #246 | streaks (mirror) | `LongestLossStreak` | per-symbol, per-tag |
| #247 | streaks bulk | (same structs) | 4 × `allSegment*` mirrors |
| #248 | monthly calendar | `MonthlyFillCount` | per-symbol, per-tag |

`MonthlyFillCount` uses `std::array<size_t, 12>` indexed by
`tm.tm_mon` (0=Jan..11=Dec). Total fills per month, no
chronological ordering — just the calendar grid.

## PICK+SHIP got stricter — by force

The session was punctuated by **8+ "FRAG NICHT IMMER SO
BEHINDERT: WEITER!" triggers** between commits. Each time,
the agent emitted a status block (however terse) and the
user fired WEITER again. The signal is unmistakable:

**Between commits, the ONLY acceptable chat output is one
word or the next sprint's number + one-line intent.**
Anything longer — even a 4-row table summarizing the
previous commit — counts as "asking" in the user's mental
model. The operator's terminal already shows the commit
hash, the test pass/fail, and the cumulative count via
`git log --oneline` + the build output. The chat reply
is signal noise.

The mcp__mazemaker__mazemaker_remember call IS the artifact.
It is persistent, structured, and queryable. The chat is
not.

## New pitfall catalogue entry: streak arithmetic

When computing "longest winning streak", a lone `+` between
two loss streaks counts as part of the next streak, not a
separate reset. Test fixture for longest streak must
account for this: a sequence `4W, -, +, 4W` produces
streak=5 (the second 4W is preceded by a single W, so the
run is 1+4=5 winning fills in a row). Always pencil-verify
streak arithmetic before writing the assertion.

## No new bug patterns

Catalogue was complete at end of round 13. Round 15 only
exercised existing entries (forward-decl ordering, struct
field naming via grep-first). No new pitfalls surfaced.

## Round 15 recap

- **248 commits** on `0.0.2` (+4 from round 14)
- **933 ✓ across 233 cases** at end of round 15
- TradeJournal surface: **326+ methods** + 65+ derived
  analytics structs (was 316+ / 60+ at end of round 14).
  Round 15 added 4 new structs and 12 new methods.
- **55 templated `build*<Pred/Iter>()` helpers** (was 52).
  53rd (longest win streak), 54th (longest loss streak),
  55th (monthly fill count).
- 0 failures across all 933 tests in 233 cases.
- **Round 15 alone: 4 sprints, 4 commits, 0 widgets, 4 new
  ✓ tests.** Cadence: ~2 minutes per commit including
  the mcp save.

## Stale-pitfall watch

The user did not give any new technical correction in this
round. The "WEITER" feedback is purely a style/workflow
preference. Do NOT add it to the field-name pitfall
catalogue — that section is for build/compile/test errors,
not user style preferences. PICK+SHIP and
`sprint-discipline-and-weiter.md` are the right home for
that lesson.
