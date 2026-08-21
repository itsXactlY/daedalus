# mimeapps.list Two-Section Gotcha

## Symptom

`xdg-mime default <X>.desktop <mime>` runs without error. But `xdg-mime query default <mime>` keeps returning the OLD default. The new entry never "takes".

## Why

`~/.config/mimeapps.list` has TWO sections:

```
[Added Associations]
x-scheme-handler/http=google-chrome.desktop;my-new.desktop;...

[Default Applications]
x-scheme-handler/http=google-chrome.desktop
```

- `xdg-mime default <X> <mime>` appends to the `[Added Associations]` section (the "I have a preference" list).
- `xdg-mime query default <mime>` reads the FIRST entry of the `[Default Applications]` section.
- These two sections are NOT automatically kept in sync. If `[Default Applications]` already has a different value, your new default is invisible to the rest of the system.

This is an XDG/MIME spec quirk, not a bug. Most desktop environments use the same logic. Both `xdg-open` and any app that calls into the MIME database (including Wine's winebrowser.exe) read from `[Default Applications]`.

## Fix recipe

Edit `~/.config/mimeapps.list` BY HAND. For each mime type you want to override, replace the line in BOTH sections. For chrome cleanup, also delete the chrome-wrapper.desktop references from BOTH sections (deleting the `.desktop` file does NOT remove the mimeapps entry — it leaves a dangling reference that some launchers still resolve to).

For the operator's case (C&C Generals Online, June 2026), the working diff was:

```
- x-scheme-handler/http=google-chrome.desktop;wine-browser.desktop;chrome-wrapper.desktop;firedragon.desktop;...
+ x-scheme-handler/http=wine-browser.desktop;firedragon.desktop;...

- x-scheme-handler/https=google-chrome.desktop;wine-browser.desktop;chrome-wrapper.desktop;firedragon.desktop;...
+ x-scheme-handler/https=wine-browser.desktop;firedragon.desktop;...

- text/html=google-chrome.desktop
+ text/html=wine-browser.desktop
```

And identical treatment in `[Default Applications]`.

## Verification

```bash
xdg-mime query default x-scheme-handler/https   # must show the new .desktop
xdg-mime query default x-scheme-handler/http
xdg-mime query default text/html
xdg-settings get default-web-browser
grep -c "google-chrome\|chrome-wrapper" ~/.config/mimeapps.list   # must be 0
```

## Why not just `xdg-settings set default-web-browser`?

`xdg-settings set default-web-browser` updates ONE field: the user's "default web browser" preference. It does NOT change the per-mime defaults in `mimeapps.list`. Most apps go through the per-mime default. So setting `default-web-browser` alone is usually insufficient.

Use BOTH: hand-edit mimeapps.list AND `xdg-settings set default-web-browser`.

## When the .desktop file is gone but mimeapps still references it

Symptoms: clicking a link opens nothing, or `xdg-open` errors with "no application knows how to open". `xdg-mime query default` still shows the removed file. Cause: stale entry in mimeapps.list.

Fix: edit mimeapps.list, remove the dangling reference. Or: `xdg-mime default <real-default>.desktop <mime>` — but this only fixes `[Added Associations]`, not `[Default Applications]`, so prefer the hand-edit.

## Related: `desktop-file-validate`

If a `.desktop` file is syntactically broken, xdg-mime silently ignores it. Validate:
```bash
desktop-file-validate ~/.local/share/applications/<x>.desktop
```
Exit 0 = OK, exit 1 = syntax error. Common breakage: missing `Type=Application`, malformed `Exec=` line, wrong MimeType syntax.

## Tooling note

Some distros' package managers (apt, dnf, pacman) overwrite mimeapps.list when installing browser packages. If a Chrome update keeps re-asserting itself as default, the fix is usually to lock the mimeapps.list file with chattr +i (root) or to set a "default" override in `~/.config/xdg-desktop-portal/portals.conf` if you're in a Flatpak context.
