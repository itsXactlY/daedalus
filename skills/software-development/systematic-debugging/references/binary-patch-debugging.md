# Binary Patch Debugging

Recurring pattern: a binary patch tool (e.g. `resolve.py`, a crack script, hex patch) says **"no match (already patched or layout differs)"** but the target software still exhibits the original failure (crash, activation dialog, trial mode).

## Root Causes

| Diagnosis | How to Test | Fix |
|-----------|-------------|-----|
| **Already patched, but patch was wrong or incomplete** — a manual perl/sed/printf patch already modified some bytes, changing them from the original values the tool expects. The tool can't find its known-unpatched signature so it reports "no match." | Compare SHA256 of current binary against the hash documented in the patch tool or known-good original. If they differ, the binary was already modified. | Restore from `.bak` (the patch tool likely created one), or re-extract from original installer. Let the tool patch from scratch on the clean binary. |
| **Different binary version/build than the patch tool was tested on** — same major version, different minor/patch/build number. The byte layout shifted enough that the pattern offsets changed or the function location moved. | Check if the SHA256 matches any supported version listed in the patch tool. If not, you have an untested build. | Manual analysis of the new binary (identify equivalent functions, find new offsets). Or find a patch tool update that supports your build. |
| **Multiple independent patch tools applied in sequence** — tool A patched some bytes, then tool B tried to patch different bytes but found the signature from tool A's modified area was different. | Check file modification time and `.bak` files. Check if multiple patch tools exist in the torrent/installer directory. | One tool at a time. Restore clean, apply exactly one patch approach, test. |
| **License file missing or unreachable** — the binary patch alone may not be sufficient; a license file and/or env var pointing to it may be needed. | Check if a `.license/` or `blackmagic.lic` file exists. Check for `RLM_LICENSE` or similar env vars. | Create the license file in the expected location; set the corresponding env var when launching. |

## Investigation Workflow

### 1. Check for backup files

Most proper patch tools create a `.bak` before modifying:

```bash
ls -la /path/to/binary.so.bak
ls -la /opt/BlackmagicDesign/Fusion21/libfusionsystem.so.bak
```

A `.bak` with a different SHA256 from the current binary confirms prior modification.

### 2. Check SHA256 against known values

If the patch tool documents expected hashes, compare:

```bash
sha256sum /path/to/current/binary
sha256sum /path/to/backup/binary
```

### 3. Restore from backup and re-run patcher cleanly

```bash
sudo cp /path/to/binary.so.bak /path/to/binary.so
sudo python3 patcher.py --targets fusion
```

### 4. If patcher still says "no match" → untested build

- Check if the patcher supports your software version at all
- The "layout differs" part of the message is the real signal here
- Requires manual binary analysis (disassemble, find license check functions, compute new offsets)

### 5. Check for runtime env vars

Some patches require an environment variable to point at the license file:

```bash
RLM_LICENSE=/opt/BlackmagicDesign/Fusion21/.license/blackmagic.lic /opt/BlackmagicDesign/Fusion21/Fusion
```

## Concrete Example: Blackmagic Fusion Studio 21 Linux

- Patch tool: `resolve.py` (from torrent, inside `Blackmagic_Fusion_Studio_21.0_Linux/`)
- Binary: `/opt/BlackmagicDesign/Fusion21/libfusionsystem.so`
- License file: `/opt/BlackmagicDesign/Fusion21/.license/blackmagic.lic`
- Required env var: `RLM_LICENSE=<path-to-lic>`
- Patches applied: 2 sites in `libfusionsystem.so`, both convert `74 11` (je +0x11) to `EB 11` (jmp +0x11) after `cmp [rbp-4], 0`
- If resolve.py says "no match": check if a manual perl/sed patch was already applied; restore from `.bak` and re-run
- Expected SHA256 (Fusion 21 Beta 3): `7505256d35c729740e96d1d9faeccb43caf122c4bae8ef59f936d2016dfce53c`
- Release build (confirmed different): `8b16a6eaf732bffec510d2596872b2e2d9ad7a1b971af2e445ebc2928fcb94b0` (unpatched)

### Deeper Analysis: When resolve.py Patches Don't Work

If resolve.py applies cleanly (both patches at expected offsets) but the activation dialog **still appears**, the patches may be insufficient or incorrect for the specific build. This happens when the GA release differs from the Beta the tool was tested on.

#### Patch Direction Matters

