# Podroid VM rootfs — verified current state (2026-08-07)

Ist-Zustand of the substrate-A VM rootfs, verified by reading the full build
pipeline (`jrwl-messenger/android/podroid/build-rootfs/`, `build-all.sh`,
`Dockerfile.rootfs`, app-side `PodroidService.kt` / `SettingsRepository.kt`)
plus the mazemaker-mobile client (`LocalPodHermes.kt`, `LocalPodMcpProxy.kt`).
Use this map before any "add service X natively into the Podroid VM" task.

## Build flow (how the VM image is produced)
`./build-all.sh rootfs` → `build-rootfs/Dockerfile.rootfs`:
- Stage 1 `vsock-builder` (alpine:3.23 arm64, qemu-user): compiles
  `podroid-vsock-agent`, `podroid-hostd`, `podroid-overlay-normalize` (C, musl-static).
- Stage 2: Alpine minirootfs 3.23.4 aarch64 → `/work/build-rootfs.sh` runs
  `apk add` + copies `build-rootfs/files/` (the overlay staging dir) into the
  rootfs → `mksquashfs` (zstd level 19, xattrs preserved) →
  `app/src/main/assets/alpine-rootfs.squashfs` (~395 MB, shipped inside the APK).
- Boot: initramfs `init-podroid` stacks squashfs (lower, RO) + ext4 (upper,
  persistent) → overlayfs → `switch_root` into OpenRC (runlevels pre-symlinked
  at build time — host is x86_64, cannot chroot into aarch64).

## What the rootfs installs (`build-rootfs.sh` Z.16–56)
Containers: `podman`, `docker`+`docker-openrc`+`docker-cli-compose`, `lxc`+
templates+openrc+bridge, `crun`, `fuse-overlayfs`, `slirp4netns`,
`aardvark-dns`/`netavark`, iptables/ip6tables/nftables/bridge-utils/iproute2.
System: alpine-base, openrc, bash, shadow+shadow-uidmap (newuidmap/newgidmap
get cap_setuid/cap_setgid xattrs, Z.61–64), doas+sudo (setuid, %wheel),
gcompat, curl, ca-certificates, gzip, xz, `python3` (NO py3-pip), dropbear
(SSH). GUI: tigervnc (Xvnc), pulseaudio, fonts. Emulation: `qemu-x86_64`
user-mode (binfmt registered in `podroid-bootstrap` Z.50–66).
**No Node.js, no build toolchain (gcc/musl-dev), no GPU stack.**
Root password `podroid` (SHA-512, Z.87–88). Runlevel symlinks Z.280–286 now
include `iris-pod`, `podroid-hermes`, `podroid-hermes-mcp`.

## hermes-agent: ALREADY NATIVE in the VM (as of 2026-08-07)
- `build-rootfs.sh` Z.117–129 copies `/etc/init.d/podroid-hermes` +
  `podroid-hermes-mcp` into the squashfs.
- Z.175–200 unpacks vendor tarball
  `build-rootfs/files/usr/local/share/hermes/hermes-podroid.tar` (191 MB) →
  `/opt/hermes` (venv + `start.sh` + static `hermes-agent.bin` exec-wrapper);
  repo `files/opt/hermes/start.sh` + `config.template.yaml` +
  `mcp-mazemaker-watch.sh` override the tarball copies.
- `start.sh`: `API_SERVER_HOST=0.0.0.0`, `API_SERVER_PORT=8088`,
  `HERMES_HOME=/opt/hermes/hermes-agent-data`; per-install bearer generated
  once via `secrets.token_hex(32)` → `$HERMES_HOME/api_server.key` (survives
  reboots in the persistent overlay); seeds `config.yaml` from template only
  if absent; `exec /opt/hermes/venv/bin/hermes gateway run`.
- `config.template.yaml`: `openrouter_free` custom provider, empty api_key,
  model `tencent/hy3:free`. Operator pastes key via app; NO key ships.
- Tarball producer: `projects/podroid-hermes/vm-image/build_rootfs_native.sh`
  (podman arm64 + qemu; venv at FINAL path `/opt/hermes/venv` — shebang rule)
  then `inject_venv.sh`, manually copied into `build-rootfs/files/...`.
- Note: verify the built squashfs actually contains the venv after a rebuild
  (host may lack `unsquashfs` — extract via a container or trust the date
  ordering: tarball older than squashfs ⇒ included).

## Mazemaker engine: NOT in the VM
- Zero hits for `wonderland|8765|8000` in `build-rootfs/` and `build-all.sh`.
  No mazemaker-pro/python-engine, no Postgres/pgvector, no bge-m3, no MCP
  server inside the guest.
