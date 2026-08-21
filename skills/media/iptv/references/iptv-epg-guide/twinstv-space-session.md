# twinstv.space / World 8K — Full Session (2026-06-28)

## Provider

- **Domain:** twinstv.space → 103.211.100.216
- **Name in API:** "World 8K"
- **Server header:** CDN PROXY SERVICE
- **Nameserver:** 49.12.222.213 (Hetzner)

## Credentials (Xtream XC API)

| Field    | Value            |
|----------|------------------|
| username | e3e6b19489998    |
| password | bde21c158f       |
| Status   | Active           |
| Expires  | 2027-05-27 (ts: 1811541600) |
| Max conn | 1                |
| Protocols| m3u8, ts, rtmp   |
| Timezone | Europe/Amsterdam |

## Endpoint Behavior

| Endpoint                                  | HTTP  | Size     | Notes                                    |
|-------------------------------------------|-------|----------|------------------------------------------|
| `/xmltv.php?username=...&password=...`    | 200   | 77 MB    | Valid XMLTV, ends with `</tv>`            |
| `/get.php?username=...&password=...&type=m3u_plus` | 884 | 0 bytes  | CDN_PROXY_SERVICE blocks M3U             |
| `/player_api.php?username=...&password=...&action=user_info` | 200 | 496 B | JSON account info |
| `/player_api.php?action=get_live_categories` | 200 | 78 KB | 895 categories (DE\| FUSSBALL.TV, DE\| PRIME, DE\| JOYN, etc.) |
| `/player_api.php?action=get_live_streams` | 200 | 20 MB | 54,745 streams as JSON |
| `/live/USER/PASS/STREAM_ID.ts`            | 302  | —        | Redirects to CDN at 185.245.1.89 |

## M3U Generation Details

The M3U was built from `player_api.php?action=get_live_streams` JSON. Each stream has:

- `stream_id` — numeric ID used in stream URL
- `name` — channel display name
- `stream_icon` — channel logo URL
- `epg_channel_id` — EPG matching ID (8,214 of 54,745 have this)
- `category_id` → `category_name` from get_live_categories

Stream URL format: `http://twinstv.space/live/USER/PASS/STREAM_ID.ts`

Result: 11.9 MB M3U file, 54,745 channels across 895 categories.

## Jellyfin API Setup on tpad

| Step | Endpoint | Body | Result |
|------|----------|------|--------|
| Add M3U tuner | POST /LiveTv/TunerHosts | `{"Type":"m3u","Url":"/tmp/twinstv_playlist.m3u","FriendlyName":"World 8K"}` | HTTP 200, ID: df0f4658e6604e6eac99bd269f84a709 |
| Add EPG provider | POST /LiveTv/ListingProviders | `{"Type":"xmltv","Path":"/tmp/guide.xml","FriendlyName":"World 8K EPG"}` | HTTP 200, ID: 4ac6d69e8bef439bb0347b3b304fa7cb |
| Link EPG→tuner | POST /LiveTv/ListingProviders | same EPG body + `"EnabledTuners":["df0f..."]` | HTTP 200 |
| Ch. mapping | POST /LiveTv/ListingProviders/4ac6d.../ChannelsMapping | — | HTTP 200 |
| Guide refresh | POST /LiveTv/Guide/Refresh?replaceAllLanguages=true | — | OK |

**Result after setup:**
- 8,345 channels in Jellyfin
- Guide: 7-day window (2026-06-28 to 2026-07-05)
- First channel (DE: DAS ERSTE HD): 7,548 programs loaded
- Verified: programs have actual titles like "Im Namen des Gesetzes", "Tennis: ATP & WTA"

## Jellyfin Target (tpad)

- **Host:** Tpad-P50 (ssh config alias: `tpad`)
- **Jellyfin:** System service `/usr/bin/jellyfin`, runs as `jellyfin` (uid 952)
- **Data dir:** `/home/alca/.local/share/jellyfin/` (mostly empty before setup)
- **Config:** Jellyfin 10.11.11 with "Xtream Live" plugin pre-installed (unused)
- **Files deployed:** `/tmp/guide.xml` (77 MB), `/tmp/twinstv_playlist.m3u` (12 MB)

## Server Availability

- First attempt: all ports timeout (80, 443, 8080, 8880, 8443 etc.)
- Second attempt (retry after ~60s): port 80 responds normally
- Pattern: intermittent availability; retry works

## Channels

Hungarian-focused EPG (AMC HU, ATV HU, AXN, Animal Planet, BBC Earth, etc.) plus extensive German channels (DAS ERSTE, ZDF, FUSSBALL.TV, PRIME, JOYN, etc.) and international.
