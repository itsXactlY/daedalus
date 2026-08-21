---
name: daedalus-observability-patterns
title: Daedalus Agent Observability Patterns
description: Pattern catalog for LLM agent observability, recovery, and identity stability. Maps three academic patterns (CYGNET pre-execution gate, Model-Native Computing Architecture, Semantic Invariance testing) to failure modes operators see in production agent deployments.
trigger: agent crash loops in logs; missing telemetry in production rollout; canary identity drift after model swap
---

# Daedalus Agent Observability Patterns

A pattern catalog for three failure modes that recur in production LLM agent
deployments: **crash loops**, **telemetry blind spots**, **identity drift**.
Each pattern is grounded in a 2026 academic paper and includes a problem
statement, mechanism, operator question, and a runtime verification signal.

Use this when an agent is failing in production but the failure does NOT map
to a clean code defect — the agent is "running fine" but producing wrong
outputs, looping, or losing its identity.

---

## Pattern 1 — CYGNET Pre-Execution Gate

**Reference:** Tomczak, N. (2026). *CYGNET: Cypher Gate for Neural
Execution Triage and Cost Containment.* arXiv:2606.04645.
**Problem:** Agent crash loops caused by structurally broken queries being
executed against production state — same broken query, same error, retry
budget exhausted, then halt or runaway spin.
**Core mechanism:** Place a lightweight gate BETWEEN the agent's query
generator and the downstream executor. Triage on syntactic well-formedness,
schema validity, and estimated cost; route broken queries to a corrector
before they reach production. Median overhead 5.6 ms.
**When to apply (operator question):** "Is my agent retrying the same
broken query against production, burning cost and time before crashing?"
**Runtime signal:** A `gate_decision` log line on every query recording
`{query_hash, verdict, corrector_invoked, latency_ms}`; alert when
`verdict == reroute` rate exceeds 5% over 5 minutes.

---

## Pattern 2 — Model-Native Computing Architecture

**Reference:** Lin, H., Pao, H., Zhan, S. (2026). arXiv:2606.00288
(*Model-Native Computing Architecture*).
**Problem:** Telemetry blind spots — operators see the agent "is doing
something" but cannot answer: what is in cache? what is the working set?
is the scheduler starving it? does it have permission for what it attempts?
**Core mechanism:** Treat the agent runtime as a computer system. Map
LLM → CPU, KV cache → processor cache, context window → main memory,
agent framework → OS, scheduler → process scheduler, permissions → page
table. Log every action against one of these axes.
**When to apply (operator question):** "I have agent logs but cannot tell
WHY the agent is slow, expensive, or hitting permission walls — am I
missing the architectural layer of telemetry?"
**Runtime signal:** A `mnca_metric` event on every LLM call carrying
`{kv_cache_hit_ratio, context_window_used_tokens, context_window_capacity,
scheduler_queue_depth, permission_decision}`; plottable as time-series.

---

## Pattern 3 — Semantic Invariance Canary

**Reference:** Zarzà, I. D., Curtò, J., Cabot, J. (2026). *Semantic
Invariance in Agentic AI.* Semantic Scholar 9336f87bd96208dd0d43f19b087e507fdc64032c.
**Problem:** Canary identity drift — a known-good reference agent silently
shifts outputs after model swap or prompt change. The shift is semantic,
not syntactic (outputs still parse but mean different things).
**Core mechanism:** Metamorphic testing with 8 semantic-preserving
transformations (paraphrase, reorder, format-shift, entity-swap, …) across
7 foundation models / 4 architectural families. Identity = invariance under
transformation; drift = a transformation that flips a decision.
**When to apply (operator question):** "After my last model swap, the
canary agent looks fine in dashboards but I am not confident it is the
SAME agent. Did its identity drift?"
**Runtime signal:** A `semantic_invariance_probe` job running N=20
paired transformations on every model swap or weekly; emits `{pair_id,
decision_a, decision_b, invariant}`; alert when invariant_rate < 0.85.

---

## When to Apply — Decision Matrix

Map observed failure mode to the pattern that addresses it.

| Observed failure mode | First pattern to apply | Why |
|----|----|----|
| Agent retries the same broken query and crashes | **CYGNET pre-execution gate** | Triage breaks the loop before execution, not after failure |
| Agent slow/expensive/over-budget but no metric explains it | **Model-Native Computing Architecture** | You are missing architectural telemetry — emit KV-cache, context, scheduler, permission signals |
| Canary agent outputs LOOK fine but drift suspected after model swap | **Semantic Invariance Canary** | Metamorphic probes detect decision-flip under paraphrase that dashboards miss |
| Agent crash-loops AND you cannot tell why | **CYGNET first**, then **Model-Native** | Stop the bleeding, then instrument to explain the root cause |
| Identity drift suspected AND telemetry is sparse | **Semantic Invariance first**, then **Model-Native** | Drift is silent without probes; add architectural telemetry to explain context-window effects on invariance |
| Permission denied storms / scheduler starvation | **Model-Native Computing Architecture** | Permission and scheduler are architectural-layer signals; other patterns do not surface them |
| Post-deployment regression hunt across model swap | **Semantic Invariance Canary** as detector, **Model-Native** for cost/latency delta, **CYGNET** only if queries are now structurally invalid | Layered defense per axis of regression |
| Production rollout of a new agent version | All three in order: **CYGNET** (gate new query shapes), **Model-Native** (instrument from day one), **Semantic Invariance** (canary on day two) | Each pattern covers a different class of regression |

---

## Verification

For each pattern, confirm at least ONE runtime signal in your agent logs
that would surface the addressed failure mode:

1. **CYGNET pre-execution gate** — Search logs for `gate_decision` events.
   Absent → gate is not wired and crash loops will reach production.
   Present → count `verdict == reroute` over the last 24h; > 5% rate
   means regression pending.
2. **Model-Native Computing Architecture** — Search logs for `mnca_metric`
   events with `kv_cache_hit_ratio` and `context_window_used_tokens`.
   Absent → you have an event log, not telemetry. Present → confirm
   the metrics are plottable as time-series (Prometheus / OpenTelemetry
   exporter).
3. **Semantic Invariance canary** — Search for `semantic_invariance_probe`
   results on the canary for the most recent model swap. Absent → run
   the probe manually: pick 5 paraphrased pairs from your eval set,
   confirm decision invariance, fail loudly on any flip.

If any of the three signals is missing in your current logging stack,
that is your next instrumentation ticket — not a research project, a
one-day wiring job.

---

## References

- Tomczak, N. (2026). arXiv:2606.04645.
- Lin, H., Pao, H., Zhan, S. (2026). arXiv:2606.00288.
- Zarzà, I. D., Curtò, J., Cabot, J. (2026). Semantic Scholar
  9336f87bd96208dd0d43f19b087e507fdc64032c.

All three surfaced from Pulse-Wurm 2.0 tick 2026-06-19 (memory id
822471) on the LLM agent observability/recovery/identity cluster.