- What exists is MCP CLIENT wiring: `mcp-mazemaker-watch.sh` (loop POLL=15 /
  SETTLE=45) idempotently writes
  `mcp_servers.mazemaker = {url: http://<default-gw>:8790/mcp, enabled:true}`
  into `config.yaml` and restarts `podroid-hermes` once when the proxy is
  reachable but hermes registered <1 MCP server (hermes only retries MCP 3×
  at startup). Port 8790 is the APP's `LocalPodMcpProxy.kt` (binds ONLY the
  AVF/crosvm/tap interface), which tunnels MCP JSON-RPC via QR-paired
  token+AES+TLS `GatewayClient.pod("POST","/mcp")` to the DESKTOP gateway
  :8443 → `cmd:pod` → mazemaker pod :8765/mcp. So engine access requires app
  open AND phone paired to desktop — that is the current architecture.

## Ports / services
Guest OpenRC: `podroid-bootstrap` (modules, cgroup2, ZRAM 1.5×RAM lz4,
binfmt, 9p downloads, binds /var/lib/docker + /var/lib/containers/storage to
raw ext4), `podroid-network` (QEMU: static 10.0.2.15/24 gw 10.0.2.2; AVF:
DHCP over TAP), `podroid-hostd` (guest→Android bridge, argv0-dispatched
multicall podroid-notify/forward/open/power/headless/server), `podroid-vsock`
(AVF-only, vsock 9100 ctl, seed `etc/podroid/forwards.conf`), `podroid-x11`
(Xvnc 5900 no-auth + pulseaudio 4713 raw PCM, both loopback-forwarded only),
`dropbear` :22, `iris-pod` (podman container, REST 9091 + WS 9092, vendored
tar + sha256-stamp reload), `podroid-hermes` :8088, `podroid-hermes-mcp`
(watcher, no port), docker/lxc/dnsmasq.lxcbr0 in default runlevel.
Android-side auto-injected forwards (`PodroidService.kt` Z.329–367):
9922→22 (SSH if enabled), 5900, 4713, 9091, 9092, 8088→8088 — all
loopbackOnly. AVF host-bridge vsock 9101.

## How code gets into the VM (three paths)
1. **Baked into squashfs**: extend the apk list in `build-rootfs.sh` and/or
   stage files in `build-rootfs/files/`, rebuild rootfs (docker) + APK.
2. **Runtime `apk add`**: persists in the ext4 overlay, survives reboots.
3. **Vendor tarball** (preferred for big stacks): place tar in
   `files/usr/local/share/...`, unpack in `build-rootfs.sh` (hermes pattern:
   `tar -C $ROOTFS -xf` paths relative to /) OR `podman load -i` at first
   boot (iris pattern). New services additionally need: an init.d script
   copied in Z.107–129 style + entry in the runlevel loop Z.280 + an
   Android-side loopback forward in `PodroidService.kt` Z.359–367 style.

## Hard limits
- RAM default **512 MB** (`SettingsRepository.kt` Z.126 `pref(KEY_VM_RAM,512)`;
  QEMU tb-size 512 MiB). NOTE: "~1 GB" is a myth — task hints citing it are
  wrong. ZRAM 1.5×RAM lz4 as swap. CPUs default **2** (Z.132).
- **No GPU** — no VirtIO-GPU/Vulkan in the kernel config; software rendering
  only. The desktop engine's `:gpu` containers (bge-m3 embeddings, dream
  worker) are CPU-only here = very slow.
- Boot: AVF/pKVM ~6 s, QEMU/TCG ~190 s. x86_64 images only via slow
  user-mode emulation. No Node, no toolchain, no system pip (venvs must be
  built with `--copies` at the final path, per `alpine-python-rootfs`).

## App-side expectations (mazemaker-mobile)
`LocalPodHermes.kt`: `BASE_URL=http://127.0.0.1:8088`,
`DEFAULT_MODEL="hermes-agent"`; `isUp()` = GET /v1/models with Bearer key;
chat = POST /v1/chat/completions (SSE, delta tokens, [DONE]) — OpenAI-compatible.
`LocalPodMcpProxy.kt`: TAP-only :8790, only POST /mcp, 404/405 otherwise.

## Gap list for "hermes-agent + mazemaker NATIVE in the VM"
Already done: hermes-agent native (venv, gateway :8088, per-install key);
missing OpenRouter key is operator-side. Missing for mazemaker native:
engine code + python deps (vendor-tarball to /opt/mazemaker like hermes),
PostgreSQL + pgvector, bge-m3 embeddings on CPU, wonderland MCP front on
guest :8765 + new 8765→8765 loopback forward, license client; plus raise VM
RAM (512 MB default too tight for Postgres + engine) and accept no-GPU.
