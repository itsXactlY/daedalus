---
name: podman-deep-dive
description: Podman container runtime — inside out, upside down. Rootless containers, OCI runtime, storage, networking, pods, compose, and Docker compatibility.
category: devops
tags: [containers, podman, rootless, oci, docker]
created: 2026-04-26
---

# Podman — Inside Out, Upside Down

## What Podman IS

Podman (Pod Manager) is a daemonless container runtime. Where Docker needs a persistent `dockerd` daemon running as root, Podman spawns containers as **direct child processes** of the calling user. No daemon = no daemon restart = no orphaned containers.

**Key difference from Docker:**
- Docker: `dockerd` (root) → containers (root/different user)
- Podman: containers are direct children of your shell process (rootless by default)
- Podman can also **behave like a daemon** via `podman.systemd service` for systemd integration

## Architecture

### Rootless Mode (how it actually works)

```
User namespace mapping (uid_map/gid_map):
  container_uid 0   → host_uid 1000 (your user)
  container_uid 1   → host_uid 100000 (shifted range)
  container_uid 2-65536 → host_uid 100001-165536

→ Container root (uid 0 inside) IS your user on the host
→ Container processes run as YOU, not as root
```

On Arch Linux with cgroup v2:
- `cgroupManager: systemd`
- Uses `crun` as OCI runtime (not runc) — faster, written in C
- Network: `netavark` + `aardvark-dns` (custom DNS resolver for containers)

### Storage Layout (Arch default)

```
~/.local/share/containers/storage/
├── storage.lock
├── libpod/
│   ├── containers/     # container layer data
│   └── pods/          # pod metadata
├── overlay/           # image layers (overlay fs)
│   ├── l/
│   └── vfs/          # upper/wrk dirs
└── volumes/          # named volumes

~/.config/containers/storage.conf  (optional overrides)
```

**Graph driver: overlay** on **btrfs** backing filesystem
- Native overlay diff supported (fast diffs)
- `mount_program` not needed (btrfs handles it)

### Networking

```
netavark (new) — custom network stack for rootless containers
├── creates bridge networks
├── manages iptables/nftables rules
└── supports port forwarding

aardvark-dns — custom DNS server
├── listens on 127.0.0.1:53
├── resolves container names/hostnames
└── used instead of /etc/hosts for inter-container DNS
```

Unlike Docker's `docker0` bridge, netavark handles rootless networking via:
- Slirp4netns (network namespaces with slirp)
- Pasta (newer, faster, less overhead)
- Aria2 (alternative)

### Pods

Podman has native **Pod** support (Kubernetes pods):
```
podman pod create --name mypod
podman run -d --pod mypod nginx
podman pod inspect mypod
```
All containers in a pod share: network namespace, hostname, IPC namespace.

### Socket & API

**Default rootless socket:** `/run/user/$UID/podman/podman.sock`

Enable systemd-managed socket (daemon mode for scripting):
```bash
systemctl --user enable --now podman.socket
# Now accessible via: podman --url unix:///run/user/1000/podman/podman.sock ps
```

Or use `podman run -d --name podman serve quay.io/podman/stable api`
Then: `export PODMAN_VAROCK_PATH=/run/user/1000/podman/podman.sock`

## Podman Kube Workflow (podman play kube)

Podman supports Kubernetes-style YAML via `podman play kube`. This is the preferred way to manage persistent pods declaratively.

### Start a pod from YAML
```bash
podman play kube --network=podman mypod.pod
```
`--network=podman` puts the pod on a podman-managed network. Without it, containers may not have DNS resolution.

### Stop and remove
```bash
podman pod stop mypod && podman pod rm mypod
```

### Inspect running pod
```bash
podman pod inspect mypod
podman ps --format "{{.Names}}"  # container names inside pod
```

### Recreate a pod (update + redeploy)
```bash
podman pod stop mypod && podman pod rm mypod
podman play kube --network=podman mypod.pod
```

### Key YAML elements for pods
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: mypod
spec:
  containers:
    - name: app
      image: docker.io/image:latest
      args: ["gateway", "run"]
      ports:
        - containerPort: 8642
          hostPort: 8642
      env:
        - name: API_SERVER_ENABLED
          value: "true"
        - name: API_SERVER_HOST
          value: "0.0.0.0"
        - name: API_SERVER_KEY
          value: "your-api-key-here"
      resources:
        requests:
          memory: 2G
          cpu: 1000
        limits:
          memory: 4G
          cpu: 2000
      volumeMounts:
        - name: data
          mountPath: /opt/data
        - name: host-home
          mountPath: /host-home
      healthCheck:
        startup:
          exec:
            command: ["curl", "-sf", "http://localhost:8642/health"]
          initialDelaySeconds: 15
          periodSeconds: 10
          failureThreshold: 30
  volumes:
    - name: data
      hostPath:
        path: /home/user/.app/data
        type: Directory
    - name: host-home
      hostPath:
        path: /home/user
        type: Directory
  restartPolicy: always
