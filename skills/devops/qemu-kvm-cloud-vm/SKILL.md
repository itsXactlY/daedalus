---
name: qemu-kvm-cloud-vm
description: Spin up a disposable Debian/Ubuntu KVM VM on a Linux host (Arch/Garuda/etc.) from an official cloud image — no installer ISO, no interactive install. Covers finding the current cloud image URL, cloud-init seeding (user/SSH key/password), QEMU virtio + KVM launch with host SSH-forward, systemd-user autostart, and the stale-known_hosts trap on reused forwarded ports. Use when a user says "set up a VM", "Debian/Ubuntu VM in ~/vm", "quick KVM instance", or wants a throwaway Linux guest to SSH into.
---

# QEMU/KVM Cloud-Image VM (no installer)

Stand up a runnable Debian/Ubuntu VM in minutes using an official cloud image
+ cloud-init. No netinst ISO, no debian-installer preseed, no interactive
install. The guest boots straight into a provisioned, SSH-able system.

## When to use
- "set up a Debian/Ubuntu VM in ~/vm", "quick KVM instance", "throwaway Linux guest"
- Need a clean Linux environment to SSH into from the host.
- Target Debian release by codename: Trixie=13, Bookworm=12, Sid=unstable.

## Architecture
- Host runs QEMU with KVM (`-machine type=q35,accel=kvm`). Requires `/dev/kvm`.
- Guest disk = downloaded cloud-image QCOW2, resized with `qemu-img resize`.
- Provisioning = a small `cidata` ISO (cloud-init `user-data` + `meta-data`)
  attached as a virtio CD-ROM. cloud-init creates the user, injects the SSH
  key, enables password auth, runs `package_update`.
- Networking = QEMU user-mode (`-netdev user,hostfwd=tcp::2222-:22`) → host
  reaches guest via `ssh -p 2222 user@localhost`. No bridge needed.

## Steps (canonical)
1. **Find the current image URL** — cloud images live in DATED subdirectories,
   not at the top level. Don't guess the path; scrape it:
   ```bash
   BASE=https://cloud.debian.org/images/cloud/<codename>/
   LATEST=$(curl -s --max-time 25 "$BASE" | grep -oE 'href="[0-9][^"]*"' \
            | sed 's/href="//;s/"//' | sort -r | head -1)
   curl -s --max-time 25 "$BASE$LATEST" | grep -oE 'href="[^"]*genericcloud-amd64[^"]*\.qcow2"' \
     | sed 's/href="//;s/"//' | head -1   # -> debian-13-genericcloud-amd64-<date>.qcow2
   # Full URL: $BASE$LATEST<filename>
   ```
   Pick `genericcloud` (minimal, no cloud-vendor lock-in) over `generic`/`nocloud`.
2. **Download + resize:**
   ```bash
   mkdir -p ~/vm && cd ~/vm
   curl -L --max-time 300 -o trixi-base.qcow2 "<URL>"
   qemu-img resize trixi-base.qcow2 20G
   ```
3. **Cloud-init ISO** — `user-data` creates the user, injects host SSH key,
   sets a password fallback, enables password SSH auth:
   ```yaml
   #cloud-config
   hostname: trixi-vm
   users:
     - name: alca
       groups: sudo
       sudo: ALL=(ALL) NOPASSWD:ALL
       shell: /bin/bash
       lock_passwd: false
       passwd: <openssl passwd -6 trixi>
       ssh_authorized_keys:
         - <cat ~/.ssh/id_ed25519.pub>
   ssh_pwauth: true
   package_update: true
   runcmd:
     - sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
     - systemctl restart ssh
   ```
   `meta-data`: `instance-id: trixi-vm` + `local-hostname: trixi-vm`.
   Build ISO: `mkisofs -o cloud-init.iso -V cidata -r -J user-data meta-data`
   (fallback `genisoimage` or `xorriso -as mkisofs`).
4. **Launch (KVM, 2 vCPU/2GB, virtio, SSH forward):**
   ```bash
   qemu-system-x86_64 -name trixi-vm -machine type=q35,accel=kvm -cpu host \
     -smp 2 -m 2048 -boot order=c \
     -drive file=trixi-base.qcow2,if=virtio,format=qcow2 \
     -drive file=cloud-init.iso,if=virtio,format=raw,media=cdrom \
     -netdev user,id=net0,hostfwd=tcp::2222-:22 -device virtio-net-pci,netdev=net0 \
     -display none -daemonize -pidfile trixi-vm.pid
   ```
