---
name: discord-linux-repair
description: Diagnose and repair a broken/crashing Discord desktop app on Linux (Arch and other distros) — especially Electron MODULE_NOT_FOUND crashes caused by an incomplete payload extraction. Covers the /usr/bin/discord launcher gate, the updater_bootstrap installer.db gate, the non-GUI node require-repro, and the pkill self-kill trap.
---

# Discord Linux Repair

## When to use
- Discord crashes on launch with `Error: Cannot find module 'X'` / `MODULE_NOT_FOUND` in a requireStack rooted at `~/.config/discord/app-*/modules/...`.
- Discord won't start after an update; the payload under `~/.config/discord/app-<ver>` is missing files (e.g. `node_modules` dirs inside the module folders).
- A `MODULE_NOT_FOUND` for a JS dependency (`windows-notification-state`, `cld`, `ws`, …) — NOT a native `.node` ABI mismatch.

## How Discord's payload works (Arch / official tarball)
- The pacman `discord` package is a thin launcher: `/usr/bin/discord` execs the binary at `~/.config/discord/Discord` (a symlink → `~/.config/discord/app-<ver>/Discord`, often wrapped by `~/.local/bin/discord` with `--disable-gpu` for NVIDIA).
- The real app payload lives in `~/.config/discord/app-<ver>/` and is downloaded/extracted by `/usr/share/discord/updater_bootstrap` on first run / update. The ~2 MB pacman tarball contains only the launcher + bootstrap, NOT the ~200 MB app.
- Each module under `app-<ver>/modules/<name>-1/<name>/` may ship its own `node_modules/` for external deps (`discord_utils/node_modules/windows-notification-state`, `discord_spellcheck/node_modules/cld`). Discord also lazy-downloads "optional" modules (`discord_rpc`, `discord_krisp`, …) at first runtime launch.
- User data (login tokens, settings) lives OUTSIDE `app-<ver>/` (in `Local Storage`, `Cookies`, `Preferences`). Moving the payload is safe and non-destructive to the session.

## Diagnostic procedure
1. Reproduce the missing module WITHOUT launching the GUI. Pasted stacks usually truncate the `Cannot find module 'X'` header — find the real name:
   ```
   cd ~/.config/discord/app-<ver>/modules/discord_utils-1/discord_utils
   node -e "try{require('windows-notification-state')}catch(e){console.log(e.code, e.message.split('\n')[0])}"
   ```
   `MODULE_NOT_FOUND` = JS dep missing. A `NODE_MODULE_VERSION` / "compiled against a different Node.js version" error = native `.node` ABI mismatch (different problem — this skill's re-download fix does NOT address that).
2. Enumerate ALL bare (external) requires to see the full blast radius:
   ```
   grep -rhoE "require\('([^.][^']*)'\)" ~/.config/discord/app-<ver>/modules
   ```
   Core modules (`util`, `fs`, `path`, `child_process`, `http`, `os`, `net`, `events`, `process`, `assert`, …) are fine. Anything else must resolve from a `node_modules` dir.
3. Confirm the missing backing dirs: `find ~/.config/discord/app-<ver>/modules -name node_modules`. If a required dep has no backing dir anywhere, the payload is incomplete. A single missing dep at module-load (top of the requireStack) crashes the whole app; fix the payload, not one module.

## The fix — force a clean re-download
Two gates stop a naive re-launch from repairing anything:

- **Symlink gate:** `/usr/bin/discord` only runs the bootstrap (download) if `~/.config/discord/Discord` is missing/non-executable. If the broken symlink is still present, relaunch just re-execs the broken binary → crash again.
- **installer.db gate:** `updater_bootstrap` checks `~/.config/discord/installer.db`. If it records `<ver>` as installed, bootstrap prints `Install Complete` and downloads NOTHING — even after you delete the payload dir. (It lies; trust the DB, not the message.)

```
set +e
rm -f ~/.config/discord/Discord                                       # drop symlink so launcher re-bootstraps
mv ~/.config/discord/app-<ver> ~/.config/discord/app-<ver>.broken     # backup, reversible
mv ~/.config/discord/installer.db ~/.config/discord/installer.db.bak   # clear the 'already installed' gate
/usr/share/discord/updater_bootstrap --no-zenity ~/.config/discord stable https://updates.discord.com/
# watch it actually DOWNLOAD 0→100% then "Install Complete"; app-<ver>/ reappears with node_modules
ln -sf ~/.config/discord/app-<ver>/Discord ~/.config/discord/Discord   # restore launcher symlink
```
- Pass `--no-zenity` so the bootstrap doesn't try to pop a GUI progress dialog in a non-interactive/agent context (the launcher auto-picks `--zenity` when stdout isn't a tty, which hangs headless).
- Remove the `.broken` backup only after verifying the fix (it can be several hundred MB).

## Verification
- Re-run the `node -e require(...)` repro for each previously-missing dep — should print `OK`.
- Smoke launch (bounded): `/usr/bin/discord --disable-gpu --disable-gpu-compositing >/tmp/discord_smoke.log 2>&1 &`, wait ~12 s, confirm the process is alive (`pgrep -x Discord`) and no NEW `MODULE_NOT_FOUND` / `Cannot find module` lines appear in `~/.config/discord/logs/`. Then kill the test instance (see Pitfalls). Optional modules get fetched during this first run — expected, not a regression.
- A reusable probe is shipped as `scripts/verify-discord-modules.sh`.

## Pitfalls
- **pkill self-kill trap (universal, not just Discord):** `pkill -f 'app-<ver>/Discord'` KILLS THE SHELL running it, because the pattern string appears in that shell's own command line, so `pkill -f` matches its own parent process. Always use `pgrep -x Discord` to list PIDs, then `kill -9 <pids>` by number — or `pkill -x Discord` (matches the process *name/comm*, not the cmdline, so it won't match bash). Never put the literal target path in a `pkill -f` pattern.
- **"Install Complete" is a lie:** if installer.db still says the version is installed, bootstrap reports success without downloading. Clear installer.db (move it) before re-bootstrapping.
- **Native vs JS:** a missing `.node` throws a *different* error (`NODE_MODULE_VERSION`). This skill's re-download fix targets missing *JS* deps / whole-payload corruption, not ABI mismatches (those need an Electron-version-matched rebuild).
- **Optional modules fetch at runtime:** a fresh payload may list fewer module dirs than a previously-broken one (e.g. no `discord_rpc` until first launch). That's normal — don't panic that modules "disappeared."

## Support files
- `references/diagnostic-transcript.md` — the real error, require-chain analysis, and the exact command sequence from a worked repair.
- `scripts/verify-discord-modules.sh` — re-runnable probe: greps every module for bare requires and tests each with node, reporting which (if any) still fail to resolve.
