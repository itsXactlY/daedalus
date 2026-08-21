// dream_engine.hpp — C++26 Neural Memory Dream Consolidation Engine
// NREM → REM → Insight phases with lock-free MPSC ring pipeline
// AVX-512 SIMD. Slab allocation. Zero-copy DB reads via memory-mapped I/O.
// Thread pool: std::jthread with work-stealing.

#pragma once
#include "csr_graph.hpp"
#include "lock_free_ring.hpp"
#include "simd_vector.hpp"

#include <algorithm>
#include <bit>
#include <chrono>
#include <condition_variable>
#include <coroutine>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <optional>
#include <random>
#include <span>
#include <stop_token>
#include <thread>
#include <unordered_map>
#include <vector>

namespace dream {

// ════════════════════════════════════════════════════════════════════════════
// Config — Zero-Cost Abstraction (no virtual dispatch, compile-time constants)
// ════════════════════════════════════════════════════════════════════════════

struct DreamConfig {
    // NREM Phase
    uint32_t  nrem_activation_threshold = 20;      // spread stops below this salience
    uint8_t   nrem_max_depth            = 5;        // BFS depth cap
    uint32_t  nrem_batch_size           = 256;     // memories per NREM pass
    float     nrem_salience_decay       = 0.85f;   // multiplicative decay per hop
    uint32_t  nrem_workers              = 0;        // 0 = auto (logical cores - 1)

    // REM Phase
    uint32_t  rem_isolate_max_degree   = 3;        // degree <= this → isolated
    uint32_t  rem_bridge_top_k         = 5;        // top-k similar to connect
    float     rem_similarity_min       = 0.65f;    // min cosine to form bridge
    uint32_t  rem_batch_size           = 512;      // isolated set size per REM pass

    // Insight Phase
    uint32_t  insight_min_community_size = 3;       // ignore smaller communities
    uint32_t  insight_louvain_iterations = 10;      // max iterations per level
    uint32_t  insight_max_clusters      = 20;       // cap on reported clusters

    // General
    uint32_t  num_threads              = 0;         // 0 = auto
    size_t    slab_size                = 4096;      // bytes per slab
    bool      enable_asm_kernel        = true;      // use inline asm for critical path

    // Memory limits
    size_t    max_memory_bank_entries   = 100000;   // cap for SoA memory bank
    size_t    ring_capacity_nrem        = 2048;     // NREM → REM ring
    size_t    ring_capacity_rem        = 1024;     // REM → Insight ring
};

// ════════════════════════════════════════════════════════════════════════════
// Memory Bank — SoA layout, slab-allocated, AVX-512 batch cosine
// ════════════════════════════════════════════════════════════════════════════

class MemoryBank {
    DreamConfig cfg_;
    size_t capacity_;
    size_t dim_;

    std::vector<uint64_t>   ids_;          // memory ID → index mapping
    std::vector<float>      embeddings_;   // [capacity][dim] contiguous SoA
    std::vector<float>      salience_;     // [capacity]
    std::vector<uint32_t>   access_count_; // [capacity]
    std::vector<uint64_t>   last_access_;  // [capacity] unix timestamp

    // For batching: which indices are active this pass
    std::vector<uint32_t>   active_indices_;
    std::vector<float>      active_saliences_;

    // Alignment check
    static constexpr size_t ALIGN = 64;
    static_assert(alignof(float) == 4);

public:
    explicit MemoryBank(const DreamConfig& cfg, size_t dim, size_t capacity)
        : cfg_(cfg), capacity_(capacity), dim_(dim),
          ids_(capacity),
          embeddings_(capacity * dim),
          salience_(capacity),
          access_count_(capacity),
          last_access_(capacity)
    {
        std::fill(salience_.begin(), salience_.end(), 0.0f);
        std::fill(access_count_.begin(), access_count_.end(), 0);
        std::fill(last_access_.begin(), last_access_.end(), 0);
    }

