# BTQuant Vulkan — Phase 9: In-process MockProducer (standalone binary)

Closes the Phase 8 "Open / next": no more `scripts/mock_producer.py`
dependency. Binary runs out-of-the-box.

## Files

- `src/data/mock_producer.{hpp,cpp}` — C++ port of `scripts/mock_producer.py`.
- `src/main.cpp` (initData, cleanup) — auto-start + auto-stop.
- `test/test_integration.cpp` — Test 9 verifies UQTB header + tick increment.

## Format (must match scripts/mock_producer.py + data_spine.hpp)

```
Header @ 0x0000 (4096 bytes total):
  bytes 0-3   : "UQTB" magic (4 bytes, ASCII)
  bytes 4-5   : version u16 LE (currently 1)
  bytes 6-7   : symbol_count u16 LE (currently 1)
  bytes 8-4095: zero padding

Symbol records @ 0x1000 (128 bytes each):
  bytes 0-7   : bid_price (double LE)
  bytes 8-15  : ask_price (double LE)
  bytes 16-23 : bid_size (double LE)
  bytes 24-31 : ask_size (double LE)
  bytes 32-39 : timestamp (uint64 LE, microseconds since epoch)
  bytes 40-43 : seq (uint32 LE)
  bytes 44-47 : flags (uint32 LE)
  bytes 48-127: zero padding
```

MarketDataProcessor reads via `data_spine.open()` which mmaps the file and
parses the same way. **The producer must write the same byte layout or
MarketDataProcessor will read garbage.**

## MockProducer class

```cpp
class MockProducer {
public:
    explicit MockProducer(std::string hotspinePath = "/dev/shm/btquant_hotspine",
                         std::string symbol = "BTC/USDT",
                         std::string exchange = "binance",
                         double priceStart = 67500.0,
                         uint32_t intervalMs = 100);
    ~MockProducer();

    std::optional<std::string> start();   // spawns thread; opens + truncates shm
    void stop();                          // joins thread; closes fd
    bool running() const;
    uint64_t sequence() const;
    double lastPrice() const;
private:
    bool writeHeader();
    void runLoop();
    // ...
};
```

GBM step in `runLoop()` (matches the Python producer exactly):
```cpp
double dW = noise(rng) * std::sqrt(dtSec);
price = std::max(price * std::exp(kSigma * dW), 1.0);  // kSigma = 0.0002
double spread = kBaseSpread * (1.0 + std::abs(dW) * 50.0);
double bid = price - spread * 0.5;
double ask = price + spread * 0.5;
double bidSize = sizeJitter(rng);  // uniform [0.05, 5.0]
double askSize = sizeJitter(rng);
uint64_t seq = m_seq.fetch_add(1);
uint64_t tsUs = micros_since_epoch();
uint32_t flags = 0;
```

Sleep pattern: `sleep_until(nextTick)` where `nextTick += intervalMs` —
not `sleep(intervalMs)` after writing. Avoids drift over time.

## Auto-start logic (main.cpp initData)

```cpp
void initData() {
    // 1. Decide whether to start the in-process producer.
    const char* demoEnv = std::getenv("BTQUANT_DEMO");
    bool wantDemo = (demoEnv && demoEnv[0] == '1');
    struct stat shmStat{};
    bool shmExists = (::stat("/dev/shm/btquant_hotspine", &shmStat) == 0);

    if (wantDemo || !shmExists) {
        if (auto err = mockProducer.start()) {
            std::fprintf(stderr, "[BTQuant] MockProducer start failed: %s\n",
                         err->c_str());
        }
    }

    // 2. Start MarketDataProcessor regardless — it opens the SHM file
    //    that the mock producer (or an external one) is writing.
    if (auto err = marketData.start("/dev/shm/btquant_hotspine", 16)) {
        std::fprintf(stderr, "[BTQuant] MarketDataProcessor start failed: %s\n",
                     err->c_str());
    }
    windowManager.setMarketData(&marketData);
}
```

**First-writer-wins rule:** if `/dev/shm/btquant_hotspine` already
exists (e.g., `scripts/mock_producer.py` is running), the in-process
producer does NOT start. External Python producer wins. If both want
to write, the last `pwrite` wins per symbol record (128 bytes), but
the seq/timestamp fields will be inconsistent between the two
producers, causing the aggregator's tick count to fluctuate. Don't run
both at once.

