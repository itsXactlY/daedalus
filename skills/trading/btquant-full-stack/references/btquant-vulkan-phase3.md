# btquant_vulkan Phase 3 — Widget Wire-up + Candle Aggregation

## Context

Third session on the `btquant_vulkan/` rebuild (2026-06-19). After
Phase 2 left the 4 original widgets (Order Book / DOM / Trades / TPO)
using their own internal static mock data, the user asked for both the
remaining options rolled together: (1) wire all 4 widgets to the
live `MarketDataProcessor::snapshot()` and (2) add a real per-minute
OHLCV candle aggregator so the TPO widget no longer reconstructs
candles from trades in-widget.

The result: 5 widgets, all live, with deterministic candle aggregation
that any future widget (Volume Profile, Footprint) can read for free.

For Phases 1 + 2 (build rescue, compute pipeline, live data
ingestion), see `references/btquant-vulkan-rebuild-fixes.md`. This file
documents ONLY the new patterns from Phase 3.

## 22. Widget-to-MarketDataProcessor wire-up — `setMarketData` pattern

The 4 trading widgets each got a
`setMarketData(::btquant::MarketDataProcessor*)` setter. `WindowManager`
owns the widget instances and exposes a single `setMarketData(data)`
that propagates to all 4. Each widget's `render()` then does:

```cpp
bool isLive = false;
data::OrderBook book{};     // (or Trade vector, or Candle vector, etc.)
if (m_data) {
    auto snap = m_data->snapshot(1);   // 1 trade / 1 candle — last-known state
    if (snap.snapshot_seq > 0) {
        book = snap.order_book;          // or trades = snap.recent_trades
        isLive = true;
    }
}
if (!isLive) {
    // Internal synthetic fallback — small random walk, shown when no
    // producer is running. Keeps the UI alive during demos.
    static double fallbackMid = 100.0;
    ...
}
```

This dual-path (live → fallback) means the UI shows data the moment the
binary starts, regardless of whether the producer is online. The
header shows "Source: LIVE" or "synthetic" so the operator can see at
a glance whether real data is flowing.

The whole pattern fits in ~30 lines per widget and is the canonical
way to attach any future widget (Footprint, VPVR, Risk Panel) to the
MarketDataProcessor.

## 23. Namespace forward-declaration trap (Eliess-style)

**Symptom:** `error: 'MarketDataProcessor' wird in diesem Gueltigkeitsbereich
nicht deklariert; meinten Sie 'btquant::ui::MarketDataProcessor'?`
— the compiler thinks the member-pointer `class MarketDataProcessor* m_data`
refers to a `btquant::ui::MarketDataProcessor`, not the real
`btquant::MarketDataProcessor`. Subsequent assignments from
`::btquant::MarketDataProcessor*` trigger
`Incompatible pointer types assigning to 'class MarketDataProcessor *'
from 'class ::btquant::MarketDataProcessor *'`.

**Root cause:** Forward-declaring `class MarketDataProcessor;` INSIDE
`namespace btquant::ui { ... }` declares a brand-new class
`btquant::ui::MarketDataProcessor`, shadowing the real one in the
parent namespace. Even though the .cpp includes the full
`market_data_processor.hpp` (which defines
`btquant::MarketDataProcessor`), the member-pointer type in the .hpp
is still the local shadow class. The LSP error "Use of undeclared
identifier 'MarketDataProcessor'" is misleading — it IS declared,
just in the wrong namespace.

**Fix:** Forward-declare at GLOBAL scope BEFORE opening the inner
namespace, and use fully-qualified `::btquant::X*` in function
signatures:

```cpp
// widget.hpp
namespace btquant { class MarketDataProcessor; }   // GLOBAL fwd decl

namespace btquant::ui {
class MyWidget {
    void setMarketData(::btquant::MarketDataProcessor*);  // fully qualified
    ::btquant::MarketDataProcessor* m_data = nullptr;    // fully qualified
};
}
```

The `::btquant::` prefix unambiguously references the global namespace
where the real class lives, even when the call site is inside
`namespace btquant::ui`.

**Generalization:** Any time a class lives in namespace `N` and you
need to reference it from a sub-namespace `N::Sub`, the forward
declaration MUST be at global scope (or in `N` directly), NOT inside
`N::Sub`. Same trap for any cross-namespace references.

## 24. Minute-candle aggregation in `MarketDataAggregator`

Previously the TPO widget reconstructed candles from the rolling
trade buffer — wasteful (rebuilt every frame) and limited (only saw
what was in the 200-trade window). Now the aggregator buckets ticks
into per-minute OHLCV candles with bucket-aligned timestamps:

