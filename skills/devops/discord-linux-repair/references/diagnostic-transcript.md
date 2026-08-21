# Discord MODULE_NOT_FOUND — Worked Diagnostic (Arch, app-1.0.146)

## Symptom
Discord crashed on launch. Pasted stack (header truncated) ended in:
```
code: 'MODULE_NOT_FOUND',
requireStack: [
  '.../app-1.0.146/modules/discord_utils-1/discord_utils/index.js',
  '.../discord_desktop_core-1/discord_desktop_core/core.asar/bundle.js',
  '.../discord_desktop_core-1/discord_desktop_core/index.js',
  '.../resources/app.asar/bundle.js'
]
```

## Find the real missing module (no GUI needed)
The header `Cannot find module 'X'` was cut off. Reproduce it directly:
```
cd ~/.config/discord/app-1.0.146/modules/discord_utils-1/discord_utils
node -e "try{require('windows-notification-state')}catch(e){console.log(e.code, e.message.split('\n')[0])}"
# -> CODE: MODULE_NOT_FOUND
# -> MSG: Cannot find module 'windows-notification-state'
```
`discord_utils/index.js:8` does `require('windows-notification-state')` unconditionally at module load.

## Blast-radius check
```
grep -rhoE "require\('([^.][^']*)'\)" ~/.config/discord/app-1.0.146/modules | sort -u
```
Non-core bare requires found: `cld` (discord_spellcheck), `windows-notification-state` (discord_utils), `ws` (discord_rpc). None had a backing `node_modules` dir anywhere → whole payload extraction was incomplete.

Distinguish: `discord_utils.node` (native) was PRESENT → so the failure is a missing *JS* dep, not an ABI issue (which would throw `NODE_MODULE_VERSION`).

## Why it wouldn't self-heal
- `/usr/bin/discord`: only re-downloads if `~/.config/discord/Discord` (symlink) is missing. It was live → relaunch re-execed the broken binary.
- `updater_bootstrap`: checked `installer.db` (recorded 1.0.146 as installed) → printed "Install Complete" and downloaded nothing, even after the payload dir was deleted.

## Fix applied
```
rm -f ~/.config/discord/Discord
mv ~/.config/discord/app-1.0.146 ~/.config/discord/app-1.0.146.broken
mv ~/.config/discord/installer.db ~/.config/discord/installer.db.bak
/usr/share/discord/updater_bootstrap --no-zenity ~/.config/discord stable https://updates.discord.com/
# -> Downloading Discord 0→100%, Installing 0→100%, "Install Complete", app-1.0.146 recreated
ln -sf ~/.config/discord/app-1.0.146/Discord ~/.config/discord/Discord
```

## Verification (real output)
```
require('windows-notification-state') -> OK   (notificationstate.node present)
require('cld')                         -> OK
require('ws')                          -> OK  (discord_rpc fetched at runtime during smoke test)
```
Smoke launch stayed up 12s, made live CDN calls (HTTP 200), no MODULE_NOT_FOUND in any *current* log. Pre-fix "Cannot find module" lines in `renderer_js.log` were dated July 10/11 (historical).

## Cleanup
Removed the 516 MB `app-1.0.146.broken`. Left `installer.db.bak` (151 KB, harmless, deletable).

## pkill self-kill trap
`pkill -f 'app-1.0.146/Discord'` killed the shell itself (pattern matched its own cmdline).
Fix: `pgrep -x Discord` → PIDs → `kill -9 <pids>`, or `pkill -x Discord` (matches comm, not cmdline).
