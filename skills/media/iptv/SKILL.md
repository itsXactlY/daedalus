---
name: iptv
description: |
  IPTV on German fiber (Telekom GPON) and Xtream panels — both tapping live multicast
  streams off the wire AND ingesting EPG/XMLTV into Jellyfin. Use when the user wants to
  receive IPTV multicast (router passthrough, IGMP proxy/snooping, VLC / ethernet-tap
  reception) OR fetch XMLTV/EPG from an Xtream panel and import it into Jellyfin.
---

# IPTV

Class-level skill for the two IPTV workflows on this operator's fiber. The original
narrow skills `iptv-multicast-tapping` and `iptv-epg-guide` are absorbed as the two
workflows below; their support files live under `references/<source>/`.

## Workflow A — Multicast tapping (absorbed from `iptv-multicast-tapping`)

Receive live IPTV off the GPON line with zero trace.

1. **Audit existing hardware FIRST.** Don't change router config blindly — note the
   current IPTV passthrough / VLAN setup before touching it.
2. **Router IPTV passthrough** — enable IPTV/VLAN passthrough for the target port.
3. **IGMP Proxy / IGMP Snooping** — required for the STB multicast groups to be
   forwarded. LAN vs WLAN pitfalls: multicast rarely crosses WLAN cleanly; prefer a
   wired client or an IGMP-querier on the LAN.
4. **Reception options:**
   - **VLC multicast** — `udp://@239.x.x.x:port` style URLs.
   - **Ethernet tap** — managed switch port mirror of the STB's port (cleanest,
     zero-trace capture).
   - **Optical coupler** — passive split if no managed switch is available.
5. **Pitfalls** — IGMP join timing, TTL, and the STB's dedicated multicast VLAN.

Support: `references/iptv-multicast-tapping/telekom-multicast-ips.md` — known
Telekom multicast IP ranges.

## Workflow B — EPG / XMLTV ingestion (absorbed from `iptv-epg-guide`)

Pull guide data from Xtream panels into Jellyfin.

1. **Xtream API endpoints** — auth + `xmltv.php` / `player_api.php` live-TV and EPG.
2. **CDN protection quirks** — watch for **HTTP 884** (provider-side CDN block);
   requires the correct auth token + UA + host header, not just the URL.
3. **Validation** — parse the XMLTV, confirm channel IDs map to the Jellyfin TV source.
4. **Remote deployment** — ship the fetched guide to the Jellyfin host (the guide
   import runs there, not on the operator box).

Support: `references/iptv-epg-guide/twinstv-space-session.md`.

## See also

- `media/linux-media-server-audio` — the Jellyfin audio side.
- `creative/threejs-living-viz` — unrelated viz, listed only to disambiguate.
