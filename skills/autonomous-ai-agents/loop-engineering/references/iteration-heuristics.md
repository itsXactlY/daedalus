# Per-Iteration Heuristics for Autonomous Code-Improvement Loops

When the loop's job is "make ONE focused improvement per run, rotating between N files," what does a high-value improvement look like? The patterns below were distilled from a 2026-06-20 cron iteration on the maze-crew visualization files (`maze-crew-bio.html`, etc.) — they generalize to any autonomous loop that touches hand-written frontend / creative code.

## Pattern 1: Dormant UI Element Detection (highest leverage)

**The signal:** A CSS rule, `@keyframes`, `.active` class toggle, or `<div id="...">` DOM element exists, but no `classList.add(...)` / `getElementById` call in the JS ever references it. The feature was *designed* but never *wired up*.

**Why it's high leverage:** Such dormant elements are usually a 1–10 line JS change away from working, and they often replace cruder workarounds elsewhere in the file. The visual payoff is disproportionate to the edit size because the CSS is already polished.

**Diagnostic grep sequence:**
```bash
# 1. Find CSS class toggles (.active, .visible, .open, .shown, etc.)
grep -nE '\.(active|visible|open|shown|focused)' file.html | head -20

# 2. Find what JS actually toggles via classList
grep -nE 'classList\.(add|remove|toggle)' file.html | head -20

# 3. Diff: classes defined in CSS that have NO matching classList call
#    → these are the dormant candidates

# 4. Find DOM ids declared but never referenced
grep -nE 'id="[^"]+"' file.html    # declared
grep -nE 'getElementById' file.html  # referenced
# Mismatch → dormant id
```

**Companion signal — global hacks as fossilized workarounds:**
- `body.style.filter = '...'`
- `document.documentElement.style.transform = '...'`
- Inline `<style>` overrides applied per-frame via JS

These usually exist because the proper overlay/element wasn't wired up yet. When you find a dormant element that matches the hack's effect, *replace the hack with the proper wiring* — global hacks distort HUD/controls too, the proper overlay doesn't.

**Concrete example (2026-06-20, maze-crew-bio.html run #20):**
- CSS declared: `#phase-flash { opacity: 0; }` with `.ch-r` / `.ch-g` / `.ch-b` radial-gradient channels at `mix-blend-mode: screen`, and `.ch-r` / `.ch-b` `translateX(±3px)` on `.active`
- JS was doing: `body.style.filter = 'hue-rotate(60deg) saturate(2)'` for 400ms on every phase transition
- Fix: one function `triggerPhaseFlash()` that adds `.active` class for 260ms with `void el.offsetWidth` reflow trick — replaces the body-filter hack in both auto and manual phase paths
- Visual win: chromatic channel separation now appears ONLY on canvas (overlay is z-index 7, HUD at z-index 10 stays clean) — bug fix + visual upgrade in ~15 lines

## Pattern 2: Isolated Syntax Check for Large HTML Files

**The problem:** Big hand-written HTML files often have pre-existing syntax issues that survive in browsers via tolerance (e.g. shorthand object literal with mixed getter/setter). When you patch such a file and run `node --check`, the pre-existing errors drown out any check of your actual change.

**The pattern:**
```bash
# Extract the script block and run node --check on it
awk '/<script type="module">/{flag=1; next} /<\/script>/{flag=0} flag' \
  file.html > /tmp/check.mjs && node --check /tmp/check.mjs

# For just your new function:
cat > /tmp/mine.mjs << 'EOF'
function myNewFunction() { /* ... */ }
EOF
node --check /tmp/mine.mjs
```

**When to use:** After any patch on a 500+ line HTML file. Don't trust "the page loads" alone — the browser may paper over issues that `node --check` would surface cleanly if isolated.

**Pitfall:** `node --check` on the full extracted script can fail on pre-existing issues unrelated to your patch. That's fine — note them in the iteration log ("pre-existing issue X, out of scope") and validate your edit in isolation.

## Pattern 3: Rotation Log Discipline

**The mechanic:** When the loop rotates between N files, the iteration log must record (a) which file was last touched, (b) what changed, (c) what's next. Without this, the next iteration re-reads everything from scratch and may re-pick the same file.

**Minimum viable log format:**
```markdown
| Run | Date | File | Change |
|-----|------|------|--------|
| 1 | YYYY-MM-DD | file-a.html | One-line summary of the change |
| 2 | YYYY-MM-DD | file-b.html | One-line summary of the change |

## Next Up
**file-c.html**
```

**Why it works:** The "Next Up" line is the single most valuable piece — it makes rotation a one-glance decision. The "Change" column's one-line summary doubles as a regression-avoidance guide ("don't undo what run #N did").

**Update procedure:** Append a row, then move "Next Up" pointer to the next file in rotation. Don't rewrite history.

## Pattern 4: Reflow Trick for Re-Triggerable CSS Transitions

When a CSS transition is gated on a class change (`.active`), and you need to retrigger it while the class is already present:

```js
el.classList.remove('active');
void el.offsetWidth;  // force reflow — this is the key line
el.classList.add('active');
```

Without the `void el.offsetWidth` line, removing-then-adding the same class in the same JS tick is coalesced by the browser into "no change," and the transition doesn't replay. This bites when rapid user input (or fast automatic phase cycling) needs to retrigger visual feedback.

## Anti-Patterns to Avoid

- **Whole-file rewrites.** Each iteration is ONE focused change. If you find yourself wanting to rewrite, you've exceeded the iteration's scope — log it for a future "big pass" iteration.
- **Refactoring unrelated code.** "While I was in there, I cleaned up X" is forbidden — it bloats the diff and risks regressions in code that worked.
- **Adding complexity for its own sake.** A 30-line fix is a 30-line fix only if it earns its size. The pattern of replacing body-filter hacks with proper overlays usually nets *fewer* lines.
- **Picking the same file twice in a row because it has more issues.** That defeats rotation. If a file genuinely needs more love, do ONE focused change and rotate. Next cycle, it'll still need more love — that's fine.
- **Skipping the iteration log update.** The log is the loop's short-term memory. Without it, the next iteration is amnesiac.