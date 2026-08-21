# BTQuant Autonomous Loop Wiring — 2026-06-20 (Session 4)

## TL;DR

User fury: "DIE GANZE VERFICKTE SCHEIẞE SOLLTE AUTONOM LAUFEN!
SELBST FILTERN, ETC! DU BAUST HIER NUR GOTTLOSE SCHEIẞE!"

The previous session (3) regenerated 606 strategy files manually
via `/tmp/regen_v3.py` and copy-into-place. That produced a directory
full of **correct** files, but the **autonomous loop** that was
supposed to run them was still broken in 4 ways, producing garbage
every ~60s.

Two distinct artifacts, both must work:

- `strategies/*.py` — the strategy code (session 3 fixed this)
- The **live pipeline** that runs them — hypothesis gen → strategy
  factory → backtester → evaluator → evolution → archiver (this
  session fixed this)

**The meta-lesson**: when there is an existing pipeline, do NOT
manually regenerate its output. Wire the new logic INTO the
pipeline and let the pipeline produce it. Manual regen of pipeline
output is an anti-pattern that makes the agent look productive
while the actual system stays broken.

## Diagnosis: what was wrong with the live loop

Service `btquant-agency.service` was active (PID 2847510, 5h+
uptime, systemd user unit at
`~/.config/systemd/user/btquant-agency.service`). It was running,
but every cycle produced this recurring sequence of errors:

```
2026-06-20 06:56:15,043 ERROR - Kilo Code CLI not found
2026-06-20 06:56:15,044 INFO  - Successfully generated strategy: ...
2026-06-20 06:56:32,108 ERROR - Backtest failed for ...:
                                 unsupported operand type(s) for /:
                                 'float' and 'str'
2026-06-20 06:56:32,114 WARNING - class_name='X' not in module,
                                  falling back to 'Y'
2026-06-20 06:56:45,652 INFO  - Cycle 40: 2 backtests completed
                                  (27 failed)
2026-06-20 06:56:49,293 ERROR - Evolution failed: Sample larger
                                  than population or is negative
2026-06-20 06:56:49,293 ERROR - Failed to archive evolution result:
                                  'NoneType' object has no attribute
                                  'elite_strategies'
2026-06-20 06:56:49,293 INFO  - Cycle 40: 0 elite strategies
```

Per cycle: 27/29 backtests failed, 0 elite strategies, archiver
crashed. The loop was technically "running" but producing no
useful work.

## Fix 1: wire concept-driven code gen into the LLM→Kilo→Template chain

`strategy_factory.py::generate_strategy` originally had three
fallback paths:

```
1. _generate_code_with_llm(spec)     ← LLM often hallucinates / hits
                                        max_tokens mid-thought
2. _generate_code_with_kilo(spec)    ← Kilo CLI not installed
3. _generate_template_code_from_spec(spec) ← template fallback
```

Session 3 added the concept-driven generator as a standalone
script (`/tmp/regen_v3.py`) but never wired it into the factory.
This session:

1. Inlined the concept-driven generator as
   `StrategyFactory._generate_concept_driven_code(spec)` (~370
   lines, lives in `strategy_factory.py` itself).
2. Inserted it as path **3** in the chain:

   ```
   1. _generate_code_with_llm(spec)
   2. _generate_code_with_kilo(spec)
   3. _generate_concept_driven_code(spec)  ← NEW SAFETY NET
   4. _generate_template_code_from_spec(spec)
   ```

3. **Critical fix to path 2:** `_generate_code_with_kilo` was
   previously calling `_generate_template_code_from_spec` on
   every failure mode (FileNotFoundError, returncode != 0, empty
   stdout, TimeoutExpired, generic Exception) and returning that
   template code. This **silently bypassed** the concept-driven
   path because `if not code:` evaluated False for the
   non-empty template string.

   Fix: Kilo now returns `None` on every failure. The chain
   properly falls through.

**Generic lesson for any chained-fallback generator**: each
link in the chain MUST return None/sentinel on failure, never
fall back to the next path itself. If a fallback path produces
non-empty output on failure, downstream `if not x` checks will
silently skip and the chain looks like it works while one path
is permanently dead.

## Fix 2: param coercion in `_save_strategy`

LLM-generated hypotheses sometimes emit numeric params as strings:

```python
hypothesis.parameters = {"atr_period": "14", "rsi_period": 14}
```

