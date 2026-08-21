# Phase 26 — LayoutIO (.btqlayout) Versioned Layout Profiles

NEW engine: Phase 26 — `util::LayoutIO` for versioned layout profiles. JSON-backed
file format with hand-rolled parser/writer (no external deps). Covers ALL layout-
relevant state in one file: widget visibility (11 booleans), general settings (4
fields), risk config (4 doubles), dock layout text, plus version + name metadata.

## File format (`.btqlayout`)

JSON, strict (no trailing commas, escaped strings). One object with four blocks:

```json
{
  "version": 1,
  "name": "Scalper",
  "dockLayout": "...",
  "widgets": {
    "showOrderBook": false,
    "showOrderBookDepth": true,
    ...
  },
  "general": {
    "fpsLimit": 144,
    "heatmapDensity": 256,
    "tradeWindowSeconds": 30.5,
    "theme": 1
  },
  "risk": {
    "maxPositionSizeUSD": 500000,
    "maxLeverage": 20,
    "killOnDailyLossUSD": 8000,
    "equityUSD": 25000
  }
}
```

22 fields total. Future version bump: change `kLayoutVersion`, load() rejects
anything != current version explicitly. No silent forward-compat.

## API surface

```cpp
struct LayoutSnapshot {
    Settings settings;        // covers widget visibility + risk_* + general
    std::string dockLayout;   // ImGui::SaveDockBuilderToText output
    int version = 1;
    std::string name;         // human-readable, set by save callers
};

class LayoutIO {
public:
    static std::filesystem::path layoutPath(const std::string& name);
    static std::filesystem::path layoutDir();
    static bool save(const std::filesystem::path& path, const LayoutSnapshot& snap);
    static std::optional<LayoutSnapshot> load(const std::filesystem::path& path);
    static LayoutSnapshot fromSettings(const Settings&, const std::string& dockLayout,
                                      const std::string& name = "");
    static std::vector<std::filesystem::path> list(const std::filesystem::path& dir);
};
```

## Patterns shipped

### 1. Per-block `KvPair` vectors for strict JSON

```cpp
std::vector<KvPair> widgets;
// build entries without commas...
widgets.push_back({"showOrderBook", ss.str()});

out << "{\n";
writeKvList(out, 1, top);                       // no trailing comma
out << ",\n  \"widgets\": {\n";
writeKvList(out, 4, widgets);                   // no trailing comma
out << "  },\n  \"general\": {\n";
// ...
```

`writeKvList` emits commas BETWEEN entries but never AFTER the last — produces
strict JSON that any conforming parser accepts. Don't manually `,\n` after
each writeKey call (this is exactly the bug Phase 26.1 hit — see pitfalls).

### 2. Forward-compat: consume unknown-key values

When loading a file from a future version, the parser must consume unknown
values or the rest of the file breaks. Fallback pattern:

```cpp
} else {
    // Unknown key — consume its value so we can keep parsing.
    if (c == '"') { std::string tmp; p.parseString(tmp); }
    else if (c == '{' || c == '[') { p.parseObject([&](const std::string&) {}); }
    else if (c == '-' || std::isdigit(c)) { double tmp; p.parseNumber(tmp); }
    else { bool tmp; p.parseBool(tmp); }
}
```

Without this, a file containing `"future_field": "foo"` causes the NEXT
key/value pair to fail to parse because the parser's `consume(',')` finds
the closing quote of "foo" instead of a comma.

### 3. Name sanitization (block path traversal)

```cpp
std::string clean;
for (char c : name) {
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9') || c == '_' || c == '-') {
        clean.push_back(c);
    }
}
if (clean.empty()) clean = "unnamed";
if (clean.size() > 64) clean.resize(64);
```

`layoutPath("../../etc/passwd")` → `etcpasswd.btqlayout` under profiles/.
ALWAYS inline this check in any widget that exposes "Save as…" with a
user-typed name. Reuse is fine for the sanitization logic — copy it.

### 4. Test pollution fix: clean tmp dirs before fixed-path tests

```cpp
namespace fs = std::filesystem;
for (const char* dir : {"btquant_test_replay_empty", ...}) {
    std::error_code ec;
    fs::remove_all(fs::temp_directory_path() / dir, ec);
}
```

Tests that write to FIXED tmp paths (e.g. `/tmp/<name>/journal.jsonl`)
accumulate state across runs. `remove_all` at test start ensures
deterministic first-run state. Symptom of the bug: replay tests that
worked in isolation failed after a previous run appended to the same
file — `n=4` when `n=2` expected. (See Phase 32 pollution pitfall.)