5. **Autostart (systemd user service)** — wrap the launch in a script and
   enable a user service + linger (survives logout/reboot):
   ```ini
   [Unit]
   Description=Debian Trixie VM (2 vCPU / 2GB) in ~/vm
   After=network-online.target
   Wants=network-online.target
   [Service]
   Type=forking
   WorkingDirectory=%h/vm
   PIDFile=%h/vm/trixi-vm.pid
   ExecStart=%h/vm/start-trixi.sh
   ExecStop=%h/vm/stop-trixi.sh
   Restart=on-failure
   [Install]
   WantedBy=default.target
   ```
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable trixi-vm.service
   loginctl enable-linger "$USER"   # starts even without login at boot
   ```
   For systemd-user-service hardening/lifecycle detail, see `durable-process-supervision`.

## Verification
- Wait ~30-60s for cloud-init, then:
  ```bash
  ssh -p 2222 alca@localhost 'hostname; grep PRETTY /etc/os-release; free -h | head -2; nproc; ip route | head -1; cloud-init status'
  ```
- Guest must show: hostname set, correct Debian version, RAM≈allocated,
  2 cores, default route present, `cloud-init status: done`.

## Pitfalls
- **Stale known_hosts on reused forward ports (HIGH-FREQUENCY, hit every time
  you rebuild a VM on a reused port)**: if a PREVIOUS VM used the same hostfwd
  port (e.g. `:2222`), the old host key is still in `~/.ssh/known_hosts`.
  The new VM has a different key → `REMOTE HOST IDENTIFICATION HAS CHANGED`
  → connection refused. Fix: `ssh-keygen -R "[localhost]:2222"` BEFORE
  connecting. (This bit us hard: the old `~/vm-test` VM shared port 2222, the
  stale key blocked the new VM, and the connection sat for a full 60s timeout
  before we cleared it.) If you don't control the port, use a fresh one.
- **`StrictHostKeyChecking=accept-new` is NOT enough to bypass a changed
  key** — it only adds NEW hosts, it still FAILS on a known-host MISMATCH
  (the old entry is "known", just wrong). Symptom in `-vvv`: TCP connects,
  SSH banner exchanges (`compat_banner: match: OpenSSH_...`), then
  `Host key verification failed` with the `Offending key` line. Must `-R` the
  old entry first. Last resort only: `-o StrictHostKeyChecking=no`.
- **Trixie image path (verified 2026-07-07)**: top-level
  `https://cloud.debian.org/images/cloud/trixie/` lists ONLY dated subdirs
  (e.g. `20260706-2531/`). The amd64 genericcloud file is
  `debian-13-genericcloud-amd64-20260706-2531.qcow2`. `generic` also exists
  but `genericcloud` is the minimal, no-vendor-lock choice. The
  `genericcloud` image's DEFAULT user is `debian` (not root) — the
  `user-data` `users:` block still creates `alca` fine.
- **Installer pre-flight may require podman/other deps BEFORE the script
  installs them**: the mazemaker `install.sh` (curl-pipe) does NOT install
  podman itself — it fails pre-flight with "podman not found. Install it
  with: sudo apt install podman". On a fresh cloud VM you must
  `sudo apt install -y podman` (Trixie → podman 5.4.2) before re-running the
  installer. Also: a curl-pipe installer that lands in an interactive
  onboarding wizard (browser URL + email verify + plan choice) will BLOCK in
  the agent session — that step is operator-only and cannot be automated.
- **cloud.debian.org top-level has no .qcow2** — always descend into the
  dated subdir. Guessing `…/debian-13-genericcloud-amd64.qcow2` at the top
  level 404s.
- **`-display none -daemonize` = no VGA/SPICE** — management is SSH-only.
  That's fine for a headless guest; if you need a console, add
  `-display gtk` or a SPICE socket instead.
- **virtio for both disk AND cdrom** — `if=virtio` on the cloud-init ISO
  (not `ide`). The genericcloud image expects virtio; IDE can fail to boot.
- **User-mode networking = NAT, not bridged** — guest gets 10.0.2.x, can
  reach the internet, but the host reaches it ONLY via the hostfwd port.
  No inbound from the LAN unless you add more `hostfwd` rules.
- **Resize BEFORE first boot** — `qemu-img resize` grows the QCOW2; the
  guest's cloud-init/cloud-utils-growpart expands the filesystem on first
  boot. Resizing after boot works too but is less clean.

## Support files
- `scripts/build-debian-vm.sh` — one-shot: download + resize + cloud-init ISO
  + launch + enable autostart. Parameterize codename/port/ram/cores.
- `templates/cloud-init-user-data.yaml` — the user-data above.
- `templates/start-vm.sh`, `templates/vm.systemd-user.service` — launch +
  autostart scaffolding.
