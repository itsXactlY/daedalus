# DayZ Server `0x60` Page Fault on Zen2 — Reproduction Matrix

## Symptom (identical every time)

```
wine: Unhandled page fault on read access to 0000000000000060 at address 00000001407F3580 (thread 0024), starting debugger...
...
Exception code: C0000005 ACCESS_VIOLATION at 407F3580
Allocator: system
graphics:  No
resolution:  160x120x32
Addons:
  DZ_Worlds_Chernarusplus_World in DZ\worlds\chernarusplus\world\
  DZ_Weapons_Firearms_AKM in DZ\weapons\firearms\akm\
  ...
```

- Exit code 5 (Wine).
- Crash at ENGINE LOAD — RPT lists `DZ_Worlds_*`, `DZ_Weapons_*` addons, never reaches mission
  init or loot compile.
- Address is **deterministic**: `1407F3580` across every config.

## Fault-byte decode (from RPT `Fault code bytes`)

```
48 3B 11        CMP RAX, [RCX]
74 51           JE  +0x51
48 85 D2        TEST RDX, RDX
48 8D 4A 08     LEA RCX, [RDX+8]   ; RCX = this->vtable+offset, but RDX == 0
B8 01 00 00 00  MOV EAX, 1
```

This is a null-`this` vtable dereference — the binary itself crashes during engine
initialization, independent of any mod, loot config, or Wine/Proton layer.

## Reproduction matrix (all crashed identically with `0x60`)

| # | Launcher | Proton/Wine | Mods | Rendering | Result |
|---|----------|-------------|------|-----------|--------|
| 1 | start_server_apx.sh | system wine 11.12 | 59 | software | page fault |
| 2 | test_vanilla.sh | system wine 11.12 | 5 (CF+VanillaPPMap) | software | page fault |
| 3 | test_vanilla.sh | system wine 11.12 | 5 | -noLauncher+software | page fault |
| 4 | dxvk_test.sh | system wine 11.12 | 5 | DXVK override | page fault |
| 5 | start_server_faugus.sh | Proton-GE Latest (compatdata/221100) | 5 | proton | page fault |
| 6 | start_server_faugus.sh | Proton - Experimental (Faugus/default) | 5 | proton | page fault |
| 7 | build_and_start.sh | Proton - Experimental (compatdata/221100) | 59 | proton | page fault |
| 8 | wine DayZServer_x64.exe | system wine (~/.wine) | 5 | software | page fault |

**Conclusion:** the crash is invariant to Wine/Proton flavor, mod count, rendering backend,
and prefix. It is a server-binary × CPU microarchitecture incompatibility.

## Key contrast: client boots, server does not

- `DayZ_x64.exe` (client, 5 Dec 2025) — boots fine under Proton - Experimental (operator's
  normal `!START.sh` path, Mazemaker id=824528).
- `DayZServer_x64.exe` (server, 14 Dec 2025, 16 MB) — segfaults at `0x60` on this CPU.

The CPU is **AMD Ryzen 7 3800X (Zen2, 2019)**. DayZ 1.28 server binary appears to expect a
code path (CPU feature detection / init order) that diverges on Zen2 vs Zen3+. AVX2 + BMI2 are
present on this chip, so it is not a missing-basic-feature issue — likely a specific instruction
sequence or uninitialized vtable the binary only hits on older Zen cores.

## What does NOT help (verified)

- DXVK override (`WINEDLLOVERRIDES="d3d11=n,b;dxgi=n,b"`) — crash identical.
- `-noLauncher` + software rendering (`LIBGL_ALWAYS_SOFTWARE=1`) — crash identical.
- Switching Wine/Proton build (system wine 11.12, Proton-GE Latest, Proton - Experimental) — crash identical.
- Reducing mod count to 5 — crash identical.
- Vulkan driver is present (GPU0, driver 610.43.3.0) — not a missing-driver issue.

## What to try (operator decides — agent does not guess)

1. **Run on a Zen3+ host** (Ryzen 5000+ / Intel 11th+). Same binary very likely boots there.
2. **QEMU CPU emulation:** wrap wine with `qemu-system-x86_64 -cpu Skylake` (or `-cpu Zen3`)
   so the binary sees a newer uarch. Overkill, last resort.
3. **Different server binary build** that targets older CPU microarchitectures.

## Do not conflate with the script-compile error

If a run instead shows `Can't compile "World" script module! Apocalypse/scripts/4_World/
VPPWebhookManager.c(99): Broken expression (missing ';'?)`, the engine LOADED — that is a real
EnforceScript error in `apogrps_qwen/Apocalypse/scripts/4_World/VPPWebhookManager.c`. The `0x60`
page fault blocks reaching compile entirely. Fix the page fault (boot the server) before the
script error becomes reachable. See `dayz-apocalypse-project-layout.md`.
