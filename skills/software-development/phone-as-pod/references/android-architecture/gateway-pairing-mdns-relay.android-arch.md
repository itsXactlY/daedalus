# Gateway QR-pairing → mDNS → Route-C relay: "app hits wrong endpoint" debug (2026-08-07)

Debugging path for the mazemaker-mobile app (or any phone-as-pod client that
pairs to a LAN gateway) landing on the WRONG endpoint — the phone tries
`api.mazemaker.dev` instead of the LAN gateway and gets
`404 {"error":"not_found","hint":"api.mazemaker.dev only serves /api/*, /stripe/webhook, /sse"}`.

## The pairing-code design (root context — read before diagnosing)

The QR served at `https://<host>:8443/pair` (hermes-crypto `lan_gateway.py`) is
**deliberately HOST-LESS by design** (`pairing_code()`):

```python
doc = {"v": 1, "token": GATEWAY_TOKEN, "fp": fp}   # NO host field
relay = os.environ.get("MM_RELAY_PUBLIC_URL", "").strip()
if relay:
    doc["v"] = 2
    doc["relay"] = relay
```

- v1 code = `{v, token, fp}` — the phone finds the gateway via **mDNS**
  (`_mazemaker-gw._tcp`), fetches+verifies the cert (TOFU: `sha256(SPKI)==fp`).
- v2 code = adds `relay` — **Route C** fallback for reaching the pod from
  OUTSIDE the LAN, keyed by fp. The relay public URL comes from
  `MM_RELAY_PUBLIC_URL` (systemd drop-in, NOT the .env / unit directly).

**Consequence:** if mDNS discovery fails, the app does NOT error — it silently
falls back to the relay path (`clientBase = "<relay>/gw/<fpHex>"`). If that relay
isn't actually deployed (or points at a host that only serves `/api/*`), every
call returns the 404 above. The app looks broken but it's doing exactly what the
code says: host-less code → find host via mDNS → none → use relay.

## Diagnostic sequence (in order — each step answers "is X the culprit?")

1. **Decode the actual QR the phone received** — don't guess:
   ```bash
   curl -sk https://127.0.0.1:8443/pair.json | python3 -c "
   import sys,json,base64
   d=json.load(sys.stdin); doc=json.loads(base64.b64decode(d['code']))
   print('v:',doc.get('v')); print('relay:',doc.get('relay','ABSENT')); print('host:',doc.get('host','ABSENT'))"
   ```
   - `v:1` + no relay → app SHOULD use mDNS/LAN only. Landing on a public domain
     then means mDNS is broken OR the app has a stale stored relay config.
   - `v:2` + `relay` → app will use the relay when mDNS fails. Test the relay:
     `curl -skI https://<relay>/gw 2>&1 | head -1` (expect non-404 if deployed).

2. **Is the mDNS advertise service actually running?** (the most common root cause)
   ```bash
   systemctl --user status mazemaker-apk-gateway-mdns   # must be active (running)
   pgrep -af "avahi-publish-service" | grep -v "bash -c"
   timeout 5 avahi-browse -rt _mazemaker-gw._tcp   # must list the gateway + TXT a=<LAN-IP>
   ```
   The gateway service itself (`mazemaker-apk-gateway.service`, ports 8443/38374)
   can be UP while the **mDNS advertise unit is dead + disabled** (empty journal,
   never `systemctl --user enable`d). Gateway up ≠ advertised. This exact state
   (dead/disabled mdns unit, gateway running 12h) caused the reported bug.

3. **Confirm LAN reachability** — phone and host in the same subnet:
   `hostname -I` on host vs `adb shell ip addr` (or the DHCP lease log). The
   mdns-advertise TXT `a=` field carries the routable LAN IPv4 specifically to
   sidestep mDNS returning a virbr0/`192.168.122.x` or IPv6 link-local address.

4. **Check the gateway's live relay env** (where the code value came from):
   ```bash
   systemctl --user show mazemaker-apk-gateway.service -p Environment | tr ' ' '\n' | grep MM_RELAY
   # relay config lives in ~/.config/systemd/user/mazemaker-apk-gateway.service.d/relay.conf
   ```

5. **Phone logcat** (what the app actually tried):
   `adb logcat -d | grep -iE "MzkDiscovery|MzkVM|gateway|_mazemaker|api\.mazemaker"`
   Look for: mdns `Registering listener for _mazemaker-gw._tcp` + NO
   `onServiceFound` (mDNS found nothing) → then `gateway HTTP 404: ...api.mazemaker.dev`.

## Verified fixes (2026-08-07)

**Fix A — make mDNS actually advertise (the real fix):**
```bash
systemctl --user start  mazemaker-apk-gateway-mdns
systemctl --user enable mazemaker-apk-gateway-mdns
# verify:
pgrep -af avahi-publish-service            # "Mazemaker Gateway _mazemaker-gw._tcp 8443 v=1 fp=... a=192.168.0.2"
timeout 5 avahi-browse -rt _mazemaker-gw._tcp   # wlp41s0 IPv4 = the routable LAN addr
```
The unit already has `PartOf=`/`Wants=` the gateway + `Restart=on-failure`, so
once enabled it survives gateway restarts.

**Fix B — kill the dead relay fallback (operator chose this):** if
`api.mazemaker.dev/relay/gw` returns 404 (no `relay.py` deployed on prod), the
relay fallback is worse than useless — it sends every LAN pairing down the NAT
path. Comment OUT both lines in
`~/.config/systemd/user/mazemaker-apk-gateway.service.d/relay.conf`, then:
```bash
systemctl --user daemon-reload
systemctl --user restart mazemaker-apk-gateway.service
# verify the QR is now v1 without relay:
curl -sk https://127.0.0.1:8443/pair.json   # {"v":1,"token":...,"fp":...}  NO relay
```
Keep the drop-in file with the lines commented + a dated WHY note, so the
intent is recoverable when a working relay exists. (Leave the file, comment the
vars — don't `rm` it.)

**Then: RE-SCAN the QR on the phone** (the app only does mDNS discovery at
pairing time, not continuously). Force a fresh scan: `adb shell am force-stop
<app>` + re-open + re-scan.

## Key lessons

- A host-less pairing code + downed mDNS = silent relay fallback = wrong
  endpoint 404. Diagnose the pairing-code shape FIRST, then mDNS, then relay.
- `systemctl status` of the GATEWAY is not enough — the mDNS ADVERTISE unit is a
  separate thing that can be dead/disabled while the gateway runs.
- Relay URLs ride in a systemd **drop-in** (`service.d/relay.conf`), not the
  main unit or the `.env` — check there.
- Decode the QR from `/pair.json` (base64 JSON) rather than rendering the SVG
  (the inline `.code` display truncates to `eyJ2Ij...eSJ9`; the SVG renders to a
  57×57 QR that zbarimg decodes but the value is the same truncated-looking but
  actually-full base64).
- When disabling a broken fallback, prefer comment-in-place over delete — the
  config stays greppable/recoverable.