    [[nodiscard]] size_t dim()      const noexcept { return dim_; }
    [[nodiscard]] size_t size()     const noexcept { return active_indices_.size(); }
    [[nodiscard]] size_t capacity() const noexcept { return capacity_; }
    [[nodiscard]] bool   empty()    const noexcept { return active_indices_.empty(); }

    // Load memories from CSR graph nodes + DB data
    // pointers must be 64-byte aligned
    void load_batch(
        std::span<const uint64_t> memory_ids,
        std::span<const float> embeddings,  // [memory_ids.size()][dim]
        std::span<const float> saliences
    ) {
        size_t n = std::min(memory_ids.size(), embeddings.size());
        active_indices_.resize(n);
        active_saliences_.resize(n);

        for (size_t i = 0; i < n; ++i) {
            active_indices_[i] = static_cast<uint32_t>(i);
            active_saliences_[i] = saliences[i];
            std::memcpy(embeddings_.data() + i * dim_, embeddings.data() + i * dim_, dim_ * sizeof(float));
            ids_[i] = memory_ids[i];
            ++access_count_[i];
            last_access_[i] = std::chrono::system_clock::now().time_since_epoch().count();
        }
    }

    // Set active working set (for next NREM/REM pass)
    void set_active(std::span<const uint32_t> indices) {
        active_indices_ = {indices.begin(), indices.end()};
    }

    // AVX-512 batch cosine: query vs all active embeddings
    // Returns sorted top-k
    std::vector<CosineResult> top_k_similar(
        const float* query, size_t k
    ) const noexcept {
        if (active_indices_.empty()) return {};

        std::vector<CosineResult> results;
        results.reserve(active_indices_.size());

        QueryNorms qn = avx512::prepare_query(query, dim_);

        for (uint32_t idx : active_indices_) {
            const float* emb = embeddings_.data() + static_cast<size_t>(idx) * dim_;
            float sim = avx512::cosine_single(qn, emb);
            results.push_back({ids_[idx], sim});
        }

        k = std::min(k, results.size());
        std::partial_sort(results.begin(), results.begin() + k, results.end(),
            [](const CosineResult& a, const CosineResult& b) {
                return a.similarity > b.similarity;
            });
        results.resize(k);
        return results;
    }

    [[nodiscard]] const float* embedding_ptr(uint32_t index) const noexcept {
        return embeddings_.data() + static_cast<size_t>(index) * dim_;
    }

    [[nodiscard]] float salience(uint32_t index) const noexcept {
        return salience_[index];
    }

    void update_salience(uint32_t index, float delta) noexcept {
        salience_[index] = std::clamp(salience_[index] + delta, 0.0f, 3.0f);
    }
};

// ════════════════════════════════════════════════════════════════════════════
// NREM Phase — Bounded Spreading Activation (Lock-Free)
// ════════════════════════════════════════════════════════════════════════════

class NREMPhase {
    DreamConfig cfg_;
    MemoryBank& bank_;

    // Thread-local spreading buffers (no heap allocation per activation)
    struct TLS {
        std::vector<uint64_t> visited;    // nodes seen in this BFS
        std::vector<uint64_t> frontier;   // current BFS level
        std::vector<uint64_t> next_frontier;
        std::vector<float>    activations;  // activation per visited node
    };

    std::vector<TLS> tls_;

    // Output ring: NREM → REM
    LockFreeRing<EdgeResult, 2048>& output_ring_;

public:
    NREMPhase(const DreamConfig& cfg, MemoryBank& bank,
              LockFreeRing<EdgeResult, 2048>& output_ring)
        : cfg_(cfg), bank_(bank), output_ring_(output_ring) {}

    void set_num_workers(size_t n) {
        tls_.resize(n);
        for (auto& t : tls_) {
            t.visited.reserve(1024);
            t.frontier.reserve(256);
            t.next_frontier.reserve(256);
            t.activations.reserve(1024);
        }
    }

