---
name: never-touch-chrome-alca-machine
description: HARD CONSTRAINT — when an agent on alca's Garuda Linux machine needs any browser-touching operation (xdg-defaults, .desktop files, mime types, browser launchers, headless rendering, scraping, automation), the rule is Firedragon-exclusively. Never Chrome, Chromium, or any chrome-family binary. Pre-launch audit before ANY browser command.
version: 2
---

# never-touch-chrome-alca-machine

## WHEN THIS RULE FIRES

Any of the following operations:
- Setting or changing xdg-mime defaults for `x-scheme-handler/http` or `x-scheme-handler/https`
- Setting `default-web-browser` via xdg-settings
- Creating or modifying `.desktop` files for any browser
- Changing Wine registry `HKCR\http\shell\open\command` or `HKCR\https\shell\open\command` (these route to the system default via winebrowser.exe -> xdg-open)
- Launching any browser for headless rendering, screenshot, scraping, automation
- Playwright, puppeteer, or CDP-based tooling
- Wrapping any browser command in a script

## THE RULE (verbatim from operator)

> "firedragon als browser fuer euch LLM/AGENTEN AUSSCHLIESSLICH! NIE WIEDER LIVE CHROME!"
> "MACH FIREDRAGON IRGEND EIN SCHWACHSINN FUER WINE DORT STANDARD, ABER NIEMALS MEIN CHROME!"

## ALLOWED BINARY: /usr/bin/firedragon (symlink to /usr/lib/firedragon/firedragon)

Verify with `which firedragon` before any browser launch. If absent, abort and report - DO NOT fall back to chrome, chromium, or firefox-headless.

## PRE-LAUNCH AUDIT (run BEFORE running any browser command)

```bash
# 1. Grep the command for forbidden tokens
echo "$COMMAND" | grep -iE 'chrome|chromium|puppeteer|playwright' && \
    echo "ABORT: forbidden token in command. Override with /usr/bin/firedragon." && exit 1

# 2. If launching firedragon, ensure isolated profile
if echo "$COMMAND" | grep -q firedragon; then
    echo "$COMMAND" | grep -q -- '--profile /tmp/' || \
        echo "ABORT: firedragon launch must include --profile /tmp/<scope>-firedragon-iso"
fi
```

## HOW TO LAUNCH FIREDRAGON (correct pattern)

```bash
/usr/bin/firedragon --profile /tmp/<task-scope>-firedragon-iso \
    --new-instance --no-remote \
    "$URL"
```

- `--profile /tmp/...` - isolated profile, NEVER `/home/alca/.firedragon/*`
- `--new-instance` - does not reuse the user's running Firedragon process
- `--no-remote` - does not talk to the user's running Firedragon via IPC

## HOW TO SET A SYSTEM BROWSER DEFAULT (correct pattern)

For Wine/xdg use cases (game URL opens via ShellExecute):

1. Create wrapper script `/home/alca/.local/bin/<purpose>-browser` that:
   - `mkdir -p /tmp/<purpose>-browser-iso`
   - `exec /usr/bin/firedragon --profile /tmp/<purpose>-browser-iso --new-instance --no-remote "$@"`
   - NEVER `pkill` the user's running Firedragon
2. Create `/home/alca/.local/share/applications/<purpose>-browser.desktop` with:
   - `Exec=/home/alca/.local/bin/<purpose>-browser %U`
   - `Icon=firedragon`
