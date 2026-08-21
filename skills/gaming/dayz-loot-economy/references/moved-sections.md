# dayz-loot-economy — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## 9. SOURCE-OF-TRUTH + BLIND-ACTION PITFALLS (learned 2026-07-18, hard corrections)

**THE WRONG-TREE TRAP (BIT US BADLY).** There are decoy/junk mod source dirs on
this host that LOOK like the real mod but are NOT. On this host the ONLY correct
source tree is `/home/alca/apogrps_qwen/Apocalypse/` (single combined tree:
3_Game + 4_World + 5_Mission, ~90 .c files). The dirs `/home/alca/apogrps/VanillaPPMap`
and `/home/alca/apogrps/VanillaPPMap_Server` are JUNK — a stale pre-rewrite copy
that a build script (`build_and_start_vanillappmap.sh`) wrongly pointed at. Editing
or building from them changes NOTHING in the live server.

**Operational rule (user-explicit):** Before ANY edit or build, VERIFY the actual
source tree the running build uses. Read the build script's `SRC_CLIENT`/`SRC_SERVER`
(or the `pbo -C` input path) and confirm it points at the real tree. If the user
names a specific path ("DAS HIER IST DER MOD ORDNER: /home/alca/apogrps_qwen/Apocalypse/"),
treat that as authoritative and STOP looking elsewhere. Do NOT grep sibling dirs
"just in case" — that is exactly how the junk-tree got patched.

**THE "READ THE ENTIRE FILE" RULE (user-explicit, SHOUTED, repeated 4+ times).** When the
user pastes a log/RPT and says "LIES DAS GANZE VERFICKTE FILE" / "ALLES DU LIEST ALLES DU
STÜCK SCHEIẞE" / "LES DEN GANZEN ERROR! DIE GANZE MELDUNG! ALLE ERRORS!" — they mean:
READ THE COMPLETE FILE, NOT grep excerpts. Grepping for one keyword and acting on the
first 5 hits MISSES the actual root cause that is buried 3000 lines deep (here: the
`[CE][CoreData] :: 0 root classes` line at line ~3574 that explained EVERYTHING, while
the agent was fixating on `Type does not exist` warnings at line ~3668). The failure mode
that triggered this: agent greps a symptom, patches a guess, reports "fixed", user pastes
the NEXT RPT, repeats. The whole session was this loop ~6 times.

**Hard rule:** When the user pastes an RPT/log OR tells you to read one — read it END TO END
(use read_file in offset chunks if >500 lines; use search_files ONLY to LOCATE the section,
then read_file the surrounding 50-100 lines to get full context). Do NOT conclude from a
grep hit. Specifically for DayZ server RPTs: the CE-Init block (`[CE][CoreData]`,
`[CE][TypeSetup]`, `[CE][offlineDB]`, `[DynEvent]`) is the diagnostic core — find it with
search_files, then READ THE FULL BLOCK (it spans ~100-300 lines), do not excerpt one line.
Report what the FULL read shows, not a single grep match.

**THE "STOP ACTING BLIND" RULE (user-explicit, repeated).** When the user says
"HÖR AUF BLIND IRGENDEINE SCHEISSE ZU MACHEN" or "nutze mazemaker" — they mean:
verify the REAL cause from the REAL files BEFORE applying a fix. A fix applied to
the wrong file (junk tree, wrong pbo, stale config) is worse than no fix. Sequence:
(1) locate the exact file the running process actually loads, (2) read the relevant
section, (3) apply the minimal correct change, (4) restart + verify against the real
success criterion (NOT a proxy like "port bound" — port binds during the load window
before the mission module finishes compiling; that is a ZOMBIE window, not "stable").

**Client connect target mismatch:** the client `!START.sh` historically pointed at
`192.168.0.242` (TPAD, a DIFFERENT machine). The LOCAL server binds `192.168.0.2`.
If the client "can't connect / hangs at login", first check the IP in `!START.sh`
matches the server's actual LAN IP (`ip -4 addr`). A client connecting to the wrong
host will hang or early-disconnect with no server-side error.

## 10. DayZ CLIENT under Proton — boot/hang debugging (learned 2026-07-18)

The client behaves DIFFERENTLY from the server under Proton. Two distinct failure
modes, both seen this session:

