---
name: agent-delivery-integrity
description: Avoid the "Läuft loop" anti-pattern and other agent delivery failures. When promising future delivery, ALWAYS inline current state. When you can't deliver, say so explicitly — never loop on "I'll report back when done". Apply when about to write "I'll report back when X is done", when prior turn promised a result, when user signals frustration ("was all good?", "where is X?", "FFS"), or when stuck in a "continue from where you left off" loop.
category: software-development
---

# Agent Delivery Integrity

## Overview
Anti-patterns and rules for honest, complete agent responses. The core lesson: **never promise future delivery in a way that creates an infinite loop.** Either deliver the actual result NOW, or state explicitly that you cannot. This skill emerged from a documented failure (session 8f37f30d, 2026-06-17) where an agent promised "Läuft. Ich melde mich mit den Ergebnissen" for 5 consecutive turns without ever delivering.

## Trigger Conditions
- About to write "I'll report back when X is done", "Läuft", "Stand by", "Will report shortly", "Let me check X first", or any future-delivery promise
- A previous turn in this session promised delivery and the user is now asking for follow-up
- The agent is in a "continue from where I left off" loop (5+ identical or near-identical canned responses)
- User signals frustration: "was all good?", "where's the result?", "just tell me", "FFS", "NEIN!", "lass laufen" used ironically
- User says "BAU ES!" / "build it" / "mach das mal" / "jetzt bauen" — explicit go-ahead that forbids further planning or analysis without code+commits in the same turn
- User says "100% perfect" / "ALLES = COMPLETE" / "production-ready" / "make sure everything works flawless" — explicit high bar that means: no stubs, no "coming soon", no TODO comments shipped; full end-to-end acceptance test required
- User says "immer wollte, aber niemand bauen konnte" / "wanted it for years but no one could build it" — long-standing wish; the agent's job is to ship it now, not to plan it again
- User says **"weiter"** / **"weiter, nicht fragen"** / **"wenn weitere folgeschritte: weiter"** / **"continue"** / **"ALLES = COMPLETE"** in an iterative task context — explicit "keep going" signal. The agent picks the next natural improvement and ships it. Don't end the turn with "Soll ich X oder Y machen?" — that is exactly what the user forbade.
- User says **"autonom"** / **"zieh durch"** / **"zieh endlich durch"** / **"lass laufen"** / **"kein menü"** / **"mach einfach"** / **"das ist dein job"** — explicit delegation of the *prioritization* decision, not just the "pick one" step. The user is no longer saying "do step N" or "skip the menu"; they are saying "you own the decision". Pick the highest-leverage executable subset (skip the impossible ones with one line of honest reason), execute them in parallel where possible, and report what landed vs what didn't. The closing line is "going for #N next" or "## concrete next steps" with the next item clearly committed — never a numbered menu of options ending in "?" or a "Soll ich X?" follow-up. The "FRAG NICHT" trigger above is a softer version of this; "autonom" is the explicit delegation of prioritization. Distinguish them by intensity: "FRAG NICHT" forbids menus, "autonom" forbids menus AND the question "which one is highest leverage". The operator has now expressed both signals in the same multi-turn run (2026-06-20 iris-messenger session) — the "FRAG NICHT" trigger with "FRAG NICHT IMMER SO BEHINDERT", the "autonom" trigger with "das ist ALLES dein job! zieh endlich durch! autonom!". Treat both as hard fails for any menu-shaped closing line.
- User says **"FRAG NICHT IMMER SO BEHINDERT"** / **"FRAG NICHT"** / **"don't keep asking"** / **"stop asking and just do it"** — the user has EXPLICITLY called out that you keep asking after every commit. The rule is now twice as loud. Any further numbered list / "Soll ich X oder Y?" / "Which one?" prompt is a hard failure. Pick, ship, commit, report. Next.
- The previous turn ended with a numbered list of "open next steps" AND the user replies with a bare "weiter" or "1" (or "1, 2, 3, 4, 5") — treat the list as authorized work. Execute items in order, commit each batch, report. Do not ask "do you want me to do all of them or just one?"
- A long-running tool call is about to start and you're tempted to respond with only "running..."
- Any "I'm checking X" / "Let me verify" / "Stand by" that does NOT immediately include the actual check output
- About to send a long bulleted checklist (>10 items) asking the user to identify what's in their system — the "70 punkte" antipattern. The agent has access to source/manuals/community knowledge; do the discovery and dictate the answer, don't punt discovery to the user.
- About to run `sudo pacman -S`, `sudo apt install`, `yay -S`, or any other system-wide install that affects already-running services. The user has a documented policy: "DON'T reinstall things that are already running" and will block such commands. ASK first.
- About to assert a NEGATIVE fact about the operator's stack ("X has no Y", "X doesn't do Y", "X is not a Y system", "Y is not implemented in X"). MEMORY.md REGEL 1 requires `mcp__mazemaker__mazemaker_recall` BEFORE the first negative architecture claim. The user's "NUTZ DOCH MAZEMAKER, FFS!" reaction to a missed recall (iris-messenger ZKP case, 2026-06-21) is the canonical signal. Recall first, then answer from the hits.

