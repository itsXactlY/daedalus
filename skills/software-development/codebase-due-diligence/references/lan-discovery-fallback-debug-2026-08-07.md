# LAN discovery fallback debug — service up but not discoverable (2026-08-07)

Symptom from operator: Mazemaker app paired by QR on a Pixel 7 Pro landed on the
wrong endpoint — "lol, did it route over NAT? not LAN? its trying api.mazemaker..."
The app hit `api.mazemaker.dev` and 404'd everywhere.

## Symptom signature in logcat

```
MzkVM    : dream op failed: Pod unreachable: gateway HTTP 404: {"error":"not_found","hint":"api.mazemaker.dev only serves /api/*, /stripe/webhook, /sse"}
MzkVM    : hermes:sessions failed: Bridge unreachable: gateway HTTP 404: ...
MzkMcpProxy: gateway.pod(/mcp) failed: gateway HTTP 404: ...
serviceDiscovery: [MdnsDiscoveryManager] Registering listener for serviceType: _mazemaker-gw._tcp.local
serviceDiscovery: [MdnsDiscoveryManager] Unregistering listener for serviceType:_mazemaker-gw._tcp.local
```

Two tells:
1. **mDNS ran but found nothing** — the app registered the NSD listener for
   `_mazemaker-gw._tcp` for its ~6 s timeout and got NO `onServiceFound`.
2. **It fell back to the relay URL** (`api.mazemaker.dev`) and that endpoint serves
   only `/api/*, /stripe/webhook, /sse` — so every gateway/pod/bridge command 404'd.

## Root cause

The gateway process was up:
```
ss -tlnp | grep -E "8443|38374"   → python3 listening on 0.0.0.0:8443 + 0.0.0.0:38374
systemctl --user status mazemaker-apk-gateway  → Active: active (running)
```
but the mDNS ADVERTISEMENT unit was dead + disabled:
```
systemctl --user status mazemaker-apk-gateway-mdns
  → Loaded: ...disabled
  → Active: inactive (dead)
journalctl --user -u mazemaker-apk-gateway-mdns → "No entries" (never started)
```
`avahi-browse -rt _mazemaker-gw._tcp` returned nothing. The phone's mDNS discovery
therefore found no gateway and silently took the Route C relay fallback.

## The fix

```
systemctl --user start mazemaker-apk-gateway-mdns
systemctl --user enable mazemaker-apk-gateway-mdns
avahi-browse -rt _mazemaker-gw._tcp   # until the service appears
```
Healthy advertisement (note the TXT records — `v`, `fp`, and critically `a=`):
```
= wlp41s0 IPv4 Mazemaker Gateway  _mazemaker-gw._tcp
   hostname = [alca.local]
   address = [192.168.0.2]        port = [8443]
   txt = ["v=1" "fp=..." "a=192.168.0.2"]
```
The `a=` TXT carries the routable LAN IPv4 — `mdns-advertise.sh` derives it from
`ip -4 route get 1.1.1.1` (src addr) specifically so the phone doesn't take a
virbr0/libvirt or IPv6 link-local address. This host was 192.168.0.2, the Pixel
192.168.0.109 — same /24, so LAN reachability was fine once discovery worked.

## The pairing payload shape (why no host in the code)

`provision-apk.sh` builds the QR as tiny `base64(JSON{v, token, fp, [host]})` — by
design NO relay, NO domain. The app finds the host via mDNS and pins the cert via
fp (TOFU). If the scanned QR still routed to `api.mazemaker.dev`, either the code was
an older one carrying a relay, or the app had a stale saved GatewayConfig — but the
reproducible root cause in this case was simply the dead mdns unit.

## Checklist (generalise to any "routed over NAT instead of LAN" symptom)

1. Is the serving process up? `ss -tlnp | grep :<port>` + service status.
2. Is the DISCOVERY/advertisement up? systemd unit status + `avahi-browse -rt <type>`.
   Disabled-but-present unit with empty journal = never started = silent.
3. Does the fallback path the client defaults to actually serve the request path?
   A public-API domain returning "only serves /api/*" 404s is the wrong fallback URL.
4. After starting discovery, re-trigger the client's discovery (re-scan / re-open),
   then confirm logcat shows `onServiceFound` and the app picks the LAN route.
