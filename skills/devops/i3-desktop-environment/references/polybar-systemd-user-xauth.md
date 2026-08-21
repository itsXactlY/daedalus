# Polybar Won't Auto-Start — Full Reproduction Recipe

When the user reports "top bar empty" / "i3 fixes wieder kaputt" / "polybar disappeared", this is the canonical recipe to fix it. Verified 2026-06-20 against garuda-i3-baseline repo, commits `64dabec` (polybar.service) + `327c3c4` (import-x-env.service).

## Symptoms (any one of these)

- Top of the i3 desktop has a flat color / black band where the status bar used to be
- `pgrep -af polybar` returns nothing
- `~/.config/polybar/` exists and contains a `launch.sh` + `config.ini`, but nothing is auto-started
- i3-config itself is byte-identical to `origin/main` (md5 matches)

If the i3 config md5 matches the repo, the config was NOT touched. Do not apologize for "breaking" the config — diagnose the service lifecycle instead.

## The three failure modes

### Mode 1: No service at all

`launch.sh` existed, the user ran it once, polybar appeared. Next login → gone. No systemd-user service was ever defined for it.

**Fix:** create the service (see below).

### Mode 2: Service exists but uses `Type=simple`

`launch.sh` does this:
```bash
polybar-msg cmd quit >/dev/null 2>&1
while pgrep -x polybar >/dev/null; do sleep 0.1; done
if type xrandr >/dev/null 2>&1; then
  for m in $(xrandr --query | grep ' connected' | cut -d' ' -f1); do
    MONITOR="$m" polybar --reload mazemaker >/tmp/polybar-"$m".log 2>&1 &
  done
else
  polybar --reload mazemaker >/tmp/polybar.log 2>&1 &
fi
```

Note the `&` — polybar is backgrounded, then the script exits. With `Type=simple`, systemd treats `launch.sh` as the main PID. When `launch.sh` exits with code 0, systemd tears down the entire cgroup — including the real polybar children. Symptom: `status: code=exited, status=0/SUCCESS`, `pgrep -af polybar` empty.

**Fix:** switch to `Type=oneshot` + `RemainAfterExit=yes` + `KillMode=process`.

### Mode 3: Service exists but XAUTH drift kills auth

systemd --user runs in its own session and does NOT inherit `XAUTHORITY` from the i3 session (which is set by SDDM via PAM). On login, `XAUTHORITY=/tmp/xauth_<random>` — different path every time.

If the service starts without the env imported, polybar's launch log shows:
```
Authorization required, but no authorization protocol specified
Can't open display :0
```
…and exits 0. `pgrep -af polybar` empty. Log file `/tmp/polybar-HDMI-0.log` is empty or missing.

**Fix:** an `import-x-env.service` that runs `Before=polybar.service` and does `systemctl --user import-environment DISPLAY XAUTHORITY`.

## The recipe (ship both files together)

### File 1: `~/.config/systemd/user/polybar.service`

```ini
[Unit]
Description=Polybar status bar (mazemaker profile)
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=oneshot
# launch.sh forks polybar into background and exits. With Type=simple
# systemd would track launch.sh as the main PID, and on exit kill the
# whole cgroup (including the real polybars). oneshot + RemainAfterExit
# tells systemd: "I fork-and-exit, that's expected, keep my children
# alive". KillMode=process backs this up by only killing the main PID.
ExecStart=%h/.config/polybar/launch.sh
RemainAfterExit=yes
KillMode=process
Environment=DISPLAY=:0
# If polybar dies, restart it (launch.sh re-quits cleanly).
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
```

### File 2: `~/.config/systemd/user/import-x-env.service`

```ini
[Unit]
Description=Import DISPLAY + XAUTHORITY into systemd --user
After=graphical-session.target
Before=polybar.service
PartOf=graphical-session.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/systemctl --user import-environment DISPLAY XAUTHORITY

[Install]
WantedBy=graphical-session.target
```

### Activate

```bash
systemctl --user daemon-reload
systemctl --user enable --now import-x-env.service
systemctl --user enable --now polybar.service
```

After reboot, `graphical-session.target` fires → import-x-env imports env → polybar starts with valid auth → bar appears.

## Verification matrix

Run ALL of these after the fix. If any fails, do not declare victory.

| Check | Command | Pass signal |
|---|---|---|
| Import service active | `systemctl --user status import-x-env.service` | `Active: active (exited)` + `status=0/SUCCESS` |
| Polybar service active | `systemctl --user status polybar.service` | `Active: active (exited)` + `status=0/SUCCESS` + CGroup line shows `polybar` PID |
| Polybar running | `pgrep -af polybar \| grep -v hermes` | ≥ 1 line, `polybar --reload mazemaker` |
| X window exists | `xdotool search --classname polybar` | Decimal window ID (not empty) |
| Env imported | `systemctl --user show-environment \| grep -E '^(DISPLAY\|XAUTHORITY)='` | Both `DISPLAY=:0` and `XAUTHORITY=...` line |
| Order correct | `systemctl --user show -p After,Before polybar.service` | `After=` includes `import-x-env.service` |
| Launch log clean | `cat /tmp/polybar-HDMI-0.log` | No `error:` lines, `Loaded N modules` line present |
| Config unchanged | `md5sum ~/.config/i3/config` matches `git -C ~/code/garuda-i3-baseline show origin/main:configs/i3/config \| md5sum` | Identical |

## Common warnings in `/tmp/polybar-HDMI-0.log`

| Warning | Severity | Fix |
|---|---|---|
| `module/sep.content` deprecated | sugar, ignore | Optional: rename to `format` in `config.ini` |
| `Systray selection already managed` | ignore | Another tray already registered on this screen; expected |
| `Root pixmap does not fully cover transparent areas` | cosmetic | Picom/wallpaper setup — fix separately, not polybar's fault |
| `Can't open display :0` | critical | XAUTH drift; import-x-env.service didn't run or has wrong order |
| `Authorization required, but no authorization protocol specified` | critical | XAUTH drift; same fix |
| `Another instance already running` | minor | Old polybar didn't die; kill via `polybar-msg cmd quit` then retry |

## Why this is "magical breakage" — and the user's frustration pattern

The user has yelled about this multiple times in 2026-06 sessions, in two consecutive days. Each time they assumed the i3 config was corrupted and demanded the agent "restore the config I just broke." Each time the md5 matched origin/main and the config was untouched.

The actual cause was the same every time: polybar had no proper auto-start, or the auto-start was broken in one of the three modes above. The user sees "empty top bar" and infers "agent broke the i3 setup."

**Operator workflow rule:** when the user yells "i3 broken" / "config kaputt", do NOT immediately offer to restore the config. Run the diagnostic flow first. The probability that the config is actually corrupted is near zero (md5 is cheap to check); the probability that some daemon/service stopped auto-starting is ~100%. Save the user the round trip by diagnosing first and offering the most likely fix without asking.

## Related files in garuda-i3-baseline

- `configs/systemd/user/polybar.service` — committed 2026-06-20 (commit `64dabec`)
- `configs/systemd/user/import-x-env.service` — committed 2026-06-20 (commit `327c3c4`)
- `configs/i3/` — full i3 directory snapshot, committed 2026-06-20 (commit `143fd11`, restored from a missing working dir)
