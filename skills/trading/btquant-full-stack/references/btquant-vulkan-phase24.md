# NEW engine: Phase 24 — RiskConfig persistence via state.ini

## What landed

One commit, one feature: RiskConfig edits survive restart.

- 4 new `Settings` fields: `risk_maxPositionSizeUSD`,
  `risk_maxLeverage`, `risk_killOnDailyLossUSD`, `risk_equityUSD`.
  Defaults mirror `RiskConfig::RiskConfig` so a fresh install loads
  the same values either way.
- `Settings::load` / `save` round-trip the 4 values; uses new
  `looksLikeDouble()` guard instead of the broken `isDouble`
  heuristic. `tradeWindowSeconds` parser also upgraded to the same
  guard (same latent bug — `std::stod("not_a_number")` would throw).
- `RiskLimitsPanel::setPersistFn(callback)` — fires after Apply,
  conservative preset, aggressive preset buttons.
- WindowManager wires the callback: load `state.ini` → mutate 4
  `risk_*` fields from current `RiskGuard::config()` → save back.
  Captures `settingsPath` by-value into the lambda so the closure
  doesn't dereference `this` for the path string.
- `applyPersistedRiskConfig()` runs in `initialize()` after
  `applyPersistedTheme()` — values from the previous session
  restored on startup.

Test 31 (5 checks): defaults, save→reload round-trip, missing-file
→ defaults, malformed line skipped (the bug fix), aggressive preset
round-trips.

## Pitfalls

- **`std::stod` throws on non-numeric input — always guard with a
  character-class check before parsing doubles in hand-rolled config
  parsers**. Test 31 step 4 wrote `risk_maxPositionSizeUSD=not_a_number`
  and `std::stod("not_a_number")` threw `std::invalid_argument`,
  aborting the test binary. The old `isDouble` heuristic was
  `(val is not bool) && (val is not int)` — for "not_a_number" that's
  true, so the parser would always call `std::stod`. The fix:
  `looksLikeDouble(v)` — true iff every char is in
  `{digit, ., -, +, e, E}` AND at least one char is a digit. Apply
  to every existing `isDouble` call site too — `tradeWindowSeconds`
  had the same latent bug and was upgraded in the same commit.
  Generalizes to ANY hand-rolled `key=value` parser using
  `std::stod` / `std::stol` / `std::stoi`.

- **`configDir` hoisting in WindowManager ctor**: previously declared
  twice (once for journal, once for hotkey), now declared once at the
  top of the ctor. The RiskLimitsPanel persist callback needs the
  path BEFORE the journal/hotkey blocks execute, so the hoist was
  mandatory. Pattern: any constructor that derives multiple paths from
  one env var (`HOME` + config-dir suffix) should compute the base
  once and reuse the string for all callers in the same ctor.
  Symptom of the bug: `Use of undeclared identifier 'configDir'` at
  the persist callback registration site, because the `configDir`
  declaration lived AFTER it.

- **`setPersistFn` closure captures path by-value, not `this`**:
  `m_riskLimitsPanel->setPersistFn([this, settingsPath](const
  RiskGuard& g) { ... })`. The `this` capture is needed because the
  callback may want to log via `BTQ_LOG_INFO` (which uses static
  `m_riskGuard`), but the path string is captured by-value to keep
  the closure independent of any future ctor reordering. If the
  closure captured `this->m_settingsPath` and the ctor ever changed
  to set `m_settingsPath` AFTER the closure was registered, the
  closure would read a stale path. Capture path strings by-value.

- **`(void)parameter;` is a footgun — don't add it defensively**: I
  briefly added `(void)glfwWindow;` to silence what I assumed was an
  unused-variable warning at the top of `processHotkeys`. The
  parameter IS used later (the function's body references
  `glfwWindow` in the early-out check `if (!glfwWindow) return;`).
  The compiler doesn't fire unused-warning until later, and the
  explicit `(void)` cast blocks the actual usage from compiling
  correctly. The fix: revert the cast, let the compiler track
  real usage. Re-stated from Phase 23's "don't add (void) casts
  defensively when patching function start".

