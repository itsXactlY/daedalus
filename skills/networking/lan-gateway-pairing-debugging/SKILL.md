---
name: lan-gateway-pairing-debugging
description: Debug QR pairing that lands on the wrong gateway endpoint.
---

# LAN Gateway Pairing Debugging

## When to Use

- A phone/app was paired via QR/paste code but traffic lands on the WRONG endpoint
  (e.g. a public domain instead of the LAN host), or requests fail with 400/404
- "Decryption failed" / crypto errors after a gateway restart
- mDNS discovery finds nothing (`_service._tcp` never resolves)
- Any "why is my app talking to X instead of Y" during gateway pairing

Proven on the mazemaker-mobile ↔ hermes-crypto gateway stack (Android app,
Kotlin `GatewayClient`, Python `lan_gateway.py`), 2026-08-07.

## The Pairing Code Is the Source of Truth — DECODE IT FIRST

The QR/paste code is small base64 JSON. Decode it before touching anything else —
it tells you exactly what the app was told to do:

```python
import base64, json
raw = "..."  # the payload string
print(json.dumps(json.loads(base64.b64decode(raw)), indent=2))
```

Known shapes:
- `{v:1, token, fp}` — **host-less by design**: the app is EXPECTED to find the
  gateway via mDNS. No host in the code is not a bug.
- `{v:2, token, fp, relay}` — carries a Route-C relay URL for out-of-LAN reach.
- `{v:1/2, token, fp, host: "192.168.0.2:8443"}` — host baked in (mDNS-blocked fallback).

**Key insight:** if the code has NO `host` and a `relay`, the app will fall back to
the relay whenever mDNS fails — even if the gateway is right there on the LAN.

## Diagnostic Ladder (in order)

1. **Decode the pairing code** (above). Note: v? host? relay? fp?
2. **Is the mDNS advertise service RUNNING?** This is the #1 cause of "landed on
   the wrong endpoint". The gateway may be listening fine while nothing publishes
   the DNS-SD service:
   ```bash
   systemctl --user status <gateway>-mdns.service   # e.g. mazemaker-apk-gateway-mdns
   pgrep -af "avahi-publish-service"                # must show the service + TXT records
   timeout 5 avahi-browse -rt _mazemaker-gw._tcp    # must resolve, NOT be empty
   ```
   A unit that is `inactive (dead)` with an empty journal = never started/enabled.
   Fix: `systemctl --user start <mdns>.service && systemctl --user enable <mdns>.service`.
   Verify TXT contains the routable LAN IPv4 (an `a=<ip>` TXT record) — that is how
   the phone skips virbr0/link-local addresses.
3. **Is the gateway actually listening?** `ss -tlnp | grep <port>` — confirm the
   port is bound. Gateway "running" ≠ mDNS publishing.
4. **Same LAN subnet?** Phone IP vs host IP (`hostname -I`, DHCP log). If different
   subnets / no multicast between them, mDNS can never work — then a host-carrying
   code or relay is REQUIRED, not optional.
5. **Does the relay actually exist?** `curl -sk <relay-url>` — a relay that 404s
   means the fallback path is dead too: the app falls to a wrong endpoint AND the
   backup is broken. Decision: either deploy the relay (relay.py) or REMOVE the
   relay from the pairing code entirely (uncomment/clear the env var that feeds it)
   so the app never attempts the dead path. Prefer removing a dead relay over
   leaving it — a v1 host-less code + working mDNS is the clean LAN setup.

## Stale-Session Self-Healing (400 "Decryption failed")

Symptom: app worked, then a gateway restart (config change, service restart)
breaks EVERY request with `400 {"error": "Decryption failed"}`.

Root cause: the client cached `client_key`/`session_id` in memory; the restarted
gateway no longer recognises that session. The gateway answers 400 (not 401), so
clients that only invalidate-on-401 never recover.

Fix pattern (Kotlin GatewayClient):
- `postCommand`: detect `400` + body containing "ecrypt" (case-insensitive) →
  throw `GatewayException(code = "decryption")` instead of a generic HTTP error.
- `command()`: catch `code == "decryption"`, call `invalidateSession()`, and retry
  ONCE with a fresh handshake (a `retried: Boolean` param guards the single retry;
  re-entering `ensureSession()` does the renegotiation).
- Also invalidate on local decrypt failure (AEADBadTagException / IllegalArgumentException).
- Verify the wire format matches the server: `nonce[16] | tag[16] | ciphertext`
  on both sides (Python: `cipher.nonce + tag + ct`; Kotlin splices tag before ct).

## Pitfalls

- **QR from `http://host:port/pair` returns an HTML page** with an inline SVG QR —
  the `.code` block may show a MASKED/truncated value (`eyJ2Ij...eSJ9`). The real
  payload is in the SVG. Extract the `<rect>` modules, render to PBM, decode with
  `zbarimg` (see references/qr-svg-decode-recipe.md).
- **Don't trust "it was working before"** — a systemd drop-in or env var change
  (e.g. adding a relay URL) changes what the NEXT pairing code carries. Re-decode.
- **App logcat is authoritative for which endpoint the app chose** — grep the
  app's own tags (`MzkVM`, `MzkGw`, `MzkMcpProxy`) for `HTTP 404` + the hint text.
- **Restarting the gateway invalidates in-memory sessions** — after any gateway
  restart, expect one session-renegotiation round; make the client self-heal.
- ADB is often not in PATH: `export PATH=$PATH:~/Android/Sdk/platform-tools`.

## Reference

- `references/qr-svg-decode-recipe.md` — decode an inline-SVG QR from a pairing HTML page
- `references/mazemaker-mobile-pairing-2026-08-07.md` — full worked example (mDNS dead,
  relay deactivated, GatewayClient self-heal commit)