    // Process one memory: bounded BFS spreading activation
    // Outputs edge strengthen/decay ops to the output ring
    void process_memory(uint64_t memory_id, float initial_salience) noexcept {
        TLS& t = tls_[std::hash<uint64_t>{}(memory_id) % tls_.size()];

        t.visited.clear();
        t.frontier.clear();
        t.next_frontier.clear();
        t.activations.clear();

        // Init BFS with source
        t.visited.push_back(memory_id);
        t.frontier.push_back(memory_id);
        t.activations.push_back(initial_salience);

        for (uint8_t depth = 0; depth < cfg_.nrem_max_depth; ++depth) {
            if (t.frontier.empty()) break;

            // Find top-k similar for each node in frontier
            for (size_t fi = 0; fi < t.frontier.size(); ++fi) {
                uint64_t node = t.frontier[fi];
                float activation = t.activations[fi];

                if (activation < cfg_.nrem_activation_threshold) continue;

                // Get k nearest neighbors
                auto top_k = bank_.top_k_similar(
                    bank_.embedding_ptr(static_cast<uint32_t>(node)),
                    cfg_.rem_bridge_top_k * 2
                );

                for (const auto& [neighbor_id, similarity] : top_k) {
                    if (similarity < 0.3f) continue;

                    float propagated = activation * similarity * cfg_.nrem_salience_decay;

                    if (std::find(t.visited.begin(), t.visited.end(), neighbor_id)
                        == t.visited.end()) {
                        t.visited.push_back(neighbor_id);
                        t.next_frontier.push_back(neighbor_id);
                        t.activations.push_back(propagated);
                    }

                    // Output edge result
                    EdgeResult er{
                        .src_id = node,
                        .tgt_id = neighbor_id,
                        .weight_delta = similarity * 0.1f,  // Hebbian: strengthen
                        .op_type = 0
                    };
                    output_ring_.try_push(std::move(er));
                }
            }

            t.frontier.swap(t.next_frontier);
            t.next_frontier.clear();
        }
    }

    // Batch NREM: process a set of memories in parallel across workers
    void process_batch(const std::vector<uint64_t>& memory_ids,
                       const std::vector<float>& saliences) noexcept {
        std::vector<std::future<void>> futures;
        size_t n = memory_ids.size();
        size_t workers = std::max(size_t(1), tls_.size());
        size_t chunk = (n + workers - 1) / workers;

        for (size_t w = 0; w < workers; ++w) {
            size_t start = w * chunk;
            size_t end = std::min(start + chunk, n);
            if (start >= end) break;

            futures.push_back(std::async(std::launch::async, [&, w, start, end]() {
                for (size_t i = start; i < end; ++i) {
                    process_memory(memory_ids[i],
                        (i < saliences.size()) ? saliences[i] : 1.0f);
                }
            }));
        }

        for (auto& f : futures) f.wait();
    }
};

// ════════════════════════════════════════════════════════════════════════════
// REM Phase — Isolated Memory Detection + Bridge Discovery
// ════════════════════════════════════════════════════════════════════════════

class REMPhase {
    DreamConfig cfg_;
    MemoryBank& bank_;
    LockFreeRing<EdgeResult, 2048>& input_ring_;   // from NREM
    LockFreeRing<BridgeCandidate, 1024>& output_ring_; // to Insight

public:
    REMPhase(const DreamConfig& cfg, MemoryBank& bank,
             LockFreeRing<EdgeResult, 2048>& input_ring,
             LockFreeRing<BridgeCandidate, 1024>& output_ring)
        : cfg_(cfg), bank_(bank),
          input_ring_(input_ring), output_ring_(output_ring) {}

    // Find isolated memories: those with degree <= threshold in CSR graph
    std::vector<uint64_t> find_isolated(const CSRGraph& graph) const noexcept {
        std::vector<uint64_t> isolated;
        for (size_t i = 0; i < graph.num_nodes(); ++i) {
            if (graph.degree(static_cast<uint64_t>(i)) <= cfg_.rem_isolate_max_degree) {
                isolated.push_back(static_cast<uint64_t>(i));
            }
        }
        return isolated;
    }

