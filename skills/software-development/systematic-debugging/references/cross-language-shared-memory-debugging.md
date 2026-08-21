# Cross-Language Shared-Memory Debugging

## When This Applies

You have TWO processes in DIFFERENT languages sharing a memory region:
- Python producer writing to `/dev/shm/foo`
- C++ consumer reading from the same `/dev/shm/foo` via `mmap` + `reinterpret_cast`

Both sides define their own struct layout. **The structs almost never match on the first try.** This reference documents the diagnostic technique that finds the mismatch in 5 minutes instead of 5 hours.

## The Case Study — BTQ_Render_Engine, 2026-06-18

**Symptom:** `OrderbookPanel Auto-selected: UNKNOWN (ID=2965605936)` — garbage symbol ID where a known symbol (1-20) should be. Trade data was fine, orderbook data was garbage.

**Root cause:** C++ `HotOrderbookSnapshot` struct was missing `alignas(64)`. Natural `sizeof` = 6424 bytes, but the Python producer padded each orderbook to 6464 bytes for cache-line alignment. The C++ iterated the ring buffer using `sizeof(HotOrderbookSnapshot)` = 6424 as the implicit stride, so after the first orderbook every read was misaligned.

**Diagnostic chain:**

1. **Check the symptom is real.** Read the SHM directly with Python mmap to see what the producer actually wrote:
   ```python
   import mmap, struct
   with open('/dev/shm/btquant','rb') as f:
       s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
       ob_base = 4096 + 50000*40  # header + trades
       for i in range(10):
           sid = struct.unpack_from('<I', s, ob_base + i*6464 + 16)[0]
           print(f"slot {i}: sid={sid}")  # → all 1-20, perfect
   ```

2. **Compare strides.** Python comment said `alignas(64): 6424 -> 6464`. Python stride = 6464. C++ `sizeof(HotOrderbookSnapshot)` = 6424. **Mismatch.** C++ reads slot N at `base + N*6424`, Python wrote slot N at `base + N*6464` — diverging after slot 0.

3. **Verify the fix.** Added `struct alignas(64) HotOrderbookSnapshot`, rebuilt, re-ran. OrderbookPanel now shows `BTCUSDT (ID=1), ActiveSyms=20`.

**The general rule:** when a C++ consumer reads garbage from a Python-produced SHM, the bug is almost always:
- **Stride mismatch** (Python pads to alignment, C++ doesn't) — most common
- **Field order mismatch** (Python `pack_into` order differs from C++ struct order) — second
- **Endianness** — rare on x86_64 vs x86_64, common on cross-arch
- **Size mismatch** (Python struct omits a field C++ expects) — easy to miss

## The Diagnostic Technique

**Phase 1: Prove the producer is correct.**
Read the SHM directly with a Python script using `struct.unpack_from`. Verify the bytes at the expected offsets are the values the producer code claims to write. If they're wrong, the producer is the bug — don't blame the consumer yet.

**Phase 2: Compare struct layouts side by side.**
For each shared struct, write down:
- Python: `struct.pack_into` format string and field order
- C++: struct member order and types
- Python stride vs C++ `sizeof`
- Python header size vs C++ header size

Anything that doesn't match is a candidate.

**Phase 3: Check alignment explicitly.**
Python comments like `# alignas(64): 6424 -> 6464` or `# cache-line aligned` are load-bearing. The C++ struct must have the matching `alignas(N)` directive, otherwise `sizeof` rounds DOWN to the natural alignment, not UP to the requested alignment.

**Phase 4: Verify end-to-end with a round-trip value.**
Pick a small integer field (symbol_id, sequence number) and verify it's the same value when written by Python and read by C++. If the value is garbage, the offsets don't match. If the value is correct but the application misbehaves, the bug is elsewhere.

## The Cross-Language FFI Checklist

When two languages share memory, ALL of these must match:

| Property | How to verify |
|---|---|
| Field order | Side-by-side comparison of struct definitions |
| Field types (including size) | uint32 vs uint64 is a silent disaster |
| Field offsets (after padding) | `offsetof` in C++, `struct.calcsize` in Python |
| Struct total size | `sizeof` in C++, `struct.Struct.size` in Python |
| Alignment | `alignas(N)` in C++, manual padding in Python |
| Endianness | `<` (little) vs `>` (big) vs `!` (native) |
| Cache-line stride | Python often pads explicitly, C++ needs `alignas(N)` to match |
| Padding bytes at end of struct | Compiler-inserted padding must match Python's explicit zero-padding |

## The One-Liner Diagnostic

```bash
# Replace /dev/shm/Foo with your SHM path, OFFSET/SIZE/COUNT with your struct
python3 -c "
import mmap, struct
with open('/dev/shm/Foo','rb') as f:
    s = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    for i in range(5):
        off = OFFSET + i*STRIDE
        print(f'slot {i}: ' + ', '.join(
            f'{k}={struct.unpack_from(FMT, s, off+O)[0]}'
            for k, FMT, O in FIELDS
        ))
"
```

If the values look sane, the producer is fine and the bug is on the C++ side (usually stride or field order). If the values are garbage, the producer is the bug.

## Prevention: Shared Constants Header

The long-term fix for FFI drift is a SINGLE source of truth for the layout:

```python
# btquant_shm_layout.py — generated from the C++ header
HOTSPINE_HEADER_SIZE = 4096
TRADE_SIZE = 40
OB_SIZE = 6464  # includes 40 bytes cache-line padding
OB_HDR_SIZE = 24
# ...
```

```cpp
// btquant_shm_layout.hpp — the canonical definition
constexpr size_t HOTSPINE_HEADER_SIZE = 4096;
constexpr size_t TRADE_SIZE = 40;
constexpr size_t OB_SIZE = 6464;  // includes 40 bytes cache-line padding
// ...
```

Both languages `include` or `import` the same numbers. No drift possible. Without this, every layout change requires a coordinated update in N languages, and one missed update creates silent data corruption that only end-to-end testing catches.

## What "100% perfect" testing looks like for FFI

If your stack has cross-language shared memory, "100% perfect" verification includes:

1. **Symbol/round-trip check:** a known value written by the producer must be read back identically by the consumer. Garbage values are a stride/offset mismatch.
2. **Count check:** the consumer's `count` of valid records must equal the producer's `count`. Diverging counts mean the consumer is reading the wrong slots.
3. **Zero-warning check:** no `Invalid X data` or `UNKNOWN` warnings in the consumer log. These are the consumer's defensive code catching misaligned reads.
4. **Independent SHM read:** use Python mmap to read the SHM directly and verify the data the producer claims to write is actually there. This catches producer bugs that the consumer's validation misses.

The 100-iteration code review and the openhands smoke test both missed the stride mismatch because neither did an end-to-end symbol_id round-trip. A shared constants header + automated round-trip check would have caught it on the first commit.
