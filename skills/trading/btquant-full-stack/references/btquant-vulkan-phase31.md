# Phase 31 — Hotkey-driven layout switching (Ctrl+1..Ctrl+9)

**Status:** shipped 2026-06-20. Commit af326a52. 21 commits / 23 widgets / 38 tests.

## What landed

Nine new `HotkeyAction` values (`SwitchLayout1`..`SwitchLayout9`, enum
ordinals 22..30, `COUNT` bumped from 22 to 31) plus default bindings
`Ctrl+1`..`Ctrl+9`. `WindowManager::dispatchAction` routes each to a
new `loadLayoutByIndex(N-1)` helper, which picks the Nth `.btqlayout`
file from `LayoutIO::list()` (sorted alphabetically) and applies it
via the existing `loadLayout(name)` pipeline (Phase 27).

**New public method on WindowManager:**
```cpp
bool loadLayoutByIndex(size_t index);
```
- Returns `false` + logs `BTQ_LOG_WARN` when `index >= profiles.size()`.
- Returns `true` after `loadLayout(profiles[index].stem().string())`.

**New default bindings (in `HotkeyMap::defaults()`):**
```cpp
m.set(HotkeyAction::SwitchLayout1, { GLFW_KEY_1, true, false });
m.set(HotkeyAction::SwitchLayout2, { GLFW_KEY_2, true, false });
... // 3..9 same shape
```
And matching `case HotkeyAction::SwitchLayoutN: return "SwitchLayoutN";`
in `actionName()` so the hotkey help overlay shows the new keys.

Test 38: 6 invariants covering all-9-actions-registered,
Ctrl+1/Ctrl+9 binding shape, `match()` routes keys to actions,
`actionName()` round-trip, out-of-range index no-op with empty HOME,
huge index no-op. 6/6 green.

## PITFALL: enum ordinal break when adding new values mid-range

Adding 9 values after `ToggleHotkeyEditor=21` shifts `COUNT` from 22
to 31. Anything that **persisted the enum value as an integer** (e.g.
the `prevAction[COUNT]` debounce array in
`WindowManager::processHotkeys`) must be re-sized or it indexes out
of bounds. The fix is mechanical: change `prevAction[COUNT]` to use
the new `COUNT` value, OR switch to `std::vector<bool>` sized from
the enum.

In Phase 31 the `prevAction[]` is sized from `HotkeyAction::COUNT`
directly (no hardcoded `22`), so the bump is transparent. **Always
size enum-keyed arrays from the enum**, never from a literal. The
template was set up correctly in Phase 23; Phase 31 just exercised
the contract.

## PATTERN: N parallel enum values for N-tuple configurable actions

When adding 1..N configurable actions (here N=9 for layout slots),
the canonical pattern is:

1. **One row per enum value** in `HotkeyMap::defaults()` — explicit,
   not a loop. Each binding is greppable + self-documenting.
2. **One row per enum value** in `actionName()` — explicit, not a
   loop. Same rationale.
3. **One case per enum value** in `dispatchAction()` — explicit, not
   a loop. Forces you to handle each action individually; missing a
   case is a compiler warning (unhandled enum value).
4. **Single shared helper** that all N cases call into:
   `loadLayoutByIndex(N-1)`. The helper is the one place where the
   "what does N mean" logic lives; the cases are dumb dispatchers.

This pattern generalizes to ANY user-mappable action with a small N
(say 1..16): color slots, audio channels, monitor outputs, account
IDs. Avoid `for (int i = 0; i < N; ++i) bind(i, key+i)` loops because
they hide the dispatch surface from `grep`.

## PATTERN: out-of-range as a clean no-op

`loadLayoutByIndex(9999)` when only 3 profiles exist returns `false`
+ logs a warning. It does NOT crash, does NOT fall back to "apply
profile 0" (which would silently change user state), does NOT pop an
error dialog. The "safe no-op" choice respects the user's context:
they probably hit Ctrl+9 by accident or are partway through saving a
new profile.

**Reusable rule:** any `byIndex` / `byOrdinal` / `byKey` helper in
this codebase must treat out-of-range as a clean no-op. The user can
recover (click the menu instead, count profiles, etc.) — the program
must not crash and must not silently apply the wrong resource.

## PITFALL: `getpid()` not in global namespace (carry-forward from Phase 18)

Test 38 step 5 uses `std::to_string(::getpid())` to build a unique
tmp dir path. `getpid()` is declared in `<unistd.h>`. Without that
include, clang fires "No member named 'getpid' in the global
namespace; did you mean 'getpt'?". Phase 18 noted the same pitfall
and recommended `std::to_string(static_cast<long>(::time(nullptr)))`
as an alternative when `<unistd.h>` is awkward. Phase 31 uses the
explicit `<unistd.h>` include because the test file already includes
several POSIX headers and the include is well-justified.

**Reusable rule:** if you need a tmp-dir-uniquifier in a test and the
file already includes `<unistd.h>` (or any POSIX header that
transitively pulls it in), use `getpid()`. Otherwise fall back to
`time(nullptr)`. Both are sufficient for cross-run uniqueness.

## How this fits with prior phases

- **Phase 27** (`applyLayoutSnapshot` + `saveLayoutAs`/`loadLayout`)
  — this phase adds the `loadLayoutByIndex` wrapper that dispatches
  over the sorted profile list.
- **Phase 23** (unified `dispatchAction`) — this phase extends the
  switch with 9 more cases, no architectural change. Confirms the
  "data → dispatch → side-effect" three-layer pattern scales.
- **Phase 21** (HotkeyMap data layer + F-key table refactor) — the
  default-bindings list in this phase is a 1:1 copy of the existing
  F2-F12 shape. Ctrl+1..Ctrl+9 slots into the same `HotkeyMap::defaults()`
  table without disturbing the F-key table.
- **Phase 22** (HotkeyEditor modal) — Ctrl+1..Ctrl+9 are visible in
  the hotkey editor with labels `"Ctrl+1"` etc., user can rebind
  them like any other action.

## Deferred (unchanged)

- Per-profile risk config visibility in the SwitchLayout hotkey help
  row — currently just shows "Switch to profile Nth". Could show
  the actual profile name once profile names are sorted.
- Cycle behavior on the same key — pressing Ctrl+1 twice rapidly
  re-applies the same profile (no-op). A "round-robin" mode would
  cycle through profiles in order, but that's a UX change, not just
  a hotkey wiring.
