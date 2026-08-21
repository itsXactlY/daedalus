// bench_dream.cpp — Dream Engine Performance Benchmark
// Compile: g++ -std=c++26 -O3 -mavx512f -march=native -flto -fno-exceptions
// Run: ./bench_dream [num_memories] [num_edges] [num_threads]
// Output: CSV of phase timings, memory usage, throughput

#include "dream/dream_engine.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <random>
#include <sstream>
#include <thread>
#include <vector>

using namespace dream;
using namespace std::chrono;

// ── RNG ──────────────────────────────────────────────────────────────────────
static std::mt19937_64 rng(42);

// ── Data Generation ─────────────────────────────────────────────────────────
static std::vector<float> generate_embeddings(size_t count, size_t dim) {
    std::vector<float> embeddings(count * dim);
    std::normal_distribution<float> dist(0.0f, 1.0f / std::sqrt(static_cast<float>(dim)));
    for (auto& x : embeddings) x = dist(rng);
    return embeddings;
}

static std::vector<uint64_t> generate_memory_ids(size_t count) {
    std::vector<uint64_t> ids(count);
    std::iota(ids.begin(), ids.end(), 0);
    std::shuffle(ids.begin(), ids.end(), rng);
    return ids;
}

// Generate a scale-free graph (Barabási–Albert model)
// This mimics real neural memory graphs which are scale-free
static std::vector<std::tuple<uint64_t, uint64_t, float>>
generate_scale_free_edges(size_t num_nodes, size_t target_edges) {
    std::vector<std::tuple<uint64_t, uint64_t, float>> edges;
    edges.reserve(target_edges);

    // Start with a triangle
    edges.push_back({0, 1, 0.5f});
    edges.push_back({1, 2, 0.5f});
    edges.push_back({0, 2, 0.5f});

    std::vector<size_t> degree(num_nodes, 0);
    for (const auto& [s, t, w] : edges) {
        ++degree[s];
        ++degree[t];
    }

    std::vector<float> probs(num_nodes);
    size_t m = 2;  // edges per new node

    for (size_t new_node = 3; new_node < num_nodes && edges.size() < target_edges; ++new_node) {
        float total_deg = 0.0f;
        for (size_t i = 0; i < new_node; ++i) total_deg += static_cast<float>(degree[i]);
        if (total_deg < 1e-6f) total_deg = 1.0f;

        for (size_t i = 0; i < new_node; ++i) probs[i] = static_cast<float>(degree[i]) / total_deg;

        std::vector<size_t> targets;
        std::discrete_distribution<size_t> dist(probs.begin(), probs.begin() + new_node);

        for (size_t j = 0; j < m && edges.size() < target_edges; ++j) {
            size_t target = dist(rng);
            if (target == new_node) continue;
            float weight = 0.3f + 0.4f * std::uniform_real_distribution<float>(rng);
            edges.push_back({new_node, target, weight});
            ++degree[new_node];
            ++degree[target];
        }
    }

    return edges;
}

// ── Memory Usage ─────────────────────────────────────────────────────────────
static size_t get_rss_kb() {
    std::ifstream stm("/proc/self/status");
    std::string line;
    while (std::getline(stm, line)) {
        if (line.compare(0, 6, "VmRSS:") == 0) {
            std::istringstream iss(line.substr(7));
            size_t kb;
            iss >> kb;
            return kb;
        }
    }
    return 0;
}

// ── Benchmark ─────────────────────────────────────────────────────────────────
struct BenchResult {
    double nrem_ms;
    double rem_ms;
    double insight_ms;
    size_t rss_kb;
    uint64_t edges_updated;
    uint64_t bridges_found;
    uint64_t communities;
    double nrem_throughput;  // activations per second
    double rem_throughput;
};

static BenchResult run_benchmark(
    size_t num_memories,
    size_t num_edges,
    size_t embedding_dim,
    size_t num_threads
) {
    DreamConfig cfg{};
    cfg.nrem_workers = static_cast<uint32_t>(num_threads);
    cfg.num_threads  = static_cast<uint32_t>(num_threads);
    cfg.nrem_batch_size = 256;
    cfg.rem_batch_size  = 512;

    DreamEngine engine(cfg, embedding_dim, num_memories * 2);

    // Generate data
    auto edges = generate_scale_free_edges(num_memories, num_edges);
    engine.load_graph(edges, num_memories);

    auto embeddings = generate_embeddings(num_memories, embedding_dim);
    auto ids = generate_memory_ids(num_memories);
    std::vector<float> saliences(num_memories, 1.0f);
    engine.load_memories(ids, embeddings, saliences);

    // Warm-up (OS page cache, CPU frequency scaling)
    engine.run_cycle();

    // Benchmark
    size_t rss_before = get_rss_kb();

    auto start = high_resolution_clock::now();
    auto cycle_result = engine.run_cycle();
    auto end = high_resolution_clock::now();

    size_t rss_after = get_rss_kb();

    double total_ms = duration<double, milli>(end - start).count();

    BenchResult result{};
    result.nrem_ms      = duration<double, milli>(cycle_result.nrem_duration).count();
    result.rem_ms       = duration<double, milli>(cycle_result.rem_duration).count();
    result.insight_ms   = duration<double, milli>(cycle_result.insight_duration).count();
    result.rss_kb       = rss_after - rss_before;
    result.edges_updated = cycle_result.edges_updated;
    result.bridges_found = cycle_result.bridges_found;
    result.communities  = cycle_result.communities;
    result.nrem_throughput = num_memories / (result.nrem_ms / 1000.0);
    result.rem_throughput  = (result.bridges_found > 0)
        ? static_cast<double>(result.bridges_found) / (result.rem_ms / 1000.0)
        : 0.0;

    return result;
}

// ── CSV Output ────────────────────────────────────────────────────────────────
int main(int argc, char** argv) {
    // Default: 100K memories, 500K edges, 16 threads, 1024d
    size_t num_memories = (argc > 1) ? std::atoll(argv[1]) : 100000;
    size_t num_edges    = (argc > 2) ? std::atoll(argv[2]) : 500000;
    size_t num_threads  = (argc > 3) ? std::atoll(argv[3]) : std::thread::hardware_concurrency();
    size_t embedding_dim = 1024;

    std::printf("# Dream Engine Benchmark\n");
    std::printf("# Memories: %zu | Edges: %zu | Dim: %zu | Threads: %zu\n",
                num_memories, num_edges, embedding_dim, num_threads);
    std::printf("# CPU: ");
    std::fflush(stdout);
    std::system("grep 'model name' /proc/cpuinfo | head -1 | sed 's/.*: //'");
    std::printf("# %s", asctime(localtime(nullptr)));
    std::printf("\n");

    std::printf("%-12s %-12s %-12s %-12s %-10s %-12s %-12s %-12s %-12s\n",
        "NREM_ms", "REM_ms", "Insight_ms", "Total_ms",
        "RSS_KB", "Edges", "Bridges", "Communities", "NREM_ops/s");
    std::fflush(stdout);

    auto result = run_benchmark(num_memories, num_edges, embedding_dim, num_threads);

    double total = result.nrem_ms + result.rem_ms + result.insight_ms;
    std::printf("%-12.3f %-12.3f %-12.3f %-12.3f %-10zu %-12llu %-12llu %-12llu %-12.0f\n",
        result.nrem_ms, result.rem_ms, result.insight_ms, total,
        result.rss_kb,
        static_cast<unsigned long long>(result.edges_updated),
        static_cast<unsigned long long>(result.bridges_found),
        static_cast<unsigned long long>(result.communities),
        result.nrem_throughput);

    return 0;
}
