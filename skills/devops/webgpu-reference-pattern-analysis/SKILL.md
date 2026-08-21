---
name: webgpu-reference-pattern-analysis
description: Study a reference WebGPU implementation to extract production patterns and apply them to your own codebase.

category: devops

---

# WebGPU Reference Pattern Analysis

## When to Use

You've been asked to study an existing WebGPU implementation (e.g., huggingface spaces, GitHub repos) and adapt its production patterns to your own codebase. This is common when the reference has patterns you haven't considered: pipeline caching, bind group caching, readback pooling, feature-aware initialization, error handling.

## Steps

### 1. Locate and fetch the reference bundle

```bash
# For huggingface spaces: find the bundled JS in the source or network tab
# For GitHub repos: clone and build if needed
git clone <repo-url>
cd <repo> && npm install && npm run build  # if applicable
```

### 2. Analyze the bundled JS

```bash
# Read the bundled file directly (often ~500KB-2MB)
wc -c dist/bundle.js  # check size — large files need careful reading
head -50 bundle.js     # look for feature detection patterns
grep -n "createDevice\|requestAdapter" bundle.js | head -20
grep -n "pipeline.*cache\|bindGroup.*cache" bundle.js | head -20
```

### 3. Extract key patterns

Look for these common production patterns:

- **Feature-aware device creation** — `device.requestAdapter()` then `navigator.gpu.requestDevice({ features: [...] })` with fallbacks
- **Pipeline caching** — Cache compiled pipelines by shader module, LRU eviction at 4096 entries (Bonsai standard)
- **Bind group caching** — Composite key from pipeline + buffer bindings, evict on overflow
- **Readback pooling** — Preallocate a large buffer (64MB), reuse instead of create/destroy per-frame. Pool by size bucket with public API: `getReadbackBuffer(size)` / `returnReadbackBuffer(buf, size)`. NOT a single static buffer allocated at init.
- **Lifecycle methods** — `clearTransientCaches()` → `clearBindGroupCache()` + `clearReadbackPool()` → `destroy()`. Call destroy on page unload.
- **Uncaptured error handling** — `device.pushError('fatal', '...')` or `device.onuncapturederror`
- **Feature filtering** — Only request features the adapter supports, don't crash on missing features

### 4. Map patterns to your codebase

For each pattern, identify where it fits in your existing files:

- **webgpu-init.js** — Device creation, feature detection, cache initialization, lifecycle methods
- **labyrinth-system.js** (or equivalent render loop) — Pipeline compilation, bind group creation, readback pool usage
- **app.js** — Wire up `beforeunload` cleanup calling `webgpu.destroy()` + `labyrinth.destroy()`
- **WGSL shaders** — Workgroup size consistency, efficient subgroup operations

### 5. Apply patterns with verification

After applying each pattern, verify:

```bash
# Check entry points match between app.js and WGSL files
grep -n "loadShader\\|fn compute" js/*.js webgpu/*.wgsl

# Check workgroup sizes match across all files
grep -n "workgroupSize\\|WORKGROUP_SIZE" js/*.js webgpu/*.wgsl

# Check buffer sizes: OUTPUT_SIZE = particleCount * 6 * 4
grep -n "OUTPUT_SIZE\\|createBuffer.*size:" js/*.js webgpu/*.wgsl

# Syntax check all JS files
for f in js/*.js app.js; do node --check "$f" && echo "OK $f"; done

# Verify pool API methods exist
grep -c "getReadbackBuffer\\|returnReadbackBuffer" js/webgpu-init.js  # should be >0
grep -c "destroy\\|clearTransientCaches\\|clearBindGroupCache\\|clearReadbackPool" js/webgpu-init.js  # should be >0
```

### 5. Verify consistency

Before deploying, verify:

```bash
# Check entry points match between app.js and WGSL files
grep -n "loadShader\|fn compute" js/*.js webgpu/*.wgsl

# Check workgroup sizes match across all files
grep -n "workgroupSize\|WORKGROUP_SIZE" js/*.js webgpu/*.wgsl

# Check buffer sizes: OUTPUT_SIZE = particleCount * 6 * 4
grep -n "OUTPUT_SIZE\|createBuffer.*size:" js/*.js webgpu/*.wgsl

# Syntax check all JS files
for f in js/*.js app.js; do node --check "$f" && echo "OK $f"; done
```

