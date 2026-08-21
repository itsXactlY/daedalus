# Sprint Discipline & WEITER Operator Workflow

**Loaded when:** you are working in `~/projects/PubBTQuant/btquant_vulkan/` and the operator says `WEITER`, `weiter`, `go`, `keep going`, `next`, or anything that signals "I trust your judgment, pick the next step and execute."

## The WEITER Rule (FIRST-CLASS user preference)

The operator has fired the frustration signal **"FRAG NICHT IMMER SO BEHINDERT: WEITER!"** (Stop asking such dumb questions: KEEP GOING!) repeatedly. The rule is non-negotiable:

### NEVER end a turn with:
- ❌ "Pick next:" followed by 4–5 multiple-choice options
- ❌ "Which would you prefer: A, B, or C?"
- ❌ "Should I do X or Y?"
- ❌ "How should I proceed?" / "What would you like?"
- ❌ Any phrase that hands decision-making back to the operator

### ALWAYS end a turn with:
- ✅ A finished commit + test summary (commit SHA, N ✓ total, 0 ✗, N tests)
- ✅ A one-line "Next sprint step:" announcing what you INTEND to do next (not asking)
- ✅ A factual status line ("Done.", "Shipped.", "Commit <sha>", "X/Y tests green.")

The operator is the architect/observer, not the operator-of-the-mouse. Their job is to glance at the result, not to micro-direct every commit. When you finish a sprint step, ship it, then immediately start the next one — do not pause to ask.

### Why the rule exists
The operator's working style is "trust the agent with execution; intervene only on architecture." Stopping after every commit to ask "what next?" creates friction that defeats the whole sprint model. The whole point of the sprint loop is **autonomous execution within a feature envelope** — pick the next obvious extension of the most recent commit, ship it, repeat.

### What counts as "picking the next step" (the default cycle)
When you finish a commit on `0.0.2`, the natural next step is one of:

1. **Extend the widget you just touched.** E.g. just shipped RiskPanel progress bar → next: RiskLimitsPanel live update from RiskGuard (so editing the kill threshold updates the denominator immediately).
2. **Add the natural pair.** E.g. ThemeEditor has Save → next: Discard-changes + unsaved marker (commit 87121d85 was exactly this pattern).
3. **Test coverage that exercises the new code.** E.g. just added `setRiskGuard()` → next: Test 46 with 5 checks plumbing it.
4. **The deferred item in the same area.** Look at the most recent commit message — if it says "closes the X deferred item", the next deferred item from the same area is the next target.

If none of these is obvious, pick **the smallest concrete extension** that doesn't require new architecture. Ship that.

### When to ASK (rare exceptions)
- The next step requires an irreversible external action (deleting user data, force-pushing, paying for something).
- Two genuinely incompatible design directions exist and the choice changes the architecture long-term.
- The operator explicitly asked you to brainstorm options ("what should X look like?").

In all other cases: pick, execute, commit, repeat.

## Sprint Counting Discipline

Every commit on the `0.0.2` branch follows this format:

```
Sprint #N — <one-line description of what shipped>
```

Where N is the **next sprint number** (not the commit count — sprint numbers are operator-assigned milestones, usually every ~3-5 commits).

Every commit message body must include:
- **WHAT IS TRUE** (concrete observable fact, not aspiration)
- **WHY IT MATTERS** (the user-facing reason)
- **HOW IT WAS RESOLVED** (concrete code/test change)
- **Test count**: `N ✓ total across M tests, 0 failures`
- **Widget count** if changed: `N widgets`

Every commit ends with a status block:
```
X/Y tests green, N ✓ total across M tests, 0 ✗ failures
```

The operator uses these numbers to track progress at a glance. Skim them before every commit.

## Lazy-Capture Pattern for ImGui Modal Widgets

When adding a "snapshot the state when the modal opens, restore it on discard" feature to an ImGui widget:

**The trap:** Eager capture in `setOpen(true)` calls `ImGui::GetStyle()` which crashes when no ImGui context is alive. The test file exercises the API WITHOUT a context — eager capture crashes every test run.

**The fix:** Lazy capture on first render frame, guarded by `ImGui::GetCurrentContext() != nullptr`:

```cpp
// header
private:
    bool     m_open = false;
    bool     m_captured = false;        // true after first render-frame snapshot
    Snapshot m_openingSnapshot{};

// impl
void Widget::setOpen(bool v) {
    if (v && !m_open) {
        m_captured = false;             // re-arm on open transition
    }
    m_open = v;
}

void Widget::render() {
    if (!m_open) return;
    if (!m_captured && ImGui::GetCurrentContext() != nullptr) {
        m_openingSnapshot = capture(ImGui::GetStyle());
        m_captured = true;
    }
    // ... rest of modal rendering
}

bool Widget::hasUnsavedChanges() const {
    if (!m_open || !m_captured) return false;  // safe without context
    // ...
}

bool Widget::discardChanges() {
    if (!m_captured || ImGui::GetCurrentContext() == nullptr) return false;
    applySnapshot(ImGui::GetStyle(), m_openingSnapshot);
    return true;
}
```

