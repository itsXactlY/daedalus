# Subagent Verification Timing — Race Condition Analysis

## The Problem

When a captain spawns an editor and a checker subagent in the same `delegate_task` batch
(tasks array), both launch concurrently. The checker's file reads can race against the
editor's file writes, causing the checker to read stale state.

## Reproduction (Rework Loop Run #1, 2026-08-03)

**Setup:** Fix the film section in index.html — replace iframe+trailer/ with native video.

**Editor subagent (task-0):**
- Read index.html (1400 lines)
- Applied 3 patches: cache-buster update, film frame rewrite, caption edit
- Reported success: "1 file modified, 7 ins / 7 del"

**Checker subagent (task-1):**
- Read index.html (same path)
- Ran 10 verification checks
- Reported 5 FAILs:
  - `grep -c 'autoplay'` → 1 match (should be 0)
  - No `<video>` tag found
  - `href="trailer/"` still present
  - `<iframe id="filmIframe">` still present
  - Play SVG span still present

**Captain's direct re-read (after both returned):**
- All 3 patches present and correct
- 0 inline styles, 0 autoplay, video element correct, no iframe
- All verification checks passed

**Root cause:** The checker launched at the same time as the editor. Its file reads
completed before the editor's patches were written to disk. The checker saw the
PRE-patch state of index.html.

## Why This Happens

1. `delegate_task` with `tasks: [A, B]` spawns both subagents concurrently
2. Each subagent gets its own terminal session and file access
3. Filesystem writes from A are not guaranteed to be visible to B immediately
4. Even if A finishes first, B's file reads may have already started
5. The OS page cache, buffer flushing, and process scheduling all contribute

## The Fix

**Captain's own verification is the real gate.** After both subagents return:
1. Re-read the modified file(s) directly
2. Run the verification checks yourself (or via terminal)
3. Never trust a subagent checker's FAIL report without cross-checking

## Alternative: Serialized Verification

If you need the checker to be reliable, serialize:
1. Spawn editor, wait for completion
2. Re-read the file to confirm changes landed
3. Then spawn checker (or just verify yourself — faster)

This costs one extra round-trip but eliminates the race.

## Key Principle

Subagent summaries are self-reports. An editor claiming "changes applied" should be
verified by reading the file. A checker claiming "all checks pass" should be verified
by re-running the checks. The captain's direct verification is the only trustworthy gate.
