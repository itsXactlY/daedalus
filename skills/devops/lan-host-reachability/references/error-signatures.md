# Error signatures -> meaning (LAN host reachability)

| Symptom | Meaning | Action |
|---|---|---|
| `ssh: connect to host X port 22: No route to host` | IP not on network (off, or different subnet) | confirm this-host subnet; scan /24 |
| `ip neigh show X` -> `FAILED` | no ARP reply; IP unassigned to any live host | scan for new lease |
| `Connection refused` | host up, sshd not listening / filtered | check sshd; maybe wrong port |
| `Permission denied (publickey,password)` | host up, but your key rejected | likely NOT your target (impostor) OR key missing |
| `Unable to negotiate ... no matching host key type found. Their offer: ssh-rsa,ssh-dss` | ancient sshd (OpenSSH <7) | `-o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa` |
| `command-line line 0: Bad key types '+ssh-rsa,ssh-dss'` | ssh-dss can't be re-enabled in modern OpenSSH | drop ssh-dss, use `+ssh-rsa` only |
| SSH banner `SSH-2.0-OpenSSH_5.1p1 Debian-5` | embedded/IoT/NAS, NOT a modern Arch/Garuda box | treat as impostor, do not connect as target |

## Impostor heuristic (seen this session: 192.168.0.162)
A /24 scan surfaced an OpenSSH_5.1p1 Debian-5 host (MAC `00:d0:b8:…`) on the same
home subnet. It was an old embedded device, NOT the target ThinkPad P50 (which runs
current OpenSSH). A naive "first SSH host = target" assumption would have connected
to the wrong box.

Confirm target identity via three independent signals:
1. **Banner version** — a Garuda/Arch host runs current OpenSSH; ancient versions = embedded.
2. **MAC OUI** — matches the vendor you expect (Lenovo for a P50, not a NAS/IoT OUI).
3. **Key acceptance** — your `IdentityFile` (ed25519) authenticates the real host; an
   impostor rejects it with "Permission denied (publickey)".