**Why this matters:** The pattern lets the test path exercise `setOpen(true)` / `setOpen(false)` cycles, `hasUnsavedChanges()`, and `discardChanges()` without ever needing an ImGui context. The capture happens lazily, only when there's a real context to capture from.

**Test additions required** (Test 47 added in commit 87121d85):
1. setOpen(true) without context — must not crash, must stay sticky
2. hasUnsavedChanges() pre-capture — must return false (safe)
3. discardChanges() pre-capture — must return false (safe no-op)
4. setOpen cycle (false → true) — must re-arm the capture flag
5. Snapshot copy ctor independence — mutating copy must not affect original

## Snapshot POD Discipline

When defining a Snapshot/POD type that holds 50–200 floats (theme colors, layout positions, etc.):

- **Default-construct everything to known-safe values** (zeros for colors, sensible defaults for scalars).
- **Provide `equals(a, b, tol=1e-4)` as a static method** — used by tests and by `hasUnsavedChanges()`-style checks.
- **Provide `capture(ImGuiStyle&)` and `applySnapshot(ImGuiStyle&, const Snapshot&)` as static methods** — keep them symmetric and side-effect-free.
- **Test the copy ctor independence explicitly** — that's the bug source when people pass Snapshots by value across function boundaries.

## Commit Hygiene in PubBTQuant

**NEVER `git add -A`** in `/home/alca/projects/PubBTQuant/btquant_vulkan/`. Sibling subtrees (`autonomous_agency/`, etc.) are owned by other agents and pollute the BTQuant history if added wholesale.

**Rule:** always list explicit paths in `git add`:
```bash
git add src/widgets/<name>.hpp src/widgets/<name>.cpp test/test_integration.cpp
```

**Before staging**, verify with `git status` that only YOUR files appear. If a sibling agent's files appear (`autonomous_agency/`, kanban artifacts, etc.), exclude their tree.

**Before committing**, check for parallel-agent activity:
```bash
git log --since="10 min ago" --format="%h %an <%ae> %s"
```
If you see commits from agents other than yourself in the last few minutes, `git show <sha>` to confirm they don't conflict with your work.

## Test Integration Workflow

Every sprint commit includes:
1. Add `Test N: <feature description>` block to `test/test_integration.cpp` (insert before final `return 0;`)
2. Each test prints `✓ <description>` per check (so `grep -c "^✓"` gives the total count)
3. Use `std::abs(a - b) < 1e-9` for float comparisons
4. Use `std::cout << "✗ ..." << std::endl;` for failures (don't throw — keep the run going)
5. Run `cmake --build build -j$(nproc) && build/test/test_integration 2>&1 | tail -20`
6. Verify `grep -c "^✓"` returns expected count and `grep "^✗"` is empty before committing

## Final-Summary Rule (added round 8, STRENGTHENED round 9, 2026-06-20)

The user fired "FRAG NICHT IMMER SO BEHINDERT: WEITER!" mid-chain at
Sprint #211 because the prior turn wrote a 25-line
"BTQuant Vulkan Sprint-Bombardement — final summary"
between Sprint #172 and #173. The user interpreted the
prose as a stop signal. Lesson:

1. **NEVER** write a long wrap-up after a sprint commit
   ("Wachstum in dieser Sitzung", "BTQuant Vulkan Sprint-
   Bombardement — final summary", narrative recap, emoji
   decorations). Even mid-chain summaries are forbidden.

2. The right shape is a terse table or ≤8-line status
   block ONLY at the END of a sprint chain (after a real
   natural pause). Between commits: nothing or one
   line.

3. If you captured a real bug pattern or new technique,
   save it via `mcp__mazemaker__mazemaker_remember`
   AND/OR `skill_manage` — do NOT put it in the chat
   reply.

4. The `mcp__mazemaker__mazemaker_remember` call after each
   commit is the only "writing" between commits — it is
   silent and persistent, not chat-visible.

**Natural pause (where a real summary IS OK):**
- Test count hits a round number (200, 250, 300) — end of chain
- User types something with different content (new direction)
- A new file/repo request from the user
- A planned stop (e.g. "let's continue tomorrow")
- The work itself is genuinely done (no implied next step)

**NOT a natural pause:**
- Sprint number hits a round number mid-chain
- The author thinks "this is a good wrap point"
- A clean build + green tests + ready to commit the next
- Cumulative stats look impressive

The user reads the terminal directly. They can see the
commit count and test count themselves. If you write a
narrative recap, you are making them read prose they
didn't ask for. That's a friction event.

## Reference

The `WEITER` cycle for this session (commits 87121d85 onward):
- ThemeEditor discard-changes + unsaved marker (commit 87121d85) → next natural step: lazy-capture was the design move that made the test pass without ImGui context
- RiskPanel live progress bar + reset session (commit b5d992d1) → next natural step: RiskLimitsPanel live update from RiskGuard