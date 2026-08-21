# BTQuant Vulkan — Phase 18: TradeJournal + integrated OrderTicket pipeline

Date: 2026-06-20. Commit: `d56117cb feat: TradeJournal — JSONL fill persistence at ~/.config/btquant_vulkan/journal.jsonl`. Test 25: 11 invariants, all green. Sprint state at end: 15 commits, 19 widgets, 25 tests.

## What landed

- `src/data/trade_journal.{hpp,cpp}` — append-only JSONL journal at
  `~/.config/btquant_vulkan/journal.jsonl`
  - `JournalFill` struct: timestamp_us, symbol, isLong, qty, price, realizedDelta
  - `TradeJournal` class:
    - constructor takes path
    - `append(fill)` — appends one JSON line, creates parent dir if missing
    - `loadAll(&skippedCount)` — reads all lines, skips malformed, counts them
    - `recent(n)` — last N fills, newest first
    - `count()` — line count (cheap)
    - `clear()` — removes file
  - Pure: `toJsonLine` / `fromJsonLine` — hand-rolled flat-object JSON parser
    (no nlohmann/json dependency since the system header isn't available)
  - Escapes `"`, `\`, control chars in symbol strings
  - Skips lines missing required keys (sym, side, qty, px)
- WindowManager integration:
  - `m_tradeJournal` member; path = `$HOME/.config/btquant_vulkan/journal.jsonl`
  - Startup logs on-disk fill count + skipped-line count
  - OrderTicket submit callback appends after each successful fill
    (timestamp = `std::chrono::system_clock::now()` in µs)
  - Ctrl+K kill switch appends the closing fill

## Architecture: integrated OrderTicket → RiskGuard → PositionBook → TradeJournal pipeline

The OrderTicket submit callback is now a 5-step pipeline. The order of
operations matters — each step can short-circuit or feed the next:

```
OrderTicket.submit(summary)
  ├─ 1. Resolve symbol from m_marketData (fallback: literal "BTC/USDT")
  ├─ 2. Resolve fill price from latest snapshot (fallback: ticket limit input)
  ├─ 3. Validate qty > 0 and price > 0 → BTQ_LOG_WARN + return on fail
  ├─ 4. RiskGuard.checkOrder(qty, price, isBuy)
  │      └─ reject if notional/leverage/kill tripped → BTQ_LOG_WARN + return
  ├─ 5. PositionBook.fill(sym, isBuy, qty, price)
  │      └─ returns realized P&L delta (0 on open, ±X on close/flip)
  ├─ 6. RiskGuard.addRealized(realized) (only if non-zero)
  │      └─ BTQ_LOG_ERROR if isKillTripped() now true
  ├─ 7. TradeJournal.append(JournalFill{timestamp, sym, isBuy, qty, price, realized})
  │      └─ BTQ_LOG_WARN on append failure
  ├─ 8. PositionPanel.recordFill(FillRecord)
  └─ 9. BTQ_LOG_INFO with realized delta (only if non-zero)
```

The Ctrl+K flatten path shares steps 6 + 7 (session tracking + journal)
but skips the positionBook.fill (it calls flatten() directly).

## Architecture: hand-rolled JSONL parser

The choice to skip nlohmann/json came from the dependency reality:
`find_package(nlohmann_json QUIET)` in `CMakeLists.txt` quietly fails
on this system (`nlohmann_json_DIR: nlohmann_json_DIR-NOTFOUND` in the
cache). The only nlohmann/json.hpp on the filesystem is the fetched copy
in `dependencies/BTQ_Render_Engine/build/_deps/json-src/` — not on the
include path for `btquant_vulkan`.

Trade-off:
- **nlohmann**: more features (nested objects, arrays, schema validation),
  but adds a dependency that breaks the build on this system. Would
  require adding `FetchContent_Declare(nlohmann_json ...)` like imgui
  is handled.
- **Hand-rolled**: ~50 lines for a flat-object parser with primitive
  values. Doesn't handle nested objects or arrays. Sufficient for the
  journal's flat row schema.

For the journal use case (flat objects with strings/numbers/booleans),
hand-rolling is the right call. Reserve nlohmann for cases with nested
structure.

The parser implementation:
1. Skip whitespace, expect `{`
2. Loop: read key (quoted string), `:`, value (quoted string OR bareword)
3. Handle escape sequences in strings: `\"`, `\\`, `\n`, `\r`, `\t`
4. Trim trailing whitespace from raw values
5. Stop at `}` or end of input

`fromJsonLine` is permissive: missing required keys → `nullopt`.
`loadAll(&skippedCount)` uses this to skip malformed lines gracefully
without aborting the load.

## Architecture: append-only JSONL over SQLite

Trade-off rationale for choosing JSONL:
- **SQLite**: queryable (WHERE clause, joins), ACID, scales to millions
  of rows. Requires linking libsqlite3 (system package or FetchContent).
- **JSONL**: append-friendly (no schema migrations), greppable, easy
  to repair with text editor, no dependency. Linear scan is fine for
  thousands of fills; for 10k+ rows, switch to SQLite.

For the journal use case (handful of fills per session, weeks of data
before it grows), JSONL wins on simplicity. The `TradeJournal::count()`
is O(N) line count which is fine for the realistic data volume. If the
journal ever hits 100k+ rows, swap to SQLite without changing the
public API (loadAll/recent/append all stay the same shape).

## Test 25 — 11 invariants

- empty journal → count 0, loadAll empty, skipped 0
- append 3 fills → count 3
- round-trip: qty/price/side/realized intact
- recent(2) returns last 2 in newest-first order
- recent(N>size) returns all reversed
- malformed line skipped (size+1, skipped=1)
- clear() removes file
- pure toJsonLine/fromJsonLine round-trip
- malformed/empty/{} → nullopt
- escape round-trip with quotes + backslashes in symbol
- escape survives: `weird/"sym\name` round-trips to itself

## Pitfalls (NEW — captured this phase)

- **System nlohmann/json is NOT installed** — `find_package(nlohmann_json
  QUIET)` in `CMakeLists.txt` silently fails (`nlohmann_json_DIR:
  nlohmann_json_DIR-NOTFOUND`). The only working copy is the fetched one
  in `dependencies/BTQ_Render_Engine/build/_deps/json-src/` which is
  NOT on this project's include path. For a flat-object schema, hand-
  rolling a JSON parser is ~50 lines and avoids adding a FetchContent
  cycle. Trade journal schema is exactly this — flat rows with
  strings/numbers/booleans. Reserve nlohmann for nested structures
  (config trees, API responses).
- **`getpid()` is not in the global namespace on glibc** — it's
  declared in `<unistd.h>`. Writing `std::to_string(::getpid())` in a
  test file that doesn't include `<unistd.h>` fails with "No member
  named 'getpid' in the global namespace; did you mean 'getpt'?". Use
  `std::to_string(static_cast<long>(::time(nullptr)))` instead — `time`
  is in `<ctime>` which most C++ TUs already include via `<chrono>` or
  `<iomanip>`. (See `btquant-vulkan-phase18.md` pitfall #2.)
- **Pipeline order matters in OrderTicket submit** — the 9-step
  pipeline documented above is the canonical order. Skipping a step or
  reordering can produce inconsistent state: e.g. feeding the journal
  before the risk check means a rejected order writes a "ghost fill"
  to disk; feeding the journal after PositionPanel.recordFill but
  before the positionBook.fill means the panel shows the fill but the
  book doesn't. The order is: validate → risk-check → book-fill →
  session-track → journal → panel → log.
- **`TradeJournal::append` does NOT create the journal file on
  construction** — the file only exists after the first `append()`. If
  you grep for the journal immediately after startup with no orders
  submitted, you'll get "file not found". This is intentional: an empty
  journal = no file = no clutter. Don't add a touch-on-construction
  side effect; document the "lazy create" behavior instead.

## Lessons carried forward (already in SKILL.md)

- **Pure-math statics as the test seam**: `TradeJournal::toJsonLine` /
  `fromJsonLine` are static. The filesystem-touching `append` /
  `loadAll` / `recent` / `count` / `clear` use temp paths in tests.
  Same pattern as PositionCalculator, OrderTicket, RiskGuard. The pure
  helpers are the cheapest invariants to verify; the filesystem
  integration is verified by reading back what was written.
- **Two-CMakeLists trap**: hit again this phase — `trade_journal.cpp`
  had to be added to BOTH `CMakeLists.txt` AND `test/CMakeLists.txt`.
  Already covered in Phase 15 pitfalls, but worth re-flagging because
  it's fired in 4 of the last 6 phases.
- **Substring-filter / count test invariants need the magnitude
  computed correctly** — Phase 16 flagged "off-by-10× in P&L test
  assertions". Phase 18 had no such trap because the journal math is
  string serialization, not numerical. The lesson: before writing any
  assertion that involves multiplication, do the full computation by
  hand on paper first.

## Sprint progression summary

End of Phase 18: 15 commits, 19 widgets, 25 tests. The "FRAG NICHT IMMER SO BEHINDERT: WEITER!" trigger fired 5+ times across this sprint. The user's signal is consistent and unambiguous: ship code, ship commits, don't ask. The pipeline integration (RiskGuard + PositionBook + TradeJournal all feeding from OrderTicket submit) is the natural endpoint of the trading-domain sprint — every subsequent feature can be added without touching this pipeline, just by extending one of the four subsystems or adding a new pre/post-step.

## Persistent file layout after Phase 18

```
~/.config/btquant_vulkan/
├── state.ini           # widget visibility + theme + heatmap density
├── theme.ini           # ImGui color/style snapshot (Phase 13)
├── profiles/*.ini      # user-saved named layouts (Phase 11)
└── journal.jsonl       # fill history — append-only JSONL (Phase 18)
```

All four files are user-level config, not in-repo. `state.ini` is
hand-rolled key=value (Phase 5), `theme.ini` uses `c<i>.<ch>=` format
to avoid 2-digit index ambiguity (Phase 13), `profiles/*.ini` use the
same format as `state.ini`, `journal.jsonl` is one JSON object per
line (Phase 18).