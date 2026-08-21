---
name: mazemaker-demo
category: mazemaker
description: Fast, iteration-efficient mazemaker demo for Discord/CLI — hits ALL key features in 5-7 tool calls (not 400). Uses mazemaker_health (one-call stats+dream+AFE), targeted recall, and graph traversal. Never needs iteration limit bumps.
---

# Mazemaker Demo — Iteration-Efficient

## When to Load

- User asks "gib mal ne mazemaker demo" / "show me mazemaker" / "demonstrate the memory engine"
- User wants current stats + recall demo + dream engine showcase + graph overview
- **ESPECIALLY in Discord** where the agent starts cold (no pre-loaded context) and risks hitting 400-iteration limit

## Core Principle

**One call replaces four.** `mazemaker_health` returns corpus stats, dream stats, AFE status, and DAE freshness — that's what used to take `stats` + `dream_stats` + `dream_control` + `health` as separate calls.

## The 7-Call Demo Script

Call these in order. Each builds on the last. If someone interrupts or asks a side question mid-demo, answer that first then resume — don't restart.

### 1. health — the single-pull snapshot

```
mazemaker_health()
```

Returns: `memories`, `connections`, `dream.sessions`, `dream.total_processed`, `dream.total_strengthened`, `dream.total_pruned`, `dream.total_bridges`, `dream.total_insights`, `insight_types` (bridge + cluster), `afe` status, `dae` note.

This alone is the bulk of any "what's the state" answer. Lead with it.

### 2. recall — semantic search (pick 1-2)

```
mazemaker_recall(query="<something the user cares about>")
```

Pick queries relevant to the audience:
- **General demo:** "mazemaker recall performance" or "dream engine status config"
- **Code/trade audience:** "trading strategy backtest result" or "btquant deployment"
- **DayZ audience:** "dayz vppmap layout fix" or "enforce script singleton pattern"
- **Random fun:** "carbonara italian food preference" (the running meme)

If the first recall returns weak hits (sim < 0.4), say so honestly: "sim=0.25, mid-flight re-embedding" — **do NOT** call recall again with a paraphrased query. That's the cascade pattern. Accept the result and move on.

### 3. recall_multi — multi-angle (optional, 1 call)

```
mazemaker_recall_multi(angles=["mazemaker demo iteration", "discord demo limit 400", "mazemaker demo timeout"])
```

Shows the fusion feature. Only if the audience is technical enough to care about RRF.

### 4. think — graph traversal (1 call, pick a memory from step 2)

```
mazemaker_think(memory_id=<id from step 2>, depth=2)
```

Shows the knowledge graph in action. "From memory about X, here's what it connects to."

### 5. dream_control — daemon status (1 quick call)

```
mazemaker_dream_control(action="status")
```

Returns running/idle + cycle count. If idle: "daemon is paused, runs on demand" — that's fine. Don't start a dream cycle mid-demo unless specifically asked (it blocks).

### 6. graph — top weighted connections (1 call)

```
mazemaker_graph(limit=10)
```

Shows the strongest semantic edges. Not always needed — skip if you're already at 5-6 calls.

### 7. quota — usage (optional, 1 call)

```
mazemaker_quota()
```

Only if asked about limits or pricing.

## What NOT To Do (Iteration Traps)

### ❌ Don't call these separately — they're all in health:
- `mazemaker_stats` → part of health
- `mazemaker_dream_stats` → part of health  
- `mazemaker_dream_control("status")` → do call separately if you need daemon run state (health doesn't include this)
- `mazemaker_afe_facts` → part of health
- `mazemaker_mazemaker_health` → that's the whole point

### ❌ Don't cascade on weak recall:
If `mazemaker_recall` returns sim=0.3 or lower, DO NOT call it again with a rephrased query. Accept the result, explain why (e.g. "re-embedding in progress / corpus shape"), and move on. One recall, one answer.

### ❌ Don't run dream cycles mid-demo:
`mazemaker_dream()` with phase="nrem" takes minutes on a 200K-corpus. The 180s or 600s timeout will fire before it finishes. The agent blocks waiting. The user sees silence. The iteration counter ticks up on timeout. Bad.

If someone asks "can it dream right now?" Say "yes, daemon is configured, NREM processes 2000 memories per cycle with 50/30/20 sampling — but a cycle takes minutes. Let me show you the accumulated stats instead." Then show health.

### ❌ Don't explore too deep:
`mazemaker_think` with depth=5 on a heavily connected memory returns hundreds of neighbours. That's too much output. Depth=2 is enough for a demo.

### ❌ Don't re-explain the skill:
Don't say "I loaded the mazemaker-demo skill" or "according to the mazemaker-demo skill" — just deliver the demo naturally.

## If Asked for Deeper Details

| Question | Use | Instead of |
|---|---|---|
| "Show me NREM params" | `mazemaker_dream_config(action="get")` | Multiple separate calls |
| "Show me connection details" | `mazemaker_think(memory_id=X)` | `mazemaker_graph` again |
| "Show me latest memories" | `mazemaker_browse(limit=5)` | Recalling vague queries |
| "Is the encrypt-on-write bug fixed?" | `mazemaker_recall("encrypt on write cipher embedding wonderland")` | Starting from scratch |
| "Show me dream cycles" | `mazemaker_dream_stats` (if health not fresh) | Health already has it |

## Demo Narrative Template

```
🧠 **Mazemaker Live** — 200K memories, 57K connections, 1024-d BGE-M3

**Health snapshot:**
📦 {health.corpus.memories} memories, {health.corpus.connections} connections
💭 {health.dream.sessions} dream sessions, {health.dream.total_processed} paths processed
   → {health.dream.total_strengthened} edges strengthened
   → {health.dream.total_pruned} edges pruned  
   → {health.dream.total_bridges} bridges discovered
🔍 {health.dream.insight_types.bridge} bridge insights, {health.dream.insight_types.cluster} cluster insights

**Cross-session recall:**
{mazemaker_recall result — 1-2 hits with sim >= 0.4, cite by id}

**Graph traversal (from id=X):**
{mazemaker_think — depth 2, show connected concepts}
```

## Verification

- Count your tool calls before firing. If you're at 6+ and the user hasn't asked for more details, wrap up.
- If you're at 8+ calls and not done, you've fallen into a cascade or an unnecessary deep dive. Stop, summarize what you have, offer to go deeper.
- Never exceed 10 tool calls in a single demo session. If the user wants more, they'll ask — that's a new turn, not more iterations in this one.
