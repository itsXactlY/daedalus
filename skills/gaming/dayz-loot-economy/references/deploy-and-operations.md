# DayZ Loot Deploy + Server Operations (Linux)

Condensed from the Apocalyps3nd rebuild session (2026-07-17). Covers live
deploy with backup/validator, the Faugus/GE-Proton server launch, and the
Zen2 CPU-crash diagnostic that ended the session.

## Live Deploy (backup + validator, per "no prod file without backup")

1. Pre-flight backup of live `db/types.xml`, `db/events.xml`, `mapgroupproto.xml`
   → `backups/pre_apocalyps3nd_<timestamp>/`.
2. Copy generated XMLs into
   `Server/mpmissions/dayzOffline.chernarusplus/db/`:
   - `types.xml` REPLACES the live one (re-balanced, all mods)
   - `cfgeconomycore.xml`, `cfgspawnabletypes.xml`, `cfgrandompresets.xml`,
     `events.xml`, `cfgeventgroups.xml` are often ABSENT live — copy them in.
3. mapgroupproto extension already injected (verify 7 `APX_Underground_*` groups).
4. Run `validate_deploy.py` — exit 0 = deploy valid.

`validate_deploy.py` checks: live types.xml unique+count, CE rootclasses
(non-empty), distribution orphaned-refs (0), `APX_Underground_*` present in
mapgroupproto, T4 items 100% bound to `APX_Underground_*`.

## Start script (Faugus / GE-Proton path)

`start_server_faugus.sh` (lives in `Server/`):
- Loads all 59 mods with `@Apocalyps3nd_Loot` LAST (loot overlay).
- Runs `validate_deploy.py` pre-flight; aborts if it fails.
- Launches via `umu-run` (Faugus-managed GE-Proton), NOT裸 wine.

Env block (from `faugus-launcher list`):
```
WINEPREFIX=/home/alca/Faugus/default
PROTONPATH=Proton-GE Latest
STEAM_COMPAT_DATA_PATH=$WINEPREFIX
PROTONFIXES_DISABLE=1
PROTON_USE_WOW64=1
WINEDLLOVERRIDES="d3d11=n,b;dxgi=n,b"
WINEDEBUG=-all
UMU_RUN=/home/alca/.local/share/faugus-launcher/umu-run
```
DayZ Server is NOT a Steam app → `umu-run DayZServer_x64.exe ...` directly
(GAMEID=umu-default). Do NOT use a Steam AppID.

The裸-wine `start_server_apx.sh` also exists but segfaults on Zen2 (see below).

## THE ZEN2 CPU CRASH (invariant, survives all launchers)

Symptom: server dies before "Game server started" with
`wine: Unhandled page fault on read access to 0000000000000060`.

RPT (`profile/DayZServer_x64_<ts>.RPT`):
```
Exception code: C0000005 ACCESS_VIOLATION at 407F3580
Fault address:  407F3580 C0000005:40C34058 Unknown module
Fault code bytes: 48 3B 11 74 51 48 85 D2 74 28 48 8D 4A 08 B8 01
```
Disassembly: `48 3B 11`=CMP RAX,[RCX]; `74 51`=JE; `48 85 D2`=TEST RDX,RDX;
`48 8D 4A 08`=LEA RCX,[RDX+8]; `B8 01`=MOV EAX,1 → NULL-`this` vtable call.

Verified IDENTICAL across 5 launch configs:
1.裸 wine 11.12 Staging, full mods
2.裸 wine, vanilla-only (`@CF;@VanillaPPMap`) — NO loot build
3. `-noLauncher` + software rendering
4. DXVK override (`d3d11=n,b;dxgi=n,b`)
5. Faugus / GE-Proton via umu-run

Conclusion: DayZ 1.28 `DayZServer_x64.exe` (Dec 2025 build) is
CPU-incompatible with AMD Ryzen 3800X (Zen2). The CLIENT (`DayZ_x64.exe`,
also 1.28) boots fine under the same prefix. The fault offset `1407F3580` is
invariant → it is a binary/CPU issue, not Wine/Proton/Loot.

Fix paths (none verified in-session):
- Run server on a Zen3+ host (Ryzen 5000+, etc.)
- Use an older server binary that targets Zen2
- QEMU-emulate a newer CPU (`-cpu` flag)

Do NOT keep swapping Wine/Proton versions — the offset won't move.
