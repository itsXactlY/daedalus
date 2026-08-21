# Mazemaker Hermes Bridge Troubleshooting for Android APKs

Use this when Mazemaker Mobile / a Hermes-integrated Android APK reports that it is not connected to the bridge, or when the phone times out against the bridge endpoint.

## Expected topology

```text
Android APK  ->  http://<pod-lan-ip>:8769  ->  mazemaker-hermes-bridge.service  ->  Hermes/pod/session APIs
```

The Mazemaker pod/MCP endpoint is typically `:8765`; the mobile Hermes bridge sidecar is typically `:8769`.

## Phone-side split test

Open this from the phone browser:

```text
http://<pod-lan-ip>:8769/sessions
```

Examples:

```text
http://192.168.0.2:8769/sessions
```

If the phone browser times out, the APK is not the first thing to debug. The bridge service or LAN path is unreachable.

If the phone browser works but the APK fails:

1. Force-stop the APK and reopen it.
2. Check the app host is the pod LAN IP, not `127.0.0.1`.
3. Check whether the installed APK is debug or release. Release cannot update over debug without uninstall-first because signatures differ.

## Host-side command recipe

```bash
systemctl --user status mazemaker-hermes-bridge.service --no-pager
systemctl --user is-enabled mazemaker-hermes-bridge.service
ss -ltnp '( sport = :8769 )'
curl -m 5 -sS http://127.0.0.1:8769/sessions | head -c 300
curl -m 5 -sS http://<pod-lan-ip>:8769/sessions | head -c 300
ip -4 addr show scope global
```

## Decision table

| Observation | Meaning | Next action |
|---|---|---|
| `curl 127.0.0.1:8769` works, `curl <pod-lan-ip>:8769` times out | Bridge bound to localhost only | Fix systemd ExecStart/bind to LAN |
| `ss` shows `127.0.0.1:8769` | Phone cannot reach service | Override service to source bridge and restart |
| `ss` shows `0.0.0.0:8769` or `[::]:8769` | Bind is correct | Check firewall, router isolation, guest WiFi, subnet |
| `curl 127.0.0.1:8769` times out | Service down/crashed | Check status/journal, enable --now |
| Phone browser works, APK fails | App state/config/install issue | Force-stop app, check host, debug/release signature |
| Host IP is not configured pod IP | App points at wrong address | Update app host to current LAN IP |

## Systemd drop-in fix for localhost-only bind

Create/edit:

```text
~/.config/systemd/user/mazemaker-hermes-bridge.service.d/override.conf
```

Use:

```ini
[Service]
Environment=MAZEMAKER_HERMES_BRIDGE_BIN=
ExecStart=
ExecStart=/usr/bin/python3 %h/projects/mazemaker-architect/bridge/mazemaker-hermes-bridge.py
```

Why clear `MAZEMAKER_HERMES_BRIDGE_BIN`? The original unit may set it to the Nuitka binary:

```ini
Environment=MAZEMAKER_HERMES_BRIDGE_BIN=%h/.local/bin/mazemaker-hermes-bridge
ExecStart=%h/.local/bin/mazemaker-hermes-bridge
```

If the source bridge script honors that env var, leaving it set can accidentally route back to the stale binary.

Apply:

```bash
systemctl --user daemon-reload
systemctl --user enable --now restart mazemaker-hermes-bridge.service
ss -ltnp '( sport = :8769 )'
curl -m 5 -sS http://<pod-lan-ip>:8769/sessions | head -c 300
```

Expected listener:

```text
0.0.0.0:8769
```

or:

```text
[::]:8769
```

## Pitfalls

- Editing the drop-in file does nothing until `systemctl --user daemon-reload` and service restart.
- Android `127.0.0.1` is the phone itself. It is not the host.
- A timeout from the phone is a network/service problem first, not an APK parsing problem.
- Do not reinstall the APK before proving the bridge endpoint from the phone browser.
- Do not chase WebSocket endpoints for this failure. The bridge issue is HTTP reachability on `:8769`.
- Debug-to-release APK upgrades require uninstall-first because signatures differ; this wipes saved host/token unless backed up.