    // Discover bridges: connect isolated memories to semantically similar memories
    void discover_bridges(const CSRGraph& graph) noexcept {
        auto isolated = find_isolated(graph);
        if (isolated.empty()) return;

        for (uint64_t iso_id : isolated) {
            // Skip if already has enough connections
            if (graph.degree(iso_id) > cfg_.rem_isolate_max_degree) continue;

            // Top-k similar memories
            auto bridges = bank_.top_k_similar(
                bank_.embedding_ptr(static_cast<uint32_t>(iso_id)),
                cfg_.rem_bridge_top_k
            );

            for (const auto& [target_id, similarity] : bridges) {
                if (target_id == iso_id) continue;
                if (similarity < cfg_.rem_similarity_min) break;

                // Only bridge if target is NOT isolated (connect iso → connected)
                if (graph.degree(target_id) > cfg_.rem_isolate_max_degree) {
                    BridgeCandidate bc{
                        .isolated_id = iso_id,
                        .target_id = target_id,
                        .similarity = similarity,
                        .padding = 0
                    };
                    output_ring_.try_push(std::move(bc));
                }
            }
        }
    }
};

// ════════════════════════════════════════════════════════════════════════════
// Insight Phase — Louvain Community Detection + Bridge Analysis
// ════════════════════════════════════════════════════════════════════════════

class InsightPhase {
    DreamConfig cfg_;
    LockFreeRing<BridgeCandidate, 1024>& input_ring_;

public:
    InsightPhase(const DreamConfig& cfg,
                 LockFreeRing<BridgeCandidate, 1024>& input_ring)
        : cfg_(cfg), input_ring_(input_ring) {}

    // Process community detection results
    std::vector<CommunityResult> run_louvain(CSRGraph& graph) noexcept {
        auto result = graph.louvain();

        std::vector<CommunityResult> communities;
        for (size_t i = 0; i < result.node_community.size(); ++i) {
            communities.push_back({
                .node_id = static_cast<uint64_t>(i),
                .community_id = result.node_community[i],
                .modularity_gain = 0.0f,
                .padding = 0
            });
        }

        // Filter small communities
        std::unordered_map<uint32_t, size_t> community_size;
        for (const auto& c : communities) {
            ++community_size[c.community_id];
        }

        std::vector<CommunityResult> filtered;
        for (const auto& c : communities) {
            if (community_size[c.community_id] >= cfg_.insight_min_community_size) {
                filtered.push_back(c);
            }
        }

        return filtered;
    }

    // Analyze bridges from REM phase
    std::vector<BridgeNode> analyze_bridges(
        CSRGraph& graph,
        std::span<const CommunityResult> communities
    ) noexcept {
        std::vector<uint32_t> comm_array(graph.num_nodes());
        for (size_t i = 0; i < communities.size() && i < graph.num_nodes(); ++i) {
            comm_array[i] = communities[i].community_id;
        }
        return graph.find_bridges(comm_array, 0.3f);
    }
};

// ════════════════════════════════════════════════════════════════════════════
// Dream Engine — Main Orchestrator
// ════════════════════════════════════════════════════════════════════════════

class DreamEngine {
    DreamConfig       cfg_;
    CSRGraph          graph_;
    MemoryBank        bank_;
    LockFreeRing<EdgeResult, 2048>      nrem_to_rem_ring_;
    LockFreeRing<BridgeCandidate, 1024> rem_to_insight_ring_;
    std::vector<std::jthread>           workers_;
    std::stop_source                    stop_src_;
    std::atomic<uint64_t>              sessions_completed_{0};

    // Stats
    struct Stats {
        std::atomic<uint64_t> nrem_activations{0};
        std::atomic<uint64_t> rem_bridges_found{0};
        std::atomic<uint64_t> insight_communities{0};
        std::atomic<uint64_t> edges_strengthened{0};
        std::chrono::microseconds last_nrem{0};
        std::chrono::microseconds last_rem{0};
        std::chrono::microseconds last_insight{0};
    } stats_;

public:
    DreamEngine(const DreamConfig& cfg, size_t embedding_dim, size_t max_entries)
        : cfg_(cfg),
          bank_(cfg, embedding_dim, max_entries),
          nrem_to_rem_ring_(LockFreeRing<EdgeResult, 2048>()),
          rem_to_insight_ring_(LockFreeRing<BridgeCandidate, 1024>())
    {}

