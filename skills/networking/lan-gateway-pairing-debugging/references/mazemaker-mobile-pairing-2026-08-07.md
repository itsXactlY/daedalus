# Worked example — mazemaker-mobile ↔ hermes-crypto gateway pairing (2026-08-07)

Full session transcript of a real "paired per QR but lands on wrong endpoint"
debug on the operator's stack. Kept as a narrative so the diagnostic ladder in
SKILL.md has a concrete shape to map onto.

## Stack

- Android app `dev.mazemaker.mobile` (mazemaker-mobile repo, Kotlin)
- Gateway: `lan_gateway.py` from hermes-crypto, systemd user unit
  `mazemaker-apk-gateway.service`, ports 8443 (HTTPS) + 38374 (TCP)
- mDNS advertise: `mazemaker-apk-gateway-mdns.service` →
  `mdns-advertise.sh` → `avahi-publish-service "Mazemaker Gateway" _mazemaker-gw._tcp 8443`
- Route C relay env in systemd drop-in
  `~/.config/systemd/user/mazemaker-apk-gateway.service.d/relay.conf`:
  `MM_RELAY_URL=wss://api.mazemaker.dev/relay/gw`,
  `MM_RELAY_PUBLIC_URL=https://api.mazemaker.dev/relay`
- Phone: Pixel 7 Pro, Android 16, arm64, on same /24 (192.168.0.109 vs host 192.168.0.2)

## Symptom

App paired via QR from `https://127.0.0.1:8443/pair`, then every call failed:
```
gateway HTTP 404: {"error":"not_found","hint":"api.mazemaker.dev only serves /api/*, /stripe/webhook, /sse"}
```
Operator: "landet on wrong endpoint. did it route over NAT? not LAN?"

## Diagnosis (the ladder in practice)

1. Logcat (`adb logcat -d | grep MzkVM|MzkMcpProxy`) showed the app WAS trying
   api.mazemaker.dev, plus a separate `MzkMcpProxy: gateway.pod(/mcp) failed`
   from the on-device proxy.
2. Decoded the pairing code from `/pair.json`: `{v:2, token, fp, relay:
   https://api.mazemaker.dev/relay}` — NO host. So the app could only reach the
   gateway via mDNS, and had a relay fallback for when mDNS fails.
3. `systemctl --user status mazemaker-apk-gateway-mdns` → **inactive (dead)**,
   empty journal = never started/enabled. `avahi-browse -rt _mazemaker-gw._tcp`
   → nothing. THAT was the root cause: no mDNS → app fell back to relay → relay
   domain 404s.
4. `ss -tlnp | grep 8443` → gateway WAS listening. Gateway running ≠ mDNS
   publishing (the missing link).
5. `curl -sk https://api.mazemaker.dev/relay/gw` → HTTP 404 → the relay was NOT
   deployed (no relay.py process). The fallback path was dead too.

## Fixes applied

1. **Start + enable mDNS advertise** (the real fix):
   ```bash
   systemctl --user start mazemaker-apk-gateway-mdns
   systemctl --user enable mazemaker-apk-gateway-mdns
   pgrep -af avahi-publish-service   # → "Mazemaker Gateway _mazemaker-gw._tcp 8443 v=1 fp=… a=192.168.0.2"
   timeout 5 avahi-browse -rt _mazemaker-gw._tcp   # → resolves with address 192.168.0.2, port 8443
   ```
   Note the `a=192.168.0.2` TXT — the advertise script computes the primary LAN IPv4
   so the phone skips virbr0/link-local.
2. **Deactivate the dead relay** (operator chose B): commented out both
   `MM_RELAY_*` lines in the drop-in, `systemctl --user daemon-reload && restart
   mazemaker-apk-gateway.service`. Re-decode `/pair.json` → now `{v:1, token, fp}`,
   no relay. App can no longer fall into the dead path; if mDNS fails it now gives
   a clean "couldn't find the gateway" error instead of relay 404s.
3. **Stale-session self-healing** (discovered after the gateway restart): the app
   then hit `400 {"error": "Decryption failed"}` because its in-memory
   `client_key`/`session_id` was from the pre-restart gateway. Fixed in
   `GatewayClient.kt`:
   - `postCommand` flags 400 + body containing "ecrypt" as
     `GatewayException(code="decryption")`
   - `command()` catches it, `invalidateSession()`, retries exactly once
     (`retried` guard) → fresh handshake renegotiates the session.
   - Commit `46aaedc` on `feat/thebox-autoupdate`.

## Key commands kept for reuse

```bash
# Does mDNS advertise actually run?
systemctl --user status mazemaker-apk-gateway-mdns
pgrep -af avahi-publish-service
timeout 5 avahi-browse -rt _mazemaker-gw._tcp

# Is the gateway listening?
ss -tlnp | grep -E "8443|38374"

# What does the pairing code REALLY carry?
curl -sk https://127.0.0.1:8443/pair.json   # {"code": "<b64>", "fp": "..."}
# …then base64-decode 'code'

# Does the relay exist?
curl -sk -o /dev/null -w "%{http_code}\n" https://api.mazemaker.dev/relay/gw

# Phone side
export PATH=$PATH:~/Android/Sdk/platform-tools
adb logcat -d | grep -iE "MzkVM|MzkGw|MzkMcpProxy|gateway"
```