**Mode A — "modded version" dialog blocks startup (FIXED).** Client hangs at a
"GROUP" / "You are playing a modded version of the game" dialog and never proceeds.
Headless auto-start never dismisses it. Fix: append to the client `DayZ.cfg`
(`.../compatdata/221100/pfx/drive_c/users/steamuser/Documents/DayZ/DayZ.cfg`):
```
disableNaDialog=1;
disableServerInfo=1;
```
After that the client connects (all login states pass, position assigned).

**Mode B — hangs in WaitPreloadCamLoginState, no error in RPT (FIXED).** Client passes
login, reaches `WaitPreloadCamLoginState`, then sits ~2 min and terminates. The
client RPT has ONLY ~24 lines (Inputs load + "Termination successfully completed"),
NO SCRIPT (E), NO crash. Root cause: client uses **wined3d (software rendering)**
instead of DXVK because no `WINEDLLOVERRIDES` is set and the pfx `d3d11.dll` is the
Windows original. World render-init never completes. Fix: in the client start script
export before `exec`:
```bash
export PROTON_USE_DXVK=1
export WINEDLLOVERRIDES="d3d11=n,b;dxgi=n,b"
```
The RTX 4060 Ti is visible to Vulkan (`vulkaninfo` shows it) — DXVK uses it and the
client boots through PreloadCam. NOTE: boot is SLOW (minutes) even with DXVK at 43 mods;
"takes forever" is NORMAL, not a hang — wait it out, don't kill at 90s.

**Client RPT location:** `.../compatdata/221100/pfx/drive_c/users/steamuser/AppData/Local/DayZ/DayZ_x64_*.RPT`
The SERVER RPT is in `Server/profile/`. They are DIFFERENT files — a client-side
"early disconnect" with no server error means: read the CLIENT RPT, not the server's.

## 12. Unified client/server start scripts (working pattern, 2026-07-18)

**USER PREFERENCE (explicit, 2026-07-18): "ICH WILL EINEN START-SERVER.SH STARTER
HABEN, SELBE WEG WIE DER VERFICKTE CLIENT" — when the user has a WORKING script
(the client `!START.sh`), REPLICATE ITS STRUCTURE 1:1 for the new one. Do NOT invent
a new schema, reorder the sections, or add novel flags. Copy: same `set -euo pipefail`,
same config block layout, same helper functions (`log`/`fail`/`ensure_exists`/
`build_mod_string`), same env exports. Only the binary + args differ
(`-server -config -port -profiles -mod -servermod` instead of `-connect -port -name`).**

Keep client and server MOD_LIST IDENTICAL (43 mods here) to avoid client/server
mismatch hangs. Working scripts:
- `/home/alca/games/DayZ/Server/start_server.sh` — exact 43-mod list + 4 servermods
  (`@Apocalypse_Server;@BuilderLoader;@CarCoveraLca;@EditorLoader`), Proton - Experimental,
  port 2302. Built 1:1 from the client `!START.sh`. (Do NOT use the older
  `start_server_apx_unified.sh` / `start_server_apx.sh` detours — they had a `cd`
  ordering bug that made `ensure_exists` fail.)
- `/home/alca/games/DayZ/Client/!START.sh` — same 43-mod list, DXVK exports,
  absolute `DAYZ_CLIENT` path, connects `192.168.0.2:2302`.

Both use `STEAM_COMPAT_DATA_PATH=/home/alca/.local/share/Steam/steamapps/compatdata/221100`
and `PROTON_PATH=".../Proton - Experimental/proton"`. Server under Proton - Experimental
BOOTS FINE on this host (no Zen2 crash in this config — see §8 correction below).

Script must `cd "$(dirname "$0")"` IMMEDIATELY after `set -euo pipefail` (before the
`ensure_exists` checks) and use ABSOLUTE paths for `DAYZ_CLIENT`/`DAYZ_SERVER` —
otherwise a detached/non-cwd launch dies with "not found at DayZ_x64.exe".

## 14. THE "dynamic groups: 0" RED HERRING + ASYNC LOOT SPAWN WINDOW (PROVEN 2026-07-18)

**THE TRAP THAT COST ~6 ITERATIONS THIS SESSION.** After a correct config (types.xml in
root, cfgeconomycore `<economycore>/<classes>/<rootclass>` format, usages registered),
the server boots and the RPT STILL shows:
```
[CE][Hive] :: Initializing of spawners done.
  dynamic groups: 0
```
An agent reads `dynamic groups: 0` and concludes "loot is broken, config still wrong"
→ patches a guess → restarts → same `0` → loop. **THIS IS WRONG.** `dynamic groups: 0`
at boot is NORMAL and IRRELEVANT.

