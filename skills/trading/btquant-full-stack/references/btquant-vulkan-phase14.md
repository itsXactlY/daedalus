# Phase 14 — Symbol swap wireup (Ctrl+P → MarketDataProcessor::setSymbol)

## Scope

Close the gap left by Phase 11/12: SymbolPicker (Ctrl+P modal) existed and
fired its callback, but the callback only logged. The picked symbol was
never routed into the live data pipeline. Phase 14 closes that loop so
picking "ETH/USDT" actually swaps the active feed.

## Files touched (commit `6b07fc9e`, 14 files / +556/-5)

| File | Change |
|---|---|
| `src/data/data_spine.hpp` | + `std::optional<uint32_t> findSymbolIndex(const std::string&) const;` |
| `src/data/data_spine.cpp` | + `findSymbolIndex` impl — linear scan over `m_symbolSymbols` |
| `src/data/market_data_processor.hpp` | + `setSymbol(const std::string&)` + `activeSymbolIndex()` accessor; + `std::atomic<std::optional<uint32_t>> m_activeSymbolIndex{std::nullopt};` |
| `src/data/market_data_processor.cpp` | + `setSymbol` impl: atomic idx update + aggregator reset + counter zero; `start()` now resolves initial symbol index against the spine; runLoop filters by `entries[*idxOpt]` |
| `src/ui/window_manager.hpp` | + `::btquant::MarketDataProcessor* m_marketData = nullptr;` cache |
| `src/ui/window_manager.cpp` | + `<algorithm>` include; `setMarketData()` caches into `m_marketData`; SymbolPicker callback forwards to `m_marketData->setSymbol(sym)` + watchlist promotion (rotate-or-insert) |
| `src/widgets/symbol_picker.hpp` | + `void setFilter(const std::string& f)` — public test hook for substring narrowing (production path is `render()` reading ImGui input) |
| `test/test_integration.cpp` | + Test 17 extended: filter narrowing (3/1/5); + Test 21: setSymbol field update + tick counter reset + aggregator clear |

## Pattern: WindowManager caches the data source so callbacks can dispatch

Before Phase 14, `WindowManager::setMarketData(data)` only PROPAGATED the
pointer to widgets (`m_orderBookWidget->setMarketData(data)`, …). It did
NOT retain the pointer itself. This meant the SymbolPicker callback —
which is owned by WindowManager — could not reach the data source.

**Fix:** add `::btquant::MarketDataProcessor* m_marketData = nullptr;` to
WindowManager. Set it in `setMarketData()` alongside the propagation.
The callback can now do `m_marketData->setSymbol(sym)`.

This generalizes: any modal/widget callback in WindowManager that needs
to talk to the data source needs the cached pointer, not just the
propagated-to-widgets copy.

## Pattern: DataSpine entries are index-correlated with symbols

`DataSpine::readAllEntries()` returns `std::vector<HotSpineEntry>` where
`entries[i]` corresponds to spine symbol slot `i`. The `HotSpineEntry`
struct does NOT carry a `symbol_index` field — there's no need; the
position in the vector IS the index.

**Don't add `symbol_index` to HotSpineEntry.** It's redundant. Use the
vector position.

```cpp
// Correct (entries are index-correlated):
auto entries = m_spine->readAllEntries();
if (idxOpt && *idxOpt < entries.size()) {
    const auto& e = entries[*idxOpt];   // <-- position, not field
    /* ... */
}

// Wrong (don't try to tag entries):
if (e.symbol_index != *idxOpt) continue;   // no such field
```

## Pattern: atomic<optional<uint32_t>> for thread-safe active symbol index

`MarketDataProcessor::setSymbol()` runs on the main thread (called from
the SymbolPicker callback). `runLoop()` reads the active symbol index on
the background thread. C++17 `std::atomic<std::optional<uint32_t>>` works
fine for this — it's lock-free for `uint32_t`-sized payloads and the
engine stores the optional's discriminator in the same atomic word.

```cpp
std::atomic<std::optional<uint32_t>> m_activeSymbolIndex{std::nullopt};

// Producer (setSymbol):
m_activeSymbolIndex.store(m_spine ? m_spine->findSymbolIndex(sym)
                                  : std::nullopt,
                          std::memory_order_release);

// Consumer (runLoop):
auto idxOpt = m_activeSymbolIndex.load(std::memory_order_acquire);
if (idxOpt && *idxOpt < entries.size()) { /* feed entries[*idxOpt] */ }
```

Pitfall: don't use `std::atomic<std::optional<uint32_t>>` if the optional
holds a non-trivial type (e.g. `std::optional<std::string>`). C++20
specializes atomic for optional<T> where T is trivially copyable, but
C++17 has only the integer-sized specialization. For string payloads,
use a mutex.

## Pattern: setSymbol = atomic idx + aggregator reset + counter zero (no thread join)