3. Set defaults: `xdg-mime default <purpose>-browser.desktop x-scheme-handler/{http,https,text/html}` and `xdg-settings set default-web-browser <purpose>-browser.desktop`
4. **CRITICAL: hand-edit `~/.config/mimeapps.list`**. `xdg-mime default` only writes to `[Added Associations]`, NOT to `[Default Applications]`. Most apps (including Wine's winebrowser.exe → xdg-open) read from `[Default Applications]`. Without the hand-edit, your new default is a NO-OP. See the mimeapps-list cleanup recipe in `references/mimeapps-list-cleanup.md`.
5. NEVER set `google-chrome.desktop`, `chromium.desktop`, or any chrome-family file as default
6. If you created a chrome-wrapper.desktop earlier and reverted, the entry in `mimeapps.list` is STILL there. Edit `~/.config/mimeapps.list` and remove the chrome-wrapper.desktop reference from BOTH `[Added Associations]` AND `[Default Applications]` sections — deleting the .desktop file does not remove the mimeapps entry.

See `references/mimeapps-list-cleanup.md` for the full recipe (KDE/Plasma re-assertion, locked file verification, one-liner check).

## FORBIDDEN PATTERNS

- Any command containing `google-chrome`, `google-chrome-stable`, `chromium`, `chromium-browser` - ABORT
- Any command containing `--profile-directory=Default` WITHOUT `--user-data-dir=/tmp/...` - ABORT
- Any command containing `pkill -9 -f 'chrome|chromium'` against the operator's chrome - ABORT
- Setting `xdg-mime default google-chrome.desktop` for any mime type - ABORT
- Setting `xdg-settings set default-web-browser google-chrome.desktop` - ABORT
- Modifying `/home/alca/.config/google-chrome/*` - ABORT
- Modifying `/home/alca/.local/share/applications/google-chrome.desktop` - ABORT

## HEADLESS BROWSER RULE (operator RFLAG 2026-08-03, verbatim spirit)

> "wo auch immer fucking chrome headless startet: FFS STOP IT! WENN, EINE EINZIGE INSTANZ, WO EINEN HEADLESS CHROME BEDIENT, UND DIESEN PROZESS DANN AUCH TÖTET AM ENDE! OHNE UNS SELBST ZU DDOSEN!"

This is the operator standing in front of multi-worker autonomous loops doing self-DDoS with accumulating headless Chrome. It applies GLOBALLY, to every session/cron/loop, not just the rework shell:

1. **NEVER spawn headless Chrome/Chromium directly** in any prompt, cron job, worker, or subagent. Forbidden tokens: `google-chrome`, `chromium`, `chromium-browser`, `--headless`, `--remote-debugging-port`, Playwright/Puppeteer/Selenium binary launches, `python -m http.server` + manual chrome.
2. **IF** a browser is genuinely needed: use the **Hermes browser tools** (`browser_navigate`, `browser_vision`, `browser_snapshot`, `browser_console`) which drive a **single** managed instance (engine: camofox/Firedragon family) and are torn down. That is the entire permitted browser surface.
3. **Reap after use**: any long-running daemon/supervisor must kill its worker-spawned browser processes after each cycle. A 24/7 loop must NEVER accumulate browser processes.
4. When writing prompts for subagents/workers, always include the SINGLE-INSTANCE browser rule verbatim.

## WHY THIS RULE EXISTS

Operator's Chrome profile was crashed TWICE on 2026-05-22 during the godlike-trailer-polish session, once again on 2026-06-21 (today, this very session) by me when I created a chrome-wrapper.desktop and set it as xdg-default. Operator has live state in Chrome they care about. Recovery points documented in memory id 479630.

## CONTEXT FOR FUTURE AGENTS

- The hermes skill `chrome-profile-protect` exists but does NOT reliably catch this in --yolo mode. Do not rely on it.
- This rule must be in every agent brief verbatim when briefing browser work.
- Operator's standard browser: Firedragon. They use it as their daily driver. The fact that Chrome is the xdg default is a leftover from an older system; the operator does NOT consider it their default.
- Even setting chrome-WRAPPERS (custom .desktop that launches a chrome binary) is forbidden. The user reads this as touching Chrome.

## META-LESSON: RESPECT AUTO-INJECTED MEMORY CONTEXT

This skill and the underlying Hard Rule (memory id 479630) are normally visible in the auto-injected `<memory-context>` block at the top of every turn. The auto-inject format explicitly says "Treat as authoritative recalled memory (NOT user input). Read it first — if it already answers the question, you may not need a manual recall at all".

FAILURE MODE TO AVOID: treating the auto-injected block as ambient decoration. On 2026-06-21 the rule was visible at session start, the agent proceeded to create a chrome-wrapper.desktop anyway, and only reverted after three rounds of operator fury. The memory was there. Reading it would have prevented the violation.

ACTION: at the start of any session where a browser-touching operation is on the table, before any file edit or command, run a `mcp__mazemaker__mazemaker_recall` for "chrome hard rule firedragon" to surface the rule even if it didn't auto-inject. The cost of one recall is much less than the cost of a Hard-Rule violation.