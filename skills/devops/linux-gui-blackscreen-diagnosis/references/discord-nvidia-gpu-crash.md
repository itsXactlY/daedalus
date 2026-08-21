# Case: Discord blackscreen — NVIDIA + Electron GPU-process crash

## Environment
- OS: Garuda Linux (Broadwing), kernel 7.1.3-zen1-2-zen
- WM: i3, X11 (DISPLAY=:0, no Wayland)
- GPU: NVIDIA GeForce RTX 4060 Ti, driver 610.43.03
- App: Discord 1.0.146 (native /usr/bin/discord script), Electron 37.6.0, Chrome 138.0.7204.251
- Launch path: launcher → /usr/bin/discord

## Symptom
Discord window opens but is a flat dark-grey void (~30 luminance, stdev ~0). No UI,
no login, no text. Process stays alive; window present. `xwininfo` confirms a window exists.

## Root cause (from the app's OWN Sentry fatal report in the log)
```
"gpu": {"name":"GPU","active":true,"id":"0x2803","vendor_id":"0x10de","driver_version":"610.43.03"},
"crashpad.LOG_FATAL":"gpu_data_manager_impl_private.cc:415: GPU process isn't usable. Goodbye.\n"
```
The Electron GPU process crashes on launch under this NVIDIA driver. With hardware
acceleration ON, the renderer never paints → blackscreen.

## Red herrings ruled out
- TLS `net_error -200` / `Time is after notAfter` in log → only the
  `error-reporting-proxy/web` telemetry endpoint. Main `discord.com` cert valid
  (notBefore 2026-06-30, notAfter 2026-09-28); `curl -sS -I https://discord.com`
  returns HTTP/2 200. NOT the cause.
- `Cannot find module 'windows-notification-state'` → harmless Windows-only module
  warning, unrelated to rendering.

## Fix (proven working)
1. Wrapper `~/.local/bin/discord` (user-owned; `~/.local/bin` precedes `/usr/bin`
   in PATH, so it intercepts every PATH-based launch):
   ```sh
   #!/bin/sh
   exec /usr/bin/discord --disable-gpu --disable-gpu-compositing "$@"
   ```
   `chmod +x ~/.local/bin/discord`.
2. Desktop override `~/.local/share/applications/discord.desktop` (user-local beats
   the system file; the system `/usr/share/applications/discord.desktop` hardcodes
   `/usr/bin/discord` and would bypass the wrapper):
   ```
   Exec=discord --url -- %u
   ```
   (PATH-resolved → uses the wrapper.)
3. Harmless extra: `"enableHardwareAcceleration": false` in
   `~/.config/discord/settings.json` — NOT sufficient alone (see pitfalls).

## Verification
- `grep -c "GPU process isn't usable" /tmp/discord_wrap.log` → 0 (was 1 without wrapper).
- `python3 scripts/check_window_render.py --class discord` →
  mean_lum 151, stdev 94, bright 10095/19968, black 125 → RENDERED.

## Trade-off
Software rendering instead of GPU → slightly higher CPU on scroll, but stable.
Restoring GPU accel properly would require fixing the NVIDIA/EGL/vaapi crash path
(deeper rabbit hole); `--disable-gpu` is the standard accepted fix.
