# BTQuant Sprint Patterns — 2026-06-20 round 2 (#53-#68)

Sixteen back-to-back sprints shipped without breaking the chain. Companion to
`sprint-patterns-2026-06-20.md` (the #44-#52 chain). New patterns only —
patterns that already worked carry over from the previous reference.

## 1. PICK+SHIP reinforced (do NOT offer a pick-list)

**User preference (FIRST-CLASS, REINFORCED 2026-06-20):** the user opened
this run with "FRAG NICHT IMMER SO BEHINDERT: WEITER!" — German for "stop
asking so dumb: keep going!" This was the same preference captured in
section 1 of the previous patterns file. It's now established enough that
offering ANY pick-list at sprint end is a workflow violation.

**Concrete shape of the violation to avoid:**
- After `git commit`, do NOT respond with "WEITER — pick: A, B, C, D" or
  similar.
- Do NOT pause to ask "should I keep going on the per-symbol risk story
  or pivot to the kill switch confirmation dialog?"
- Do NOT summarize "what was shipped in this batch" before starting the
  next patch — the user reads git log, not assistant narration.

**Correct shape:** immediately read the next relevant file, start the
next patch. Decision-making is the agent's job. If the previous commit
extended a data layer, the next commit extends the matching UI layer.
If you can't pick a next step, the previous commit was too narrow —
commit something bigger next time.

## 2. Three-layer per-symbol feature architecture

When shipping a "per-symbol" feature on top of an existing single-bucket
guard / config / state, the work splits cleanly into three layers, each
in its own sprint:

| Layer    | Sprint | What                                               |
|----------|--------|----------------------------------------------------|
| Data     | #53    | `addRealized(double, symbol)` overload + per-symbol accessors in `RiskGuard` |
| Visual   | #58    | `RiskPanel` per-symbol kill budget rows (renders what #55 stored) |
| Edit     | #54    | `RiskLimitsPanel` per-symbol cap UI (writes what #53 reads) |
| Edit     | #59    | `RiskLimitsPanel` per-symbol kill UI (writes what #55 reads) |

Same pattern works for any other "per-X" feature: alert thresholds, exposure
caps, max position sizes, drawdown limits. The three-layer split lets
each commit stay reviewable and tests stay focused.

**Rule:** never ship a "per-symbol X" feature in a single mega-commit.
Split. The user reviews per-commit.

## 3. Tag attribution threads through four surfaces

Sprint #49 added `JournalFill::tag`. By sprint #65 the tag now flows
through four distinct surfaces, each with its own sprint and tests:

| Surface                  | Sprint | How tag arrives                 |
|--------------------------|--------|---------------------------------|
| `TradeJournal` (disk)    | #49    | JSON/CSV serialization         |
| `OrderTicket` (input)    | #50    | Tag input field on the ticket  |
| `RecentFillsPanel` (UI)  | #56    | Same `JournalFill` is pushed to the panel |
| `PositionPanel` (UI)     | #65    | Plumbed via WindowManager submit callback |

**Lesson:** when adding a field to the data layer, immediately map out
the surfaces that should carry it. Add them in increasing-distance
sprints (closest first). Closing the loop with PositionPanel was the
last step — without it, the trader sees the tag in the journal export
but not in their active trading UI.

## 4. State-coupling pitfall — ship the wire, not just the widget

Sprint #64 shipped `HotkeyHelpOverlay` with `m_open` flag, but never
wired `m_open` to `showHotkeyHelp` (the existing state variable that
the Ctrl+/ hotkey toggled). Result: the overlay was created but never
visible. The inline `showHotkeyHelpWindow()` was the one actually
rendering. Dead code path that compiled and tested clean.

Sprint #66 fixed it by syncing both directions:
```cpp
m_hotkeyHelpOverlay->setOpen(showHotkeyHelp);
m_hotkeyHelpOverlay->render();
showHotkeyHelp = m_hotkeyHelpOverlay->isOpen();  // persist X / Esc
```

**Rule:** when shipping a new widget that replaces existing inline UI:
in the SAME commit, wire the new widget's visibility flag to the
existing state variable, both directions. Otherwise the widget is dead
code that looks alive in tests but never appears in the app.

## 5. LSP stale-error pattern during rapid hpp+cpp patches

When you patch `widget.hpp` and then `widget.cpp` in quick succession,
the LSP often shows errors on the cpp file:
```
ERROR: Use of undeclared identifier 'm_filter'
```
This is a STALE LSP view — the actual build succeeds because the build
uses the real compiler, not the LSP cache.

**Rule:** after any rapid hpp+cpp patch, run `cmake --build build
--target <bin>` to verify the actual compiler agrees. Don't waste
turns patching the cpp to "fix" identifiers the LSP claims are missing
when the build is clean. The LSP refreshes on the next idle cycle.

**Counter-example to watch for:** if the build ALSO fails, then the
errors are real. Trust the build output, not the LSP output.

## 6. Atomic file rewrite with .tmp + rename

Sprint #62 added `TradeJournal::setTagAt()` / `setTagByTimestamp()`.
Implementation pattern that works for any "edit one line in an
append-only log" use case:

```cpp
namespace {
bool rewriteAll(const std::string& path,
                const std::vector<JournalFill>& fills) {
    std::string tmp = path + ".tmp";
    {
        std::ofstream out(tmp, std::ios::trunc);
        if (!out.is_open()) return false;
        for (const auto& f : fills) {
            out << TradeJournal::toJsonLine(f) << "\n";
        }
        out.flush();
        if (!out.good()) return false;
    }
    fs::rename(tmp, path);  // atomic on POSIX
    return true;
}
}  // namespace
```

The `out.flush()` + close-before-rename is critical: rename on POSIX
only succeeds if no process holds the destination open for writing.

**Test pattern:** verify atomic by checking `fs::exists(path + ".tmp")`
is false after a successful edit.

## 7. Test density discipline

Over 16 sprints, test density held at ~6.86 ✓ per test:
- 488 ✓ across 71 tests
- Each Test N block has 6-8 numbered checks
- Empty journal / single-element / mixed-sign / large-volume corner cases
  are worth their own check
- Off-by-one in literal string sizes happens — count characters in the
  test source, don't trust your visual count

**Counter-example (Sprint #65):** test 4 expected `copy.tag.size() == 35`
but the literal was 34 chars. Test failed, fixed to 34. Suggests adding
`static_assert(kTagLiteral.size() == N)` style guards when literal-size
matters, OR just always print the actual size on failure.

## 8. Memory format that builds a chronological log

Every sprint saves memory with the same template — this session saved
16 entries (mazemaker ids 824821-824854) that form a chronological log:

```
**Sprint #N — <feature name> (committed).**

**WHAT IS TRUE:** <1-2 sentences>
**WHY IT MATTERS:** <1-2 sentences>
**HOW IT WAS RESOLVED:** <1-2 sentences>
**Test N (M checks all green):** <per-check list>
**X ✓ total across Y tests, 0 failures. N widgets, M commits. Sprint #N.**
```

Each entry ends with cumulative stats so the operator can grep by sprint
number and see exactly what was added. The `state` word (which the
operator's MEMORY.md emphasizes) is implicit — committed code IS the
state. Memory is the WHAT/WHY/HOW, not a duplicate of `git log`.

## 9. Status checkpoint cadence

After ~14 sprints, give a status checkpoint with:
- Total tests + cumulative failures
- Widget count
- Commit count
- Per-sprint summary table (sprint #, feature, files changed)
- "Next obvious gaps" — 2-3 specific follow-up candidates, NOT a
  pick-list to vote on

The checkpoint is FOR the operator (helps them decide whether to keep
shipping this shape or pivot). It is NOT a pause for permission — the
next sprint starts in the same response.

## 10. Sprint shape variety after 10+ in a row

Sprints #44-#52 and #53-#68 were both long chains of small features.
After ~10 sprints in a chain, the variety drops and most new sprints
start to feel like variations on the same theme. Counter-signals:
- New widget? Yes → fresh surface area, good pivot
- New accessor on existing data class? Yes → still meaningful
- New render column on existing widget? Diminishing returns — consider
  state coupling / refactor instead

**Rule for variety:** every ~10 sprints, force at least one "touches a
new layer" sprint (new data class, new file format, new network path).
This run had #62 (file format editing) and #67 (new accessor on journal)
as the variety pivots. Without them the chain becomes wallpaper.

## Cumulative run stats

- Sprints #53-#68 (16 sprints)
- 26 widgets (added RecentFillsPanel #56, HotkeyHelpOverlay #64)
- 488 ✓ across 71 tests (0 failures)
- 57 commits on `0.0.2`
- All work in `/home/alca/projects/PubBTQuant/btquant_vulkan/`
- Memory: mazemaker ids 824821-824854 (16 entries)
- Half-century commit mark reached at #50 (commit 2454ced4 in this run)
- Tests-total mark crossed at 488 ✓ (#67)

PICK+SHIP was upheld throughout. Zero pick-lists offered at sprint end.