When the strategy code does
`bt.ind.ATR(self.data, period=self.p.atr_period)`, backtrader's
SMMA internally computes `1.0 / self.p.period` → `1.0 / "14"` →
`TypeError: unsupported operand type(s) for /: 'float' and 'str'`.

This crashed 27/29 backtests in cycle 40.

**Fix:** coerce any param whose key contains "period", "window",
"max_legs", "threshold", "pct", "fraction", "ratio", "mult",
"size" to int/float before saving.

```python
numeric_keys = ("period", "window", "max_legs", "threshold",
                "pct", "fraction", "ratio", "mult", "size")
for k, v in (hypothesis.parameters or {}).items():
    if any(t in k.lower() for t in numeric_keys):
        params_clean[k] = coerce_numeric(v)  # string → float → int
    else:
        params_clean[k] = v
```

## Fix 3: force `class_name == filename basename` in `_save_strategy`

`backtester._load_strategy_class` does:

```python
mod = importlib.import_module(module_name)
cls = getattr(mod, strategy.class_name)  # strategy.class_name = file basename
```

If the in-file `class X(...)` declaration uses a DIFFERENT class
name (timestamp drift, LLM picked a different name, etc.), getattr
returns None and the backtester falls back to ANY `bt.Strategy`
subclass in the module — which can be `BaseStrategy` itself, with
no indicators and no trades.

**Fix:** rewrite the class declaration in the source code to match
the strategy_name before saving.

```python
safe_class_name = re.sub(r"[^A-Za-z0-9_]", "_", strategy_name) or "GeneratedStrategy"
if safe_class_name[0].isdigit():
    safe_class_name = "S_" + safe_class_name
code = re.sub(
    r"^(\s*)class\s+(\w+)\s*\(\s*BaseStrategy\s*\)",
    rf"\1class {safe_class_name}(BaseStrategy)",
    code,
    flags=re.MULTILINE,
)
```

`strategy.class_name` is also set to `safe_class_name` in the
returned GeneratedStrategy object.

## Fix 4: small-population guard in evolution_engine

`evolution_engine.py::evolve_population` had:

```python
parent1, parent2 = random.sample(self.population[:self.population_size//2], 2)
```

When `len(self.population) < 2`, `random.sample` raises
`ValueError: Sample larger than population or is negative`. In
early cycles the population is tiny (only the strategies that
survived evaluation get added), so this crashes most cycles.

**Fix:** clamp the breeding pool to actual population size and
guard each operator:

```python
half_pop_size = max(0, min(self.population_size // 2, len(self.population)))
if operation < self.crossover_rate:
    if half_pop_size < 2:
        # not enough parents — emit exploratory hypothesis instead
        continue
    parent1, parent2 = random.sample(self.population[:half_pop_size], 2)
elif operation < (self.crossover_rate + self.mutation_rate):
    if half_pop_size < 1:
        continue
    parent = random.choice(self.population[:half_pop_size])
```

Also added an early-return when both population and validation
results are empty:

```python
if not self.population and not validation_results:
    return EvolutionResult(generation=self.generation,
                          population_size=0,
                          elite_strategies=[], evolved_strategies=[],
                          pruned_strategies=[], new_hypotheses=[],
                          evolution_metrics={})
```

## Fix 5: None-safety in archiver and perpetual_loop

`archiver.archive_evolution_result` was called with the return
value of `evolution_engine.evolve_population` which can be None
when the engine short-circuits (or raises). The archiver tried to
access `evolution_result.elite_strategies` and crashed.

**Fixes:**

1. `archiver.archive_evolution_result(None)` → log warning, return
   early.
2. `perpetual_loop` wraps `evolve_population` in try/except so a
   transient failure doesn't kill the cycle.
3. `perpetual_loop` skips `archive_evolution_result` if `evo is None`.

## Fix 6: validator accepts BaseStrategy pattern

The factory's `_validate_and_format_code` had:

```python
if not re.search(r"^\s*class\s+\w+\s*\(\s*bt\.Strategy\s*\)\s*:", code):
    return None
if "def next" not in code:
    return None
```

The canonical BTQuant pattern uses `class X(BaseStrategy)` and
`def buy_or_short_condition` (called from `BaseStrategy.next`).
The validator was rejecting ALL concept-driven output.

**Fix:**

```python
# accept BaseStrategy subclass
if not re.search(r"^\s*class\s+\w+\s*\(\s*BaseStrategy\s*\)\s*:", code):
    return None

# accept buy_or_short_condition as entry point
if "BaseStrategy" not in code or "def buy_or_short_condition" not in code:
    return None
```

