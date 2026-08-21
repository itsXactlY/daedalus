# BTQuant SHM Layout — Canonical Constants

The Python producer (`mock_data_producer.py`) and the C++ consumer (`HotSpineDataBridge` in `hotspine_data_bridge.cpp`) MUST agree on these constants. Drift causes **silent data corruption** — the consumer doesn't crash, doesn't error, just reads garbage (denormal prices, zero sizes, "Invalid trade data" warnings, or orderbook panels showing UNKNOWN symbols). Compile-clean is necessary but not sufficient; only an end-to-end smoke test catches drift.

## The 8 Constants

These must match EXACTLY across producer and consumer:

| # | Constant | Value | Purpose |
|---|---|---|---|
| 1 | `HEADER_SIZE` | **4096** | Bytes reserved for SHM header (magic, seq numbers, metadata). Cache-line aligned. |
| 2 | `TRADE_SIZE` | 40 | Bytes per trade record |
| 3 | `OB_SIZE` | 6464 | Bytes per orderbook record (`alignas(64): 6424 → 6464`) |
| 4 | `OB_HEADER` | 24 | OB header: `uint64+uint64+uint32+uint8+uint8+uint8[2]` |
| 5 | `OB_DATA` | 6400 | OB price/size data: `200*16 + 200*16` |
| 6 | `OB_PAD` | 40 | OB trailing pad: `6464 - 24 - 6400` |
| 7 | `TRADE_CAP` | 50000 | Max trade slots in ring buffer |
| 8 | `OB_CAP` | 2000 | Max orderbook slots in ring buffer |

`TOTAL_SIZE = HEADER_SIZE + TRADE_CAP * TRADE_SIZE + OB_CAP * OB_SIZE`

`MAGIC = 0x42545155` (BTQU header magic)

## Reference Implementation (Python producer, 2026-06-18 state)

```python
# /home/alca/projects/PubBTQuant/mock_data_producer.py
HEADER_SIZE = 4096  # must match C++ HOTSPINE_HEADER_SIZE in hotspine_data_bridge.cpp
TRADE_SIZE = 40
OB_SIZE = 6464      # alignas(64): 6424 -> 6464
OB_HEADER = 24      # uint64+uint64+uint32+uint8+uint8+uint8[2]
OB_DATA = 6400      # 200*16 + 200*16
OB_PAD = 40         # 6464 - 24 - 6400
TRADE_CAP = 50000
OB_CAP = 2000
TOTAL_SIZE = HEADER_SIZE + TRADE_CAP * TRADE_SIZE + OB_CAP * OB_SIZE
MAGIC = 0x42545155
```

## Symptom → Cause Mapping

Use this table during smoke testing. If you see any of these symptoms, jump to the matching row:

| Symptom (in BTQuantTerminal output or smoke-test log) | Likely cause | Fix |
|---|---|---|
| Trade count > 0 but prices are `2.12e-314` (denormal) or all `0.0`, sizes all `0` | `HEADER_SIZE` mismatch: Python writes trades at smaller offset than C++ reads them, gap is mmap noise | Bump Python `HEADER_SIZE` to match C++ `HOTSPINE_HEADER_SIZE` (production-side is authoritative) |
| Trade count = 0, but consumer log says "HotSpineDataBridge connected to /btquant" cleanly | SHM file missing by name OR producer in zombie FD state (see Producer pipe-break pitfall in SKILL.md) | `lsof /dev/shm/btquant`; if no result, `ls /proc/<producer_pid>/fd/` for `(deleted)` marker → kill + restart producer |
| Consumer connects, reads trades, but **sizes** are all 0 (prices look OK) | `OB_SIZE` mismatch — C++ reads wrong number of bytes per OB; trade region OK because it's before OB | Verify `OB_SIZE`, `OB_HEADER`, `OB_DATA`, `OB_PAD` all match |
| OrderbookPanel auto-selects `UNKNOWN (ID=<large integer>)`; `ActiveSyms` grows unbounded (218 → 378) | **`alignas(64)` missing on `HotOrderbookSnapshot` in C++** — Python writes OB at stride 6464 (with 40 bytes pad), C++ `sizeof(HotOrderbookSnapshot)` = 6424 without `alignas`. After the first OB, C++ reads misaligned slots and gets garbage `symbol_id`s. Trade data is fine because `HotTrade` natural sizeof(40) matches Python's `TRADE_SIZE`. | Add `struct alignas(64) HotOrderbookSnapshot { ... };` in `include/hotspine_data_bridge.hpp`. Python comment on line 12 even says `alignas(64): 6424 → 6464` — C++ was missing the directive. |
| "Invalid trade data" warnings flooding the log, trade count oscillates 0/N/0/N | Producer and consumer racing on `seq` counter due to misalignment | All 8 constants mismatch in some combo — full layout audit required |
| Consumer connects but immediately disconnects, no errors | `MAGIC` mismatch — header validation fails | Verify `MAGIC = 0x42545155` in both files |
| **Widgets render blank or "nothing works" but no errors in log** | ImGui PushID/PopID leak in a panel (e.g. WatchlistPanel). After thousands of leaked PushIDs, ImGui's ID stack is corrupted → all subsequent widget IDs are wrong → widgets either don't render or render in wrong parents | grep the log for `[imgui-error].*Mismatching PushID/PopID` — find the panel, find the missing PopID. One PushID per PushID, always. |

