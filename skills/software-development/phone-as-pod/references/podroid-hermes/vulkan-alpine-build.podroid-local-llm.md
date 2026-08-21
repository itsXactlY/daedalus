# Vulkan build deps for llama.cpp in Alpine (podroid rootfs)

## Symptom
`cmake -DGGML_VULKAN=1 ...` aborts:
```
CMake Error at .../FindPackageHandleStandardArgs.cmake:227 (message):
  Could NOT find Vulkan (missing: Vulkan_LIBRARY glslc) (found version "1.4.321")
Call Stack ... ggml/src/ggml-vulkan/CMakeLists.txt:9 (find_package)
-- Configuring incomplete, errors occurred!
```
Note it FOUND the version (vulkan-headers present) but still needs the LIBRARY (.so symlink) and `glslc`.

## Fix (Alpine apk)
In `build_rootfs_native.sh`, the `apk add` line must include BOTH:
- `vulkan-loader-dev`  → provides `/usr/lib/libvulkan.so` (the dev symlink llama.cpp links against)
- `glslang`            → provides `/usr/bin/glslc` (SPIR-V shader compiler, required by ggml-vulkan)

Minimal working set:
`apk add --no-cache build-base cmake git vulkan-headers vulkan-loader vulkan-loader-dev glslang vulkan-tools linux-headers`

In the slim-down `apk del` keep `vulkan-loader` (runtime lib) but drop the dev bits:
`apk del build-base cmake git vulkan-headers linux-headers vulkan-loader-dev glslang`

## Guard (so a broken rootfs can't ship)
The rootfs script's `set -e` did NOT abort on the failed llama build — it packed a rootfs with no llama-server. Add after the `cmake --build` line:
`test -x /opt/llama.cpp/build/bin/llama-server || { echo "LLAMA BUILD FAILED"; exit 1; }`

## Why each package
- `vulkan-headers`   = C headers only (that's why version was "found").
- `vulkan-loader`   = runtime `libvulkan.so.1` (used at runtime IF the guest exposes Vulkan).
- `vulkan-loader-dev` = the `libvulkan.so` symlink CMake's find_package needs to link.
- `glslang`        = `glslc` to compile GLSL→SPIR-V at build time (embedded in the binary).

## Context
Observed 2026-07-13 on `podroid-hermes/vm-image/build_rootfs_native.sh` during the "local OLMoE (Apache-2.0 MoE) into the Pixel pod" task. The original `apk add` had `vulkan-headers vulkan-loader vulkan-tools` — missing the two dev packages above. Rebuild runs on x86_64 host via podman+qemu-aarch64 (slow).
