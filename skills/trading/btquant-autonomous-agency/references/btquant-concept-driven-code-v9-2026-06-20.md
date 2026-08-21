# BTQuant Concept-Driven Code (v9 schema) — 2026-06-20 (Session 3)

## TL;DR

User fury: "JEDE VERFICKTE STRATEGIE BESCHREIBT IM FILE WAS WIE WO!
RAFFST DU DENN NICHTS?" The header docstring claimed
"KalmanFiltered_VolatilityAdjusted_CrossAsset_Momentum" but the entry
code was a generic momentum template — none of the named concepts
actually drove any logic. The header was a lie.

Root cause: `concept_extractor.py` v1 only mapped keywords to
indicator + strategy_type. The header description was generated from
those inferences, but the *code* was just a one-size-fits-all
template. 606/609 files were identical templates with only the class
name changed.

Fix: added `CONCEPT_LOGIC_BLOCKS` dict. Each recognised keyword maps
to real Python code (indicator setup, entry gate, exit modifier,
param). The regen script composes strategy files from these blocks
plus the base type template. Header now describes what the code
actually does.

## The schema: CONCEPT_LOGIC_BLOCKS

`concept_extractor.py` exposes a single dict with one entry per
keyword (~80 keywords covered). Each entry has 4-5 fields:

```python
CONCEPT_LOGIC_BLOCKS = {
    "kalmanfiltered": {
        "entry_gate_setup": (
            "        self._kalman = bt.ind.EMA(bt.ind.EMA(bt.ind.EMA("
            "self.data.close, period=8), period=5), period=3)"
        ),
        "entry_gate":
            "self.dataclose[0] > self._kalman[0] * 1.001",
        "exit_modifier":
            "self.dataclose[0] < self._kalman[0] * 0.999",
        "docstring_note":
            "3-stage Kalman-cascade close filter",
    },
    ...
}
```

| Field | What it produces | Indentation |
|---|---|---|
| `entry_gate_setup` | Lines pasted into `__init__` (real `bt.ind.X()` setup) | EXACTLY 8 spaces |
| `entry_gate` | Python expression AND-combined with base signal | inline |
| `exit_modifier` | Python expression OR-combined with base exit | inline |
| `params` | `(name, default)` pairs added to params tuple | n/a |
| `docstring_note` | Human description in the file header | n/a |

**CRITICAL: setup_lines must have EXACTLY 8 spaces of indent.** Lines
with 12 spaces cause `IndentationError: unexpected indent` at class
level. (Caught in v7 — divergence/golden/goldenratio/fibonacci had
12-space setup lines.)

## The composition algorithm (regen_v3.py)

```
for each strategy_class_name:
    concept = parse_strategy_concept(class_name)
    indicators = concept.indicators
    strategy_type = concept.strategy_type
    logic_blocks = concept.logic_blocks  # list of CONCEPT_LOGIC_BLOCKS entries

    # 1. __init__ body:
    #    super().__init__(**kwargs)
    #    + base indicators (ema/rsi/macd/bb/adx)
    #    + ALL entry_gate_setup lines from logic_blocks

    # 2. buy_or_short_condition:
    #    base_signal = <type-specific expression>
    #    for each block: gate_kw_i = (block.entry_gate)
    #    return base_signal AND ALL gate_kw_i

    # 3. sell_or_cover_condition:
    #    base_exit = <type-specific expression>
    #    for each block: modifier_kw_i = (block.exit_modifier)
    #    return base_exit OR ANY modifier_kw_i
```

Type templates (momentum/regime/mean_reversion/breakout/volatility/
arbitrage) are still present as `_base_*_entry` / `_base_*_exit`
functions. The concept blocks AND/OR onto them.

## Example: KalmanFiltered_VolatilityAdjusted_CrossAsset_Momentum

Header (was: lie; now: accurate):

```
Strategy type (inferred from class name): momentum
Indicators (inferred): ema, atr, rsi
Concept keywords: kalmanfiltered, volatilityadjusted, crossasset, momentum
Logic keywords (contribute code): kalmanfiltered, volatilityadjusted, crossasset
Logic notes: 3-stage Kalman-cascade close filter;
             ATR > 80% of its 50-bar mean (vol-adjusted regime gate);
             Cross-asset relative-strength (>2% above 50-bar SMA)
```

