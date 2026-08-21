#!/bin/bash
# One-shot Debian/Ubuntu cloud-image VM builder.
# Usage: build-debian-vm.sh [codename] [port] [ram_mb] [cores]
#   codename : trixie (default) | bookworm | sid
#   port     : host SSH forward port (default 2222)
#   ram_mb   : default 2048
#   cores    : default 2
#
# Produces ~/vm/ with: <name>-base.qcow2, cloud-init.iso, start-<name>.sh,
# stop-<name>.sh, and a systemd-user service enabled with linger.
set -e

CODENAME="${1:-trixie}"
PORT="${2:-2222}"
RAM="${3:-2048}"
CORES="${4:-2}"
NAME="${CODENAME}-vm"
VMHOME="$HOME/vm"
PUBKEY="$(cat "$HOME/.ssh/id_ed25519.pub" 2>/dev/null || echo)"
HASH="$(openssl passwd -6 "${CODENAME}" 2>/dev/null || echo)"

mkdir -p "$VMHOME"
cd "$VMHOME"

echo "==> resolving cloud image for $CODENAME"
BASE="https://cloud.debian.org/images/cloud/${CODENAME}/"
LATEST=$(curl -s --max-time 25 "$BASE" | grep -oE 'href="[0-9][^"]*"' | sed 's/href="//;s/"//' | sort -r | head -1)
IMG=$(curl -s --max-time 25 "$BASE$LATEST" | grep -oE 'href="[^"]*genericcloud-amd64[^"]*\.qcow2"' | sed 's/href="//;s/"//' | head -1)
[ -z "$IMG" ] && { echo "FAILED to find image for $CODENAME"; exit 1; }
URL="${BASE}${LATEST}${IMG}"
echo "    $URL"

echo "==> download + resize"
curl -L --max-time 300 -o "${NAME}-base.qcow2" "$URL"
qemu-img resize "${NAME}-base.qcow2" 20G

echo "==> cloud-init"
cat > user-data <<EOF
#cloud-config
hostname: ${NAME}
users:
  - name: alca
    groups: sudo
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
    passwd: ${HASH}
    ssh_authorized_keys:
      - ${PUBKEY}
ssh_pwauth: true
package_update: true
runcmd:
  - sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
  - systemctl restart ssh
EOF
cat > meta-data <<EOF
instance-id: ${NAME}
local-hostname: ${NAME}
EOF
if command -v mkisofs >/dev/null; then mkisofs -o cloud-init.iso -V cidata -r -J user-data meta-data;
elif command -v genisoimage >/dev/null; then genisoimage -o cloud-init.iso -V cidata -r -J user-data meta-data;
else xorriso -as mkisofs -o cloud-init.iso -V cidata -r -J user-data meta-data; fi

echo "==> start/stop scripts"
cat > "start-${NAME}.sh" <<EOF
#!/bin/bash
cd "\$(dirname "\$0")"
exec qemu-system-x86_64 -name ${NAME} -machine type=q35,accel=kvm -cpu host \
  -smp ${CORES} -m ${RAM} -boot order=c \
  -drive file=${NAME}-base.qcow2,if=virtio,format=qcow2 \
  -drive file=cloud-init.iso,if=virtio,format=raw,media=cdrom \
  -netdev user,id=net0,hostfwd=tcp::${PORT}-:22 -device virtio-net-pci,netdev=net0 \
  -display none -daemonize -pidfile ${NAME}.pid
EOF
chmod +x "start-${NAME}.sh"
cat > "stop-${NAME}.sh" <<EOF
#!/bin/bash
cd "\$(dirname "\$0")"
[ -f ${NAME}.pid ] && { kill "\$(cat ${NAME}.pid)" 2>/dev/null && echo stopped; rm -f ${NAME}.pid; }
EOF
chmod +x "stop-${NAME}.sh"

echo "==> systemd user service + autostart"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/${NAME}.service" <<EOF
[Unit]
Description=Debian ${CODENAME} VM (${CORES} vCPU / ${RAM}MB) in ~/vm
After=network-online.target
Wants=network-online.target
[Service]
Type=forking
WorkingDirectory=%h/vm
PIDFile=%h/vm/${NAME}.pid
ExecStart=%h/vm/start-${NAME}.sh
ExecStop=%h/vm/stop-${NAME}.sh
Restart=on-failure
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable "${NAME}.service"
loginctl enable-linger "$USER"
systemctl --user start "${NAME}.service"

echo "==> done. Wait ~45s, then: ssh -p ${PORT} alca@localhost"
echo "    (if a previous VM used port ${PORT}, first: ssh-keygen -R \"[localhost]:${PORT}\")"