Unlike a producer restart, `setSymbol` does NOT stop+join the runLoop.
The aggregator clears in-place under the snapshot mutex; the next tick
is read against the new index.

```cpp
void MarketDataProcessor::setSymbol(const std::string& sym) {
    m_symbol = sym;
    std::optional<uint32_t> idx;
    if (m_spine && m_spine->isOpen()) idx = m_spine->findSymbolIndex(sym);
    m_activeSymbolIndex.store(idx, std::memory_order_release);
    {
        std::lock_guard<std::mutex> lock(m_snapshotMutex);
        m_aggregator.reset();
        m_latestSnapshot = Snapshot{};
        m_latestSnapshot.snapshot_seq = ++m_snapshotSeq;
    }
    m_ticksSeen.store(0, std::memory_order_relaxed);
    m_parseErrors.store(0, std::memory_order_relaxed);
}
```

Why no join: aggregator state is the only thing that needs to be coherent
across the swap. The runLoop keeps polling the spine — `readAllEntries()`
returns the same vector, just with a different active index. Zero downtime
on the snapshot path. The next widget poll sees `snap.snapshot_seq`
incremented (the ++m_snapshotSeq inside the lock) so consumers can detect
the clear.

## Watchlist promotion pattern: rotate-or-insert

When the user picks a symbol from the picker, promote it to the top of
the watchlist so they see it highlighted without scrolling.

```cpp
auto cur = m_watchlistWidget->symbols();
auto it = std::find(cur.begin(), cur.end(), sym);
if (it != cur.end()) std::rotate(cur.begin(), it, it + 1);  // move to front
else                  cur.insert(cur.begin(), sym);        // new entry
m_watchlistWidget->setSymbols(cur);
```

`std::rotate` is O(1) on the range; cheaper than erase+insert_front.

## Pitfalls (Phase 14)

### Pitfall #1: WindowManager callbacks can't reach the data source

A modal/widget callback installed in WindowManager needs the
MarketDataProcessor pointer to do useful work. If
`WindowManager::setMarketData()` only PROPAGATES to widgets and does
not RETAIN the pointer, the callback is stuck logging. ALWAYS cache
the pointer in WindowManager alongside the propagation.

### Pitfall #2: DataSpine entries are positionally index-correlated

`readAllEntries()` returns a vector where `entries[i] == spine symbol i`.
Don't add `symbol_index` to `HotSpineEntry`. Don't write
`if (e.symbol_index != idx) continue;` — the field doesn't exist. Use
the position.

### Pitfall #3: Test expectation off-by-one with substring matching

Filter "A" against `{AAPL, GOOG, MSFT, AMZN, META}` matches **3** symbols
(AAPL, AMZN, META — all contain lowercase 'a'), not 2. Case-insensitive
substring matching is correct; my mental model was wrong. Before writing
a "filter narrows to N" test, enumerate the expected matches by hand —
counting only the obvious ones (AAPL, AMZN) misses META.

### Pitfall #4: `<algorithm>` for std::find/std::rotate in callbacks

WindowManager's SymbolPicker callback uses `std::find` and `std::rotate`
for watchlist promotion. Don't assume `<algorithm>` is transitively
included by `<imgui.h>` or `<imgui_internal.h>` — ImGui's headers don't
pull it in. Add `#include <algorithm>` explicitly in window_manager.cpp
when introducing the first algorithm-using callback.

## Test extensions

### Test 17 extended (3 new invariants)
- `setFilter("A")` narrows to 3 (AAPL, AMZN, META)
- `setFilter("MS")` narrows to 1 (MSFT)
- `setFilter("")` clears filter, restores all 5

### Test 21 new — MarketDataProcessor::setSymbol (6 invariants)
- initial symbol = BTC/USDT
- no-spine → activeSymbolIndex nullopt
- synthetic ticksSeen > 0 after 20 polls
- setSymbol updated field → ETH/USDT
- ticksSeen reset to 0 on swap
- aggregator cleared (no bleed across swap) — `snap.recent_trades.empty() && snap.recent_candles.empty()`

## State after Phase 14

- 11 commits
- 17 widgets
- 21 tests, all green
- Build + smoke (`timeout 3 ./build/btquant_vulkan` exit 0) clean

## Lessons carried forward

- **Callback reachability requires state caching.** When designing a
  Manager struct that owns widgets AND has callbacks installed on those
  widgets, decide upfront whether callbacks need to talk to external
  resources (data sources, settings, loggers). If yes, the Manager MUST
  cache those resources — propagating-to-widgets is not enough.
- **Index correlation is an invariant, not a coincidence.** When a data
  source returns a vector of "things indexed by N", document the
  invariant on the function. Don't tag each entry with its index —
  position is the index. Future code that wants "give me entry for
  symbol K" reads `entries[K]`, not `entries.find_by_index(K)`.
- **Always enumerate expected matches for filter tests.** Don't
  eyeball — write the explicit list before the assertion. Substring
  filters are the easiest place to under-count.