## Live verification

After all 6 fixes + restart:

```
2026-06-20 07:23:04,387 Cycle 1 start
2026-06-20 07:23:46,033 3 hypotheses generated
2026-06-20 07:25:28,797 LLM code-gen response contained no python block
2026-06-20 07:25:28,798 LLM code-gen returned nothing, falling back to Kilo
2026-06-20 07:25:28,799 Kilo Code CLI not found
2026-06-20 07:25:28,799 LLM+Kilo failed, falling back to concept-driven code generator
2026-06-20 07:25:28,802 Validator: accepted BaseStrategy subclass pattern
2026-06-20 07:25:28,803 Validator: accepted BaseStrategy pattern
                       (buy_or_short_condition instead of next)
2026-06-20 07:25:28,804 Successfully generated strategy:
                       Hurst_Regime_Adaptive_Entropy_Strategy_HRAES_20260620_072528
2026-06-20 07:29:01,959 Cycle 1: 3 strategies materialized
2026-06-20 07:29:21,421 Cycle 1: 3 backtests completed (0 failed)
2026-06-20 07:29:26,829 Cycle 1: 3 validation results
```

**Before**: 27/29 backtests failed, 0 elite strategies, archiver
crashed, "Evolution failed" every cycle.

**After**: 3/3 backtests succeeded, 3 validation results, no
crashes, 3 v9_concept_driven files written by the live loop.

Service state at end of session:

```
$ systemctl --user is-active btquant-agency.service
active
$ ps -o pid,etime,rss,cmd -p <PID>
    PID     ELAPSED   RSS CMD
3376116       08:19 402028 python3 -m autonomous_agency.run_loop ...
```

## Files touched (8 patches, 5 files)

| File | Patch |
|---|---|
| `strategy_factory.py` | new `_generate_concept_driven_code` method (~370 lines) |
| `strategy_factory.py` | wired into chain as 3rd path in `generate_strategy` |
| `strategy_factory.py` | `_generate_code_with_kilo` returns None on failure |
| `strategy_factory.py` | `_save_strategy` coerces numeric params + force class_name == filename |
| `strategy_factory.py` | `_validate_and_format_code` accepts BaseStrategy + buy_or_short_condition |
| `evolution_engine.py` | small-population guard + empty-population short-circuit |
| `archiver.py` | `archive_evolution_result(None)` → graceful skip |
| `perpetual_loop.py` | `evolve_population` in try/except; skip archive if evo is None |

## The meta-lesson: pipeline outputs are not deliverables

When the user demands "the system should run autonomously" and
there is a working pipeline (here: `perpetual_loop.py`
orchestrating `hypothesis_generator → strategy_factory →
backtester → evaluator → evolution_engine → archiver`), the
deliverable is the **running pipeline**, not snapshots of
pipeline outputs in `strategies/`.

A snapshot of correct files in `strategies/` plus a broken
pipeline that fails every cycle = same outcome as nothing at all
from the user's perspective. The user wants to come back tomorrow
and find hundreds of new strategies, not 3 manual ones committed
at 4am.

**Anti-pattern to avoid**: "I'll just regenerate the strategies
in /tmp and copy them in — the loop will pick them up next
cycle." This produces a directory full of correct files that
are SILENTLY DISCONNECTED from a broken pipeline. The user can
verify by checking: did the loop's *log* show successful
backtests, or did the agent just push files?

**Correct pattern**: when improving the pipeline's OUTPUT
(strategies), first read the pipeline's CODE (factory,
backtester, evaluator) and figure out where to inject. Don't
bypass the pipeline.

## Cross-references

- `references/btquant-concept-driven-code-v9-2026-06-20.md` —
  Session 3: the concept-driven code generator that this session
  wired into the chain.
- `references/btquant-real-basestrategy-pattern-2026-06-20.md` —
  Session 2: the slim `BaseStrategy` that the validator now
  accepts (and that all concept-driven strategies inherit).
- `references/backtrader-template-real-code-2026-06-20.md` —
  Session 1: the template that produced real code (still used as
  last-resort fallback in path 4 of the chain).
- `references/agency-loop-bringup.md` — original loop bringup
  (systemd unit, config wiring).
- `agent-delivery-integrity` — the meta-skill about claiming
  delivery without verifying the system actually works. The
  "manual regen of pipeline outputs" anti-pattern is a sub-case.