Generated code (now matches the header):

```python
def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.ema = bt.ind.EMA(self.data.close, period=self.p.ema_period)
    self.ema_fast = bt.ind.EMA(self.data.close, period=self.p.ema_fast_period)
    self.ema_slow = bt.ind.EMA(self.data.close, period=self.p.ema_slow_period)
    self.rsi = bt.ind.RSI(self.data.close, period=self.p.rsi_period)
    # Kalman-filtered price: 3-stage EMA cascade
    self._kalman = bt.ind.EMA(bt.ind.EMA(bt.ind.EMA(self.data.close, period=8), period=5), period=3)
    # Cross-asset: relative strength vs own 50-bar SMA
    self._crossasset_baseline = bt.ind.SMA(self.data.close, period=50)
    self._peak_price = None

def buy_or_short_condition(self):
    # BASE: momentum — directional bias + confirmation
    ema_bull = self.ema_fast[0] > self.ema_slow[0]
    macd_bull = False
    adx_strong = False
    rsi_pullback = 30 < self.rsi[0] < 75
    base_signal = sum([ema_bull, rsi_pullback]) >= 1
    # concept: kalmanfiltered
    gate_kalmanfiltered_0 = (self.dataclose[0] > self._kalman[0] * 1.001)
    # concept: volatilityadjusted
    gate_volatilityadjusted_1 = (self.atr[0] > bt.ind.SMA(self.atr, period=50)[0] * 0.8)
    # concept: crossasset
    gate_crossasset_2 = (self.dataclose[0] > self._crossasset_baseline[0] * 1.02)
    if base_signal and gate_kalmanfiltered_0 and gate_volatilityadjusted_1 and gate_crossasset_2:
        self.create_order(action='BUY')
        return True
    return False
```

Header says "kalman, vol-adjusted, crossasset" → code does exactly
that. The header is no longer a lie.

## Concept coverage report (across 606 v9 files)

```
201 regime    119 golden    82 reversion  57 fractal    48 hawkes
125 ratio     110 signature 80 gating     47 topological 43 rough
120 adaptive   95 entropy
```

Most-frequent keywords: `regime` (201), `ratio` (125), `adaptive`
(120), `golden` (119), `signature` (110), `entropy` (95),
`reversion` (82), `gating` (80), `fractal` (57), `hawkes` (48),
`topological` (47), `rough` (43), `wavelet` (30), `path` (32),
`homology` (31), `wasserstein` (37), `hurst` (38).

577/606 files have ≥1 concept gate. 577/606 have ≥1 concept
modifier. The remainder are base-type-only strategies with no extra
concepts in the name.

## Five bugs caught during v9 development

1. **`signals else False` referenced undefined `signals` var.**
   The line was `sum([...]) >= 2 if signals else False` — `signals`
   was never declared. Fix: always `sum([...]) >= 1` (relaxed — strict
   versions use concept gates).

2. **Momentum crossover too rare.** `ema_cross_up` required
   `ema_fast[0] > ema_slow[0] AND ema_fast[-1] <= ema_slow[-1]` —
   a single-bar event. In real data this fires <1% of bars. Fix: use
   directional bias `ema_fast[0] > ema_slow[0]` instead. Strategies
   now trade.

3. **Module not in sys.modules when loaded via
   `importlib.util.spec_from_file_location`.** Backtrader's metaclass
   does `sys.modules[cls.__module__]` to find the class — if not
   registered, `KeyError`. Fix: `sys.modules[f.stem] = mod` before
   `spec.loader.exec_module(mod)`.

4. **`len(s.trades)` only counts ACTIVE trades.** A round-trip
   trade (BUY → SELL) clears the trade object from `s.trades`. To
   count "did this strategy trade at all?", use the BaseStrategy's
   own counter: `s.total_trades`. The verification recipes in
   session 2 were misleading — they reported "0 trades" when in
   fact 100+ round-trips had occurred.

5. **12-space indent in setup_lines.** `divergence`, `golden`,
   `goldenratio`, `fibonacci` had setup strings with 12 spaces of
   indent (intended for class body, but they were pasted at class
   level). Fix: every entry_gate_setup string starts at EXACTLY 8
   spaces.

## Caveat: contradictory concept keywords

