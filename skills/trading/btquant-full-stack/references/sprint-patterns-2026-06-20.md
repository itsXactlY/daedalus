# BTQuant Sprint Patterns — 2026-06-20 chain (#44-#52)

Nine back-to-back sprints shipped without breaking the chain. This file
captures the patterns that made it work, distilled from the actual session.

## 1. PICK+SHIP — NEVER ASK "WHAT NEXT?"

**User preference (FIRST-CLASS):** after every `git commit`, do NOT respond
with "WEITER — pick: A, B, C, D" or any pick-list. The user said
"FRAG NICHT IMMER SO BEHINDERT: WEITER!" after every commit when this
happened across #44-#52.

**Rule:** immediately pick the highest-value next step (continuity with
recent work, paired data-layer + UI, hot-path UX wins), read the relevant
files, and start the next patch. Decision-making is the agent's job, not
the user's. Pick what you'd build if the user wasn't there.

The SKILL.md already mentions this preference in the description and the
"Open / next" section, but it gets drowned out by 100KB of phase history.
The rule needs to be louder than any temptation to ask "what's next?".

## 2. Pure-helper extraction for ImGui testability

UI features with modifier-state logic need a test surface that doesn't
require an ImGui context. Pattern:

- Extract the modifier logic into a pure static helper:
  `static bool effectiveSideOnSubmit(bool currentSide, bool altDown)`
- Or add a `setLastTagForTest(...)` setter that primes state without
  going through render.
- The render path calls the helper; tests call the helper directly.

Examples in this session:
- Sprint #47: `OrderTicket::effectiveSideOnSubmit(side, altDown)` — tests
  verify plain-click keeps side, Alt-click flips side, helper is
  referentially transparent.
- Sprint #52: `OrderTicket::setLastTagForTest(tag)` — tests prime
  `m_lastTag` without driving render loop.

## 3. Schema-extension test backwards-compat

Adding a CSV/JSON column (e.g. Sprint #49 added the tag column to
TradeJournal) breaks every test that hardcoded the old format. Pattern:
in the same patch that adds the column, grep for tests asserting on the
old format and update them.

Common broken assertions:
- Header string: `"timestamp_iso,symbol,side,qty,price,realized_delta"`
  (no trailing newline → includes it when comparing)
- Comma count per row: every `if (commas != N)` check
- Field count comment: "6 fields" / "7 fields"

Sprint #49 added the tag column and broke Test 50's assertions.
Fix in same patch: update header to include `,tag\n`, update comma
count to 6, update field count to 7.

## 4. Brace-init field-add pain

Every time a struct gets a new field, every existing `{a, b, c}` brace-init
at a call site breaks compile. Recurring pain in BTQuant:

- `HotkeyBinding` grew `alt` (Sprint #42) → every `{key, ctrl, shift}`
  became `{key, ctrl, alt, shift}` — broke HotkeyMap defaults, HotkeyEditor
  tests, journal replay sites, all the place.
- `JournalFill` grew `tag` (Sprint #49) → no break because tag has default
  constructor `= ""` (last field, can be omitted from brace-init).
- `OrderTicket` grew `m_altSubmitsOpposite` / `m_clearAfterSubmit` /
  `m_rememberLastTag` → no break because these are at the END of the
  member list with default initializers.

**Lesson:** when adding a struct field, decide upfront:
- If the field is at the END with a default → minimal break.
- If the field is in the MIDDLE or has no default → must update all init
  sites in the same patch.
- Use `git grep -nE '\{[^{}]*\bstructName\b'` before merging if needed.

## 5. Paired-sprint pattern

When adding a data-layer field, immediately add the UI to set it in the
next sprint:

| Sprint | Layer | What |
|---|---|---|
| #49 | data  | `JournalFill::tag` field + JSON/CSV serialization |
| #50 | UI    | `OrderTicket` Tag input field that writes to it |
| #51 | query | `TradeJournal::exportCSVByTag()` for per-strategy reporting |
| #52 | UX    | `OrderTicket` remembers the last-used tag so trader doesn't retype |

Each sprint is small (1-3 files, 100-300 lines), testable on its own, and
chains directly to the next. The chain reads coherently end-to-end.

Same pattern applies to other two-layer features: data first, UI next,
ergonomics after.

## 6. Lazy capture for ImGui context-dependent features

From Sprint #41 (ThemeEditor discard-changes): a `m_captured` flag
deferred snapshot capture to first render frame, so `setOpen(true)`
was safe even when no ImGui context was alive (the test path).

Pattern: any feature whose state depends on `ImGui::GetStyle()` /
`ImGui::GetIO()` / `ImGui::GetCurrentContext()` should have a
"captured on first render" pattern:

```cpp
void setOpen(bool v) {
    if (v && !m_open) m_captured = false;  // arm for next render
    m_open = v;
}

void render() {
    if (!m_open) return;
    if (!m_captured && ImGui::GetCurrentContext() != nullptr) {
        m_openingSnapshot = capture(ImGui::GetStyle());
        m_captured = true;
    }
    // ... rest of render
}
```

This keeps `setOpen(true)` testable in a no-ImGui context, while still
capturing the live style on first render frame.

## 7. End-of-sprint commit cadence

After every successful test run, commit immediately. Don't batch up
multiple features into one commit — the user wants the diff to be
reviewable per-feature. Commit message format that worked:

```
feat: <concise feature name>

<body: 1-2 paragraphs explaining the WHY and the HOW>

Test N (M checks all green): <one-line per check>
N ✓ total across M tests, 0 failures. <milestone marker>.
```

The "Test N (M checks all green)" line is the agent's self-audit —
if a future commit breaks a check, the failure shows up in the next
test summary, not as a silent regression.