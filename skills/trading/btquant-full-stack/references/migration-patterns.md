# Struct / Signature Migration Patterns

**Loaded when:** you are adding a field to a struct or a parameter to a function that has many call sites across the codebase. Covers brace-init field-add migrations, function signature changes, and backward-compatible save-format migrations.

This file complements `references/sprint-discipline-and-weiter.md` — that file covers the WEITER operator workflow and lazy-capture pattern; this one covers the more mechanical "I changed a type, now grep and patch every site" patterns that recur every few sprints.

## Signature / Field-Add Migration (the "I just added a bool" pattern)

When you add a parameter to a public function or a field to a struct that uses brace-init across the codebase, every call site and every test must be updated atomically. Skipping a call site = compile error; the operator will say "WEITER" and you'll be back at the build loop.

This pattern is from commit 351d4bc1 (adding `bool alt` to `HotkeyBinding`), but applies to any struct widening.

### Recipe (5 steps, in order)

**1. Grep the old signature first.** Find every place the function/struct is used before you touch anything:
```bash
grep -rn "HotkeyBinding{"  src/ test/                 # brace-init sites
grep -rn "\.match("         src/ test/                # function call sites
grep -rn "m\.set(HotkeyAction" src/util/              # aggregate m.set calls
grep -rn "injectCapture"    src/ test/                # alt-function paths
```

**2. Update the header FIRST.** Add the new field with a safe default (`= false` for bool flags, `= 0` for int, etc.). Update `operator==`, `matches()`, and any helper that compares the struct. The default value IS the backward-compat path — legacy data must parse with it.

**3. Update all brace-init sites atomically.** Every `{ GLFW_KEY_X, ctrl, shift }` becomes `{ GLFW_KEY_X, ctrl, alt, shift }`. If there are dozens (32 in `defaults()` alone, in this case), use a single big patch with all the lines — don't edit one-by-one. With `patch()` you can replace 30+ lines in one call.

**4. Update all function call sites.** A signature change to `match(key, ctrl, alt, shift)` breaks every existing `match(key, ctrl, shift)` call. Common hiding places:
- WindowManager dispatch sites
- Test assertions
- Mock producers
- Other widgets that look up bindings (ThemeEditor's "Reset to default" path, HotkeyEditor's "Reset" button)

Re-grep after the patch — `grep -rn "\.match(.*,.*,.*)"` will catch any 3-arg callers you missed.

**5. Update existing tests' EXPECTATIONS, not just the new test.** Existing tests assert specific bindings (`Ctrl+Shift+B` → SubmitBuy). If the default changed (`Ctrl+Shift+B` → `Alt+B`), update the assertion too — otherwise tests fail with misleading messages like "submit bindings wrong" when the actual issue is that your expectations are stale.

### Order matters — patch in this sequence or fight cascading errors

1. Header (struct + method signatures)
2. impl .cpp (defaults + match() impl + label() + parseBinding)
3. WindowManager / dispatch sites that call the function
4. Existing tests' brace-init + function calls + EXPECTATIONS
5. New test for the new functionality (Test N+1)
6. `cmake --build build -j$(nproc) && build/test/test_integration 2>&1 | tail -20`

The build will surface every missed site as a specific error pointing to the line — grep for the error message to find the next batch. Don't try to write all the updates from memory; let the compiler tell you what's left.

### Test additions for the migration itself (Test 48 in this commit)

For every struct/signature widening, add 6–8 checks covering:
1. Default-constructed struct: all new fields default to legacy-equivalent value
2. `label()` / `toString()` reflects new field in canonical position
3. `parse()` round-trip: write the new format, read it back
4. `parse()` mixed chord: e.g. "Ctrl+Alt+K" → all three modifiers set
5. Save → load preserves the new field
6. **Legacy format still parses with new field = false** (CRITICAL — protects existing user saves)
7. `match()` honors the new field (e.g. Alt+B fires SubmitBuy, plain B does not)
8. `matches()` requires exact modifier state (Alt+B does NOT fire if Ctrl+Alt is pressed)

## Backward-Compatible Save-Format Migration

**Default to the legacy value.** When adding a feature to a serialized format (new modifier, new field, new prefix), the new field MUST default to its pre-feature value so existing on-disk data parses identically.

Example (Alt+ modifier, commit 351d4bc1):
- Old on-disk: `KillSwitch=Ctrl+K`
- New format:  `KillSwitch=Ctrl+Alt+K`
- The `Alt+` prefix is parsed only when present; absent → `alt = false`
- A line written before the feature (`Ctrl+K`) still loads as `{K, ctrl=true, alt=false, shift=false}`

The "legacy still loads" test is non-negotiable — if a legacy save breaks, the user loses their config. They will not be happy.

### General rules for serialized-format additions

- **New field defaults to its pre-feature value.** bool → false, int → 0, enum → pre-feature variant.
- **Parse only what is present.** If the new prefix is optional, don't require it.
- **Test the legacy load path explicitly.** Don't assume backwards compatibility — prove it with a test.
- **Save in the new format.** After the migration, new saves include the new field. The on-disk format does NOT need to round-trip identically with the pre-feature build — only load-compat is required.
- **One-way migration is fine.** If a user goes back to a pre-feature build, they'll lose the new field's value but their config still loads.

### When migration is NOT backward-compatible (rare)

If the new feature fundamentally changes the format (e.g. switching from line-based to JSON, or adding a required discriminator), then:
- Version the save file (add `version=2` to the header)
- Auto-migrate on load: read old format, write new format, save back
- Keep the old parser as a fallback for one version

This is heavier work. The most common case (new optional field/prefix) is covered by the default-to-legacy pattern above.

## Test-Count Canonical Metric

`build/test/test_integration` prints `✓` per check, `✗` per failure. Use these as the canonical green-count metric:

```bash
build/test/test_integration 2>&1 | grep -c "^✓"    # total green checks
build/test/test_integration 2>&1 | grep "^✗"      # any failures (should be empty)
```

Every commit message body includes `N ✓ total across M tests, 0 failures`. This number is what the operator skims to confirm progress. Update it before every commit.

If `grep "^✗"` returns anything, do NOT commit — read the failures, fix, re-run. The 0-failures invariant is the sprint discipline contract.

The trailing `[Vulkan Loader] ERROR: vkDestroyInstance: Invalid instance [VUID-vkDestroyInstance-instance-parameter]` in test output is normal — it's the test path tearing down a partial Vulkan instance and is not a test failure. Don't count it as a failure.

## Reference commits

- commit 351d4bc1 — HotkeyBinding Alt modifier + save-format migration. 6 files, 240+ / 90-. The migration patterns above all derive from this commit.
- commit b5d992d1 — RiskPanel live progress bar. No migration; new wiring only.
- commit 87121d85 — ThemeEditor discard-changes. Lazy-capture pattern (see `sprint-discipline-and-weiter.md`).