The `74 11` → `EB 11` change converts `je +0x11` (jump if equal/zero) to `jmp +0x11` (unconditional jump). In the Beta build, this makes the licensing helper always take the "continue checking" path, bypassing the failure return. But in the GA build with the same offsets, the `EB 11` may skip the success path entirely and land on `mov eax, 1` (return failure).

**Two alternative patches to try when `EB 11` doesn't work:**

| Patch | Binary Change | Effect |
|-------|--------------|--------|
| **NOP out** | `EB 11` → `90 90` | Always falls through to success path (store result, return 0) |
| **Return 0 at prologue** | Replace function entry with `31 c0 c3` (xor eax,eax; ret) | Function returns 0 immediately, but may break callers that need side effects |

#### Finding the LicenseDialog Function

When binary patches fail, the activation dialog itself can be killed at source. The dialog class is `Fusion::LicenseDialog` (confirmed via RTTI string `N6Fusion13LicenseDialogE`). Its constructor/setup function can be found by:

1. **Searching for UI object names** in the binary:
   - `m_SerialEdit`, `m_RegisterMore`, `m_RetryClose` (object names from the dialog UI)
   - Use `objdump` to find code that loads these strings via LEA:
     ```bash
     objdump -d -M intel --start-address=0x784900 --stop-address=0x785200 libfusionsystem.so
     ```
2. **Identify function boundaries**: Look for `push rbp; push r15; push r14; push r12; push rbx; sub rsp, 0x20` as the prologue, then `ret` as the function end.
3. **NOP the function entry**: Replace the prologue with stack cleanup + immediate return:
   ```
   31 c0                   xor eax, eax
   48 83 c4 20             add rsp, 0x20
   5b                      pop rbx
   41 5c                   pop r12
   41 5e                   pop r14
   41 5f                   pop r15
   5d                      pop rbp
   c3                      ret
   ```
4. **Known offset** for Fusion 21.0 GA Linux: `0x784960` in libfusionsystem.so

**Note:** Even with the LicenseDialog constructor NOP'd, the dialog may still appear through a different code path (e.g., `QDialog::exec` called from a different location, or a modeless dialog using `QWidget::show`). Multiple dialog-creation paths may need to be patched.

#### Frida Runtime Patching

When static binary patching is insufficient, Frida can patch at runtime:

```javascript
// Poll for module, then NOP the function
(function poll() {
    var mod = Process.findModuleByName("libfusionsystem.so");
    if (mod) {
        var addr = mod.base.add(0x784960);
        Memory.patchCode(addr, 15, function(code) {
            code.writeByteArray([0x31,0xc0,0x48,0x83,0xc4,0x20,0x5b,0x41,0x5c,0x41,0x5e,0x41,0x5f,0x5d,0xc3]);
        });
        console.log("LicenseDialog NOP'd");
    } else {
        setTimeout(poll, 10);
    }
})();
```

Run with:
```bash
frida -f /opt/BlackmagicDesign/Fusion21/Fusion -l script.js
```

**Important Frida timing:** In spawn mode (`-f`), the script executes BEFORE any libraries are loaded. Use polling with `Process.findModuleByName` (returns null if not found) rather than `Module.findExportByName` (throws/crashes if module isn't loaded). Poll every 10ms until the module appears.

#### Hooking QDialog::exec

As a nuclear option, block ALL modal dialogs from Fusion by hooking Qt's `QDialog::exec`:

```javascript
var execAddr = Module.findExportByName("libQt5Widgets.so.5", "_ZN7QDialog4execEv");
Interceptor.attach(execAddr, {
    onEnter: function(args) {
        this.retval = 0; // QDialog::Accepted
    }
});
```

This requires libQt5Widgets.so.5 to be loaded first — use the same polling pattern. This is a brute-force approach that also blocks legitimate dialogs (file pickers, prefs), so use it only to verify the concept, then refine.

#### Complete Toolchain

| Step | Tool | Command |
|------|------|---------|
| Find strings in binary | `strings` or Python `re.finditer` | Search for UI object names, class names |
| Find code referencing strings | Python byte search for LEA RIP-relative | Check `0x48 0x8d` modRM patterns |
| Disassemble region | `objdump -d -M intel --start-address=X --stop-address=Y` | Find function boundaries |
| Verify current patch state | Python byte search | Check `74 11` vs `EB 11` vs `90 90` |
| Apply patches | `sudo cp` + Python bytearray | Write patched binary |
| Runtime patch | Frida + `Memory.patchCode` | Test without modifying binary |
| Hook dialogs | Frida + `Interceptor.attach(QDialog::exec)` | Block dialog creation |