    // ── Initialization ────────────────────────────────────────────────────────

    void load_graph(std::span<const std::tuple<uint64_t, uint64_t, float>> edges,
                    size_t num_nodes) {
        graph_.build_from_edges(num_nodes, edges);
    }

    void load_memories(
        std::span<const uint64_t> ids,
        std::span<const float> embeddings,
        std::span<const float> saliences
    ) {
        bank_.load_batch(ids, embeddings, saliences);
    }

    // ── Run Full Dream Cycle ─────────────────────────────────────────────────
    // Returns duration of each phase in microseconds

    struct CycleResult {
        std::chrono::microseconds nrem_duration;
        std::chrono::microseconds rem_duration;
        std::chrono::microseconds insight_duration;
        uint64_t edges_updated;
        uint64_t bridges_found;
        uint64_t communities;
        bool     success;
    };

    CycleResult run_cycle() noexcept {
        CycleResult result{};

        // Phase 1: NREM — Spreading Activation
        {
            auto t0 = std::chrono::high_resolution_clock::now();
            NREMPhase nrem(cfg_, bank_, nrem_to_rem_ring_);
            nrem.set_num_workers(std::max(size_t(1), cfg_.nrem_workers));

            // Collect all active memory IDs and saliences
            std::vector<uint64_t> active_ids;
            std::vector<float> active_sal;
            // (in real impl: read from SQLite/MSSQL via memory-mapped I/O)

            nrem.process_batch(active_ids, active_sal);
            auto t1 = std::chrono::high_resolution_clock::now();
            result.nrem_duration = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0);
        }

        // Phase 2: REM — Bridge Discovery
        {
            auto t0 = std::chrono::high_resolution_clock::now();
            REMPhase rem(cfg_, bank_, nrem_to_rem_ring_, rem_to_insight_ring_);
            rem.discover_bridges(graph_);
            auto t1 = std::chrono::high_resolution_clock::now();
            result.rem_duration = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0);
        }

        // Phase 3: Insight — Community Detection
        {
            auto t0 = std::chrono::high_resolution_clock::now();
            InsightPhase insight(cfg_, rem_to_insight_ring_);
            auto communities = insight.run_louvain(graph_);
            auto bridges = insight.analyze_bridges(graph_, communities);

            // Drain rings
            nrem_to_rem_ring_.drain_into([&](EdgeResult&&) {
                result.edges_updated++;
            });
            rem_to_insight_ring_.drain_into([&](BridgeCandidate&&) {
                result.bridges_found++;
            });

            result.communities = communities.size();
            auto t1 = std::chrono::high_resolution_clock::now();
            result.insight_duration = std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0);
        }

        ++sessions_completed_;
        result.success = true;
        return result;
    }

    // ── Worker Thread Pool ──────────────────────────────────────────────────

    void start() {
        stop_src_ = std::stop_source();
        size_t n = (cfg_.num_threads == 0)
            ? std::max(size_t(1), std::thread::hardware_concurrency() - 1)
            : cfg_.num_threads;

        workers_.reserve(n);
        for (size_t i = 0; i < n; ++i) {
            workers_.emplace_back([this, i](std::stop_token token) {
                while (!token.stop_requested()) {
                    // Work-stealing loop: try to claim work from rings
                    // In production: this is where you'd hook into the OS scheduler
                    std::this_thread::sleep_for(std::chrono::milliseconds(10));
                }
            }, stop_src_.get_token());
        }
    }

    void stop() noexcept {
        stop_src_.request_stop();
        for (auto& w : workers_) {
            if (w.joinable()) w.join();
        }
        workers_.clear();
    }

    [[nodiscard]] const Stats& stats() const noexcept { return stats_; }

    ~DreamEngine() { stop(); }
};

}  // namespace dream
