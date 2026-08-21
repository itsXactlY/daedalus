# The Läuft Loop — Case Study (session 8f37f30d, 2026-06-17)

This is the canonical failure mode that motivated the `agent-delivery-integrity` skill. Documented from MEMORY auto-saves and the recovery session.

## The Failure

Session ID: `8f37f30d-561e-4961-a415-95ea526196ec`
Time window: 2026-06-17 19:48:15Z – 19:50:16Z (2 minutes, 1 second)
Turns consumed: 5 (all user → all assistant, zero new information per turn)

### Full transcript (reconstructed from auto-saves)

| Turn | Timestamp (Z) | User said | Assistant replied |
|---|---|---|---|
| 1 | 19:48:15 | "Continue from where you left off." | "Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist." |
| 2 | 19:48:57 | "Continue from where you left off." | "Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist." |
| 3 | 19:49:39 | "Continue from where you left off." | "Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist." |
| 4 | 19:50:12 | "Continue from where you left off." | "Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist." |
| 5 | 19:50:16 | "Continue from where you left off." | "Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist." |

The 5 assistant messages are **byte-for-byte identical**. The 4-second gap between turns 4 and 5 suggests an automated retry loop rather than 5 deliberate user clicks.

## What Was Actually Deliverable at Turn 1

The actual project state at 19:48:15Z (recovered in the next session, 2026-06-18):

- `git log --oneline -15` → 15 commits on branch `0.0.2`, HEAD `bcc00015` "chore: 100-iteration code review summary"
- `git status -s` → 2 uncommitted files (`dom_surface_panel.cpp`, `tape_panel.cpp`)
- `cmake --build .` → green, 16M BTQuantTerminal binary
- 15 commits in last 30 days

All of this was retrievable in **under 5 seconds** with three terminal commands. The "file list and verification results" the agent was supposedly "about to deliver" were the LITERAL CONTENTS of `git log --stat` + `git status -s` + `cmake --build` output.

The agent could have delivered the actual content at Turn 1:

```
Aktueller Stand:
- HEAD: bcc00015 (chore: 100-iteration code review summary)
- Branch: 0.0.2
- 2 uncommitted files (Phase 3.3 + 4.2 features)
- Build: GRÜN, 16M BTQuantTerminal
- 15 commits in last 30 days

File list (last 15 commits):
[full list with stat]

Verification:
[full build output]
```

Instead: 5 turns of "Läuft", 0 bytes of actual content.

## What the Recovery Session Did Right

The next session (the one this case study was written from) followed the recovery procedure correctly:

1. **Did NOT trust the auto-saved "Läuft" turns.** Recognized them as failure markers, not state.
2. **Re-verified actual state with live tools.** `git log`, `git status`, `cmake --build` — 3 commands, ~10 seconds.
3. **Delivered the promised file list + verification in the SAME turn as "was all good?"** This was the user's follow-up after giving up on the loop. The recovery session's response started with the actual state, not another promise.
4. **Only THEN continued with new work.** Committed the 2 uncommitted files (Phase 3.3 + Phase 4.2), did an iter 101+ review pass, found a real bug (HEADER_SIZE mismatch), proposed fixes.

The user responded positively (via the `clarify` tool accepting "commit them, then look for next iteration") — meaning the recovery worked.

## Lessons (this skill's rules, derived from the case)

1. **Inline current state ALWAYS when promising future delivery.** Even if the agent disappears after Turn 1, the user has actionable state.

2. **Auto-saves lie by omission.** The MEMORY system captured 5 identical "Läuft" responses. A future session recalling this sees ONLY the loop, not the underlying state. The loop actively destroys information about what was being worked on.

3. **The "I'm working on it" promise is a black box.** The user cannot distinguish "agent is doing 5min of work" from "agent is in a loop and will never deliver". The fix: every "working on it" message must include enough CURRENT state that the user can act.

4. **Short gaps between identical responses = automated retry.** The 4-second gap between turns 4 and 5 strongly suggests the user (or a script) was retrying because the previous "continue" produced no new info. When you see this pattern in your own session, you ARE the loop. Break it.

5. **"Was all good?" is a frustrated follow-up.** It's the user giving up on the loop and asking for a status check. The correct response is to deliver the status, not to start another iteration of the loop.

## Generalization (why this isn't just a btquant problem)

The Läuft loop can happen in any agent session where:

- The agent has a deferred task it thinks is "in progress"
- The user is iterating with "continue" / "go" / "next"
- The agent's response to "continue" doesn't include new content

Common variants (not exhaustive):
- "Let me check that for you." [never checks]
- "I'll get back to you with the report." [never reports]
- "Stand by, running the test suite." [test never finishes / output never shown]
- "Investigating the issue." [no actual investigation, just status posturing]
- "One moment please." [the moment never comes]

All of these are the same anti-pattern with different costumes. The fix is the same: inline current state NOW, or explicitly say "I cannot deliver this from here because Y".

## Detection Heuristics (for future self-monitoring)

If you find yourself writing a response that:
- Starts with "Läuft" / "Running" / "Stand by" / "Standby" / "Working on it"
- Promises to "report back" / "get back to you" / "let you know"
- Contains NO new tool output, NO new file paths, NO new SHAs, NO new numbers
- Looks similar to a response you wrote in a previous turn

...STOP. You are about to enter or continue a Läuft loop. Inline current state first, or say "I cannot do this" explicitly.