`BTQUANT_DEMO=1` forces the in-process producer to start even if the
SHM file exists — useful for CI / hermetic tests where you don't want
to depend on a stale file from a previous run.

`cleanup()` calls `mockProducer.stop()` AFTER `marketData.stop()` so
the consumer (MarketDataProcessor thread) sees EOF / closed fd before
the producer (MockProducer thread) cleans up. Order matters.

## Test 9 (test_integration.cpp)

```cpp
btquant::data::MockProducer mp(tmpFile.string(),
                                "BTC/USDT", "binance",
                                1000.0, 20 /* 20 ms tick */);
mp.start();
std::this_thread::sleep_for(std::chrono::milliseconds(250));  // ~12 ticks
mp.stop();

// Verify header magic.
std::ifstream in(tmpFile, std::ios::binary);
char magic[4] = {};
in.read(magic, 4);
assert(std::memcmp(magic, "UQTB", 4) == 0);

// Verify sequence advanced.
assert(mp.sequence() >= 5);

// Verify file size = 0x1000 header + 1×128B record.
assert(fs::file_size(tmpFile) == 0x1000 + 128);
```

Run: `cmake --build build && timeout 12 ./build/test/test_integration`.
Expected: `✓ MockProducer wrote UQTB header + 13 ticks (file=4224 bytes)`.

## Pitfalls (this phase)

- **`MockProducer::start()` truncates the file with `O_TRUNC`**. If a
  previous run left a stale seq counter in the file, the new run starts
  at seq=0. Downstream code that compares seq against a snapshot from
  the previous run will see "rewind" — fine for MarketDataProcessor's
  aggregator (resets each session), bad for any persistent consumer.
- **The MockProducer thread holds an fd to `/dev/shm/btquant_hotspine`
  for its entire lifetime.** If you `unlink()` the SHM file while the
  producer is running, the file is deleted but the producer's fd
  points to the inode — same zombie-fd failure mode as `python3 producer
  2>&1 | head -10`. Always stop the producer before unlinking.
- **`pwrite` writes at offset 0x1000 + 0*128 = 0x1000** (single-symbol
  layout). Multi-symbol support would need a per-symbol index. Not
  needed for v1.
- **GBM price drift is intentionally unanchored** — over hours of
  running, the price may drift to $0.01 or $1M depending on the random
  walk. Not a bug. For repeatable demos, restart the binary (which
  resets to `priceStart=67500.0`).
- **Do NOT add `std::filesystem::path` storage of the SHM path**. The
  MockProducer writes a magic-numbered binary file, not a generic
  resource — keep it as `std::string` and use C POSIX APIs (open /
  pwrite / close) directly. Adding `std::ofstream` here would force a
  seek-and-write-via-streaming pattern that doesn't match the magic-
  numbered binary header.
- **`/dev/shm` may not be mounted in containers/WSL2.** The producer's
  `open()` will fail with ENOENT. In that case, the binary falls
  through to MarketDataProcessor's synthetic generator (small random
  walk) — the UI shows data, but with much less interesting patterns
  than the GBM producer.

## What this enables

- `./build/btquant_vulkan` works standalone — no Python, no external
  process, no manual setup. New contributors can clone + build + run
  and see live heatmap data immediately.
- CI tests don't need to spawn a separate Python producer. The C++
  test binary uses the same `MockProducer` class to write a known-good
  SHM file, then `MarketDataProcessor` reads it back, then asserts on
  the snapshot contents.
- The binary can be deployed in a Docker container with `/dev/shm`
  mounted (the standard shm mount) and start producing data
  immediately on launch.

## Open / next

- Multi-symbol producer (write 4-8 symbol records in parallel, each
  with its own GBM instance)
- Replace `/dev/shm` with a UNIX domain socket for low-latency
  push (current pwrite is one syscall per tick; a streaming socket
  amortizes)
- Real connector for Hyperliquid / Binance / Coinbase — see
  `hyperliquid-connector-blueprint.md` for the wire-format spec
