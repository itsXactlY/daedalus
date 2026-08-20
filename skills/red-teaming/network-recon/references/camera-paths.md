# Common RTSP Stream Paths

## TP-Link Tapo Cameras

| Port | Protocol | Notes |
|------|----------|-------|
| 2020 | TCP | Tapo cloud protocol (often disabled) |
| 554 | RTSP | Main video stream, Digest auth required |
| 8080 | HTTP | Alternate web interface |
| 8800 | HTTP | Admin interface |
| 2020 | TCP | Video control (xinupageserver) |

**Stream path attempts:**
```
/stream1
/live
/h264
/video1
/preview
/user=admin_password=xxx
```

## Generic IP Camera Paths

| Manufacturer | Common Paths |
|-------------|------------|
| Generic/ONVIF | `/Streaming/Channels/101`, `/h264`, `/live` |
| Dahua | `/cam/realmonitor`, `/h264`, `/media/video1` |
| Hikvision | `/Streaming/Channels/1`, `/ISAPI/Streaming`, `/media` |
| Reolink | `/h264Preview_01_main`, `/live` |
| Axis | `/axis-media/media.amp`, `/mjpg` |
| Foscam | `/video.cgi`, `/img/video.flv` |

## Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 OK | Success | Stream available |
| 401 Unauthorized | Auth required | Try credentials |
| 404 Not Found | Path wrong | Try different path |
| 400 Bad Request | Malformed request | Use proper RTSP client |
| Server timeout | Port closed/filtered | Check if device is streaming |

## Authentication Types

**Digest auth response:**
```
WWW-Authenticate: Digest realm="TP-Link IP-Camera", nonce="..."
```

**Basic auth response:**
```
WWW-Authenticate: Basic realm="..."
```