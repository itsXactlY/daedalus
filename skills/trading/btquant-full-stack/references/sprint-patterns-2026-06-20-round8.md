# Sprint patterns — 2026-06-20 round 8 (#172–#202)

The fifth stretch of the BTQuant sprint chain. 30 sprints, 42
commits, 0 widgets added, 31 new ✓ tests. Hit the 200-commit
milestone at Sprint #200. The TradeJournal surface grew from 169+
to 232+ methods.

## 1. The five-pillar build-out (extending round 7's four-layer)

Round 7 documented the four-layer pattern:
journal-wide → per-symbol → per-tag → bulk all-segments.

Round 8 added a fifth pillar: **bulk all-segments-by-tag**.
For every new primitive, the order is now:

1. **Journal-wide** — `cagr()`, `journalSummaryJson()`, `tradeCountSummary()`.
2. **Per-symbol** — `cagrBySymbol("BTC")`.
3. **Per-tag** — `cagrByTag("scalp", includeUntagged=false)`.
4. **Bulk all-segments** — `allSegmentCagr()` returns `vector<SegmentCagr>` sorted DESC.
5. **Bulk all-segments-by-tag** — `allSegmentCagrByTag(includeUntagged=true)`.

If any pillar already exists from a previous sprint (grep the
.hpp first!), skip it and pick the next missing pillar. The
order of pillars within a sprint doesn't have to match the
canonical order — if per-tag exists and journal-wide doesn't,
start with the missing one. But each primitive should have
all 5 eventually.

## 2. Risk of Ruin — Gambler's ruin approximation

The `riskOfRuinBySymbol(symbol, ruinFraction=0.5)` method
approximates the probability of losing `ruinFraction` of capital
over many trades. The formula:

```
p = W * R          (gain rate per trade, R = avgW / |avgL|)
q = 1 - W          (loss rate per trade)
capitalUnits = ruinFraction / max_loss_per_trade_fraction

if p <= q:
    ruinProb = 1.0          # unfavorable odds, ruin is guaranteed
else:
    ruinProb = (q / p) ^ capitalUnits
```

`max_loss_per_trade_fraction` = `|avgLoss| / realized_equity`, with
a floor of 0.01 to avoid division blowup. The struct returns
`winRate`, `payoffRatio`, `ruinProb`, `maxLossFrac` for the trader
to debug the model.

Edge case to handle: if there are 0 wins OR 0 losses, set
`ruinProb = (losses == 0) ? 0.0 : 1.0`. Do NOT compute the formula
in that case — `R` would be 0 or infinity and `pow` would
return NaN.

## 3. CAGR — Compound Annual Growth Rate

`cagr()` convention: initial equity = $1.0, final equity = 1.0 +
cum_realized. With 1-year span and +$2 realized, CAGR = 200% (i.e.
`2.0`, not `0.02` — the trader reads percent directly).

```cpp
double cum = ...;  // sum of realizedDelta over filtered fills
if (cum <= -1.0) return -1.0;   // ruin, equity ≤ 0
double finalEquity = 1.0 + cum;
double years = spanDays / 365.0;
return std::pow(finalEquity, 1.0 / years) - 1.0;
```

Sentinel `-1.0` for the ruin case so the UI can render "RUIN"
instead of "NaN%".

Test pitfall: the first Sprint #185 test used `+$100 → +$200`
and asserted CAGR ≈ 2.0 (200%). Wrong — `cum = 200` and
`finalEquity = 201`, so `pow(201, 1/1) - 1 = 200`, not 2.0. The
test had to be rewritten to use `+$1 → +$2` to get CAGR = 2.0.
Lesson: write the test numbers such that the result fits in
intuitive range BEFORE the formula is committed. Pencil-verify
the boundary cases.

## 4. Journal summary JSON — manual serialization

`journalSummaryJson()` returns a hand-rolled JSON string with
the headline metrics. No JSON library — just `std::ostringstream`
+ the comma separators and `os << "  \"key\": " << value << ",\n"`.

This is intentional: pulling in nlohmann/json or rapidjson
adds compile time and dependency complexity for one method
that emits a flat key-value map. The downstream consumer can
parse it with any standard JSON parser; the format is stable
and the test asserts on substring matches (`"\"totalFills\": 3"`).

## 5. Already-exists detection (false start at Sprint #182)

