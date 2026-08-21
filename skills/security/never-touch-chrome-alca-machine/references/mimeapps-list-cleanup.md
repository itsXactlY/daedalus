# mimeapps.list Cleanup Recipe (Chrome removal)

When a chrome-touching mistake has been made and reverted, the revert is INCOMPLETE. The `.desktop` file can be deleted, the registry can be reset, but the entries in `~/.config/mimeapps.list` persist. Until they are removed, the chrome binary is still in the lookup chain that xdg-open and Wine's winebrowser.exe follow.

## Symptoms of incomplete revert

- `xdg-mime query default x-scheme-handler/https` returns `google-chrome.desktop` even after you deleted the chrome-wrapper.desktop file
- Clicking a link in a Wine app still triggers a Chrome launch attempt (which may or may not crash)
- New chrome-wrapper.desktop files keep appearing in `~/.local/share/applications/` (KDE/Plasma auto-recreates them in some setups)

## Step-by-step cleanup

1. **Delete all chrome-family .desktop files** you created:
   ```bash
   rm -f ~/.local/share/applications/chrome-wrapper.desktop
   rm -f ~/.local/share/applications/google-chrome.desktop  # only if YOU created it
   # DO NOT delete /usr/share/applications/google-chrome.desktop — that's a system file
   ```

2. **Hand-edit `~/.config/mimeapps.list`**. The file has TWO sections:
   - `[Added Associations]` — the "I have a preference" list (where `xdg-mime default` writes)
   - `[Default Applications]` — the "actually use this" list (where `xdg-mime query default` reads)

   For each of these mime types: `x-scheme-handler/http`, `x-scheme-handler/https`, `x-scheme-handler/about`, `x-scheme-handler/unknown`, `text/html`:
   - In BOTH sections, remove any `google-chrome.desktop`, `chrome-wrapper.desktop`, or `chrome.desktop` reference
   - Put the Firedragon-based `wine-browser.desktop` (or your actual default) FIRST in the list

3. **Verify both sections are clean**:
   ```bash
   grep -E "google-chrome|chrome-wrapper|chromium" ~/.config/mimeapps.list
   # Should return nothing
   ```

4. **Verify defaults**:
   ```bash
   xdg-mime query default x-scheme-handler/https   # should be your wrapper, not chrome
   xdg-mime query default x-scheme-handler/http
   xdg-settings get default-web-browser
   ```

5. **Optional: lock the file** if the desktop environment keeps re-asserting Chrome:
   ```bash
   chattr +i ~/.config/mimeapps.list  # needs root; reverts require chattr -i
   ```

## Why xdg-mime default is not enough

`xdg-mime default <X>.desktop <mime>` appends `X.desktop` to the `[Added Associations]` list, AFTER the existing entries. If `[Added Associations]` already has `google-chrome.desktop;...`, your new default is added AFTER Chrome. Worse, if `[Default Applications]` has Chrome and you never touch that section, `xdg-mime query default` keeps returning Chrome forever.

The only way to make the new default actually take effect is to edit BOTH sections by hand and put your new entry FIRST.

## KDE / Plasma-specific gotchas

- KDE's "Default Applications" system-settings panel can silently re-assert Chrome after a chrome-wrapper.desktop was used. After a cleanup, open System Settings → Default Applications and re-set the browser manually to Firedragon.
- `kde-cli-tools` or `kde-config-fcitx5` (or other KDE components) sometimes auto-rewrite mimeapps.list on logout/login. If the chrome entry reappears after a reboot, repeat the cleanup.

## Verification command (one-liner)

```bash
{
  echo "=== DEFAULTS ==="
  xdg-mime query default x-scheme-handler/https
  xdg-mime query default x-scheme-handler/http
  xdg-mime query default text/html
  xdg-settings get default-web-browser
  echo "=== CHROME-REFS IN MIMEAPPS ==="
  grep -cE "google-chrome|chrome-wrapper|chromium" ~/.config/mimeapps.list
  echo "=== CHROME .DESKTOP FILES ==="
  ls -la ~/.local/share/applications/ | grep -iE "chrome|chromium" || echo "none"
  echo "=== FIREDRAGON BINARY ==="
  which firedragon && ls -la $(which firedragon)
} 2>&1
```

The grep should return 0, the xdg-mime should NOT return anything containing "chrome", the ls should return "none".
