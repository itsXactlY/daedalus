---
name: linux-gui-blackscreen-diagnosis
description: Diagnose and fix black/blank/frozen GUI application windows on Linux (X11/Wayland). Covers the OBJECTIVE verification method (screenshot + window-geometry crop + PIL pixel statistics) that does NOT depend on unreliable vision models, plus the common Electron/NVIDIA GPU-process-crash root cause and its --disable-gpu fix.
---

# Linux GUI Blackscreen Diagnosis

## Trigger conditions
- User reports a black screen, blank window, "app opens but shows nothing", grey void, or frozen/empty GUI on Linux.
- Electron-based apps (Discord, Slack, VS Code, Signal, Element, etc.) showing a black window, especially on NVIDIA GPUs.
- Any "why is <GUI app> just a black box" question.

## Why this skill exists
Vision/multimodal models **hallucinate** on screenshots of broken GUIs. In a real case the model invented a "Google search / Vivaldi registration" page over a Discord blackscreen — confidently, and wrong. You CANNOT trust `vision_analyze` to tell you whether a window rendered. The reliable signal is **pixel statistics**.

## Steps
1. **Is it even running?** `ps aux | grep -i <app>`. Identify WM/compositor: `echo $DISPLAY $WAYLAND_DISPLAY`, `ps aux | grep -iE "i3|sway|kwin|kde"`. Note X11 vs Wayland — the tooling below is X11 (`maim`/`xdotool`).
2. **Find the app's own crash signal.** Launch with `--enable-logging --v=1` (Electron) and grep the log for `fatal`, `crash`, `GPU process isn't usable`, `Sentry`. The app's own error report is often the root-cause smoking gun.
3. **Rule out network/cert causes** (don't assume GPU). `curl -sS -I https://<app-domain>` and `openssl s_client -connect <domain>:443 | openssl x509 -noout -dates`. A cert error to a *telemetry* endpoint is usually a red herring — verify the MAIN domain cert is valid before blaming TLS.
4. **OBJECTIVE render check — do NOT use vision.** Use the bundled `scripts/check_window_render.py`:
   - `python3 scripts/check_window_render.py --class <wmclass>` → reports `mean_lum`, `stdev`, `bright`, `black`, `verdict`.
   - `BLACKSCREEN (flat void)` = stdev < 8 and zero bright samples (uniform fill, UI never painted).
   - `RENDERED` = stdev > 25 (real content: text, avatars, varied luminance).
   - Under the hood: `xdotool search --class` → pick LARGEST WID (ignore 10x10 splash/hidden windows) → `maim -g WxH+X+Y` → PIL luminance histogram.
5. **Identify root cause** from the log + verdict. Most common on Linux/NVIDIA: Electron GPU process crashes → blackscreen. Others: missing libs, Wayland incompatibility, broken theme.
6. **Apply the fix for the cause.** For an Electron GPU crash:
   - Launch with `--disable-gpu` (add `--disable-gpu-compositing` too).
   - NOTE: the in-app / `settings.json` `enableHardwareAcceleration: false` toggle is **ignored** by many Electron builds for the GPU process — the flag is REQUIRED.
   - To persist across ALL launch paths, wrap the binary: put a script at `~/.local/bin/<app>` (precedes `/usr/bin` in PATH) that execs `/usr/bin/<app> --disable-gpu "$@"`. Also override the system `.desktop` at `~/.local/share/applications/<app>.desktop` with `Exec=<app> --url -- %u` (PATH-resolved) because the system `.desktop` hardcodes `/usr/bin/<app>` and bypasses the wrapper.
7. **Verify the fix end-to-end.** Relaunch via the REAL launch path (plain `<app>`, no manual flags) so you exercise the wrapper. Re-run `check_window_render.py`. Fixed = `verdict: RENDERED` AND GPU-fatal-crash count 0 in the log.

## Pitfalls
- **Never trust vision_analyze for blackscreen diagnosis.** It will confidently describe content that isn't there. Pixel math is the truth.
- **Crop to the real window, not the full screen.** Desktop wallpaper contaminates full-screen luminance samples (a bright wallpaper reads as "rendered" even when the app is minimized behind it).
- **Minimized windows lie.** If the app launched minimized, your crop catches the wallpaper → false "bright/rendered" reading. Make the window visible (maximize/focus) or rely on `xdotool` geometry of the largest WID.
- **settings.json toggle != fix.** `enableHardwareAcceleration:false` alone did NOT stop the GPU crash on Discord 1.0.146 / Electron 37. Use the `--disable-gpu` flag.
- **Multiple windows share the WM class.** Discord spawns 3 `discord`-class windows (2 are 10x10 hidden). Always pick the largest by area.

## Verification
- `check_window_render.py` verdict flips `BLACKSCREEN` -> `RENDERED`.
- App log shows 0 occurrences of `GPU process isn't usable` / fatal GPU crash after the fix.

## References
- `references/discord-nvidia-gpu-crash.md` — full worked case (Discord 1.0.146, RTX 4060 Ti, driver 610.43.03, i3/X11, Garuda Linux): symptom, log excerpt, wrapper files, trade-off.

## Support files
- `scripts/check_window_render.py` — deterministic pixel-analysis probe; classifies a window as BLACKSCREEN vs RENDERED.