Sprint #182 was started as "per-segment rolling Sharpe", but
the implementation declared methods that ALREADY existed from
Sprint #134 (`rollingWindowSharpeBySymbol`, `rollingWindowSharpeByTag`
were at line 1188 of trade_journal.hpp). The duplicate
declaration produced "Redefinition" errors. The fix was:

1. `sed` out the new implementations from the .cpp file.
2. `sed` out the new declarations from the .hpp file.
3. Commit a `chore: Sprint #182 verified — already exists`
   commit (no code change, just a marker).
4. Move on to the next primitive.

Lesson: BEFORE declaring a method, `grep` the hpp for it.
If it exists, don't add it — do the next missing pillar
(per-tag if journal-wide exists, or bulk if per-tag exists).
A quick `grep -c "^    std::vector<.*> <methodName>("
src/data/trade_journal.hpp` answers in 0.1s. This is much
cheaper than the compile-test-commit-clean cycle.

## 6. Sharpe stability stats — meta-metric over rolling Sharpe

`sharpeStabilityBySymbol(symbol, window=30)` returns mean,
stddev, min, max of the per-segment rolling Sharpe series.
It calls the existing `rollingWindowSharpeBySymbol` and
aggregates. Useful for "is my segment's edge stable or
erratic?" — a high stddev relative to the mean is a red flag.

This is the pattern for ALL meta-metrics: call the underlying
per-segment time-series, aggregate. The aggregation function
fits in ~15 lines. No need to write a fresh time-series loop.

## 7. Field-name pitfall catalogue — corrections to round 7

Round 7 documented `TradingSession.duration_us` (snake_case)
as the field to use after the fix from camelCase `durationUs`.
That hint was WRONG. The actual field is `active_us`. Sprint
#172 in this round had to be patched from `cur.durationUs` to
`cur.active_us` (NOT `duration_us`).

The full updated catalogue is in the SKILL.md § Field-name
pitfall catalogue. New entries this round:
- `sharpe()` returns `Sharpe` struct, scalar is `.annualizedSharpe`
- `riskScore()` returns struct, headline is `.overall`
- `maxDrawdown()` returns `Drawdown` struct, scalar is `.maxDrawdown.maxDrawdown`
- `TradingSession.active_us` (NOT `duration_us`)

## 8. Build cadence — 30 sprints in 90 minutes

Round 8 alone produced 30 sprints in ~90 minutes of agent time
(plus compaction pauses). The pattern:

- 1 patch hpp + cpp in parallel
- 1 build (5-10s, often clean)
- 1 patch test_integration.cpp
- 1 build + test run (8-12s)
- 1 git add + commit
- 1 mcp__mazemaker__mazemaker_remember

Average ~3 minutes per sprint, including the mcp call latency.
Peak was ~1.5 minutes per sprint when the patch tool was
warm and no build break occurred.

## 9. Test discipline — accept what works, debug the rest

When a test fails (e.g. Sprint #172 build was broken, Sprint
#182 was a false start, Sprint #185 had a wrong expectation
about the CAGR units), the right move is:
1. Read the actual output of the failure.
2. Pencil-verify the formula or the test numbers.
3. Patch either the implementation (if it was a bug) or
   the test (if the test was wrong).
4. Do NOT add complexity to "make it work" — fix the
   simplest hypothesis first.

Sprint #185: the test was wrong, not the formula.
Sprint #172: the field name in the .cpp was wrong, not the
struct definition.
Sprint #182: the work was already done in a previous round.
In each case, the right action was revert + retarget, not
"add more code".

## 10. Five-pillar canvas — primitives NOT yet fully covered

At the end of round 8, primitives that are missing one or
more pillars (next session's roadmap):

- `monthlyReturns` — has per-symbol + per-tag, missing journal-wide
  and bulk all-segments.
- `monthlyMaxDrawdown` — has per-symbol + per-tag, missing
  journal-wide (it IS journal-wide as-is) and bulk.
- `drawdownRecoveries` — has per-symbol + per-tag + bulk (from
  #165), missing journal-wide "all completed" bulk and
  the by-tag bulk.
- `topWinners` / `topLosers` — has per-symbol + per-tag (from
  #147), missing the journal-wide "top N winners" (it IS that
  but is named `topWinners` not `topWinnersJournalWide` — naming
  inconsistency to fix next round).
- `rollingWindowSharpe` — has per-symbol + per-tag, missing
  bulk all-segments (would be SharpeStability for journal-wide).

These are the natural next-pick targets for round 9.