## Recovery Recipe (when drift is detected)

1. **Note both sides' values.** `grep -nE "HEADER_SIZE|HOTSPINE_HEADER_SIZE" mock_data_producer.py hotspine_data_bridge.cpp` (and all 8 constants).
2. **Pick the authoritative side.** C++ consumer (production-side) wins. The producer is dev/test scaffolding.
3. **Update the producer.** Edit `mock_data_producer.py` to match C++ values. For the `alignas(64)` case, update C++ to match Python's intent (the Python comment already documents the expected alignment).
4. **Restart both sides.**
   ```bash
   # Kill producer cleanly
   pkill -9 -f mock_data_producer.py
   # Clear stale SHM
   rm -f /dev/shm/btquant /dev/shm/btquant_symbols.json
   # Restart producer WITHOUT pipe-to-head
   nohup python3 /home/alca/projects/PubBTQuant/mock_data_producer.py > /tmp/btquant-producer.log 2>&1 &
   # Rebuild C++ binary
   cd /home/alca/projects/PubBTQuant/dependencies/BTQ_Render_Engine/build && cmake --build . -j$(nproc)
   ```
5. **Smoke-test end-to-end.** Run BTQuantTerminal, observe trade count > 0, prices in normal range, zero "Invalid trade data" warnings, OrderbookPanel shows a real symbol like `BTCUSDT (ID=1)`.

## Prevention (for the next layout change)

Any future SHM layout change MUST:

1. **Update BOTH producer and consumer in the same commit.** Don't split them across commits — they will drift again.
2. **Generate Python from C++ if possible.** Best: a build-time script that reads C++ constants and writes a `btquant_shm_layout.py`. Acceptable: a hand-maintained shared constants file referenced from both sides.
3. **Add a smoke test that asserts sane data.** Something like:
   ```python
   def test_shm_layout_integrity():
       prices = [read_trade(i).price for i in range(100)]
       assert all(0.001 < p < 1_000_000 for p in prices), f"denormal/zero prices: {prices[:5]}"
       ob_symbol_ids = [read_ob(i).symbol_id for i in range(50)]
       assert all(1 <= sid <= 20 for sid in ob_symbol_ids), f"garbage symbol_ids: {ob_symbol_ids[:5]}"
   ```
   The OB symbol_id check would have caught the `alignas(64)` bug — the 100-iter review and the HEADER_SIZE smoke test both missed it because neither verified `symbol_id` round-tripped correctly.
4. **Document the change.** Add a row to a `CHANGELOG_SHM.md` (create one if it doesn't exist) noting what changed and why.

## History

- **2026-06-18, commit 5d5a4e0a:** `HEADER_SIZE` bumped from 80 → 4096 in `mock_data_producer.py`. Silent corruption had been ongoing (denormal prices for BTC, ETH, SOL, etc. — price=2.12e-314, size=0). Discovered by openhands agent's end-to-end smoke test (39071 trades now flow with zero warnings).

  The drift was originally introduced when the C++ `HotSpineDataBridge` was given a cache-line-aligned 4096-byte header reservation for performance reasons, but the Python producer (a dev scaffold) was never updated. Both files independently defined their `HEADER_SIZE` constant with no shared source of truth.

- **2026-06-18, commit 6e0cf798:** Added `alignas(64)` to C++ `HotOrderbookSnapshot` struct. Python writes orderbooks at stride 6464 (6424 data + 40 bytes 64-byte-alignment pad — see comment on line 12 of `mock_data_producer.py`). Without `alignas(64)`, the C++ `sizeof(HotOrderbookSnapshot)` = 6424, so the ring-buffer stride was 6424 — after the first OB the C++ read misaligned slots. Symptom: OrderbookPanel showed `UNKNOWN (ID=2965605936)` (garbage `symbol_id`), `ActiveSyms` grew unbounded. Trade data was fine because `HotTrade`'s natural sizeof(40) already matches Python's `TRADE_SIZE=40`. With `alignas(64)` on the struct, the C++ rounds sizeof up from 6424 to 6464, matching the Python stride.

  **Both bugs share the same root cause:** no shared header/constants file between Python producer and C++ consumer. The 100-iter code review and the openhands HEADER_SIZE smoke test both missed the OB stride mismatch because neither did an end-to-end `symbol_id` round-trip check.

- **2026-06-18, commit b0171064:** Fixed WatchlistPanel PushID/PopID leak — pre-existing bug, not caused by SHM work. Two `PushID()` calls per row in the watchlist's render loop, only one `PopID()` at end of iteration. Every row leaked 1 ID per frame. After thousands of leaked PushIDs, ImGui's internal ID stack was deeply corrupted — every subsequent widget ID was wrong, so widgets either didn't render or rendered in wrong parents. Symptom looked like "nothing works" but the log gave it away: 4283 `[imgui-error] Mismatching PushID/PopID!` messages. Fix: add the second `PopID()` right before the existing one. One PushID per PushID, always.
