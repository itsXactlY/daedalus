# Session Dump Reading Pattern

## What happened (2026-08-02)

The user pointed to `/home/alca/projects/rework/dump.txt` (4772 lines, ~1MB) and
demanded: "read the whole dump.txt - there it is everything what all brainraped
agents MISSED". The file is a raw OpenRouter API conversation log (JSON
request/response format) from the previous session (ses_040ff3f22ffe3Bp9D6JXB2uIRR).

The agent initially failed to read it completely (stopped after first 500 lines),
which provoked: "no u have NOT READ IT COMPLETELY". The agent then read all
4772 lines in chunks of 500.

## What the dump contained

The full conversation history of the previous session, including:

1. **What was built**: Walk intro (typo → walk → crystal → glyph → seam),
   Receipts section (13 screenshots as engineering archaeology timeline),
   Worlds section (6 art styles × 15 images), Film section (native video,
   conscious click-to-play), FAQ with Gigaplan skeptic questions (RAG,
   supersession, dream cycle, graph-vs-flat).

2. **25/25 verification gates passing**: JS syntax, HTML tag balance, CSS
   variable references, media URL reachability, lazy loading, glyph
   determinism, reduced-motion detection, responsive breakpoints.

3. **The user's verdict after ALL gates passed**: "not bad für einen ersten
   proof of concept. aber bei weitem noch immer lichtjahre von NICHT statischem
   müll, super bleeding cutting edge technologie entfernt!"

4. **The unfinished attempt**: The agent started building a "persistent
   full-viewport living background maze" (fixed full-screen canvas behind the
   entire page, seeded graph breathing throughout, scroll-velocity coupling)
   but the session died with `BadRequestError: reasoning_effort: Invalid option`
   before it could ship.

## Pattern: reading large files completely

When the user says "read X completely" or "read the whole X", the correct
behavior is:

1. **Read in chunks until EOF.** Use `read_file` with `offset` and `limit`
   parameters. Each chunk returns `next_offset` for continuation.
2. **Do NOT stop early** or summarize before reaching the end. The user is
   frustrated precisely because previous agents stopped reading and started
   guessing.
3. **Report what was found** at the end, covering the full scope of the file.
4. **If the file is very large** (>100K chars), acknowledge the size and read
   systematically rather than skimming.

## Lesson: verification gates ≠ user satisfaction

The dump proved that all 25/25 gates passing does NOT mean the site meets the
operator's bar. The operator's bar is: "does the whole page breathe?" — not
"do all tags balance." Gates test correctness; the operator tests feeling.
