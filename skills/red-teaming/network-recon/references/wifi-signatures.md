# WiFi Network Signatures

## Hidden/Multi-BSS Network Indicators

### Multi-BSS AP Features (WiFi 6/6E routers)
Look for these in `iw scan` output when `Max Co-Hosted BSSID` > 0:

```
Co-Hosted BSS
Max Co-Hosted BSSID: 3
```

This indicates a single radio broadcasting multiple BSSIDs - some may be hidden guest networks.

### Hidden Network Detection

Hidden networks show:
- Empty SSID field in `nmcli`: `:SIGNAL:BSSID:CHANNEL` (no SSID before first colon)
- No `SSID:` line in `iw scan` output for that BSSID
- BSSID still visible in probe responses

### Common Hidden Network Patterns

| Vendor | OUI Pattern | Notes |
|--------|-------------|-------|
| TP-Link | 30:68:93 | Tapo cameras, Deco mesh, Archer routers |
| D-Link | 00:D0:B8 | Some cameras, NAS with RTSP |
| Arcadyan | DC:F5:1B | SpeedHomeWLAN, Bella Donna Home APs |
| Amazon | A0:D0:DC | Echo devices |
| Samsung | C8:E2:65 | SmartThings, SmartCam |
| Shenzhen | 8C:98:06 | Generic IoT devices |

### BSSID Clustering

Multi-BSS APs reuse the same OUI but increment the final bytes:
- Parent: `30:68:93:66:8B:AA`
- Guest: `30:68:93:66:8B:AB`  
- Hidden: `30:68:93:66:8B:AC`

Check all BSSIDs sharing the same first 5 bytes.