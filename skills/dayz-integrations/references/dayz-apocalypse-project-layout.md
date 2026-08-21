# Apocalypse / VanillaPPMap Project Layout

Where the DayZ mod source, scripts, PBOs, and the canonical start script live on this box.
Read this BEFORE launching or editing anything DayZ-server related.

## Canonical entrypoint (USE THIS, never self-assemble)

- **Build + start:** `/home/alca/apogrps_qwen/Apocalypse/build_and_start.sh`
  - Builds `@Apocalypse` + `@Apocalypse_Server` PBOs from `apogrps_qwen/Apocalypse/`
    via the `pbo` tool in the `dayz_dev_tools` venv (`/home/alca/projects/.btq/bin/activate`).
  - Starts the server with `STEAM_COMPAT_DATA_PATH=/home/alca/.local/share/Steam/steamapps/compatdata/221100`
    and `PROTON_PATH=/home/alca/.local/share/Steam/steamapps/common/Proton - Experimental/proton`.
  - 59-mod list (full stack) — do not trim unless debugging.
- **Minimal debug launcher:** `/home/alca/games/DayZ/Server/!START_Server_debug.bat`
  - 5 mods (`@CF;@Dabs Framework;@Dogtags;@CarCover;@VanillaPPMap`) + 3 server mods.
  - Runs under SYSTEM wine (`~/.wine`), NOT Proton. Booted the engine-load successfully and
    failed only at script compile — proof the engine itself is fine on this box.

## Source tree

- **Mission scripts:** `/home/alca/apogrps_qwen/Apocalypse/scripts/4_World/`
  - `VPPWebhookManager.c`, `GroupServerManager.c`, `VPPChatManager.c`, etc.
  - Crash-log path `Apocalypse/scripts/4_World/vppwebhookmanager.c(99)` resolves HERE.
  - NOTE the filename casing: it's `VPPWebhookManager.c` (capital), not `vppwebhookmanager.c`.
- **Client mod dest:** `/home/alca/games/DayZ/Mods/@Apocalypse/addons/Apocalypse.pbo`
- **Server mod dest:** `/home/alca/games/DayZ/Mods/@Apocalypse_Server/addons/Apocalypse_Server.pbo`

## Deployed / live config (ground truth for loot)

- **Live mission:** `/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus/`
  - `db/types.xml` — the FULL item list (5000+ items across all mods). Crawl THIS for inventory,
    not a single mod's types.xml.
  - `db/cfgeconomycore.xml`, `db/cfgspawnabletypes.xml`, `db/cfgrandompresets.xml`,
    `db/events.xml`, `db/cfgeventgroups.xml` — the 4 spawn pillars + CE.
  - `mapgroupproto.xml` — MapGroups (incl. the `APX_Underground_*` T4 zones). Lives in the
    MISSION, not in a mod PBO. Inject here with a backup.
- **Deployed PBOs:** `/home/alca/games/DayZ/Mods/@<Mod>/addons/*.pbo`

## Why you must NOT self-assemble a launcher

Session 2026-07-17: the agent wrote `start_server.sh` / `start_server_apx.sh` /
`start_server_faugus.sh`, each re-deriving mod lists + Proton paths. They all crashed with the
wrong Proton flavor / prefix and wasted the whole session. The operator said:
"darüber starten, und sonst gar nicht!" (use the project's script) and "nimm proton wo da ist!"
(use the Proton already installed, don't invent `Proton-GE Latest`). The project's
`build_and_start.sh` is the only correct entrypoint. If you must launch, run THAT in the
background and poll `server_startup.log` + `profile/*.RPT`.

## The two-crash distinction (do not conflate)

1. **`0x60` page fault** (`Exception code: C0000005`, address `1407F3580`, Exit 5) — engine
   never loads. DayZ SERVER binary on Zen2 (Ryzen 3800X). See `dayz-server-zen2-crash.md`.
2. **`Can't compile "World" script module! ... VPPWebhookManager.c(99): Broken expression`** —
   engine LOADED, a real EnforceScript compile error in the script source. Fix the `.c` in
   `apogrps_qwen/Apocalypse/scripts/4_World/`, rebuild the PBO via `build_and_start.sh`.

If you see BOTH in different runs, they are separate problems — solve the page fault first
(server won't reach compile until it boots), then the script error.