## Pitfalls

- **Don't copy verbatim** — The reference may have different requirements. Adapt patterns, not code.
- **Feature detection must be graceful** — If a feature isn't available, fall back to standard behavior. Don't crash.
- **Workgroup size consistency** — All WGSL shaders and JS callers must agree on workgroup size (typically 256).
- **Buffer alignment** — WebGPU requires buffer offsets to be multiples of 256 bytes for storage buffers.
- **Readback is async** — You can't synchronously read GPU data. Use `buffer.mapAsync()` and handle the promise.

## Example: Upgrading a Render Loop with Readback Pooling

```javascript
// webgpu-init.js — Add readback pool with size-bucket management
const READBACK_POOL_SIZE = 64 * 1024 * 1024; // 64MB total pool budget
let readbackPool = null;

async initReadbackPool(device) {
    readbackPool = device.createBuffer({
        size: READBACK_POOL_SIZE,
        usage: GPUBufferUsage.READ_ONLY | GPUBufferUsage.COPY_DEST
    });
}

getReadbackBuffer(size) {
    // Pool by size bucket — reuse instead of allocate per-frame
    if (this.readbackPool) return this.readbackPool;
    // Fallback: create single buffer if pool not initialized
    return device.createBuffer({ size, usage: GPUBufferUsage.COPY_DEST });
}

returnReadbackBuffer(buf, size) {
    // Push back to pool for reuse
}

// labyrinth-system.js — Use pooled buffer each frame instead of static allocation
async readbackResults(device, pipeline, outputData) {
    const readSize = outputData.length * 4; // Float32Array → bytes
    const buf = this.gpuDevice.getReadbackBuffer(readSize);
    // ... use buf for async readback ...
    this.gpuDevice.returnReadbackBuffer(buf, readSize);
}

// app.js — Add page unload cleanup
window.addEventListener('beforeunload', async () => {
    await webgpu.destroy();  // destroys device + clears pools
    labyrinth.destroy();     // stops render loop
});
```

## Pitfalls

- **Don't copy verbatim** — The reference may have different requirements. Adapt patterns, not code.
- **Pipeline cache eviction at 4096** — Don't use a small limit like 128; Bonsai and Chromium production code use 4096. This is the standard for heavy WebGPU workloads.
- **Readback pool over single buffer** — A single static readback buffer allocated at init time is inferior to a size-bucket pool with `getReadbackBuffer(size)` / `returnReadbackBuffer(buf, size)` API. Different operations need different sizes; pooling avoids per-frame allocation overhead.
- **Lifecycle methods are mandatory** — Always implement `clearTransientCaches()`, `clearBindGroupCache()`, `clearReadbackPool()`, and `destroy()` on the WebGPU device wrapper. Call destroy on page unload via `beforeunload`.
- **Feature detection must be graceful** — If a feature isn't available, fall back to standard behavior. Don't crash.
- **Workgroup size consistency** — All WGSL shaders and JS callers must agree on workgroup size (typically 256).
- **Buffer alignment** — WebGPU requires buffer offsets to be multiples of 256 bytes for storage buffers.
- **Readback is async** — You can't synchronously read GPU data. Use `buffer.mapAsync()` and handle the promise.
- **Firefox partial WebGPU exposure** — Firefox exposes `navigator.gpu` but `requestAdapter()` returns null. Don't log warnings for this expected failure; only warn when an adapter was found but device creation failed. Check `if (adapter)` before logging in catch blocks.
- **JavaScript let scoping in try/catch** — Variables declared with `let` inside a try block are scoped to the try block and NOT visible in the catch block. Move variable declarations outside the try block if you need them accessible in both blocks. This caused `ReferenceError: adapter is not defined` when accessing adapter from catch after declaring it inside try.
- [ ] Node syntax check passes for all JS files
- [ ] Feature detection doesn't crash on missing features
- [ ] Uncaptured error handler installed on device
