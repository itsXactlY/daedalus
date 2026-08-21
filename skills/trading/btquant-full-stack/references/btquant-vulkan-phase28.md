# Phase 28 — pendingDockLayout plumbing for ImGui::DockBuilderLoadNodes

**Status:** shipped 2026-06-20. Commit 478bf08f. 18 commits / 23 widgets / 35 tests.

## What landed

`WindowManager::pendingDockLayout` (public `std::string`) now copies
`snap.dockLayout` inside `applyLayoutSnapshot`. The render path's
`applyInitialDockLayoutIfNeeded()` consumes it on the next dock
reset: if the staged text is non-empty, feed it to
`ImGui::DockBuilderLoadNodes(dockspaceId, text)` and clear the
buffer. When the upstream ImGui dep is upgraded, the one-line
swap restores saved dock splits automatically.

Test 35: 4 invariants covering
1. `applyLayoutSnapshot` stages dock text into `pendingDockLayout`
2. Empty `snap.dockLayout` → empty `pendingDockLayout` (no clobber)
3. Re-applying with new dock text overwrites previous content
4. `applyInitialDockLayoutIfNeeded` preserves `pendingDockLayout`
   while waiting for the dockspace to register (no live ImGui ctx)

## ENVIRONMENT FACT: this ImGui tree does NOT ship DockBuilderLoadNodes

`grep -rn "DockBuilderLoad\|SaveDock" build/_deps/imgui-src/` returns
zero hits. `imgui_internal.h` in the vendored copy lacks the dock
save/load API — those functions are a **docking branch fork** feature
added in a newer ImGui than this tree ships. The "DockBuilder JSON
placeholder text" strings already in `LayoutIO::fromSettings` tests
were a future-proofing stub for exactly this gap.

**Consequence:** when `applyLayoutSnapshot` is called with non-empty
`dockLayout`, the text is logged + queued but the actual split-restore
call is wrapped in a "would call if available" comment. The plumbing
is complete; the upgrade is the trigger.

## PITFALL: defensive `ImGui::GetCurrentContext() == nullptr` guard

Before this phase, calling `WindowManager::applyInitialDockLayoutIfNeeded()`
from a test context (no live ImGui) segfaulted inside
`ImGui::DockBuilderGetNode(0)`. Test 35 step 4 crashed with exit code
139 (`Speicherzugriffsfehler`) on first run.

Fix: add the guard as the FIRST line of `applyInitialDockLayoutIfNeeded`
(after the `m_layoutResetRequested` / `m_layoutApplied` early-outs but
BEFORE any ImGui API call):

```cpp
if (ImGui::GetCurrentContext() == nullptr) return;
```

This pattern generalizes to ANY ImGui-render-path method that tests
also need to invoke for plumbing verification. The defensive cost is
zero in production (the ImGui context is always live when render
runs) and saves the test binary from a SIGSEGV.

**Reusable rule:** any `Widget::render()` or `WindowManager::renderX()`
helper that calls ImGui APIs MUST be safe to invoke from a test
context. Either gate the ImGui calls behind a context check (preferred
— preserves testability) or document the method as "requires live
ImGui context, test only via state inspection" and provide pure-math
or pure-state accessors.

## Pattern: staged resource for lazy upstream-API consumers

When a code path needs to consume an API that doesn't exist in the
current dependency but will exist in a future upgrade, the staging
pattern is:

1. Add a member field of the right type (`std::string`, `std::vector<X>`)
2. Populate it from the user-facing API (e.g. `applyLayoutSnapshot`)
3. Read it in the consumer function with a graceful fallback
   (log + clear + use default path)
4. Document the upgrade-trigger comment inline so the next
   contributor knows exactly where to swap

This pattern keeps the data flow complete today and the upgrade a
mechanical edit tomorrow — no architectural rework when the new
API lands.

## Pattern: public-member test accessors for staged state

`pendingDockLayout` is a **public** std::string member, not a
`m_pendingDockLayout` with getter. Tests assert `wm.pendingDockLayout
== "..."` directly, the same way Test 27 (MiniPriceChart) and
Test 34 (WindowManager show* bools) work. Keeps the test seam
narrow (no extra accessor method) and matches the convention
established in Phase 27.

**Reusable rule:** any state field that tests need to read or set
but production code mutates through a higher-level method should
be a public member, not a private member with getters. The
WindowManager class is exception-heavy on this point — every
show* bool, the heatmapDensity long, and now pendingDockLayout
are public. Future fields (e.g. `m_dockThemeColor`,
`m_userCaption`) should follow the same convention unless they
hold a non-trivial resource (raw pointer, mutex-guarded state).

## Deferred (unchanged, still future ImGui upgrade)

- ImGui::DockBuilderLoadNodes integration — staged, plumbing ready
- ImGui::SaveDockBuilderToText — not yet called from
  `LayoutIO::fromSettings`, so dock text in saved profiles stays
  empty until a capture path is added
- LayoutIO::fromSettings does NOT yet capture actual dock text —
  would call `ImGui::SaveDockBuilderToText(window->DockNode)` when
  the upstream API lands
- WindowManager doesn't auto-restore a layout on startup — user
  has to click Load manually
