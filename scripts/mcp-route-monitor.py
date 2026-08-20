#!/usr/bin/env python3
"""mcp-route-monitor — watch WHO routes Daedalus MCP calls.

For every enabled MCP server in ~/.daedalus/config.yaml:
  1. resolve the endpoint (URL / socket)
  2. probe it with an MCP `initialize` handshake (name, version, latency)
  3. resolve which process/container actually owns the listener (routing chain)
  4. append a timestamped line to the log, print a human-readable report

Routing chain resolution: port -> `ss -tlnp` -> PID -> /proc cmdline ->
podman container name if the owner is a passt/rootlessport forwarder.

Exit 0 if ALL enabled servers respond; 1 otherwise (for cron alerting).
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

CONFIG = os.path.expanduser("~/.daedalus/config.yaml")
LOG = os.path.expanduser("~/.daedalus/logs/mcp-route.log")
TIMEOUT = 5

def read_enabled_servers():
    """Naive parse of mcp_servers block (transport + url + enabled)."""
    servers = {}
    try:
        with open(CONFIG) as f:
            lines = f.readlines()
    except OSError as e:
        print(f"FATAL: cannot read {CONFIG}: {e}")
        sys.exit(2)
    in_block = False
    cur = None
    for line in lines:
        s = line.rstrip("\n")
        if re.match(r"^mcp_servers:", s):
            in_block = True
            continue
        if in_block:
            # end of block: next top-level key (no leading space)
            if s and not s.startswith(" "):
                break
            m = re.match(r"^  ([a-z0-9_-]+):", s)
            if m and not s.startswith("    "):
                cur = m.group(1)
                servers[cur] = {"enabled": True, "transport": "unknown", "url": None}
                continue
            m = re.match(r"^    (enabled|transport|url):\s*(.*)$", s)
            if m and cur:
                k, v = m.group(1), m.group(2).strip().strip("'\"")
                if k == "enabled":
                    servers[cur]["enabled"] = v.lower() == "true"
                elif k == "transport":
                    servers[cur]["transport"] = v
                elif k == "url":
                    servers[cur]["url"] = v
    return {k: v for k, v in servers.items()}

def mcp_initialize(url):
    """MCP initialize handshake. Returns (ok, info_dict, latency_ms)."""
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "mcp-route-monitor", "version": "1.0"}},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode()
            dt = (time.monotonic() - t0) * 1000.0
        # SSE or JSON
        info = {}
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if line.startswith("{"):
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                res = msg.get("result") or {}
                info = res.get("serverInfo", {})
                break
        return True, info, dt
    except Exception as e:  # noqa: BLE001
        return False, {"error": str(e)}, (time.monotonic() - t0) * 1000.0

def owner_of_listener(port):
    """Who owns the TCP listener on this port -> process cmdline + podman name."""
    try:
        out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return "unknown"
    for line in out.splitlines():
        if f":{port}" in line:
            m = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
            if m:
                proc, pid = m.group(1), m.group(2)
                try:
                    cmd = subprocess.run(["tr", "\\0", " "],
                                         input=open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", "replace"),
                                         capture_output=True, text=True, timeout=5).stdout.strip()
                except Exception:  # noqa: BLE001
                    cmd = "?"
                # map PID -> container name via podman (exact PID match)
                cont = "?"
                try:
                    cp = subprocess.run(["podman", "ps", "--format", "{{.Names}} {{.Pid}}"],
                                        capture_output=True, text=True, timeout=10).stdout
                    for cl in cp.splitlines():
                        parts = cl.split()
                        if len(parts) == 2 and parts[1] == pid:
                            cont = parts[0]
                except Exception:  # noqa: BLE001
                    pass
                return f"{proc} (pid {pid}) container={cont}"
    return "no listener"

def podman_container_for_port(port):
    """Which podman container publishes this host port (passt is only the forwarder)."""
    try:
        cp = subprocess.run(["podman", "ps", "--format", "{{.Names}} {{.Ports}}"],
                            capture_output=True, text=True, timeout=10).stdout
        for cl in cp.splitlines():
            parts = cl.split(None, 1)
            if len(parts) == 2 and f":{port}->" in parts[1]:
                return parts[0]
    except Exception:  # noqa: BLE001
        pass
    return None

def port_of_url(url):
    m = re.search(r":(\d+)(?:/|$)", url)
    return int(m.group(1)) if m else None

def main():
    servers = read_enabled_servers()
    if not servers:
        print("No mcp_servers found in config.")
        return 2
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    all_ok = True
    lines = [f"=== MCP route report {time.strftime('%Y-%m-%d %H:%M:%S')} ==="]
    for name, cfg in servers.items():
        if not cfg.get("enabled"):
            lines.append(f"[{name}] DISABLED (transport={cfg['transport']}, url={cfg.get('url')})")
            continue
        url = cfg.get("url") or "?"
        ok, info, ms = mcp_initialize(url)
        port = port_of_url(url)
        owner = owner_of_listener(port) if port else "socket/unix"
        cont = podman_container_for_port(port) if port else None
        if cont:
            owner += f" via-podman={cont}"
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        line = (f"[{name}] {status} url={url} server={info.get('name','?')} "
                f"v{info.get('version','?')} {ms:.0f}ms owner={owner}")
        lines.append(line)
        print(line)
    with open(LOG, "a") as f:
        f.write("\n".join(lines) + "\n")
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
