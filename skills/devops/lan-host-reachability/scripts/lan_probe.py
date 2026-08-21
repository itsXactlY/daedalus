#!/usr/bin/env python3
"""Parallel LAN SSH-host probe + fingerprint.

Usage:  python3 lan_probe.py [SUBNET_PREFIX]     # default 192.168.0

For each host with port 22 open, prints IP, MAC (OUI), and the SSH banner
version string. Used to locate a known host that drifted to a different DHCP
lease, and to flag impostor/embedded devices (ancient OpenSSH, unexpected MAC).

No shell `&` / forks — uses ThreadPoolExecutor so it runs under the Hermes
terminal tool (which blocks backgrounding with `&`).
"""
import socket
import subprocess
import sys
import concurrent.futures as cf

PREFIX = sys.argv[1] if len(sys.argv) > 1 else "192.168.0"


def probe(ip):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect((ip, 22))
        try:
            banner = s.recv(256).decode(errors="replace").strip().split("\r\n")[0]
        except Exception:
            banner = ""
        return ip, banner
    except Exception:
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass


def mac_of(ip):
    try:
        out = subprocess.run(
            ["ip", "neigh", "show", ip], capture_output=True, text=True
        ).stdout
        for tok in out.split():
            if tok.count(":") == 5 and len(tok) == 17:  # lladdr xx:xx:xx:xx:xx:xx
                return tok
    except Exception:
        pass
    return ""


def main():
    ips = [f"{PREFIX}.{i}" for i in range(1, 255)]
    found = []
    with cf.ThreadPoolExecutor(max_workers=120) as ex:
        for r in ex.map(probe, ips):
            if r:
                found.append(r)
    print(f"# SSH hosts on {PREFIX}.0/24: {len(found)}")
    for ip, banner in sorted(found, key=lambda x: int(x[0].split(".")[-1])):
        print(f"{ip:16} {mac_of(ip):18} {banner}")


if __name__ == "__main__":
    main()