**What actually happens:** DayZ does NOT spawn loot synchronously during CE init. It
loads the prototypes + types, finishes init (`Player connect enabled` / `Mission geladen`),
and spawns loot ASYNCHRONOUSLY over the next **~15–20 minutes** (driven by the spawn
threads after players connect / map sectors load). The `dynamic groups: 0` line is a
pre-spawn counter, not a failure.

**THE REAL LOOT INDICATOR — MEASURE THE BINS, NOT THE RPT BOOT LINE:**
```bash
D=.../dayzOffline.chernarusplus/storage_1/data
total=0; cnt=0; n=0
for f in "$D"/dynamic_*.bin; do
  [ -f "$f" ] || continue
  n=$((n+1)); s=$(stat -c %s "$f"); total=$((total+s))
  [ "$s" -gt 100 ] && cnt=$((cnt+1))
done
echo "Total dynamic bytes: $total | bins with loot (>100b): $cnt / $n"
```
- **Empty/fresh:** `Total dynamic bytes` ≈ 1900, all bins 49 bytes (12× empty + 1 small).
  This is the post-wipe / post-restart state BEFORE async spawn runs.
- **Loot spawning (GOOD):** total climbs to 5000–50000+, 8–12 of 12 bins exceed 100 bytes,
  `dynamic_001.bin` alone reaches 9000+ bytes. This is the proof loot is on the map.

**Verification sequence after a config fix (DO NOT declare failure early):**
1. Apply config fix (root types.xml + correct cfgeconomycore format + usages in
   cfglimitsdefinition.xml basis).
2. Restart server (safe kill — see §11; do NOT let `kill` take your own terminal).
3. Wait **≥15 minutes** after `Player connect enabled` appears in the RPT.
4. Measure `dynamic_*.bin` total bytes (above). If total > ~5000 and ≥8 bins >100b →
   **LOOT IS SPAWNING. DONE.** Do not touch config further.
5. ONLY if bins stay at ~1900 after 20+ min → config is genuinely broken; go back to
   §6 / §9 diagnostic sequence (but you would also see `885 classes` / `0 root classes`
   in `[CE][TypeSetup]`, not `5252`, which is the real tell).

**Hard rule:** `dynamic groups: 0` at boot ≠ no loot. `TypeSetup :: 5252 classes` + bins
growing past 5KB = success. Report the BIN BYTE COUNT, not the boot-line guess.

## 8. Live Deploy + Operations (DayZ Server under Wine/Linux)

The loot build is useless until it's live AND the server boots. Pattern that
worked (Apocalyps3nd 2026-07-17):

**Deploy (with backup + validator, per "no prod file without backup"):**
1. Pre-flight: back up existing live `db/types.xml`, `db/events.xml`,
   `mapgroupproto.xml` to `backups/pre_apocalyps3nd_<ts>/`.
