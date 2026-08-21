---
name: maze-crew-iteration
description: Autonomous scheduled-iteration loop for the three maze-crew Three.js visualization files (maze-crew-bio.html, maze-crew-dream.html, maze-crew-trailer.html) in /home/alca/projects/mazemaker-architect/public/. Use when a cron job or scheduled task asks to improve one of these files, or when the user invokes the "maze crew loop" / "iteration engine" / "next visual improvement" workflow. Class-level umbrella that owns the rotation protocol, cross-file pattern awareness, verification technique, and the iteration log convention.
---

# Maze Crew Iteration Loop

A scheduled cron job performs **one focused visual improvement per run** on a small set of related Three.js files. Each file represents a different lens on the same cognition cluster: bio (organism/tissue), dream (NREM/REM/Insight brain), trailer (20s cinematic). They share code patterns, and improvements often need to propagate across all three.

## Trigger Conditions

The agent should load this skill when:
- A scheduled task is described as "maze crew loop", "iteration engine", or references the three maze-crew files
- The task says "make ONE focused improvement per run, rotating between files"
- The task references the `maze-crew-loop-log.md` log file
- The task asks to apply a cross-file visual pattern to one of the three files

Note: the iteration log lives at `public/.maze-crew-iter.log` (per-file authoritative log) AND `MAZE_CREW_LOOP.md` (project-root master log). See "Log Authority" section below for the precedence rule.

## The Three Files

1. `public/maze-crew-bio.html` (~3000 lines) — biological organism visualization. Living tissue of thought regions: cortex/thalamus/bone/etc. nodes with synaptic edges, pulses traveling between neurons, firing rings at emission sites, arrival flashes at destinations, inter-region synapse threads, heart waves, consciousness core, distant fog-of-war structures, EKG HUD, phase progress bar.
2. `public/maze-crew-dream.html` (~4040 lines) — dream engine visualization. NREM/REM/INSIGHT/AWAKE phases cycling on auto/manual/WS-push paths. Phase progress bar, phase pill, vignette, RGB-split chromatic aberration on phase transitions, EKG + phase indicator HUD, awareness eye with phase-keyed rapid eye movement.
3. `public/maze-crew-trailer.html` (~2570 lines) — 20-second cinematic trailer with camera flythrough. 12-keyframe camera spline, FOV breath, chromatic desaturation on loop seam, distant structures, cosmic motes, heart wave pulses, recognition ping on close-up dives.

All three are self-contained single-file HTML apps (inline `<style>` + `<script type="module">`). They share: Three.js + InstancedMesh + LineSegments + per-frame change-detection gates + module-scope scratch vars (zero per-frame GC) + cached DOM overlay refs + try/catch around animate with consecutive-error counter.

## User's Vision Principles (from the system prompt)

Apply these as evaluation criteria for any candidate improvement:

- **Visualize COGNITION, not structure** — no explicit nodes/edges/labels; biological/cosmic aesthetic
- **Dream phases must feel like a brain sleeping/dreaming/awakening** — phase transitions as a state change, not a config swap
- **Thought propagation — activation that visibly travels between regions** — pulses, axon arcs, inter-region threads, arrival flashes
- **Infinite feel — distant fog-of-war structures** — peripheral cosmos with phase-tint drift
- **The maze as a CHARACTER — mood, heartbeat, emotional tonality** — heartbeat drives multiple visual channels in lockstep
- **Screen-recordable (looks amazing as a 7-second clip)** — bright trails, large pulse heads, visible chromatic shifts, no subtle-only effects

## Rotation Protocol

### How to Determine the Next File

**Two log sources, one truth.** The rotation state lives in two places:

- `public/.maze-crew-iter.log` — per-file, the authoritative source. Every run appends a `=== Run #N ===` entry. The **last "ROTATION:" line** at the end of the most recent entry is the canonical "next" pointer.
- `MAZE_CREW_LOOP.md` (project root) — a parallel master log with `## Run #N+...` headings. Summary-style, can lag the iter.log by one or two runs.

