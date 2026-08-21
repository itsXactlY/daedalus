# Sprint patterns — round 5 (sprints #99-#100)

Round 5 closes the third risk-adjusted metric (Sortino) and
adds a single-line headline summary at the top of the
JournalStatsPanel. The journal surface now has 18 methods
(was 16 at end of round 4), and the panel gives the trader
instant orientation before any scrolling.

## 1. Sortino — the third risk-adjusted metric (Sprint #99)

Sortino = mean(daily) / downsideDeviation × sqrt(252). Same
shape as Sharpe (#84) but the denominator is RMS of
*negative* returns only — upside volatility doesn't
penalize the score.

### Why Sortino over Sharpe for traders

Sharpe penalizes ANY volatility (a strategy with huge winning
days and modest losing days has high vol → low Sharpe even
though it's good). Sortino only penalizes the BAD kind. For
most trader strategies Sortino is the more meaningful metric.

Three angles on the same question, now all in the panel:
- **Sharpe**  — mean / all-vol (penalizes upside vol too)
- **Calmar**  — mean / worst-DD (penalizes only the bad kind)
- **Sortino** — mean / downside-vol (penalizes only losing days)

### Formula (target = 0)

```
downsideDeviation = sqrt(mean(min(0, r)²))   // RMS of negatives
dailySortino      = mean(daily) / downsideDeviation
annualizedSortino = dailySortino × sqrt(252)
```

### Sentinels

- All-positive days → downsideDeviation = 0 → Sortino = 0 →
  panel renders "**∞**" in green (same convention as
  profit-factor when there are no losses — "no bad days"
  intuition).
- Negative mean over non-trivial downside → Sortino < 0
  (red, stay-away signal).
- sampleSize < 1 → zeroed, render as "—".

### Same shared-helper pattern as everything else

`computeSortinoFromSeries(daily)` extracted alongside
`computeDrawdownFromSeries` and `computeSharpeFromSeries`.
The three `perSymbolSortino() / perTagSortino() / sortino()`
methods are thin wrappers (~70 lines each, struct + method).

Future metrics that fit the same shape (just swap the
denominator): **Sterling** (mean / avg DD), **Omega**
(probability-weighted gains/losses), **Ulcer Index** (RMS
of drawdowns). Each is a ~70-line wrapper.

## 2. Headline summary row (Sprint #100)

A single line at the top of the JournalStatsPanel, just below
"All-time P&L: $X.XX (N fills)":

```
Best: BTC (Calmar=4.20, Sharpe=1.80)   Worst: SOL (Calmar=-0.50, Sharpe=-0.30)
```

The trader's eyes land here FIRST. Answers "where am I
winning, where am I bleeding?" without scrolling through
12 sub-tables.

### Sourcing

- `perSymbolCalmar()` is already sorted DESC by the method
  (#97). First entry = best, last = worst.
- "Worst" filters out `calmarRatio==0` entries (no-DD symbols
  aren't really "worst", they're unrankable). Scan from the
  end backwards until `calmarRatio < -1e-9` OR `maxDrawdown > 1e-9`.
- Match Sharpe by linear scan over `perSymbolSharpe()` for the
  dual-metric display.
- When `best.symbol == worst.symbol` (single-symbol case),
  suppress the "Worst" line entirely.

### Why Calmar (not Sharpe) is the headline metric

Calmar is the position-sizing metric — "how much return per
unit of worst DD?" directly answers "should I bet more on
this strategy?" Sharpe is the volatility comparison; useful
for comparing strategies head-to-head, but the trader sizes
positions by Calmar, not by Sharpe.

## 3. Three-metric pattern, completed

The JournalStatsPanel now has THREE complementary risk-adjusted
metrics:

| Metric | Denominator | Color thresholds |
|---|---|---|
| Sharpe  | all-vol (stddev of all returns) | green >= 1.0, red < 0 |
| Calmar  | max DD (worst peak-to-trough)  | green >= 3.0, red < 0 |
| Sortino | downside-vol (RMS of negatives) | green >= 2.0, red < 0 |

The "Sortino green >= 2.0" threshold is the standard
interpretation (Sortino > 2 = good, > 3 = very good, > 4 =
excellent). Slightly different from Calmar's 3.0 because the
denominators measure different things.

All three together: a strategy with high Sharpe but low
Calmar = high vol with occasional brutal drops. A strategy
with low Sharpe but high Calmar = steady small gains with no
painful drawdowns. The trader reads the combination.

## 4. Cumulative state at end of round 5 (sprint #100)

- **89 commits** on `0.0.2` (was 87 at end of round 4)
- **27 widgets**
- **641 ✓ across 92 tests** (0 failures)
- **40 sprints in this run** (#61-#100)
- Journal surface: **18 methods** (was 16 at end of round 4)
  - 10 journal-wide: totalRealized, realizedBy{Symbol,Tag,Day},
    stats, maxDrawdown (with recovery), streaks, sharpe,
    perSymbolStats, perTagStats
  - 3 risk-adjusted: calmar(), sortino()
  - 12 per-axis: perSymbol{Drawdown,Sharpe,Calmar,Sortino},
    perTag{Drawdown,Sharpe,Calmar,Sortino}
- JournalStatsPanel: **13 sub-sections** (was 12 at end of
  round 4)
  - New Sortino row in journal-wide Risk-Adjusted section
  - New Sortino column in per-symbol + per-tag risk-adjusted
    tables (now 6 cols each)
  - New headline summary at the top of the panel

**The third risk-adjusted metric closes the loop.** All
three (Sharpe / Calmar / Sortino) available per-symbol and
per-tag. 18 distinct metrics on the journal surface — at this
point the trader has a complete analytics foundation.

**Natural next:** tabs to organize the 13 sub-sections,
per-symbol-per-day data (heatmap foundation), tabular CSV
export of all per-axis breakdowns, position-level P&L
(currently only round-trips).