2. Copy generated XMLs into `Server/mpmissions/dayzOffline.chernarusplus/db/`
   (types.xml replaces; ce/cfgspawnabletypes/cfgrandompresets/events/
   cfgeventgroups copied — they're often ABSENT live).
3. mapgroupproto extension already injected (verify 7 `APX_Underground_*`
   groups live).
4. Run `validate_deploy.py` (see scripts/) — checks live types.xml unique/count,
   CE rootclasses, distribution orphaned-refs, APX_Underground in map, T4
   exclusive. Exit 0 = deploy valid.

**Start script:** `start_server_apx.sh` (in Server/) — loads all 59 mods with
`@Apocalyps3nd_Loot` LAST (loot overlay), runs `validate_deploy.py` pre-flight,
then `wine DayZServer_x64.exe ... -noLauncher`. Mod-list MUST include
`@Apocalyps3nd_Loot` or the build never loads.

**CRITICAL — isolate Wine/Proton crashes from build bugs.** If the server
dies before "Game server started" with a Wine/Proton page-fault, it is an ENV
problem, NOT your loot XML. Proof technique: boot a minimal mod set (ONLY
`@CF;@VanillaPPMap`, no loot build); if it crashes the SAME way, the build is
exonerated. Don't burn time "fixing" types.xml for a segfault.

**Server launch via Faugus / GE-Proton (NOT裸 wine).** Your DayZ CLIENT runs
under Faugus/GE-Proton (`WINEPREFIX=/home/alca/Faugus/default`,
`PROTONPATH=Proton-GE Latest`); the server must use the SAME prefix or it hits
the裸-wine crash. DayZ Server is NOT a Steam app, so launch via `umu-run`
directly with `WINEPREFIX` + `PROTONPATH` + `STEAM_COMPAT_DATA_PATH` set (see
`references/deploy-and-operations.md` for the exact `start_server_faugus.sh`).
NOTE: even under Faugus/GE-Proton the server can still segfault — see below.

**THE ZEN2 CPU CRASH (deterministic, survives Wine/Proton/Faugus/DXVK).**
DayZ 1.28 `DayZServer_x64.exe` (Dec 2025 build) crashes on AMD Ryzen 3800X
(Zen2) with `Exception code: C0000005 ACCESS_VIOLATION at 407F3580`,
`Fault code bytes: 48 3B 11 74 51 48 85 D2 74 28 48 8D 4A 08 B8 01`
(`CMP RAX,[RCX]` → `JE` → `TEST RDX,RDX` → `LEA RCX,[RDX+8]` = a C++ vtable
lookup with a NULL `this`). This crash is IDENTICAL across 5 configs (裸 wine
11.12, vanilla-only mods, `-noLauncher`+software, DXVK override, Faugus/GE-
Proton) — so it is a CPU/engine-binary incompat, NOT Wine/Proton. The Client
binary (`DayZ_x64.exe`, also 1.28) boots fine; only the Server binary segfaults
on Zen2. Fix paths: run the server on a Zen3+ host, use an older server binary
that targets Zen2, or QEMU-emulate a newer CPU. Do NOT keep swapping Wine/
Proton versions — the fault offset is invariant.

Full recipe + scripts: `references/deploy-and-operations.md`.

## Linked files
- `references/underground-t4-exclusive-fix.md` — the exclusivity trap + recipe
- `references/loot-economy-architecture.md` — 4-pillar deep dive + Säulen audit
- `references/inventory-technique.md` — full multi-mod inventory sweep method
- `references/deploy-and-operations.md` — live deploy + start_server + Wine-crash isolation
- `references/start-scripts-and-client-hang.md` — unified client/server start scripts, DXVK/client-hang fixes, process-kill trap, success criteria (companion to §9-§13)
- `references/ce-cache-null-loot.md` — the types.bin/events.bin cache-shadow trap: diagnosis (mtime + "Restoring file" RPT signature), reversible rename fix, red-herring gate for excluded-mod "Type does not exist" warnings
- `references/ce-directory-protonscript-paths.md` — THE real NULL-loot root cause: CE configs must live in mission-root `ce/` (not `db/`), DayZ under Proton path mapping, diagnosis order
- `references/rpt-diagnostic-walkthrough.md` — full end-to-end RPT read technique, the `0 root classes` smoking gun, the TWO real fixes (cfgeconomycore format + root location), success signature, red-herring gate
- `references/async-loot-spawn-measurement.md` — `dynamic groups: 0` is a RED HERRING at boot; loot spawns ASYNC ~15-20min later; measure `dynamic_*.bin` byte count (not the RPT boot line) as the real loot indicator
- `references/deploy-live-script.md` — the `@Apocalyps3nd_Loot/deploy_live.py` lawful deploy path; NEVER hand-patch the live tree; cfgeventspawns.xml merge requirement for APX DynEvents
- `references/deploy-merge-vs-replace-pitfalls.md` — MERGE vs REPLACE traps: events.xml/cfgeventspawns.xml/cfglimitsdefinition.xml must be REPLACE (merge destroys Vanilla baseline); types.xml must UNION Vanilla+Mod or server loads ~480 prototypes
- `scripts/inventory_sweep.py` — scan all @Mods types.xml → unique items/cats/tiers
- `scripts/loot_audit.py` — full audit loop (orphaned/escalation/dangling)
- `scripts/generate_apx_full.py` — MANIFEST → 7 XMLs generator (single source of truth)
- `scripts/validate_deploy.py` — pre-flight validator against LIVE config (exit 0=pass)