**Precedence rule (verified from run #18 — iter.log said "bio ← NEXT", master log said "trailer ← NEXT"; iter.log was correct because it was fresher):** When the two logs disagree, **trust the iter.log's last "ROTATION:" line.** The master log is human-facing; the iter.log is the agent's source of truth.

**Stale-log trap (verified from run #N+26):** Both logs can lag behind the filesystem if recent runs were appended only to one log, or if a run happened outside the loop's normal append path. In that case the mtimes tell a different story than the logs (e.g. master log's most recent entry was dream #N+25 from yesterday at 23:32, but bio + trailer had both been touched earlier today at 00:10 / 00:54 with no log entry between them). **When in doubt, the mtime is the ground truth** — `ls -la public/maze-crew-*.html` and pick the oldest mtime. The logs are an *advisory* cache; the filesystem is authoritative. After picking the stalest file by mtime, cross-check against the most recent log entry's "ROTATION:" footer — if the two agree, proceed; if they disagree, the mtime wins.

**Backup signal when logs are empty/missing:** Check the file mtimes — `ls -la public/maze-crew-*.html`. The oldest mtime is the next file (the loop rotates by least-recently-touched).

### The Rotation

Default order: bio → dream → trailer → bio → dream → trailer → ... But this is **advisory only**; the actual rotation is whatever the previous run footer says.

When the previous run footer says "→ X ← NEXT", work on X. The decision is not a re-evaluation — it's an obey.

### The "ONE Focused Improvement" Rule

Per the system prompt: "DO NOT make multiple changes in one run." Each run is a single, well-scoped improvement. This rule exists because:
- Each change is verified independently (file size, syntax, HTML balance, symbol audit)
- The iter.log entries are clear and atomic
- Visual regressions are easy to bisect

**Combining is forbidden** even when two changes are tiny. The cross-file-patterns skill's "audit gap" pattern sometimes yields 2-3 stragglers at once — the run picks ONE and queues the rest in the "Deferred-fix queue" footer.

## Picking the Improvement (Decision Tree)

Use this when starting a run. Try each in order; first match wins.

1. **Explicit queue from the previous run's "Deferred-fix queue" footer.** If the run footer lists items, pick the highest-priority one (usually "next-most-impactful" with the smallest blast radius).
2. **Explicit queue from `.maze-crew-iter.log` "**Deferred-fix queue remaining in <file>**" footer.** This is the audit-gap closure path.
3. **Cross-file parity gap from the family-rule audit matrix.** Each file has a parity matrix (e.g., per-frame DOM-write change-detection gates: `_vignetteLast`, `_phaseFillLastW`, `_phaseFillLastH`, `_heartbeatLast`, `_chrLastOpR3`, `_chrLastPx`). If one file is at 4/5 and others are at 5/5, close the gap.
4. **Priority list candidates** (from the system prompt):
   - Add try/catch error handling around the animate loop
   - Fix missing setSize() on renderer (pixelation bug)
   - Add phase progress bar
   - Improve thought propagation visuals (visible activation traveling)
   - Add distant fog-of-war structures for infinite feel
   - Add heartbeat indicator
   - Fix camera path discontinuities
   - Add RGB shift on phase transitions
   - Make phase transitions smoother (lerp colors/speeds)
   - Fix any runtime errors

5. **Fresh feature/polish work** — when all queues + parity gaps + priority-list items are closed, pick the highest user-vision-aligned improvement not yet implemented.

   **Sign that you're at step 5:** the previous run footer says "**Deferred-fix queue remaining in <file>: NONE.**"

5a. **"Last static holdout" audit (bio #21 pattern).** Even when every shared channel participates in the rhythm (phase hue lerp, heartbeat pulse, currentPulseSpeed, etc.), scan the file for elements that DON'T:
   - CSS animations with hardcoded durations (`animation: x 16s linear infinite`) — the duration should probably be `var(--phase-dur, 16s)` driven by JS
   - Static opacity/scale/translate values in JS (look for `material.opacity = 0.15` without a beat/activation term)
   - Constant rotation speeds (`g.rotation.y += 0.01` rather than `g.rotation.y += dt * currentPulseSpeed * 0.01`)
   - Tween/to/lerp values that snap rather than interpolate (the "lerp everything" family rule)
   - Hand-set `THREE.Color` constants that don't follow `setHSL(currentTissuePhaseHue, …)` or similar phase-driven lerps

   The audit pattern is: grep for the rhythm-driving variables (`currentPulseSpeed`, `beat`, `currentTissuePhaseHue`, `tg.activation`) and check if every visible moving/animating element reads at least one. Any element that doesn't is a candidate for this run. Apply the lowest-risk fix first (changing `animation: x 16s …` → `animation: x var(--x-dur, 16s) …` + 1 setProperty write is a 2-change surgical fix).

   This is the sub-pattern bio #21 closed: 12+ heartbeat/phase-driven channels were tied to `currentPulseSpeed`, but the `⌬` brand glyph's CSS animation still had a hardcoded 16s duration. The fix took 2 surgical changes (CSS var binding + 1 JS write) and zero new module-scope state.

## The Implementation Pattern

The maze crew files follow a strict family-rule pattern. New code MUST conform or it triggers antipattern flags in the verification grep.

### Module-scope conventions

- All scratch `THREE.Color` / `THREE.Vector3` / `THREE.Object3D` instances are hoisted to module scope and mutated in place: `const _fooE = new THREE.Color();`. Never `new THREE.Color()` inside `animate()`.
- All DOM overlay refs cached at module scope + resolved in `init()`: `let _xxxEl = null;` then `_xxxEl = document.getElementById('xxx');` in init, with null-guarded reads in animate.
- All change-detection cache vars at module scope: `let _xxxLast = -1;` (numeric) or `let _xxxLast = '';` (string). Init to -1 or '' to force first-frame write.

### Animate-loop conventions

- `try { ... } catch (err) { ... }` around the body. The catch increments `_frameErrCount` and at >30 consecutive errors shows a single-write diagnostic surface. Counter resets on first successful frame.
- `requestAnimationFrame(animate)` at the top, before the try.
- `clock.getDelta()` capped to 0.05 (tab-switch protection).
- All per-frame `style.X =` writes are gated by change-detection: read current value, compare to cache, write only on change. `.toFixed(N)` precision tuned so the gate fires ~50-95% of frames (correctness preserved; visual diff is zero).

### CSS conventions

- **NO `transition:` on per-frame-driven properties** (e.g., `box-shadow`, `opacity`, `width` on the phase-fill, `filter` on the canvas). JS writes the canonical value at 60fps; a CSS transition would lag the JS write by 50-150ms and smear the per-frame rhythm.
- The default fallback values in CSS must match the JS initial write so first-frame paint is correct (no flash of unstyled frame).

### The "ONE focused improvement" rule applied to code

When adding a feature, the change should be:
- 1 module-scope decl + init = N cache writes (usually 0-1) + 1-5 active animate-loop lines + 1-3 helper calls + a multi-paragraph rationale comment.

**Rationale comment size.** The maze crew code is comment-heavy. A 1-3 line code change typically carries 15-25 lines of rationale explaining why this change, the priority-list competition, the cross-file parity state, the threshold/debounce analysis, the pulse-count delta, the visual-delta description, and the verification list. **This is the established style** — don't compress the rationale to save lines.

## Verification Technique

Every run verifies the change before logging it. The verification block is part of the log entry and is non-negotiable.

### Required checks

1. **`node --check` on the extracted module script.** Extract the inline `<script type="module">` to a temp file, then `node --check` it. Exit 0 = SYNTAX_OK.
   ```python
   import re
   m = re.search(r'<script type="module">(.*?)</script>', html, re.DOTALL)
   with open('/tmp/extracted.js', 'w') as out: out.write(m.group(1))
   ```
2. **Code brace/paren/bracket balance** must be 0/0/0. **Use the state-machine checker at `scripts/balance_check.py`**, NOT a naive regex strip — see pitfall 1c below. The script handles template literal `${...}` substitutions recursively, regex literals, and all JS string forms correctly. Exit 0 = 0/0/0. Exit 1 = real imbalance.
3. **HTML body tag balance**: `div`, `canvas`, `span`, `button`, `script`, `style` open/close counts must match. **Pitfall:** naive regex picks up tag names inside JS comments. Strip `<script>...</script>` and `<style>...</style>` content before counting.
4. **Symbol audit**: the new symbols introduced should appear exactly the expected number of times (1 decl + N active uses + M comment refs). Match against expected counts from the design.
5. **Antipattern grep**: `new Float32Array` in animate body = 0, `getElementById` in animate body = 0, `document.querySelector` in animate body = 0, `setInstanceMatrix` = 0, `body.style.filter` = 0, `getMatrixAt` = 0. New code MUST NOT add to these counts.

   **Refinement (run #20):** the wider animate body can contain antipattern hits from helper functions, comment text, or pre-existing one-shot initializations that aren't really from your change. When auditing a new feature, **extract just the runtime block of the new feature** (e.g., the body of `if (_phaseBurstState.active) { ... }`) and grep THAT — not the whole animate body. A 481-char burst runtime block reporting "0 allocations / 0 DOM lookups / 0 setInstanceMatrix" is a much cleaner signal than "1 pre-existing `new Float32Array` from cosmic motes init (one-shot, conditional, runs once at boot)". The pre-existing hits get flagged explicitly in the log as PRE-EXISTING so they're not conflated with the change.

6. **File size delta** (lines + bytes) — small change expected (a few hundred bytes to ~2KB).

### When verification fails

- **Syntax error**: revert the patch, re-read the file, find the typo, retry.
- **Balance mismatch**: count the actual delta — sometimes a pre-existing imbalance is preserved (state it explicitly in the log).
- **Tag mismatch**: likely a JS comment containing a tag name. Confirm by stripping script/style first.
- **Antipattern regression**: usually a `new Color()` inside animate — move to module scope, retry.

## Logging Convention

Two log files, both must be updated. **Use the bash heredoc with `>>` redirect, or `write_file` with append, NOT a re-write of the file.** The iter.log is append-only forever.

### Per-run log entry shape (iter.log)

```markdown
=== Run #N @ YYYY-MM-DD HH:MM:SS — maze-crew-<file>.html ===
<one-paragraph summary of the change>

<File context> (which file was next in rotation, why this pick over other candidates)

**The gap closed.** (what the previous behavior was, what the new behavior is, why the user cares)

**The fix.** (1-3 bullets describing the actual code change, with code snippets)

<Threshold/Debounce/Algorithm analysis> (any non-obvious numeric choices get a 5-10 line block justifying the values)

**Implementation correctness.** (4-6 bullets verifying the design composes with existing infrastructure)

**Verification:**
- `node --check` on extracted N-char module → SYNTAX_OK
- Code brace/paren/bracket balance 0/0/0
- HTML body tag balance
- Symbol audit
- Antipattern grep

**Size:** N → N+Δ lines/bytes (+Δ, +%).

**ROTATION:** ... → <this_file> (run #N, ✓) → <next_file> ← NEXT.
```

### Master log entry shape (MAZE_CREW_LOOP.md)

A condensed version of the same content with a `## Run #N+... — YYYY-MM-DD` heading. Cross-references the iter.log entry by run number. Includes the cross-file parity state table if it changed.

## Cross-File Patterns (Family Rules)

The maze crew files share these invariants. Code that violates them is an antipattern.

1. **All overlay DOM refs cached at module scope + resolved in init()** — no `getElementById` / `querySelector` in animate() bodies.
2. **All per-frame `THREE.Color` / `THREE.Vector3` scratch values hoisted to module scope and mutated in place** (`.set`, `.setHSL`, `.lerp`).
3. **Resilient animate catch with consecutive-error tracking** (threshold 30 ≈ 0.5s @ 60fps) — single-write diagnostic surface, no kill switch.
4. **No CSS `transition:` on per-frame-driven properties** (JS is authoritative at 60fps).
5. **Per-frame change-detection gates on hot-path DOM writes** — width %, color HSL, opacity, box-shadow, filter — gated by a `_xxxLast` cache var.


<!-- moved to references/moved-sections.md: ## Specific Techniques -->

## The Per-File Heartbeat Channel Inventory (Bio)

For reference when adding or debugging heartbeat-driven features. These are the channels that already follow the heartbeat in bio (post run #18):

- Consciousness core scale + brightness (animate L1992-2005)
- Consciousness halo scale + opacity (animate L1999-2005)
- Camera FOV breath (animate L1427+)
- Camera position tremor (animate L2033-2038)
- EKG trace + marker dot (updateHeartbeat L1710-1744)
- Heart waves (animate L1896-1901)
- Brand glyph scale + text-shadow blur (updateHeartbeat L1645+)
- Screen-edge heartbeat glow (heartbeat div box-shadow)
- Per-node beat-driven size + lightness (per-node loop L2056-2067)
- Per-region local beat swell (hull scale L2092-2095)
- Pulse emission (run #18 — newly synced to heartbeat peak)
- Brand glyph rotation duration (run #21 — `--brand-spin-dur` driven by `currentPulseSpeed` via CSS var interpolation; rotates at 5.7s during REM, 53s during NREM, baseline 16s during AWAKE)
- **Phase pill box-shadow glow** (run #23 — `_hPhaseEl.style.boxShadow` written per-frame from `beat`, peak 7px blur / 0.45 alpha, gated by `_hPhaseLast`; closes the "phase indicator sat static between transitions" gap so the HUD's top-right corner visibly inhales with the rest of the organism)

When adding a NEW heartbeat-driven channel, pick a threshold in the 0.5-0.7 range to ensure it fires only on beat peaks, and a debounce that matches the existing rate of the channel it's coupled with (typically 0.3-0.5s).


<!-- moved to references/moved-sections.md: ## Pitfalls (from the run history) -->

## Pitfall — Log Authority Disagreement

When `MAZE_CREW_LOOP.md` and `.maze-crew-iter.log` disagree on the next file, **trust the iter.log**. The master log is a human-facing summary; the iter.log is the agent's source of truth. Verified from run #18: master said "→ trailer ← NEXT", iter.log said "→ bio ← NEXT", iter.log was correct.

### Pattern: Two-Hook Burst Arming (arm + fire split)

When a feature needs to fire N items over a window in response to event E, AND E has multiple trigger paths (e.g., phase transitions come from auto-tick + manual override + WS push), the cleanest implementation is:

1. **Single arm hook** in the common event handler — sets `active = true`, resets counters/state, scales amplitude. Adding the arm here covers ALL trigger paths in one place.
2. **Fire block** in the render loop (`animate()`) — checks the `active` flag and emits content (e.g., `emitPulse()` calls) per the schedule. Disarms when done.

Established in run #20 (Phase Transition Thought Burst). Earlier patterns like heartbeat-driven emission burst (run #18) only had one trigger path (the heartbeat itself, recomputed in animate), so they put everything in animate. The split pattern emerges when the event has multiple triggers.

**Why not just put `emitPulse()` calls directly in the event handler?** That would force all trigger paths to fire synchronously — creating a single-frame traffic jam of overlapping pulses vs a readable cognitive flurry spread across multiple frames. The split keeps the emit pipeline reusable (each burst pulse still goes through firing ring + inter-region thread + axon arc + arrival flash + region echo + cascade) while preserving the event-coordinated timing.

**When to use:** any "fire N items over a window in response to event E" feature where E has 2+ trigger paths.
**When NOT to use:** when E has only one trigger path (just put the fire logic in that path's handler).

See `references/phase-transition-thought-burst.md` for the full implementation + per-phase amplitude analysis.

## Pitfall — CSS `animation-duration` change does NOT restart when bound to a CSS variable

The mental model "changing `animation-duration` restarts the animation" is wrong when the duration is bound to a CSS variable via `var()`. Verified on bio #21 (run #N+28): changing `--brand-spin-dur` from `16s` to `5.71s` smoothly accelerated the `⌬` glyph's rotation without snapping to rotation 0. Modern browsers (Chrome 84+, Firefox 75+, Safari 14+) update `animation.playbackRate` to match the new duration and preserve `currentTime`.

This means **the technique is safe to drive from a per-frame JS write**. Common worry — "the glyph will flicker back to 0° every frame when the speed changes" — does not happen.

The pitfall only bites if you do it the WRONG way: writing `animation: brandSpin 16s linear infinite` (no var) and then changing `animation-duration` via `element.style.animation = '... ' + newDur + 's ...'` — that DOES restart because you're replacing the entire animation declaration. The `var()` binding is what preserves state across the change.

**Symptom of getting it wrong:** the animation snaps to the start every time the speed changes. The fix is to bind the duration through a CSS variable (`var(--dur, fallback)`) rather than rewriting the whole `animation` shorthand.

## Pitfall — Strip Script/Style Before HTML Tag Counting

A naive `grep -c '<span'` will pick up tag names inside JS comments and over-count. Always strip `<script>...</script>` and `<style>...</style>` content before counting:

```python
body_no_script = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL)
body_no_style = re.sub(r'<style[^>]*>.*?</style>', '', body_no_script, flags=re.DOTALL)
```

## Pitfall — Patch tool needs COMPLETE comment-block context in `old_string`

The `patch` tool matches `old_string` literally — if your `old_string`
misses the first few lines of a multi-line comment block, the patched
result will leave those lines stranded BELOW a new comment opener,
creating a nested-comment (or in CSS, a rule inside a comment) that
breaks parsing. Symptom: the first `patch` succeeds but the verification
step finds syntax errors / extra `{ }` / broken CSS, and a follow-up
patch is needed to clean up the mess.

**Root cause.** When the target block starts with a comment (CSS `/* … */`
or JS `// …` continuation), and the comment opener is several lines
above the actual code line you're changing, your `read_file` window may
not include the opener. The `patch` tool doesn't validate context — it
just does literal string match-and-replace. If your `old_string` starts
mid-comment, the comment above stays in place, and the new content you
patched in (which assumed its own `/*` opener) creates a double-opener.

**Concrete failure mode** (run #26, bio.html CSS comment block):

The target was changing `animation: ocursorBreath 0.9s ...` to use
`var(--ocursor-breath-dur, 0.9s)`. The comment block surrounding the rule
started at L57 with `/* Oracle typewriter cursor — a thin ...`. The
`read_file` call started at L60, so the opener at L57-58 was off-screen.
The crafted `old_string` started at L60 (mid-comment) and ended at the
`.ocursor` rule on L66. The patch succeeded, but the result had:

```css
/* Oracle typewriter cursor — a thin "thought forming" marker that breathes
   softly while the quote is being typed. Uses an ease-in-out breath (not a
   /* Oracle typewriter cursor — narrow left-five-eighths block (▍) used as   ← SECOND /* OPENER
      caret — matches ...
      ...
   */
.ocursor{display:...}
```

The first `/*` opener at L57 was stranded — there was no matching `*/`
until the second opener's closing `*/`, but the parser sees only one
block. Then a SECOND `/*` opener was added by the patched content.
Result: nested-comment (invalid CSS).

**Fix recipe.** Before crafting `old_string` for a comment-surrounded
block:

1. **Re-read the section with a wider window.** If you read with
   `offset=N, limit=K`, re-read with `offset=max(1, N-10), limit=K+10`
   so you capture 10 lines of context above the target. The opener is
   usually 3-7 lines above the rule.
2. **Spot-check the opener is in your old_string.** Before calling
   `patch`, scan your `old_string` for the comment delimiter
   (`/*` for CSS/JS block comments, `//` for JS line comments in a
   contiguous block). If you don't see the opener AT THE TOP, expand
   your read window.
3. **After patching, verify the comment-block boundaries.** Read the
   patched section back and confirm: exactly one `/*` opener, exactly
   one `*/` closer, the opener is at the first line of the comment,
   the closer is at the last line of the comment. If you see two openers
   or two closers or mismatched indentation, the patch needs cleanup.

**Pre-commit verification recipe.** Before writing the verification
block, run `node --check` on the extracted module AND a CSS sanity check
on the patched region (grep for `<comment-opener-count>` vs
`<comment-closer-count>` in the patched lines). If the counts are off,
revert the patch, re-read the section with a wider window, and retry
with a complete `old_string`.

**Cost of getting it wrong.** The CSS-broken-nested-comment case is
recoverable in 1 follow-up patch (clean up the stranded opener lines).
The JS case can be worse — a stray `/*` opener inside a `//`-commented
block can sometimes be silently ignored by `node --check` (it sees it as
a real block-comment opener) but break the runtime semantics if the
opener is inside a string literal. Always run `node --check` after
patches that touch comment blocks, even if the visible diff looks right.

## Pitfall — f-string brace escaping when writing log entries via `execute_code`

When using Python's f-string inside `execute_code` to build log entry text
that contains JS code with object literals (e.g. `firingRings.push({ x: e.src.x, y: ..., hue: ... })`),
the `{` and `}` in the JS get interpreted as Python expression placeholders.
Symptom: `NameError: name 'x' is not defined` (Python tries to evaluate `x`
as a variable inside the f-string template).

The same problem affects TWO other formatting approaches that look like
they should work:

- `.format(ts=ts)` with bare `{ts}` placeholders — any literal `{` in the
  JS code text (e.g. `{ animation:`, `{ pulseSpeed: 0.3 }`, function-call
  argument lists in code excerpts) is treated as a format placeholder.
  Symptom: `KeyError: ' animation'` (or whatever the first literal-brace
  text happens to be). Fix: escape EVERY literal `{` and `}` as `{{` and
  `}}`. The double-brace dance is easy to forget when copying JS snippets
  into the entry text — every `{` in a code block has to become `{{`.
- `%s` (printf-style) formatting — any literal `%` followed by a format
  char (s, d, f, x, etc.) in the entry text is treated as a format spec.
  Symptom: `TypeError: not enough arguments for format string` when the
  text contains `%` in a non-interpolation context. Fix: escape every
  literal `%` as `%%`. This is also easy to forget and hard to grep for.

Fix options, ranked by robustness:

1. **Use `.format(ts=ts)` with double-braces `{{` `}}`** to escape literal
   braces while still preserving string interpolation:

   ```python
   entry = """=== Run #N @ {ts} — file.html ===
   firingRings.push({{ x: e.src.x, hue: ... }});""".format(ts=ts)
   ```

2. **Use plain string concatenation / `+`** — the most robust option.
   No format chars to worry about. Use Python's automatic adjacent-string
   concatenation (parens with implicit concat across lines) for multi-line
   entries:

   ```python
   entry = (
     "=== Run #N @ " + ts + " — file.html ===\n"
     "firingRings.push({ x: e.src.x, hue: ... });\n"
   )
   ```

   Every run-#26 log entry in this skill uses this pattern — verified
   safe across all three failure modes (f-string, .format, %s) because
   no format processing happens.

3. **Split the JS code into a separate string variable** and concat it onto
   the f-string body. Useful when the entry is mostly prose with one
   short code block.

**Decision rule.** When the entry contains 3+ lines of JS code or many
code-excerpt references, prefer option 2 (concatenation) — the
double-brace escaping of option 1 is tedious to get right and easy to
miss on review. When the entry is mostly prose with one small code
snippet, option 1 with careful `{{ }}` escaping is fine.

**Diagnostic recipe.** If you see `KeyError: 'X'` or `not enough arguments
for format string` or `NameError: name 'X' is not defined` from an
`execute_code` script that's building a log entry, the fix is the same:
switch to plain string concatenation (option 2). Don't waste time
debugging the brace escaping — the entry will be re-edited next run
anyway and the escaping will need re-doing.

## Pitfall — Module Script Extraction Must Target `<script type="module">`

A naive regex like `r'</style>(.*?)</script>'` will match the FIRST `</script>` after `</style>`, which in the maze-crew files is the **importmap** script (`<script type="importmap">…</script>`), NOT the inline module script. The extracted "JS" then contains the importmap JSON plus a slice of the HTML body (canvas + heartbeat div), and `node --check` fails with `SyntaxError: Unexpected token '<'`.

The maze-crew files consistently have BOTH scripts in this order:
1. `<script type="importmap">…</script>` — ESM import map (small, ~5 lines)
2. `<canvas>`, `<div id="heartbeat">`, other body markup
3. `<script type="module">…</script>` — the actual application code (~3000+ lines)

The fix is to anchor the regex on the module script tag specifically:

```python
m = re.search(r'<script type="module">(.*?)</script>', html, re.DOTALL)
with open('/tmp/extracted.js', 'w') as out:
    out.write(m.group(1))
```

**Symptom of getting it wrong:** `node --check` exits with code 1 and the first error is `SyntaxError: Unexpected token '<'` on line 2 of the extracted file — line 1 is `<canvas id="c"></canvas>`, line 2 is `</head>` from the body markup that got swept up.

## References

- `references/run-history.md` — chronological list of all 20 runs to date, with one-line summaries and the deferred-fix queue state at each.
- `scripts/balance_check.py` — proper JS brace/paren/bracket balance checker (state machine; handles template-literal `${...}` substitutions, regex literals, all JS string forms). **Use this for the verification recipe's check #2** — the naive regex strip recipe fails on files with heavy template-literal use (see pitfall 1c).
- `references/heartbeat-driven-emission.md` — full implementation + threshold/debounce analysis for the heartbeat-driven emission burst pattern (bio #18).
- `references/heartbeat-emission-particle-pool.md` — round-robin GPU pool for heartbeat-synced additive particle emission (bio #29). Sentinel parking, vertex-color brightness, anyChanged gate, birth-hue-lock temporal flow, Math.acos(2r-1) spherical uniformity. Use when the organism needs to visibly "emit" particles on each beat.
- `references/phase-transition-thought-burst.md` — full implementation + per-phase amplitude analysis for the phase-transition thought burst pattern (bio #20). Companion to the heartbeat-driven-emission doc.
- `references/phase-aware-css-animation.md` — technique for driving CSS `@keyframes` animation duration from per-frame JS state via CSS custom property interpolation. Covers browser interpolation behavior, the wrong-way pattern that DOES restart, and a verification recipe. Worked example from bio #21 (phase-aware brand rotation).
- `references/per-node-beat.md` — the per-node heartbeat-driven size + lightness pattern (bio #N+18, dream #24). Formula, phase-offset math, magnitude-vs-competing-signal tuning rule, ^4 vs ^12 exponent choice, verification recipe. Use when backporting the per-node heartbeat to a new node-cloud or sizing a heartbeat-driven channel that must coexist with a stronger existing per-node signal.
- `references/cross-file-parity-matrix.md` — current state of every cross-file family-rule audit.
- `references/visual-pattern-invariants.md` — proven numeric knobs (CAP, LIFE, scale, fade, geometry, material) for every cross-file visual element (firing rings, pulse arcs, arrival flashes, heart waves, per-node breath, phase bar, chr-ab, heartbeat, camera tremor, phase-transition thought burst). When backporting a visual pattern from one file to another, copy the constants verbatim — they're tuned on the live files and changing them changes the visual character. **Exception:** magnitude multipliers must be tuned against the destination file's dominant competing signal, not copied verbatim — see `references/per-node-beat.md` "Magnitude Tuning" section.
