---
name: btquant-vulkan-phase34
description: 'NEW engine: Phase 34 — Layout import/export for sharing .btqlayout profiles between machines. LayoutIO::exportTo(destPath, name) + LayoutIO::importFrom(srcPath, destName="") reusing existing load()/save(). View → Layout submenu gains Export layout… + Import layout… modals. 9 invariants in Test 41. 24 commits / 23 widgets / 41 tests.'
---
# BTQuant Vulkan — Phase 34: Layout import/export

**Context:** Phases 27/31/32 added per-machine layout management (save/load + Ctrl+1..Ctrl+9 hotkey switching + View→Layout modals). Phase 34 adds the cross-machine plumbing: read a named profile → write to an arbitrary path; read an arbitrary .btqlayout → save it under profiles/.

**Shipped (commit 3d5992bf):**

- `LayoutIO::exportTo(destPath, name)` — reads the named profile via the existing `load()` path, then `save()` to the destination. Returns false on missing source or write failure. Same on-disk format, same version, same metadata.
- `LayoutIO::importFrom(srcPath, destName="")` — reads the source via `load()`, derives the destination name from the source stem when `destName` is empty, strips any `/` or `\` components for safety, rewrites `snap.name` so the profile lists cleanly under `profiles/`, and `save()`s it under the default dir. Returns `std::optional<LayoutSnapshot>` (nullopt on load failure).
- `WindowManager` modal popups:
  - "Export Layout" — InputText for profile name (reuses `m_layoutNameBuf`) + destination path (new `m_layoutExportBuf[256]`) + Export/Cancel buttons. Calls `LayoutIO::exportTo()`.
  - "Import Layout" — InputText for source path (new `m_layoutImportBuf[256]`) + Import/Cancel buttons. Calls `LayoutIO::importFrom()`.
  - Failed operations log a `BTQ_LOG_WARN` and keep the popup open so the user can correct the path.
- View → Layout submenu gains "Export layout…" + "Import layout…" entries above the existing quick-pick list.

**Test 41 (9 invariants):**

1. `exportTo(missing profile) → false`
2. `exportTo writes file to arbitrary path` (seeded `ExportTest` profile)
3. Exported file matches original on round-trip (fields: `showOrderBook=false`, `theme=1`, `risk_maxLeverage=7.5`, `dockLayout="{\"x\":1}"`)
4. `importFrom(path, "ImportedCopy")` installs under profiles/ with the requested name
5. Imported profile visible in `LayoutIO::list()` (i.e. file landed in the right dir)
6. `importFrom(path, "")` derives name from `path.stem()`
7. `importFrom(missing file) → nullopt`
8. `exportTo(unwritable path) → false`
9. End-to-end cleanup via `std::filesystem::remove` for tmp files + `remove_all` for the isolated HOME

**Pitfall encountered (Sprint #34, not caught at first commit):**

- **`git add -A` in /home/alca/projects/PubBTQuant/btquant_vulkan/ pulls in sibling-agent trees from the parent dir** (`../autonomous_agency/` etc.). First commit attempt included 666KB of agency data; had to `git reset --soft HEAD~1` + `git reset HEAD -- ../autonomous_agency/` + recommit with explicit paths. **Rule for this project:** `git add src/ test/ CMakeLists.txt` — never the bare `-A`. Always check `git status` before `git add`; if sibling-agent files appear, exclude their tree from the staging area first. Captured in MEMORY.md and in the main skill's pitfalls section.

**Pattern: cross-machine file sharing via existing I/O layer**

When the data flow is "named profile → arbitrary file" or "arbitrary file → named profile", the right move is to add a thin wrapper around the existing `load()` + `save()` pair. The wrapper handles name derivation + path-component stripping; the actual serialization is reused verbatim. Avoids forking the parser, keeps format compatibility automatic, makes test surface tiny (round-trip + missing/unwritable path cases).

**Pattern: shared export buffer + shared import buffer**

Both modals use `char[256]` buffers (not `std::string`) because the InputText API works on raw `char*` + size. The buffers persist across modal sessions so the user's last entry is preserved (matches how Phase 27's `m_layoutNameBuf` works).

**Sprint count now: 24 commits, 23 widgets, 41 tests, all green.** Next: deferred items from Phase 32 ("Open / next") — multi-monitor DPI awareness, OrderTicket keyboard shortcut, Position calculator hot-recalc, or other.