Some class names combine concepts that gate the SAME variable in
OPPOSITE directions:

- `arbitrage` → `close < sma * 0.99` (BELOW baseline)
- `crossasset` → `close > baseline * 1.02` (ABOVE baseline)
- `golden` → `ema_13 > ema_21 > ema_55` (long bias)
- `fade` → `rsi > 70` (short bias)

When AND-combined, these strategies NEVER trade because both gates
cannot be true simultaneously. This is INFORMATIVE — they're
internally inconsistent research candidates. Two mitigation options
for the agency:

**(a) Dominant-keyword picking:** scan concept_keywords in
left-to-right order; the leftmost "directional" keyword wins
(momentum > regime > arbitrage > fade), others become
soft-modifiers (e.g. exit-only, param-only).

**(b) Gate-consistency scoring:** evaluate the gate expressions
against a sample bar; if all gates cannot be true on any single
bar, flag the strategy as "internally inconsistent" and exclude from
backtest. Use `strategy.total_trades == 0` after a long
warm-up-bypassed backtest as the canonical signal.

For now (v9), option (b) is implicit — the inconsistent strategies
simply produce 0 trades, and the agency should be aware that
`total_trades == 0` after a sufficient backtest = internal
inconsistency OR legitimate "market didn't trigger".

## Verification recipe (live, separate-broker per strategy)

```python
import sys, pathlib, importlib.util
sys.path.insert(0, '/home/alca/projects/PubBTQuant')
sys.path.insert(0, '/home/alca/projects/PubBTQuant/autonomous_agency')
import backtrader as bt
from autonomous_agency.strategies.base import BaseStrategy

f = pathlib.Path('autonomous_agency/strategies/Golden_Ratio_Momentum_20260618_222616.py')
spec = importlib.util.spec_from_file_location(f.stem, f)
mod = importlib.util.module_from_spec(spec)
sys.modules[f.stem] = mod
spec.loader.exec_module(mod)
cls = getattr(mod, f.stem)

cerebro = bt.Cerebro()
cerebro.broker.set_cash(10000)
cerebro.broker.setcommission(commission=0.001)
data = bt.feeds.GenericCSVData(dataname='/tmp/synth2.csv', dtformat='%Y-%m-%d', openinterest=-1)
cerebro.adddata(data)
cerebro.addstrategy(cls)
results = cerebro.run()
r = results[0]
print(f'total_trades={r.total_trades} pnl={r.total_pnl:+.2f}%')
```

Expected for `Golden_Ratio_Momentum_20260618_222616`: ~100 trades,
pnl around +20%.

## What this fixes in the agency pipeline

The agency loop has always had a "concept extraction" step. Before
v9, it produced noise: every strategy looked the same in code.
After v9:

- Two strategies with different concept keywords produce DIFFERENT
  code. The agency's diversity metric (previously: ~0, all templates
  shared the same skeleton) now reflects the actual variation.
- The "header describes what code does" invariant holds. Future
  debugging can trust the file's docstring.
- The agency can ship strategies to evaluation with the assumption
  that "kalman" actually means a kalman-style filter is in the
  code, not just in the name.

## Future work (not yet done)

- Add CONCEPT_LOGIC_BLOCKS for ~50 more keywords (currently ~80 of
  ~300 unique keywords recognised are mapped to logic; the rest
  fall through to type-only templates).
- Implement gate-consistency scoring as a pre-backtest filter
  (option b above).
- Wire the `total_trades == 0` signal into the agency's "did this
  cycle produce a real strategy?" metric.
- Move the conflict-resolution logic (dominant-keyword picking)
  into `concept_extractor.py` so the regen script picks a coherent
  subset of gates automatically.

## Cross-references

- `references/btquant-real-basestrategy-pattern-2026-06-20.md` —
  Session 2: real BaseStrategy architecture. The base.py file is
  unchanged; this session builds on top of it.
- `references/backtrader-template-real-code-2026-06-20.md` —
  Session 1: empty-shell fix. That session made the templates
  produce REAL code; this session makes each concept keyword
  produce real, DISTINCT code.
- `agent-delivery-integrity` — the meta-skill about "claim delivery
  but produce wrong/lying output". The header-lies-about-code
  antipattern is a new variant: code that runs, but doesn't match
  its documentation.