```cpp
struct Candle {
    double open, high, low, close, volume;
    double buyVolume, sellVolume, delta;
    uint32_t tradeCount;
    uint64_t startTime, endTime;  // microseconds, bucket-aligned
};

class MarketDataAggregator {
    // Defaults: 60s buckets, 60 candles max (1h rolling window).
    explicit MarketDataAggregator(uint64_t candle_bucket_us = 60ULL * 1'000'000ULL,
                                 size_t max_candles = 60);

    void update(const MarketTick& tick);  // folds tick into current bucket
    const std::vector<Candle>& candles() const;
    const Candle* currentCandle() const;   // in-progress bucket, null if empty
};
```

The folding logic in `update()`:
```cpp
uint64_t bucket_start = (tick.timestamp / m_candleBucketUs) * m_candleBucketUs;
if (!m_haveCurrent) {
    m_current = makeBucket(tick.timestamp, tick.price, m_candleBucketUs);
    m_currentBucketStart = bucket_start;
    m_haveCurrent = true;
} else if (bucket_start != m_currentBucketStart) {
    m_current.endTime = m_currentBucketStart + m_candleBucketUs;
    finalizeCurrentCandle();
    m_current = makeBucket(tick.timestamp, tick.price, m_candleBucketUs);
    m_currentBucketStart = bucket_start;
    m_haveCurrent = true;
}
// Fold tick into m_current (update high/low/close/volume/buy/sell/delta/count).
```

Why bucket-align timestamps: the first tick of a minute might arrive
at `00:37.5`, but all later ticks should land in the same bucket.
`(ts / 60s) * 60s` gives a stable grid boundary.

The `Snapshot` grew two new fields:
```cpp
struct Snapshot {
    // ... existing fields ...
    std::vector<data::Candle> recent_candles;     // last N finalized
    const data::Candle* current_candle = nullptr; // in-progress bucket
};
```

`snapshot()` now takes a second arg `last_n_candles` (default 60) so
widgets can bound their pull. TPO widget displays
`snap.recent_candles` + `snap.current_candle` (appended with `*` marker)
in a 7-column OHLCV+Delta+#Trades table, color-coding Delta green/red
by sign.

## 25. Widget refactor — drop widget-side candle reconstruction

Before (TPO widget reconstructed candles every frame from trades):
```cpp
auto snap = m_data->snapshot(256);
std::map<int64_t, data::Candle> byMinute;
for (const auto& t : snap.recent_trades) {
    int64_t minute = t.timestamp / 60000000;
    auto& c = byMinute[minute];
    if (c.open == 0) c.open = t.price;
    // ... rebuild OHLCV per minute from trades every frame ...
}
```

After (pure VIEW of aggregator state):
```cpp
auto snap = m_data->snapshot(1, 60);
candles = std::move(snap.recent_candles);
if (snap.current_candle) candles.push_back(*snap.current_candle);
```

The widget is now a pure VIEW of the aggregator's state. Future
widgets (Volume Profile, Footprint) get candle data for free by
reading `snap.recent_candles`.

## 26. Tests for the new aggregation

`test_integration.cpp` got a 'Test 5: candle aggregation' block with
four sub-checks, all of which must pass before declaring the feature
shipped:

| Check | Asserts |
|---|---|
| Folds in-progress ticks | open=100, high=102, low=100, close=101, volume=6, buy=3, sell=3 after 3 ticks in same minute |
| Bucket boundary finalizes | Tick at next minute pushes prior to m_candles, count goes 0->1 |
| Finalized OHLCV preserved | After boundary, candles[0].close=101, candles[0].volume=6 |
| max_candles pruning | After 11+ minute-boundary crossings, candles().size() == 5 |

Test runner: `cmake --build && ./build/test/test_integration`. Output
should show 4 new checkmark lines for candle aggregation.

## End-to-End After Phase 3

```bash
cd /home/alca/projects/PubBTQuant/btquant_vulkan
bash build.sh          # → [100%] Built target btquant_vulkan + test_integration
./build/test/test_integration    # → 5/5 tests pass (Vulkan + RingBuffer + Data structs + Candle)
python3 scripts/mock_producer.py --interval-ms 100 &
timeout 10 ./build/btquant_vulkan   # → runs 10s without crash, all 5 widgets render
```

## Cross-references

- `references/btquant-vulkan-rebuild-fixes.md` — Phases 1 + 2 (build
  rescue, compute pipeline, live data ingestion).
- `references/render-engine-build-rescue.md` — OLD engine's parallel
  build-fix log.
- `references/btquant-ui-design.md` — design language (Linear Dark +
  Kraken Purple).