- **Two paths for kill-switch data flow need to share the session
  tracker**: `Ctrl+K` flatten (manual) and auto-trip via
  `addRealized` (after each `OrderTicket.submit` fill) both write
  to `RiskGuard::m_sessionRealized`. The dispatcher refactor
  consolidated Ctrl+K into `dispatchAction(HA::KillSwitch)` but
  the auto-trip path is still inline in the OrderTicket submit
  pipeline. Both paths share the same `checkOrder` rejection path
  and `isKillTripped()` query, so a single session tracker covers
  both. Don't split the kill switch into two handlers — that
  reintroduces the Phase 17 "two converging paths" pitfall.

- **`Settings::save` writes atomically (tmp + rename)**: the existing
  `Settings::save` implementation writes to `<path>.tmp` first, then
  `fs::rename` over the final path. The persist callback can be
  called multiple times per session (every Apply + every preset
  click); atomic writes prevent corruption if the process is killed
  mid-write. Don't add a direct `out << ...` shortcut that bypasses
  the rename — the test suite assumes atomic behavior in
  `Test 6 settings load/save roundtrip`.

- **Persist callback fires on Apply, not on every keystroke in the
  edit buffer**: the user types into the `m_maxPos` / `m_maxLev` /
  `m_killUSD` / `m_equity` char buffers, but the callback only runs
  on Apply click (or a preset button). This is intentional — the
  guard on the live RiskGuard doesn't mutate per keystroke, so a
  mid-typing crash wouldn't have partially applied values anyway.
  Don't move the persist call into the `InputText` handler — every
  keystroke would write `state.ini`, which is wasteful and would
  also persist partially-typed garbage like `"1000"` instead of
  `"100000"`.

## Lessons carried forward

- **The "FRAG NICHT IMMER SO BEHINDERT" trigger fires 1x in this
  phase**, picking up exactly the first item from Phase 23's
  deferred list. Pattern is now well-documented across Phases 17,
  22, 23, 24: trigger fires → agent picks the highest-priority
  deferred item → ship + commit + report + next. Three-line
  per-turn report.

- **Settings round-trip pattern is reusable**: `load(path) →
  mutate 4 fields → save(path)` is the same shape for ThemeIO,
  TradeJournal, RiskConfig, and any future persisted widget state.
  The atomic tmp+rename in `Settings::save` and `TradeJournal::append`
  means the test suite can read the file mid-write without
  corruption. Document the pattern in any new persistence callback
  so the next one doesn't reinvent it.

- **One substantial commit per turn** continues to be the rhythm:
  Phase 24 was 11 files / ~500 lines / 5 invariants. Trying to
  also journal-replay or DOM heatmap in the same commit would have
  diluted the risk-persistence signal. One feature, one commit,
  one test block.

- **`looksLikeDouble` pattern is a checklist item for any future
  config-parser addition**: when adding new `risk_*` (or any
  double-typed) keys to `Settings`, use `looksLikeDouble(val)` not
  `isDouble` as the guard. The `isDouble` heuristic in
  `Settings::load` is still computed for backward compat but
  should be replaced with `looksLikeDouble` for all existing keys
  in a follow-up. (Currently only `tradeWindowSeconds` and the 4
  `risk_*` keys use the new guard; `fpsLimit` / `heatmapDensity` /
  `theme` use `isInt` which is character-class validated.)

- **`applyPersistedRiskConfig` runs unconditionally, even if the
  state.ini is missing**: the function loads the defaults if the
  file is absent, so a fresh install still gets the built-in
  `RiskConfig{}` defaults — same as before the persistence layer
  existed. Don't gate the apply on "file exists" — the
  `Settings::load` missing-file path returns a default-constructed
  `Settings` struct, which has all the default `risk_*` values
  anyway. This is why the test "missing state.ini → risk defaults"
  passes.

## Phase 25 deferred (open / next)

- Journal replay → PositionBook rehydration on startup (fills
  persisted to `journal.jsonl` but PositionBook starts empty)
- Layout profiles (.btqlayout — separate from the profile presets
  already in `Settings::presetScalper` etc.)
- DOM heatmap widget
- Candlestick bodies via raw draw-list (ImPlot lacks
  `PlotCandlestick` + `ImPlotCol_Fill` — already verified Phase 20)
- 14 commits / 23 widgets / 31 tests / 0 TODOs in core flow