# BTQuant Agency Loop — Bringup Recipe

**Single command to verify the perpetual motion engine is alive.**

This document is the executable hand-off. For the full session log
that brought the agency from dead to running, see
`references/agency-takeover-2026-06-18.md`. For the LLM routing
specifically, see `references/hermes-llm-gateway.md`.

## TL;DR

```bash
cd ~/projects/PubBTQuant
BTQ_LLM_INSECURE=1 python3 -m autonomous_agency.run_loop --interval 30 --hypotheses 8
```

That's it. The loop runs forever (Ctrl-C for clean shutdown).

## Pre-flight Checklist

Run `scripts/verify_loop.sh` to confirm all dependencies are
healthy. Or check manually:

```bash
# 1. Gateway alive (model advertised)
curl -sk https://localhost:8443/v1/models | grep -q wonderland && echo OK

# 2. Gateway upstream wired
curl -sk https://localhost:8443/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"wonderland","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'
# If 429 → upstream quota is empty; loop will degrade to fallback.
# If 200 → real LLM traffic.

# 3. Parquet cache present
ls -la .btq_cache/*.parquet
# If missing, run: python3 mock_data_producer.py &

# 4. Required Python packages
python3 -c "import aiohttp, psutil, apscheduler, pandas, numpy, backtrader, quantstats_lumi, reportlab, markdown, pdfkit" && echo OK
# If any missing: pip install --break-system-packages aiohttp psutil apscheduler reportlab markdown pdfkit
```

## Run Modes

```bash
# Forever (production)
python3 -m autonomous_agency.run_loop --interval 30 --hypotheses 8

# 10 cycles then exit (test)
python3 -m autonomous_agency.run_loop --max 10 --interval 5 --hypotheses 5

# Single cycle immediately
python3 -m autonomous_agency.run_loop --max 1 --interval 0 --hypotheses 1

# Verbose (DEBUG-level)
python3 -m autonomous_agency.run_loop -v --max 2 --hypotheses 3
```

All modes accept `--interval N` (seconds between cycles, default 30)
and `--hypotheses N` (strategies per cycle, default 3).

## Health Monitoring

```bash
# Live cycle stats
tail -f autonomous_agency.log

# Generated strategies
ls autonomous_agency/strategies/ | wc -l
ls autonomous_agency/strategies/ | tail -5

# Per-cycle stats (one line per cycle)
grep "Cycle .* end" autonomous_agency.log | tail -10
```

Healthy run looks like:

```
=== Cycle 1 end (8.4s) ===
Final stats: cycles_completed: 1, cycles_failed: 0,
  hypotheses_generated: 8, strategies_created: 8,
  backtests_completed: 8, backtests_failed: 0,
  elite_strategies: 0, last_cycle_seconds: 8.4
```

`backtests_failed: 0` and `cycles_failed: 0` are the key
invariants. `elite_strategies: 0` is expected as long as the
generated strategies are placeholders (no trades); once a real
code-gen backend (Kilo Code, or LLM with code-generation prompts)
is wired, this number will rise.

## Common Failure Modes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SSL: CERTIFICATE_VERIFY_FAILED` | gateway uses self-signed cert | `export BTQ_LLM_INSECURE=1` |
| `HTTP 429: Token Plan usage limit reached: 2056` | upstream MiniMax quota empty | add credits OR wait for next billing cycle; loop falls back to template |
| `Wonderland upstream is not configured` | systemd unit missing `EnvironmentFile=` | see `references/hermes-llm-gateway.md` "Systemd Unit" section |
| `'AutomatedBacktester' object has no attribute 'strategy_loader'` | someone reverted `backtester.py` and removed the `self.strategy_loader` line | re-apply the patch (see takeover log issue #4) |
| `ModuleNotFoundError: No module named 'quantstats_lumi'` | fresh install | `pip install --break-system-packages quantstats-lumi` |
| `AttributeError: 'NoneType' object has no attribute 'addindicator'` | leftover stale code from before `if feed is not None` fix | re-apply the patch from takeover log #15 |
| `Cycle 1: 0 strategies to backtest, skipping remaining phases` | LLM returned empty + fallback parser rejected the JSON | see `pitfall` in `SKILL.md` #8 — the fallback must be a top-level flat object |
| `git status` says "Revert zurzeit im Gange" | external hook started a `git revert` | `git revert --abort` and re-apply patches |

## What the Loop Does Per Cycle

```
1. Hypothesize:    N LLM calls (8 by default) via llm_adapter → gateway → MiniMax
                   Falls back to deterministic template on 4xx/5xx
2. Materialize:    Write 1 Python file per hypothesis to
                   autonomous_agency/strategies/<Name>_<timestamp>.py
                   via StrategyFactory (Kilo Code CLI fallback to template)
3. Backtest:       Run backtrader on the .btq_cache/*.parquet data
                   (~5s per backtest on 35k bars)
4. Evaluate:       Score the backtest (Sharpe, drawdown, win rate, ...)
                   On failure: synthesize a minimal ValidationResult
5. Evolve:         Genetic operators (ParameterMutation,
                   StructureMutation, Crossover) on the validation
                   set. With <5 strategies → "Sample larger than
                   population" warning, 0 elite (non-fatal).
6. Archive:        Persist the evolution result via StrategyArchiver
                   (best-effort, no-op on None)
7. Sleep:          Wait `cycle_interval_seconds` then repeat
```

## Hard Constraints (operator rule)

> "du hast ALLE freiheiten, außer das du NICHT bestehenden code
>  neu/umbaust aus BTQuant. autonomous_agency ja, rest nein!"

All edits stay inside `autonomous_agency/`. Do not modify
`dependencies/backtrader/`, `hotspine/`, `dependencies/BTQ_Render_Engine/`,
`mcp-adapter/`, project-root `run_agency.py`, or any other
top-level code. The exception is the gateway in
`projects/hermes-crypto/` (a separate project, not BTQuant) which
needed one systemd unit edit on 2026-06-18.