### 5. Hand-rolled JSON over nlohmann/json for flat schemas

For flat key=value files (no nesting except objects), a ~250-line JSON
parser is faster to ship than adding a FetchContent dependency on
nlohmann_json. Reserve nlohmann for nested structures (config trees,
API responses) where the parser would balloon past ~500 lines.

The Phase 26 parser: ~200 lines for string/number/bool/object support
with error recovery, escape handling, and forward-compat value skipping.

## Pitfalls

### A. Trailing commas in hand-rolled JSON

First writer did `out << "key": value,\n` after every key. JSON
specification forbids trailing commas — strict parsers reject them.
Fix: build entries into a `std::vector<KvPair>` then emit with
`writeKvList` which inserts commas BETWEEN but never AFTER. Symptom:
"✓ save wrote ..." but "✗ round-trip lost values" — save() succeeds
because the file IS written, load() fails because the file is invalid
JSON. Test 33 round-trip caught it on the first run.

### B. Forward-compat parser breaks on unknown keys with non-consumed values

Test 33 step 6 ("unknown keys ignored") failed on first run because the
parser didn't consume the value of `"future_field_we_dont_know": "ignored"`.
After the unknown-key branch fell through, the next `consume(',')` found
the closing quote of "ignored" instead of a comma. Fix: always consume
unknown-key values via the fallback pattern in section 2 above.

### C. Stale tmp files from previous test runs

Tests using fixed tmp paths (`/tmp/<name>/journal.jsonl`) accumulate
state across runs. TradeJournal's append-mode semantics mean the
replay test sees N=4 fills when N=2 was written. Fix: `remove_all` the
test dir at start of the test. Phase 25 was affected by this on the
Sprint 25 run that followed Sprint 24 (existing 2 fills in the file
plus 2 newly written → 4 total).

### D. layoutPath name sanitization must reject ALL of `/`, `\`, `..`, NUL, empty

`Settings::profilePath` already had this check; copy it verbatim when
adding `LayoutIO::layoutPath`. Don't write a "simplified" version that
only rejects `..` — attackers can use `\0` injection or unicode confusables.
Pattern: allow `[a-zA-Z0-9_-]` only, truncate to 64 chars, replace empty
with "unnamed". (See Phase 11 path-traversal pitfall for the security
rationale.)

### E. Strict JSON parsing rejects ES5-style unquoted keys

The hand-rolled parser only accepts `"key": value` with double-quoted
keys. ES5 allowed unquoted identifier-like keys (`key: value`). Files
that look like INI (no quotes) won't parse. Acceptable trade-off: the
LayoutIO format is internal — never exposed to user-editable INI-style
input. If user-editable JSON is ever needed, switch to a permissive
parser like nlohmann/json.

### F. test pollution `remove_all` must use `error_code` overload

```cpp
std::error_code ec;
fs::remove_all(fs::temp_directory_path() / dir, ec);  // non-throwing
// NOT: fs::remove_all(...) — throws on permission errors
```

The non-throwing overload is critical because tmp dir removal can fail
if the path is held by another process. The throwing overload aborts
the entire test binary with `std::system_error`. Generalizes to ALL
test-cleanup operations on shared tmp dirs.

## Wiring next (not shipped Phase 26)

The WindowManager doesn't yet CALL LayoutIO on startup or from menu
items. The natural next phase: View → "Save layout as…" (writes to
`LayoutIO::layoutPath(name)`) and View → "Load layout…" (lists profiles
in `LayoutIO::layoutDir()` + applies via `applyPreset` + sets dock via
`ImGui::DockBuilderLoad` or similar). The data layer is verified by
Test 33; the UI wiring is straightforward when requested.

## Verification

Test 33: 9 invariants all green.
1. save wrote file
2. all 22 fields + dockLayout + version round-trip
3. missing file -> nullopt
4. future version rejected (v=999)
5. malformed JSON -> nullopt
6. unknown keys ignored, known keys loaded
7. layoutPath sanitizes "..->etcpasswd"
8. list() found 4 .btqlayout files
9. (combined with above)

16 commits / 23 widgets / 33 tests.

## Lessons carried forward

- **Strict JSON: never trailing comma** — build with KvPair vectors
- **Forward-compat: always consume unknown-key values** — peek the
  first char and dispatch to the matching parser
- **Test tmp paths: `remove_all` at start** to avoid pollution from prior runs
- **Path traversal sanitization: copy the existing `Settings::profilePath` pattern**
- **Hand-rolled JSON: ~250 lines for flat schemas is faster than adding nlohmann**