# BTQuant Sprint Workflow — Operator-Facing Rules

This file captures the operator-iteration patterns extracted from 50+ sprint sessions on the BTQuant Vulkan UI codebase. Read this when starting a new BTQuant sprint, after a WEITER signal, or when a sprint is failing.

## ⚠️ The WEITER Rule — ABSOLUTE HARD STOP

The operator issues "WEITER" (German: "keep going") or variants like:
- "WEITER"
- "FRAG NICHT IMMER SO BEHINDERT: WEITER!" (stop asking so retarded, keep going)
- "weiter"
- "stop asking, just keep going"

**Treat this as a HARD STOP on pick-list offers. Execute autonomously.**

### ❌ NEVER DO
- End a sprint with "WEITER — pick: A, B, C, D, or your pick" — this triggers user frustration
- Ask "should I do X next or Y next?" after completing work
- Surface a 4+ item menu of options when the operator says WEITER
- Use phrases like "pick the next direction" or "what would you like"

### ✅ ALWAYS DO
- Pick the single next logical step yourself (the one with clearest extension of current work)
- Execute it fully: read code, write code, build, test, commit, save to memory
- Report what shipped with commit hash + test count + commit number
- Repeat without asking

### Why this is hard rule
The operator uses WEITER as the primary steering signal during deep-focus sprints. Each time you respond with "WEITER — pick:" you force the operator to context-switch out of their flow to read your menu, evaluate options, and respond. Over a 20-sprint session this adds minutes of friction per sprint. The rule "PICK+SHIP" is in the SKILL.md description for a reason — read it before every sprint end.

### Anti-pattern signature
If your output ends with the literal phrase "WEITER — pick:" or similar, STOP and rewrite. Pick and ship.

### Recovery
If you catch yourself offering a pick-list after a WEITER, immediately say "Picking X — executing" and proceed without waiting.

---

## Sprint Pattern (testable, small, test+commit each)

Each feature sprint follows the same shape:

1. **Read** the relevant .hpp/.cpp/.h/.cpp files to understand current state
2. **Identify** the testable extension (prefer pure functions over ImGui state when possible)
3. **Patch** .hpp + .cpp in one logical change
4. **Build** with `cmake --build build -j$(nproc)` — fix any compile error before adding test
5. **Append** `Test N: <ClassName> — <feature>` block at end of main() in test/test_integration.cpp
6. **Test** must have 5-10 checks, each with `✓` or `✗` prefix on stdout
7. **Run** `build/test/test_integration 2>&1 | grep -c "^✓"` to get total check count
8. **Commit** with `git add <explicit paths>` (NEVER `git add -A`) + message format:
   ```
   feat: <short>

   <body explaining what+why+how>

   <N> ✓ total across <N> tests, 0 failures. <M> widgets, <commit count> commits.
   ```
9. **Save** to mazemaker with `mcp__mazemaker__mazemaker_remember` (id stored in response)

---

## Testable Patterns (make tests work without ImGui context)

The test binary in `test/test_integration.cpp` does NOT have an `ImGui::CreateContext()` call. So any UI feature that exercises ImGui state can't be tested directly. Workarounds:

### Pure helper extraction
If a feature has a logic core (e.g. "should this submit flip side?"), extract it as `static bool pureFunc(args)` in the header. Render path calls the pure function. Tests call the pure function directly.

Examples:
- `OrderTicket::effectiveSideOnSubmit(currentSideIsBuy, altDown)` — pure ternary, fully testable
- `ConnectionPanel::computeState(data)` — pure path-check, fully testable
- `ThemeEditor::equals(snap1, snap2)` — pure comparison, fully testable

### Lazy capture with context guard
For features that snapshot state on `setOpen(true)` (e.g. ThemeEditor), defer capture to first `render()` frame, guarded by `if (ImGui::GetCurrentContext() != nullptr)`. Tests verify the guard returns early / no-crash without context.

```cpp
// ThemeEditor::render() — first-frame lazy capture
if (!m_captured && ImGui::GetCurrentContext() != nullptr) {
    m_openingSnapshot = capture(ImGui::GetStyle());
    m_captured = true;
}
```

### Constructor defaults match expected behavior
When adding a new flag with default=true (or any value), set the constructor initializer such that a fresh instance is in a known state. Tests check `if (instance.flag() == expected)` against the constructor default. Example: `m_lastAppliedKillUSD = 5000.0` so a fresh panel with default buffer reads as clean.

---

## State-Mutation Patterns (for transient UI state)

### Save/restore for one-shot mutations
When a UI feature needs to temporarily mutate state (e.g. OrderTicket alt-submit flips side then submits then restores), use the pattern:
```cpp
bool orig = m_state;
m_state = !m_state;
doStuff();
m_state = orig;
```
Tests verify state is restored after the operation.

### Compare against defaults for diff UI
Hotkey help overlay shows "(was: F2)" for remapped bindings by calling `HotkeyMap::defaults()` once and comparing `current != defaults.get(a)`. Tests construct a map, set a different binding, verify the inequality.

### On-disk format compatibility
When extending an enum/struct with a new field (e.g. HotkeyBinding added `alt` field), use brace-init with 4 fields going forward and keep 3-field brace-init valid via default-initialized new field. Tests verify legacy "Ctrl+K" strings still load with new field = false.

---

## Pitfalls

### `git add -A` in PubBTQuant/ — ALMOST COMMITTED AGENCY DATA
The parent directory `/home/alca/projects/` contains other-agent-managed subtrees (`autonomous_agency/` etc.) that pollute `git add -A`. Sprint #34 pulled in 666KB of agency data; had to `git reset --soft HEAD~1` + selective unstage + recommit. **Always list explicit paths in `git add`** for this project: `git add src/widgets/foo.cpp src/widgets/foo.hpp test/test_integration.cpp` — never the bare `-A`. If sibling agent's files appear in `git status`, exclude their tree before staging.

### Order matters in parseBinding (modifier chord)
When parsing "Ctrl+Alt+K", the modifier-prefix checks must run in order Ctrl → Alt → Shift. A single combined check would mis-parse "Alt" as a key name. Order is canonical, not arbitrary.

### Static + non-static member overload with same signature
C++ disallows overloading `static const char* name(S)` with `const char* name(S) const`. Promote to fully-static OR remove the instance form. Don't try to keep both.

### Header field ordering: m_captured declared in class body before use
`m_captured` must be declared in the class body BEFORE methods reference it. If a patch references `m_field` from `setOpen()` while the field is declared later, the LSP complains with "Use of undeclared identifier". Move field declarations above method definitions OR use lazy initializer pattern in render().

### ImGui::GetCurrentContext() check is mandatory for setOpen(true) hooks
Any code path in `setOpen(true)` that calls `ImGui::GetStyle()` or other context-bound APIs will crash if called outside a render loop. The test binary does not initialize ImGui. Pattern: set a "to capture" flag in setOpen, do the actual capture in render() guarded by context check.

### Pure helpers must be `static` member functions, not free functions
If a UI widget's logic is in a free function, it can't access the widget's enums or private statics. Promoting to `static` member of the class lets the test access it via `Widget::helper(args)` without an instance. Pattern works for enum-bearing logic.

### Forward-declaring ImGuiStyle is fine, full include not needed in header
Just `struct ImGuiStyle;` at the top of the .hpp is enough for parameter types that are pointers/references. Full `#include <imgui.h>` belongs in the .cpp.