# BTQuant Vulkan UI Sprint Cadence (reference)

The exact per-sprint recipe used in 35+ consecutive sprints (2026-05 → 2026-06, all green, 0 failures). Capture and reuse — every sprint follows this same shape.

## Trigger

After a sprint ends and the user says any of:
- `WEITER` / `weiter` / `weiter machen`
- `fr nicht so behindert`
- `mach weiter` / `lass laufen`
- (frustrated) `FRAG NICHT IMMER SO BEHINDERT: WEITER`
- (German) `fertig stellen` / `na dann`

→ pick the next logical item from the deferred list (see `references/deferred-list-template.md`) and execute immediately. NEVER ask.

## Per-sprint recipe (5 phases)

### Phase 1: Identify the next item (5 seconds)

In order, pick the first one that's true:

1. **Finish an in-flight widget.** If a widget has a pending TODO in its `.cpp`/`.hpp` (often a comment like `// deferred:` or `// next:...`), finish it first.
2. **Mirror a recent pattern.** If Sprint N-X shipped a pattern (CSV export, hot-reload, observer-callback), find the next place that needs it. E.g.:
   - TradesWidget had CSV export → TradeJournal (the on-disk side) needed the same export → Sprint #44.
   - Theme editor had reset buttons → next needed `discard changes` from opening snapshot → Sprint #41.
   - RiskLimitsPanel had Apply → next needed `Live update` to stream edits → Sprint #43.
3. **Expose a new struct to the UI.** If a data class was added without a UI binding, build the panel now.
4. **Refactor duplication appearing in 3+ places.** Extract the shared helper, write a test for the helper before doing the call-site conversions.
5. **Cheap & reversible.** Add a test, fix a tooltip, extract a 3-line duplication.

### Phase 2: Implement (N minutes)

- Read the target `.hpp` and `.cpp` in full before patching. Use `read_file` with offset/limit if long.
- Patch with `patch` tool — small, focused diffs.
- For API changes (new field, new signature), update **all call sites** in the same commit: widget, window_manager, test file. Run a `grep -rn <old-signature>` to catch them.
- For save-format migrations, keep the legacy format readable AND make new writes use the new format. Document the migration in the `.cpp`.

### Phase 3: Build + test (~30 seconds)

```
cd /home/alca/projects/PubBTQuant/btquant_vulkan
cmake --build build -j$(nproc) 2>&1 | tail -10
build/test/test_integration 2>&1 | grep -c "^✓"
build/test/test_integration 2>&1 | grep "^✗" | head -3
```

If build fails: fix and re-build. If tests fail: read the failure, fix the implementation (NOT the test, unless the test was wrong). Re-run.

### Phase 4: Commit (explicit paths only)

**Critical rule**: `git add -A` is BANNED in `/home/alca/projects/PubBTQuant/btquant_vulkan/`. Sibling agents commit to `autonomous_agency/` and other siblings under `projects/`. Using `-A` sweeps their work into your commit (one early sprint pulled in 666KB of agency data and had to be soft-reset).

The exact recipe:

```bash
cd /home/alca/projects/PubBTQuant/btquant_vulkan
git add src/widgets/<name>.hpp src/widgets/<name>.cpp src/ui/window_manager.cpp test/test_integration.cpp
git commit -m "feat: <WidgetName> — <one-line feature summary>

<2-4 lines: WHY this exists, WHAT changed at the API level, the test count delta>

Test N (<checks> checks all green): <one-line summary of what Test N verifies>.

<total-count> ✓ total across <N> tests, 0 failures. <widget-count> widgets, <commit-count> commits. <milestone marker if applicable>."
```

Verify after commit:

```bash
git log -1 --format="%h %s"
git show --stat HEAD | head -20
```

### Phase 5: Save state + reply (15 seconds)

```bash
# (memory tool) mazemaker_remember with label fact:btquant-sprint-N-<topic>
# Body: 60-300 words. Lead with WHAT IS TRUE, then WHY IT MATTERS, then HOW IT WAS RESOLVED.
```

Then the user reply — the EXACT shape:

```
Done. Commit <sha> — <one-line feature>. <N>/<N> ✓, 0 failures. <widget-count> widgets, <commit-count> commits.
```

**Do NOT include**:
- A "WEITER — pick:" menu
- An "Or your pick" line
- A `clarify()` call
- A question mark at the end
- An explanation of what was shipped (commit message + tests already document it)
- A "What is true / Why it matters" recap (that belongs in the mazemaker memory, not the chat)

## Test pattern (Test N block)

Every feature gets its own `Test N` block at the end of `test/test_integration.cpp`. Format:

```cpp
// Test N: <WidgetName> — <feature summary>.
// <2-line description of what the test verifies>
std::cout << "\nTest N: Testing <WidgetName> <feature>..." << std::endl;
{
    using btquant::<Namespace>;
    using <TypeAlias> = btquant::<Type>;
    
    // 1) <first check description>
    <expression>
    if (<condition>) {
        std::cout << "✓ <pass message>" << std::endl;
    } else {
        std::cout << "✗ <fail message>" << std::endl;
    }
    
    // 2) <next check>
    ...
}
```

Each check is one `if/else` with a `✓` or `✗` line. Total checks per Test N: 5-15 (8-10 is the sweet spot).

Stable count command:
```bash
build/test/test_integration 2>&1 | grep -c "^✓"
```

## Mazemaker save pattern

```python
mcp__mazemaker__mazemaker_remember(
    label="fact:btquant-sprint-N-<topic>",
    content="""**Sprint #N — <feature> (committed).**

**WHAT IS TRUE:** <2-3 sentences describing the new state of the world>

**WHY IT MATTERS:** <1-2 sentences on the user-visible value>

**HOW IT WAS RESOLVED:** <2-4 sentences on the technical design — what
fields/methods changed, why this approach over alternatives>

**Test N (X checks all green):** <one-line list of what Test N verifies>

**<total> ✓ total across <N> tests, 0 failures. <widget-count> widgets,
<commit-count> commits. Sprint #N>**""",
)
```

Note the leading asterisks (markdown) — the content is rendered as markdown in the memory viewer.

## Common sprint pitfalls (captured in SKILL.md `## Pitfalls (curated)`)

- Don't use `git add -A` (covered above)
- Static + non-static member with same signature → overload error (rename or remove one)
- ImGui context-less tests need guards (`ImGui::GetCurrentContext() != nullptr`)
- Save-format migrations: keep legacy readable
- Lazy capture for snapshot-style state (avoid eager ImGui calls in setOpen)

## Sprint count milestones (track these)

- 10 commits: first stable chunk
- 20 commits: full coverage of common widgets
- 30 commits: nice round number (mark in commit message)
- 50 tests: half-century milestone
- 100 tests: full coverage

When you cross one, mention it in the next commit message and the user reply.

## File locations

- Project: `/home/alca/projects/PubBTQuant/btquant_vulkan/`
- Tests: `test/test_integration.cpp` (one big file with N tests, all in `main()`)
- Build output: `build/btquant_vulkan`, `build/test/test_integration`
- Recent memory: search mazemaker for `fact:btquant-sprint-*-deferred` for the rolling deferred list