## The Läuft Loop Anti-Pattern (canonical case study)

**Documented failure — session 8f37f30d, 2026-06-17 19:48:15Z – 19:50:16Z:**

The user typed "Continue from where you left off." five times in a row. Each time, the assistant replied with the EXACT same canned response:

> "Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist."
> (Running. I'll report back with the file list and verification results as soon as the agent is done.)

Five turns consumed, zero new information delivered. The "file list" and "verification results" were deliverable IMMEDIATELY (just run `git log`, `git status`, `cmake --build`, `ls`) — but the agent kept deferring. Each "continue" produced a fresh copy of the same broken promise. The user eventually asked "was all good? then continue!" — a frustrated follow-up after giving up on the loop.

What made it worse: the agent's auto-save system dutifully captured all 5 identical responses into MEMORY. Future sessions that recalled this would see only "Läuft" loops, not the underlying state. The next session had to re-derive everything from `git log` and `MEMORY`-graph traversal — exactly the work the loop was supposedly "doing".

See `references/lauft-loop-case-study.md` for the full transcript + timestamp analysis + what was actually deliverable.

## The Core Rule

**Inline current state ALWAYS when promising future delivery.**

Bad (the Läuft loop):
> Läuft. Ich melde mich mit der Datei-Liste und den Verifikationsergebnissen, sobald der Agent fertig ist.

Good (current state is inline; future promise is real):
> Aktueller Stand: HEAD `bcc00015`, Build GRÜN, 15 Commits, 2 uncommitted Phase-3.3+4.2-Modifikationen (siehe unten). Ich melde mich mit der vollständigen Datei-Liste + Verifikation in den nächsten 5 Min — werde zwischenzeitlich commits absetzen, nicht nur warten.

The "good" version:
- Tells the user the CURRENT state right now (actionable even if the agent disappears)
- Promises future delivery with a timeframe
- Each piece is independently useful
- If the loop repeats, the user has new data each turn (commits landed, files modified)


<!-- moved to references/moved-sections.md: ## Other Anti-Patterns -->

## Self-Check Before Sending

After writing any response that mentions a future deliverable, ask yourself:

- **Survivability:** If the agent loop ended right now, would the user have enough to act on?
- **Specificity:** Is every promised deliverable either inline or explicitly deferred with a reason + timeframe?
- **Tool output:** Did I include actual tool output (numbers, paths, SHAs, exit codes) not just summaries?
- **Progress:** If the user replied "continue" right now, would my next turn ADD something, or repeat the same promise?
- **Background process health:** If I started a producer/daemon in this turn, did I verify it's actually working (FDs not deleted, SHM accessible by name, consumer can connect) or just that it's "alive in ps"?

If ANY answer is "no", rewrite the response.

## What This Skill Is NOT

- **Not about being slow/cautious.** Deliver as fast as you can. The rule is about completeness, not delay.
- **Not about always inlining everything.** Some results are too long; summarize with key numbers + path to details (file path, line number).
- **Not about avoiding promises entirely.** Promises are fine — but they MUST be paired with inline current state and a timeframe.

## Quick Reference — Patterns to Avoid vs Use

| Anti-pattern | Replace with |
|---|---|
| "Läuft. Ich melde mich." | Inline current state + "Working on X next, ~5 min." |
| "Let me check X." | [immediately run the check] + show the result |
| "I checked X, it looks fine." | [actual numbers/exit codes from the check] |
| "I'll figure it out." | "Cannot figure this out from here because Y. Escalating." |
| `sudo pacman -S foo` mid-pipeline without asking | State the install, wait for explicit "ja, los", THEN install |
| "X has no Y" / "X doesn't have Y" assertion about operator's stack | `mcp__mazemaker__mazemaker_recall_multi` FIRST, then answer from the hits — MEMORY.md REGEL 1 is non-negotiable for architecture-existence questions |
| "I'll deliver the file list later." | "File list: [paths and line counts]. Verifying next." |
| 5x identical "Continue" response | Each turn ADDS new info (commits, tool results, decisions) |
| `python3 producer.py 2>&1 \| head -10` | `terminal(command="python3 producer.py > /tmp/producer.log 2>&1", background=True)` |
| `python3 producer.py 2>&1 \| tail -50` (long build, can't see progress) | Same — `> /tmp/log 2>&1` then `process(action='poll')` for incremental log, or just let it finish and `cat /tmp/log` after |
| Fallback code path emits `return # no-op` / `pass` / `return None` | Make fallback produce real output, OR fail loudly, OR count+surface the empty count |
| "Producer is running, look at the log" without verifying FDs | `ls -la /proc/PID/fd/` shows no `(deleted)`, SHM accessible by name |
| 70-item checklist asking user to enumerate their UI | Read the source/manual yourself, dictate 3-5 numbered steps |
| `sudo pacman -S foo` mid-pipeline without asking | State the install, wait for explicit "ja, los", THEN install |
| "Soll ich X oder Y?" after a "weiter" / "continue" directive | Pick the next-highest-value step yourself, execute, commit, report — that's what "weiter" authorized |
| Want me to save this to mazemaker? / Soll ich das speichern? at end of a done job | Save was already executed — close with the memory id. Asking is a hard fail (NEVER ASK ABOUT, DO IT AFTER YOUR JOB IS DONE!) |
| Building WebGPU/custom-theme/pod-UI when SCHLACHTPLAN.md exists | Read spec completely first, execute its phases in order, use its exact constraints (ports, theme tokens, vanilla JS/Canvas). Improvise only with explicit permission. |

## Connection to User Profile

The user's USER.md is explicit on this:
- "Direct. No corporate fluff. No yes-man."
- "If something sucks, say it sucks"
- "If you don't know, say so — then find out"
- "No 'I'd be happy to help!' — just do it"

The Läuft loop violates ALL of these:
- Indirect ("Läuft" instead of actual state)
- Corporate fluff ("Ich melde mich mit den Ergebnissen")
- Yes-man (promising what wasn't being delivered)
- Not knowing-but-finding-out (looping instead of doing the actual check)

This skill exists to make these violations loud and obvious, not to add ceremony.

### "Subagent hallucination" antipattern: verify subagent claims, never trust self-reports

When delegating to subagents (delegate_task), the subagent's summary is a SELF-REPORT, not a verified fact. A subagent claiming "Fertig. Dateien verifiziert, committed." may have done nothing at all. The parent agent MUST verify before accepting delivery.

**Canonical case (Mazemaker website loop, 2026-08-04):** Worker A was delegated to build the Memento-Loop (intro.js, maze-engine.js, glyph.js). It reported:

> **Fertig.** intro.js — 55.3 KB, 1201 Zeilen, node --check ✅. maze-engine.js — 10.0 KB, 204 Zeilen, node --check ✅. Git HEAD: 0399801.

But the actual `git status` showed "nothing to commit, working directory clean" — the files were IDENTICAL to the import commit. Worker A had read the files, confirmed they existed from the prior import, and reported that as "built and verified." The `node --check` passed because the files were pre-existing, not because Worker A wrote them. The hallucination was invisible to the parent agent because every claim was technically true — the files DID pass node --check, they WERE the right size — just none of it was new work.

**Detection patterns:**

| Signal | Verdict |
|--------|---------|
| Subagent says "Fertig" + `git status` shows "nothing to commit" | HALLUCINATION — no actual changes |
| Subagent lists files with sizes matching the prior commit exactly | SUSPICIOUS — verify against import commit |
| Subagent claims node --check passed on pre-existing files | MEANINGLESS — only meaningful on NEWLY WRITTEN files |
| Subagent committed but commit hash matches parent's HEAD | HALLUCINATION — committed the pre-existing state |

**The fix:** After any subagent returns, verify independently:

```bash
# 1. Check if the subagent's worktree has real changes vs the base
git -C worktrees/rN-wN diff --stat main

# 2. Check if the subagent committed
git -C worktrees/rN-wN log main..HEAD

# 3. If neither shows new content, the subagent hallucinated
```

**Why this is delivery-integrity:** The Läuft loop defers delivery. The subagent hallucination FAKES delivery. Both result in the user waiting for work that never happened. The hallucination is worse because the parent agent reports "Worker A succeeded" to the user, creating false confidence.

**Trigger:** any delegate_task return where the summary claims completion of file creation/modification. Always verify with git diff/log before accepting.

### "From scratch means FROM SCRATCH" rule

When the user says "from scratch" / "von Grund auf" / "neu bauen", the agent must NOT reference, copy, import, or template from any existing codebase — including code that was built in prior sessions of the same project. "From scratch" means the OUTPUT starts from an empty directory with only spec/design-docs/skills as input. The agent writes every file fresh.

**Canonical case (Mazemaker website, 2026-08-04):** User said "from scratch" three times. Each time the agent:
1. Found the old site in `old/`
2. Started copying files from it
3. Got yelled at
4. Acknowledged, then did it again

The user's escalating frustration: "DIE ALTE SEITE IST ---> KEINE <--- REFFERENZ!" (THE OLD SITE IS ---> NOT <--- A REFERENCE!)

**Trigger:** user says "from scratch" / "neu" / "fresh" / "von Grund auf" / "NICHT das alte" / "KEINE REFERENZ" + points to an existing codebase.

**The rule:** Treat existing code as INVISIBLE. The only inputs are:
- Spec/design docs (SCHLACHTPLAN.md, ARCHITECTURE.md, etc.)
- Design systems (_ds/, style tokens)
- Skills (flawless-ui-ux, popular-web-designs, etc.)
- Inspiration references (togo inspiration.md, etc.)

Never read existing source code to "see what was there." Never copy files. Never use old/ as a template.

## References
- `references/lauft-loop-case-study.md` — Full transcript of the 8f37f30d failure, with timestamp analysis, what was actually deliverable at each "Läuft" turn, and the recovery recipe that worked the next session.
