---
name: lan-host-reachability
description: Diagnose why a known/expected SSH host is unreachable and locate it on the LAN — DHCP lease drift, wrong subnet, impostor/embedded devices, legacy SSH host keys. For multi-machine fleets (tpad/desk/NAS/GPU boxes).
---

# LAN Host Reachability & Locator

## Trigger conditions
- A host you expect to reach (e.g. `ssh host` / `mosh host`) fails with "No route to host", "Connection refused", or hangs.
- You need to connect to a machine the operator booted / moved but you don't have its current IP.
- Any subnet device-discovery task on a known LAN.

## Why this exists
The operator runs a fleet (desk, tpad ThinkPad P50, NAS, GPU boxes, routers). Hosts get DHCP leases that drift from their reserved IP, boot onto a different subnet, or sit behind a firewall. A naive `ssh host` retry loop burns minutes and still fails. This playbook gets you from "No route to host" to either a working connection or a confirmed diagnosis in one pass — without fabricating a "connected" result.

## Steps (one ordered pass)
1. **Read the ssh config target** — `grep -A6 -iE '^host <name>' ~/.ssh/config` to get HostName / User / IdentityFile. Note the expected IP.
2. **Quick ssh probe** (deterministic, no password prompt):
   `ssh -o ConnectTimeout=6 -o StrictHostKeyChecking=accept-new -o BatchMode=yes <user>@<host> 'hostname' 2>&1 | head`
   - "No route to host" → device not on network at that IP (off, or different subnet).
   - "Connection refused" → host up, sshd not listening / filtered.
   - "Permission denied" → host up, auth issue (wrong key **or a different device**).
3. **Confirm THIS host's subnet**: `ip -4 addr show | grep -E 'inet '` — so you know what /24 to scan.
4. **Targeted liveness**: `ping -c2 -W2 <ip>` and `ip neigh show <ip>` (ARP). "FAILED" ARP + 100% loss = IP not assigned to any live host.
5. **Subnet scan for SSH** (find the host if DHCP gave a different lease):
   - If nmap present: `timeout 120 nmap -T4 -p22 --open <subnet>/24 2>/dev/null | grep -E 'Nmap scan|open'`
   - If not: run `scripts/lan_probe.py <subnet-prefix>` (parallel socket probe + banner/MAC fingerprint; no shell `&`, which the terminal tool blocks).
6. **Fingerprint every candidate** — do NOT assume the first SSH host is your target (see Pitfalls):
   - SSH banner/version: `ssh -v -o BatchMode=yes <user>@<cand> 'x' 2>&1 | grep -i 'remote software version'` (auth fails; banner shows pre-auth).
   - MAC OUI: `ip neigh show <cand>` → `lladdr`.
   - Key acceptance: a real match accepts your `IdentityFile`; an impostor rejects it ("Permission denied (publickey)").
7. **If found and it's yours but hostkey negotiation fails on legacy algo**, force legacy host keys:
   `ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa -o BatchMode=yes <user>@<ip> 'hostname'`
   (Modern OpenSSH drops ssh-rsa/ssh-dss by default. NOTE: `-o HostKeyAlgorithms=+ssh-rsa,ssh-dss` ERRORS — ssh-dss can't be re-enabled; use `+ssh-rsa` alone.)

## Pitfalls
- **mosh vs ssh for automation**: the operator may say "mosh host", but mosh needs the server installed + UDP 60000-6100 open and is interactive. For agent scripting use `ssh` with `BatchMode=yes` — deterministic, no prompt, same key. Reserve mosh for the operator's interactive use.
- **DHCP lease drift**: the ssh config's reserved IP may not match what the host actually got. A /24 scan catches it. Don't keep hammering the stale IP.
- **Impostor devices**: a subnet scan often reveals OTHER SSH hosts (old NAS, router, IoT) running ancient OpenSSH (e.g. `OpenSSH_5.1p1 Debian-5`). These are NOT your target — confirm via banner version (a Garuda/Arch box runs current OpenSSH), MAC OUI, and key acceptance before connecting. See `references/error-signatures.md`.
- **Shell `&` backgrounding is blocked** in the terminal tool — use nmap, or `scripts/lan_probe.py` (python ThreadPoolExecutor), never `for ip; do ( … & )`.
- **Don't infinite-poll**: cap at ~3–4 min of `ssh` retries; if still dark, do ONE /24 rescan, then hand back to the operator (clarify: booted? on this wifi? give IP). Never fabricate "connected".
- **Legacy host-key syntax**: `+ssh-rsa,ssh-dss` is rejected ("Bad key types"); use `+ssh-rsa` only.

## Verification
- Success: `ssh -o BatchMode=yes <user>@<resolved-ip> 'hostname; uname -a'` returns the expected hostname.
- Then gather a spec snapshot in ONE call before any heavy setup: `nproc; free -h; df -h; gcc --version; python3 -c "import huggingface_hub"` etc.

## Support files
- `scripts/lan_probe.py` — parallel port-22 scanner + banner/MAC fingerprint (use when nmap is unavailable or you want structured output).
- `references/error-signatures.md` — symptom → meaning table + the impostor-device heuristic.
