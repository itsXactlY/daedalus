# BTQuant Sprint Patterns (sprints 43-44)

**Loaded when:** building bound-widget enhancements or CSV exporters in `~/projects/PubBTQuant/btquant_vulkan/`. Companion to `sprint-discipline-and-weiter.md` — that file covers the WEITER workflow and lazy-capture; this one covers UI-state-binding and CSV-export patterns that emerged in sprints 43-44.

## Live-Update Toggle Pattern (bound widgets streaming to a data object)

When a widget owns editable state (char[] buffers, sliders, checkboxes) AND has a bound external data object (RiskGuard, PositionBook, OrderTicket draft, etc.), the default UX is "Apply" button. For the highest-value field — usually the one the user is most likely to tweak mid-session — add a **Live update** checkbox that streams changes immediately.

**Why:** RiskLimitsPanel's kill threshold is the dial a trader will spin 5+ times per session based on intraday P&L. Making them click Apply each time is friction that breaks the sprint's "live and responsive" feel. The other caps (max position, max leverage, equity) are set once and rarely tweaked — keep them Apply-gated.

**Implementation recipe (commit f01ee6f2):**

```cpp
// header — private
bool m_liveUpdate = false;
double m_lastAppliedKillUSD = 5000.0;   // matches default buffer, see below

// public
void setLiveUpdate(bool v) { m_liveUpdate = v; }
bool isLiveUpdate() const { return m_liveUpdate; }
bool isKillDirty() const {  // buffer vs last-applied
    return editedKillOnDailyLossUSD() != m_lastAppliedKillUSD;
}

// impl — apply path tracks last-applied value
void Widget::applyToGuard() {
    // ... push to guard ...
    m_lastAppliedKillUSD = c.killOnDailyLossUSD;   // <-- key line
}

void Widget::applyBufferToGuardField() {  // called per keystroke when live
    ::btquant::RiskConfig c = m_guard->config();
    c.killOnDailyLossUSD = editedKillOnDailyLossUSD();
    m_guard->setConfig(c);
    m_lastAppliedKillUSD = c.killOnDailyLossUSD;
}

// render loop
if (ImGui::Checkbox("Live update", &m_liveUpdate)) {
    if (m_liveUpdate) applyBufferToGuardField();  // sync on engage
}
if (ImGui::InputText("Kill on loss", m_killUSD, sizeof(m_killUSD))) {
    if (m_liveUpdate) applyBufferToGuardField();
}
if (isKillDirty()) ImGui::TextColored(yellow, "* unsaved");
else if (m_liveUpdate) ImGui::TextDisabled("(live)");
```

**Critical initialization detail:** Set `m_lastAppliedKillUSD` to the default buffer's parsed value (5000.0 for the conservative config). Otherwise a freshly-constructed panel reads dirty (5000 != 0) and the "* unsaved" hint flashes for no reason. Same logic applies to any "buffer vs last applied" tracker — both sides must start equal.

## Private-State Buffer Test Design

When testing widgets that own private char[] buffers or other private state, do NOT try to mutate private members via test helpers or friends. Test the **public invariants**:

1. **State-machine toggles** — `setLiveUpdate(true)` / `setLiveUpdate(false)` / `setLiveUpdate(true)` ends in the correct state.
2. **Accessor round-trip** — `editedKillOnDailyLossUSD()`, `editedMaxPositionSizeUSD()` return the default buffer's parsed value (5000.0, 100000.0, etc.).
3. **External-state isolation** — rebind the widget to a NEW bound object; the buffer state stays independent (no leakage from the prior binding).
4. **Rebind doesn't stomp** — when `setRiskGuard(&newGuard)` is called, the buffer stays at its parsed value, the new guard stays at its own config (no buffer→guard data leak).

**Why:** Trying to test "isKillDirty true when buffer diverges from guard" by mutating the buffer via snprintf requires either making the buffer public, adding a friend declaration, or adding a test-only setter — all of which leak implementation into the public surface. The cascade failure on Test 49 was caused by this: test 4 assumed `m_lastAppliedKillUSD` started at 0.0 (wrong) so the buffer's 5000.0 read as dirty. Fix the test by checking public invariants instead.

The pattern generalizes to any widget with private edit state:
- Test that toggles work
- Test that accessors return parsed defaults
- Test that rebinding to a new backing object doesn't stomp
- Test that apply paths update the last-applied tracker (via the only public way — observing the bound object's state after the apply)

## CSV Export Dual-Mode Pattern (pure serializer + I/O wrapper)

When a widget has data the user wants to export (TradesWidget live trades, TradeJournal persisted fills, PositionBook current state, etc.), expose TWO methods on the data-owning class:

```cpp
// Pure serializer — testable, no I/O, deterministic.
static std::string formatFillsCSV(const std::vector<JournalFill>& fills);

// I/O wrapper — calls formatFillsCSV + writes file with create_directories.
bool exportCSV(const std::string& path) const;
```

**Why split:** `formatFillsCSV` is what tests assert against. `exportCSV` is the wired-up path the widget's "Export CSV…" modal calls. They stay byte-identical because both go through the same serializer. If you add a new field, you update both in lockstep, but the tests only need to assert on the pure path.

**Header convention:** `timestamp_iso,symbol,side,qty,price,realized_delta` — snake_case, chronological metadata first, trade size next, P&L attribution last. ISO-8601 UTC with microsecond precision. Side rendered as `BUY`/`SELL` (not `buy`/`sell` — human-readable for spreadsheets). Keep byte-identical to other widget's CSV exports so a downstream pipeline ingests both without parser changes.

**I/O behavior:** trunc, not append. Existing file is overwritten. Create parent directories. Return false on any error (no exception throw — keep the caller's render loop happy).

**Tests required** (Test 50 pattern, ~10 checks):
1. Empty data → header-only CSV
2. N rows → N+1 newlines (header + N)
3. Header byte-exact
4. Every row has expected comma count
5. ISO-8601 timestamp format on at least one row
6. Side renders correctly (BUY/SELL on at least one row of each)
7. exportCSV writes file at given path
8. On-disk content == in-memory formatXxxCSV output (no extra junk)
9. exportCSV overwrites stale content (trunc, not append)
10. Clean fields stay unquoted (RFC-4180 hook is idempotent for normal input)

## Reference commits (sprints 43-44)

- commit f01ee6f2 — RiskLimitsPanel live-update mode for kill threshold. 3 files, 214+ / 5-. Live-update checkbox, applyBufferToGuardField(), last-applied tracker, "* unsaved" / "(live)" hint.
- commit 34cfcb94 — TradeJournal CSV export of persisted fills. 3 files, 272 insertions. formatFillsCSV() + exportCSV(), ISO-8601 timestamps, RFC-4180 quoting hook.

Both followed the standard sprint discipline: build clean, add Test N with 7-10 checks, verify `grep -c "^✓"` and `grep "^✗"` is empty, commit, report.