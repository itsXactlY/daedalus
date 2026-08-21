cmake_minimum_required(VERSION 3.28)
project(NeuralDreamEngine CXX)

# ════════════════════════════════════════════════════════════════════════════
# C++26 — GCC 14+, Clang 18+, MSVC 2024 17.12+
# ════════════════════════════════════════════════════════════════════════════
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Colors
if(CMAKE_CXX_COMPILER_ID IN_LIST GNU Clang AppleClang)
    # GCC/Clang
    set(CMAKE_CXX_FLAGS_INIT "-Wall -Wextra -Wpedantic")
    if(CMAKE_BUILD_TYPE STREQUAL "Release")
        list(APPEND CMAKE_CXX_FLAGS_INIT "-O3 -march=native -fno-exceptions")
    endif()
elseif(MSVC)
    # MSVC: /permissive- for standards conformance
    add_compile_options(/permissive- /W4)
endif()

# ════════════════════════════════════════════════════════════════════════════
# AVX-512F (mandatory — fatal if not available)
# ════════════════════════════════════════════════════════════════════════════
include(CheckCXXSourceCompiles)
check_cxx_source_compiles("
    #include <immintrin.h>
    int main() {
        __m512 v = _mm512_setzero_ps();
        return _mm512_testz_ps(v, v);
    }
" HAVE_AVX512F)
if(NOT HAVE_AVX512F)
    message(FATAL_ERROR
        "AVX-512F not available. This engine requires AVX-512F.\n"
        "  Your CPU: ${CMAKE_SYSTEM_PROCESSOR}\n"
        "  GCC/Clang: use -mavx512f flag\n"
        "  Or compile for a different target machine.")
endif()

# Also check AVX-512 CD (conflict detection for hyper-threading)
check_cxx_source_compiles("
    #include <immintrin.h>
    int main() {
        __m512 v = _mm512_setzero_ps();
        return _mm512_cmpneq_ps_mask(v, v);
    }
" HAVE_AVX512CD)
if(NOT HAVE_AVX512CD)
    message(STATUS "AVX-512CD not available — may impact HT scheduling")
endif()

# ════════════════════════════════════════════════════════════════════════════
# OpenMP (thread pool parallelism)
# ════════════════════════════════════════════════════════════════════════════
find_package(OpenMP)
if(OpenMP_CXX_FOUND)
    list(APPEND CMAKE_CXX_FLAGS_INIT ${OpenMP_CXX_FLAGS})
endif()

# ════════════════════════════════════════════════════════════════════════════
# Link-Time Optimization (cross-TU inlining of SIMD kernels)
# ════════════════════════════════════════════════════════════════════════════
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    include(CheckIPOSupported)
    check_ipo_supported(RESULT LTO_SUPPORTED OUTPUT LTO_ERROR)
    if(LTO_SUPPORTED)
        set(CMAKE_INTERPROCEDURAL_OPTIMIZATION TRUE)
    else()
        message(WARNING "IPO not supported: ${LTO_ERROR}")
    endif()
endif()

# ════════════════════════════════════════════════════════════════════════════
# Sanitizers (Debug only)
# ════════════════════════════════════════════════════════════════════════════
if(CMAKE_BUILD_TYPE STREQUAL "Debug" OR DEFINED ENV{ENABLE_SANITIZERS})
    if(CMAKE_CXX_COMPILER_ID IN_LIST GNU Clang)
        add_compile_options(-fsanitize=address,undefined,leak)
        add_link_options(-fsanitize=address,undefined,leak)
    endif()
endif()

# ════════════════════════════════════════════════════════════════════════════
# Source Files
# ════════════════════════════════════════════════════════════════════════════
set(SOURCES
    src/dream_main.cpp
    src/simd_vector.cpp
    src/csr_graph.cpp
    src/lock_free_ring.cpp
)

set(HEADERS
    include/dream/lock_free_ring.hpp
    include/dream/simd_vector.hpp
    include/dream/csr_graph.hpp
    include/dream/dream_engine.hpp
)

add_library(dream_engine STATIC ${SOURCES} ${HEADERS})

target_include_directories(dream_engine PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(dream_engine PRIVATE
    OpenMP::OpenMP_CXX
    Threads::Threads
)

# ── Inline ASM availability ────────────────────────────────────────────────
target_compile_definitions(dream_engine PRIVATE
    DREAM_ASM_AVAILABLE=$<BOOL:${HAVE_AVX512F}>
)

# ════════════════════════════════════════════════════════════════════════════
# Benchmarks
# ════════════════════════════════════════════════════════════════════════════
add_executable(bench_dream
    benchmarks/bench_dream.cpp
    ${SOURCES}
)
target_link_libraries(bench_dream PRIVATE dream_engine Threads::Threads)
target_compile_definitions(bench_dream PRIVATE DREAM_BENCHMARK)

# ════════════════════════════════════════════════════════════════════════════
# Tests
# ════════════════════════════════════════════════════════════════════════════
find_package(Catch2 QUIET)
if(Catch2_FOUND)
    enable_testing()
    add_executable(test_dream
        tests/dream_test.cpp
        src/simd_vector.cpp
        src/csr_graph.cpp
        src/lock_free_ring.cpp
    )
    target_link_libraries(test_dream PRIVATE Catch2::Catch2 dream_engine)
    target_include_directories(test_dream PRIVATE include)
    include(CTest)
endif()

# ════════════════════════════════════════════════════════════════════════════
# Install
# ════════════════════════════════════════════════════════════════════════════
include(GNUInstallDirs)
install(TARGETS dream_engine
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)
install(DIRECTORY include/dream/
    DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/dream
    FILES_MATCHING PATTERN "*.hpp"
)