```

### Volume Mount Patterns

**Host home access from container:**
```yaml
volumes:
  - name: host-home
    hostPath:
      path: /home/alca
      type: Directory
volumeMounts:
  - name: host-home
    mountPath: /host-home
```
Inside the container: `/host-home/` maps to host `/home/alca/`. Useful for gateway pods that need to read/write host files.

**Named volumes (for persistent data):**
```bash
podman volume create hermes-data
podman run -v hermes-data:/opt/data myimage
```

### Docker Compatibility

```bash
# Install podman-docker (provides `docker` CLI wrapper)
paru -S podman-docker

# Now `docker ps` == `podman ps`
# Useful for docker-compose, dockerfile builds, etc.

# Alternative: set DOCKER_HOST
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock
docker ps  # actually calls podman
```

### Quadlets (systemd-native containers)

Podman can generate systemd unit files from container specs:
```bash
podlet basic nginx --name nginx → /etc/containers/systemd/nginx.container
# More declarative than docker-compose, systemd-native
```

## Common Commands

```bash
# Run
podman run -d --name nginx -p 8080:80 nginx:alpine
podman run -it --rm ubuntu bash
podman run --pod new:mypod -d redis

# Manage
podman ps -a
podman stop nginx
podman rm nginx
podman images
podman rmi nginx

# Build (Dockerfile-compatible)
podman build -t myapp .
podman build -f Dockerfile.dev -t myapp:dev .

# Volumes
podman volume create mydata
podman run -v mydata:/data nginx
podman run -v $(pwd)/data:/data nginx  # bind mount

# Networks
podman network create mynet
podman network inspect mynet

# Logs
podman logs -f nginx
podman logs --tail 100 nginx

# Exec
podman exec -it nginx sh

# Inspect
podman inspect nginx
podman port nginx

# System
podman system df        # disk usage
podman system prune -a  # cleanup
podman system reset     # nuclear option
```

## Podman vs Docker Key Differences

| Feature | Podman | Docker |
|---------|--------|--------|
| Daemon | No (rootless by default) | Yes (dockerd) |
| Root | Containers run as user | Daemon runs as root |
| Pods | Native K8s-style pods | No (docker-compose grouping only) |
| systemd | Native quadlets | systemd via unit files |
| Socket | user-specific | /var/run/docker.sock |
| Build | buildah (podman build) | docker build |

## Useful Debug Commands

```bash
# See what's happening inside
podman ps --format json | jq
podman inspect --format '{{.State}}' nginx

# Storage
podman system connection list
cat ~/.local/share/containers/storage/libpod/containers/*.json 2>/dev/null | jq

# Rootless debugging
ls ~/.local/share/containers/containers.log 2>/dev/null
podman --log-level=debug run --rm hello-world

# Check cgroups
cat /proc/1/cgroup
ls /sys/fs/cgroup/

# Check namespaces of a running container
ls /run/user/1000/netns/  # network namespaces
ls /proc/$(podman inspect --format '{{.State.Pid}}' nginx)/ns/  # container namespaces
```

## Installation (Arch Linux)

```bash
paru -S --needed podman
# Dependencies auto-installed: crun, conmon, netavark, aardvark-dns, containers-common
```

## Your System State (April 2026)

```
Podman: 5.8.2
Runtime: crun 1.27.1
Network: netavark 1.17.2 + aardvark-dns 1.17.1 + pasta (passt 2026_01_20)
Storage: overlay on btrfs at ~/.local/share/containers/storage/ (~402GB used)
Cgroups: v2 + systemd
Socket: /run/user/1000/podman/podman.sock (ENABLED via systemctl --user)
Docker compat: podman-docker installed → `docker ps` works natively
```

## Network Security Finding (CRITICAL)

**Default networking has NO isolation.** No `podman0` bridge. Containers inherit host's network stack and reach the LAN. For isolation: create a custom network.

## GPU Access

`nvidia-container-toolkit` NOT installed. Install with: `pkexec pacman -S --noconfirm nvidia-container-toolkit`

## Deployment Files Created (April 2026)

```
~/.config/containers/
├── registries.conf, systemd/*.container, *.podman-compose.yml, *.podman.kube.yml

~/.hermes/docker/podman/
├── docker-compose.yml, Dockerfile.neural-memory, hermes-backup.sh, ARCHITECTURE.md
```

## Security Summary

| Test | Result |
|------|--------|
| Container root → host root escape | BLOCKED |
| `--cap-add ALL` grants dangerous caps | YES (SYS_ADMIN, NET_ADMIN) |
| Default mount syscall | BLOCKED by seccomp |
| Host root write via `-v /:/host` | BLOCKED |
| CPU/memory limits | WORK via cgroups v2 |

Gold standard: `podman run --read-only --cap-drop ALL --security-opt=no-new-privileges:true --network=none myimage`
