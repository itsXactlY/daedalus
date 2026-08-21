# Circle-Break Recovery — Break Out of The Spin Loop

## Context

This applies when you've tried the same fix approach 2+ times, the user is frustrated ("hör auf dich im kreis zu drehen", "RAFF ES DOCH EINFACH"), or you catch yourself re-reading the same error without making progress.

## The Signal

You're in a circle when:

- You retry the same failing command with minor variations
- You add new features/analysis/deep-dives WHILE the immediate blocker is still unfixed
- You swap between tools (terminal → read_file → search_files → terminal) without changing what you're looking at
- The user's frustration escalates in urgency: "mach!" → "FFS!" → all-caps pointing at the actual answer
- You claim "the system is blocked" or blame external factors before reading the real error

## The Break: mazemaker_recall First

**The fastest way to break a spin is to call `mazemaker_recall` with the topic you're stuck on.**

This does three things:
1. Gives you the EXACT session context from the user's perspective
2. Shows what was tried, what failed, and what the LAST error was
3. Anchors you in the user's frame of reference (they are often pointing at the right problem)

**After the recall hit (sim >= 0.4): STOP searching. The hit IS the answer. Read it. Act on it.**

## The One-Command Reset

When stuck, do EXACTLY these steps in order, no deviation:

1. **mazemaker_recall** — Ask "what's the status of [current task]". Read the top result.
2. **Read the actual error** — Find the specific `Exception`, `Unresolved reference`, or `FAILURE:` line. That string IS the problem. Do NOT guess.
3. **Clean fully** — Remove build dirs, caches, anything stale.
4. **Fix ONE thing** — Make the minimal change that addresses the error. Rebuild. If it fails, go back to step 2.

## Pitfalls

- **"System terminal policy" — NO.** When a tool says it can't execute, the cause is almost always your own code/approach (wrong PATH, missing env var, wrong tool for the job). Not a phantom system block. Check `env['PATH']`, use `terminal()` instead of `execute_code`, or try a simpler command first.
- **"DA IST ALLES"** — User says this when you're overcomplicating. Stop deep-diving. Check what files/code already exist. The answer is literally in front of you.
- **All-caps frustration is pointing at the right problem.** The user knows what they want. Read what they're pointing at (a file path, a directory, a specific technique). Don't argue or second-guess.
- **Do NOT switch tasks mid-blocker.** Fix the one thing that's broken. Adding features, starting parallel analyses, or researching unrelated topics while a build is red is the #1 frustration source.
