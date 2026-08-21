# ImGui Render Verification Checklist

You can't see the GUI from the terminal. Verify rendering from the log alone. Five checks, in order:

## 1. imgui-error count

```bash
grep -c "imgui-error" /tmp/btq_terminal.log
```

**Target: 0.** If the count is in the dozens, suspect an ImGui ID stack issue. If in the hundreds or thousands, the ID stack is being corrupted every frame — see `pushid-popid-leak-watchlist.md`.

## 2. Panel init messages

```bash
grep -E "Created new|Initialized with|✓ Applied" /tmp/btq_terminal.log | sort -u
```

**Look for:** Each panel in the layout should log its initialization. Missing panels = missing from the layout or failed to create.

## 3. Data flow rate

```bash
grep -E "Trade W=.*Book W=" /tmp/btq_terminal.log | tail -3
```

**Look for:** `Trade W` and `Book W` should increment steadily over time. A flat count = data not flowing. `Trade W=N R=0` on first sync = initial catch-up, then `R=N` once caught up.

## 4. Periodic render messages

```bash
grep "OrderbookPanel\|Rendering" /tmp/btq_terminal.log | tail -5
```

**Look for:** Panels that log per-frame (or per-N-frames) "Rendering" messages. Confirms the main loop is running. If these stop appearing, the render loop has stalled.

## 5. Clean shutdown

```bash
grep "Shutdown complete\|Vulkan.*cleaned" /tmp/btq_terminal.log
```

**Look for:** `Shutdown complete. Goodbye!` and `[VulkanCore] Swapchain resources cleaned up`. A clean shutdown without Vulkan validation errors means the render loop exited gracefully.

## Quick all-in-one check

```bash
echo "WARNINGS: $(grep -cE '\[WARNING\]' log)"
echo "ERRORS: $(grep -cE '\[ERROR\]' log)"
echo "Crashes: $(grep -cE 'fatal|abort|segfault' log)"
echo "imgui-errors: $(grep -c 'imgui-error' log)"
```

All four should be 0 for a healthy run.

## What this checklist does NOT tell you

- Whether panels look correct visually (colors, spacing, font rendering)
- Whether user interactions work (clicking, dragging, keyboard)
- Whether the layout is aesthetically pleasing

These require a human looking at the screen. The checklist confirms the backend is running and not generating errors, which is a necessary but not sufficient condition for correct rendering.
