// lock_free_ring.hpp — C++26 Lock-Free MPSC Ring Buffer
// Lock-Free Multi-Producer Single-Consumer ring for dream phase pipelines
// NO locks. NO atomics on the hot path except the single uint64_t head counter.
// Consumer-side: single thread reads, uses acquire/release semantics.
//
// Producers (NREM workers): atomic increment of head, then store slot.
// Consumer (Insight phase): read head with acquire, process slots, release tail with release.

#pragma once
#include <array>
#include <atomic>
#include <bit>        // std::has_single_bit
#include <cassert>
#include <optional>
#include <stop_token>

namespace dream {

template<typename T, size_t Capacity>
    requires std::has_single_bit<Capacity>
class LockFreeRing {
    // Layout: [0..Capacity-1] slots + 2 cache lines for head/tail to avoid false sharing
    static constexpr size_t PADDING = 64 / sizeof(size_t);

    struct alignas(64) PaddedHead {
        std::atomic<uint64_t> value{0};
        char pad[64 - sizeof(std::atomic<uint64_t>)];
    };

    std::array<PaddedHead, 1> head_;  // Only written by CONSUMER (Insight phase)
    alignas(64) std::atomic<uint64_t> tail_{0};  // Written by PRODUCER (NREM workers)

    // Slots: cacheline 0 holds the control word, rest is payload
    struct alignas(64) Slot {
        std::atomic<uint64_t> sequence{0};  // CAS key: even=empty, odd=owned
        T payload;
        char pad[64 - sizeof(std::atomic<uint64_t>)];
    };
    static_assert(sizeof(Slot) == 64, "Slot must be exactly one cache line");

    std::unique_ptr<Slot[]> slots_{new Slot[Capacity]};

    // Init sequences: slot i has initial sequence = i*2 (even = empty)
    static constexpr uint64_t EMPTY_SEQ = 0ULL;
    static constexpr uint64_t FULL_SEQ  = 1ULL;

public:
    static_assert(Capacity >= 2 && Capacity <= (1ULL << 20));

    LockFreeRing() {
        for (size_t i = 0; i < Capacity; ++i) {
            slots_[i].sequence.store(i * 2, std::memory_order_relaxed);
        }
        head_.value.store(0, std::memory_order_relaxed);
        tail_.store(0, std::memory_order_relaxed);
    }

    // ── PRODUCER (NREM workers — called from multiple threads) ──────────────
    // Returns true if enqueued, false if ring is full.
    // Lock-free: only updates tail_. No CAS needed on fast path.
    bool try_push(T&& item) noexcept {
        uint64_t tail = tail_.load(std::memory_order_relaxed);
        Slot& slot = slots_[tail % Capacity];
        uint64_t seq = slot.sequence.load(std::memory_order_acquire);

        // Full? (tail points to slot that consumer hasn't released yet)
        if ((tail - (seq >> 1)) >= Capacity) {
            return false;  // Ring full
        }

        // Take ownership: CAS from (seq) to (seq+1)
        uint64_t desired = seq + 1;
        if (!slot.sequence.compare_exchange_strong(
                seq, desired,
                std::memory_order_acq_rel,
                std::memory_order_acquire)) {
            return false;  // Lost the race, ring full from our perspective
        }

        // Write payload (only we own this slot now)
        slot.payload = std::move(item);

        // Release: mark FULL with seq = tail*2+1
        slot.sequence.store(tail * 2 + 1, std::memory_order_release);
        tail_.fetch_add(1, std::memory_order_relaxed);
        return true;
    }

    // Variadic push for constructing in-place
    template<typename... Args>
    bool try_emplace(Args&&... args) noexcept {
        T item(std::forward<Args>(args)...);
        return try_push(std::move(item));
    }

    // ── CONSUMER (Insight phase — single-threaded) ─────────────────────────
    // Returns nullopt if empty.
    // Single-threaded: no atomics on hot path, just load head and check.
    std::optional<T> try_pop() noexcept {
        uint64_t head = head_.value.load(std::memory_order_acquire);
        Slot& slot = slots_[head % Capacity];
        uint64_t seq = slot.sequence.load(std::memory_order_acquire);

        // Empty?
        if (seq != head * 2 + 1) {
            return std::nullopt;
        }

        // Read payload
        T item = std::move(slot.payload);

        // Mark EMPTY and advance head
        slot.sequence.store((head + 1) * 2, std::memory_order_release);
        head_.value.store(head + 1, std::memory_order_release);
        return item;
    }

    // Drain all available items (for Insight phase processing loop)
    template<typename F>
    size_t drain_into(F&& consumer) noexcept {
        size_t count = 0;
        while (auto item = try_pop()) {
            consumer(std::move(*item));
            ++count;
        }
        return count;
    }

    // ── Diagnostics ─────────────────────────────────────────────────────────
    [[nodiscard]] size_t capacity() const noexcept { return Capacity; }

    // Approximate usage (consumer reads this — may be stale by one producer batch)
    [[nodiscard]] size_t approx_size() const noexcept {
        uint64_t tail = tail_.load(std::memory_order_relaxed);
        uint64_t head = head_.value.load(std::memory_order_acquire);
        return (tail >= head) ? static_cast<size_t>(tail - head) : 0;
    }

    [[nodiscard]] bool is_empty() const noexcept {
        return approx_size() == 0;
    }
};

// ── Spreading Activation Task (NREM → REM) ───────────────────────────────────
struct SpreadingTask {
    uint64_t memory_id;
    float    initial_salience;
    float    threshold;       // Early-exit below this
    uint8_t  max_depth;       // Bounded BFS depth
    uint8_t  padding[6];
};

// ── Edge Result (NREM → REM) ────────────────────────────────────────────────
struct EdgeResult {
    uint64_t src_id;
    uint64_t tgt_id;
    float    weight_delta;
    uint32_t op_type;  // 0=hebbian_strengthen, 1=decay, 2=bridge_new
};

// ── Bridge Candidate (REM → Insight) ─────────────────────────────────────────
struct BridgeCandidate {
    uint64_t isolated_id;
    uint64_t target_id;
    float    similarity;
    uint32_t padding;
};

// ── Community Result (Insight → DB) ─────────────────────────────────────────
struct CommunityResult {
    uint64_t node_id;
    uint32_t community_id;
    float    modularity_gain;
    uint32_t padding;
};

}  // namespace dream
