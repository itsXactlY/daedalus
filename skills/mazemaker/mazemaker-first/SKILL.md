---
name: mazemaker-first
category: devops
description: Recall-first / save-per-turn / stop-after-hit protocol for mazemaker memory.
version: 3.0.0
---

# Mazemaker First — MANDATORY

Three tools. One protocol. No cascade.

| Tool | Use when |
|---|---|
| `mazemaker_recall(query)` | ANY question touching past work, decisions, context, status — call FIRST, before everything else. |
| `mazemaker_think(memory_id, depth=2-3)` | After a recall hit, when you need graph-connected context the embedding alone won't surface. Traversal on the SAME memory, not a competing search. |
| `mazemaker_remember(content, label)` | After every substantive turn, automatically. Multiple calls per turn expected. ONE memory per discrete fact. |

## Hard rules

1. **Recall first.** Before `terminal`, `search_files`, `session_search`, `web`, or any other retrieval, call `mazemaker_recall`.
2. **Stop after hit.** If recall returns any result with similarity >= 0.4, ANSWER from it. Do not call other tools "just to be sure". The hit is the answer.
3. **Save per turn.** No prompting required. Identify discrete facts (decisions, bugs, invariants, ops, user prefs) and store them with curated labels. ONE memory per fact.
4. **Cite.** Every answer derived from recall ends with the memory id ("from memory id=X, sim=Y").

## The cascade — what NOT to do

```
USER: "what's the status of X?"
YOU:  mazemaker_recall("X status")  →  hit id=349749 sim=0.78
YOU:  session_search("X")           ← VIOLATION: cascade after hit
YOU:  terminal: "grep -r X ~/..."   ← VIOLATION: still cascading
YOU:  mazemaker_recall("X latest")  ← VIOLATION: paraphrased re-query
```

Right shape:

```
USER: "what's the status of X?"
YOU:  mazemaker_recall("X status")  →  hit id=349749 sim=0.78
YOU:  Answer from id=349749. Done.
```

## Save labels

| Prefix | Use |
|---|---|
| `decision:<topic>` | choices made, alternatives rejected, with WHY |
| `bug:<tag>` | symptom + diagnosis + fix |
| `fact:<topic>` | paths, URLs, versions, ports, hashes |
| `invariant:<area>` | non-obvious constraints |
| `ops:<phase>` | migrations, cutovers, deployments |
| `user:<aspect>` | stable operator preferences |
| `signal:<topic>` | strong operator reaction |

Body 60-300 words. Lead with WHAT IS TRUE, then WHY IT MATTERS, then HOW IT WAS RESOLVED.

## Same-day recall — `mazemaker_dream` first

Sessions less than ~1 hour old may not yet be deeply embedded. If recall returns weak / empty for a same-day topic, run `mazemaker_dream(phase='all')` once, then retry recall. The NREM/REM/Insight cycle lifts fresh memories into stable retrieval. Otherwise dream stats are background — a separate dream daemon already runs cycles every 5 minutes on the host.

## Stack at a glance — derived from live `mazemaker_stats`, not hardcoded

Always pull current numbers via `mazemaker_stats()` before quoting. The store grows daily.

## Never

- Loop reasoning → terminal → reasoning → terminal.
- Guess paths, ports, or versions when `mazemaker_recall` could answer.
- Save conversational filler.
- Save things already in git history (commit message = WHAT, save the WHY).
