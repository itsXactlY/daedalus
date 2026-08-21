# Sprint patterns — round 4 (sprints #91-#98)

Round 4 of the BTQuant journal surface build-out. Started with
the per-symbol / per-tag risk & Sharpe variants (#91, #93),
ended with the per-symbol / per-tag Calmar variants + their UI
columns (#97, #98). In between: the recovery date + Calmar
ratio additions (#95, #96).

## 1. Shared-helper pattern — refactor journal-wide → per-axis variants

The big insight of this round. Once `maxDrawdown()` and
`sharpe()` were refactored to delegate to
`computeDrawdownFromSeries(daily)` and
`computeSharpeFromSeries(daily)`, every per-axis variant
became a ~50-line thin wrapper that:

1. Loads fills
2. Groups by axis (symbol, tag, etc.)
3. For each group: bucket by local day, derive the daily series
4. Feed the series into the shared compute helper
5. Sort by primary metric DESC with deterministic tie-break

```cpp
std::vector<PerSymbolDrawdown>
TradeJournal::perSymbolDrawdown() const {
    std::vector<JournalFill> fills = loadAll();
    std::unordered_map<std::string, std::vector<JournalFill>> bySymbol;
    for (const auto& f : fills) bySymbol[f.symbol].push_back(f);

    std::vector<PerSymbolDrawdown> out;
    for (auto& kv : bySymbol) {
        PerSymbolDrawdown e;
        e.symbol = kv.first;
        e.fillCount = kv.second.size();
        auto buckets = bucketByLocalDay(kv.second);
        std::vector<std::pair<std::string, double>> series;
        for (auto& bkv : buckets) {
            series.emplace_back(std::move(bkv.first), bkv.second);
        }
        auto dd = computeDrawdownFromSeries(series);
        e.maxDrawdown = dd.maxDrawdown;
        e.peakDate    = dd.peakDate;
        e.troughDate  = dd.troughDate;
        e.recoveryDate = dd.recoveryDate;   // transparent
        e.recoveryDays = dd.recoveryDays;
        e.currentDD   = dd.currentDD;
        out.push_back(std::move(e));
    }
    std::sort(out.begin(), out.end(),
              [](const PerSymbolDrawdown& a,
                 const PerSymbolDrawdown& b) {
                  if (a.maxDrawdown != b.maxDrawdown)
                      return a.maxDrawdown > b.maxDrawdown;
                  return a.symbol < b.symbol;   // tie-break for determinism
              });
    return out;
}
```

**RULE for any future per-axis metric:** if it can be expressed
as a function of a (date, value) chronological series, put the
algorithm in a shared helper and add per-axis wrappers. New
metrics cost ~70 lines each (struct + method) instead of
~200. Sortino, Sterling, Omega — all of them are thin
wrappers waiting to be written.

**Refactor before extend:** the refactor of `maxDrawdown()` and
`sharpe()` to use the helpers preserved behavior byte-identical.
The 20 cross-method invariants in Test 85 still passed. Don't
add per-axis variants to a method that hasn't been refactored
yet — duplicate the algorithm once first, then generalize.

## 2. "Zip by name" pattern for cross-referenced UI columns

When a single UI table needs data from multiple methods (e.g.
the per-symbol risk-adjusted table showing Sharpe AND Calmar),
fetch each method independently and zip by axis-name into an
`unordered_map` for O(1) row lookup. Don't bloat the struct.

```cpp
auto perSymSh = m_journal->perSymbolSharpe();
auto perSymCl = m_journal->perSymbolCalmar();
std::unordered_map<std::string, double> calmarBySymbol;
calmarBySymbol.reserve(perSymCl.size());
for (const auto& c : perSymCl) {
    calmarBySymbol[c.symbol] = c.calmarRatio;
}
// ... inside the per-row loop:
double symCalmar = 0.0;
bool   symHasCalmar = false;
auto it = calmarBySymbol.find(e.symbol);
if (it != calmarBySymbol.end()) {
    symCalmar = it->second;
    symHasCalmar = true;
}
```

**Why:** PerSymbolSharpe has 5 fields. Adding a 6th (`calmar`)
would inflate every per-symbol Sharpe return for every call
site. The zip pattern keeps the struct lean and the cost is
one extra O(N) fetch per render — negligible at journal scale.

## 3. Recovery algorithm — absolute cumulative equity, not from-trrough

When implementing `recoveryDate` / `recoveryDays` (Sprint #95),
the first version walked the daily series accumulating equity
*from the trough forward* and compared that against
`worstDDPeak`. That's WRONG. The from-trough cumulative starts
at 0, but the peak we're recovering to is an absolute level
(e.g. $100). The fix: walk cumulative equity from the START of
the series, but only consider dates after the trough.

```cpp
// Correct: cumulative from start, only after trough.
bool seenTrough = false;
double cum = 0.0;
int daysFromTrough = 0;
for (const auto& kv : daily) {
    cum += kv.second;             // cumulative from start
    if (!seenTrough) {
        if (kv.first == troughDateAtWorst) seenTrough = true;
        continue;
    }
    daysFromTrough++;
    if (cum >= worstDDPeak - 1e-9) {  // absolute comparison
        dd.recoveryDate = kv.first;
        dd.recoveryDays = static_cast<size_t>(daysFromTrough);
        break;
    }
}
```

Test 90 caught this: a +100 / -50 / +60 fixture had equity 50
at the trough (not 0), so the from-trough math said "60 from
trough < 100 peak → not recovered", but in absolute terms the
trough-day equity is 50 and the recovery criterion is
"cumulative equity at the next day ≥ 100", which is satisfied
at day 0 (cum = 110).

**Rule of thumb:** when comparing to a level, use a level
(absolute cumulative). When comparing to a delta, use a delta
(from-trough delta). Don't mix.

## 4. Test arithmetic — always verify the peak/trough math by hand

Caught in Test 91 (losing year). Fixture: +50, -100. Peak=50,
trough=-50. maxDD = peak - trough = 50 - (-50) = 100, NOT 50.
I encoded maxDD=50 in the expectation. Test failed loudly,
fixed the expectation.

**Rule:** before encoding expected values, write out the
cumulative equity curve on paper:

```
Day -2:  +50  → equity  50  (peak 50)
Day -1: -100  → equity -50  (peak still 50, trough -50)
                                  maxDD = 50 - (-50) = 100
```

The two-line pencil sketch catches the off-by-100 errors that
hand-coding skips. Saves a test failure cycle and the
implementation isn't actually wrong — the test was.

## 5. Local pass/fail counters in tests (NOT file-scope)

`pass` and `fail` are declared LOCAL to Test 85. Other tests
(Test 80, 81, 82, 83, 84) don't track them at all — they just
print ✓/✗. When adding a new test:

```cpp
std::cout << "\nTest 86: Testing TradeJournal.perSymbolDrawdown()..."
          << std::endl;
{
    using btquant::TradeJournal;
    using btquant::JournalFill;

    int pass = 0;       // LOCAL — not file-scope
    int fail = 0;
    // ... test body uses ++pass / ++fail ...
    std::cout << "  ─── " << pass << "/" << (pass + fail)
              << " perSymbolDrawdown tests passed"
              << " (✗ = " << fail << ")" << std::endl;
}
```

The first attempts in this round used `pass++ / fail++` at
file scope — failed with `undeclared_var_use` LSP errors.
Fix: declare them at the top of each new test block. Always.

## 6. Recovery + Calmar edge cases

The new fields have four documented states that the UI must
handle distinctly:

```cpp
// recoveryDate / recoveryDays:
dd.recoveryDate == "" && dd.recoveryDays == 0  // not recovered
dd.recoveryDate == "" && dd.maxDrawdown == 0  // no DD ever
dd.recoveryDate == "YYYY-MM-DD"               // recovered
                                            // daysFromTrough > 0

// calmarRatio:
calmarRatio == 0   // no DD yet (sentinel; metric undefined)
calmarRatio <  0   // losing year over non-trivial DD (stay-away)
calmarRatio >= 3.0 // very good (green threshold)
```

UI formatting: "YYYY-MM-DD (N days)" when recovered, "— (not
recovered)" when still in DD, "(no DD)" when maxDrawdown == 0.
Calmar: "—" when sentinel 0 with no DD, red when negative,
green when >= 3.0, dim otherwise.

## 7. Color thresholds — recap of the round-4 conventions

| Metric | Green | Red | Dim | Sentinel |
|---|---|---|---|---|
| Sharpe daily/annual | >= 1.0 | < 0.0 | else | 0 = no signal |
| Calmar | >= 3.0 | < 0.0 | else | 0 = no DD |
| Max DD | always red | — | — | 0 = no DD |
| Current DD | — | > 0 | == 0 (at ATH) | 0 = at ATH |
| Recovery | — | — | always (info) | "" = not recovered |

The "1.0 for Sharpe" / "3.0 for Calmar" thresholds are the
classic industry interpretations (Sharpe > 1 = good, > 2 =
very good, > 3 = excellent; Calmar > 3 = strong).

## 8. Cumulative state at end of round 4 (sprint #98)

- 87 commits on `0.0.2`
- 27 widgets
- **641 ✓ across 92 tests** (0 failures)
- **38 sprints in this run** (#61-#98)
- Journal surface: **16 methods** (was 10 at end of round 3)
  - 10 journal-wide: totalRealized, realizedBy{Symbol,Tag,Day},
    stats, maxDrawdown (now with recovery), streaks, sharpe,
    perSymbolStats, perTagStats
  - 6 per-axis: perSymbolDrawdown, perSymbolSharpe,
    perSymbolCalmar, perTagDrawdown, perTagSharpe, perTagCalmar
  - 1 risk: calmar()
- JournalStatsPanel: **12 sub-sections** (was 7 at end of
  round 3). Per-symbol and Per-tag risk + risk-adjusted tables
  each got 1-2 new columns. Risk section got Recovery column
  and Calmar mini-row.

Per-axis per-symbol / per-tag shape is now complete: 16
distinct metrics available per axis. Future work is either
new metrics (Sortino / Sterling / Omega — thin wrappers via
the shared helpers) or per-symbol-per-day data (heatmap
foundation) or panel organization (tabs).
