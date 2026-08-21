# Cross-arch support: qemu-x86_64 + binfmt_misc in the Podroid VM

How to run amd64 (x86_64) container images inside the Podroid
guest VM, which is aarch64 (Linux 7.0.10 on QEMU 11.0.0 virt
machine). The setup requires three pieces: the qemu-x86_64
binary, a binfmt_misc registration, and the right ordering of
the OpenRC services that run during boot.

## Why this is needed

The iris-messenger .bin is built with `./build-podman-image.sh
amd64` — host arch is x86_64 (no native arm64 build). The
Podroid VM runs aarch64 (because that's the QEMU virt machine
default). The container image is OCI amd64. Without
cross-arch support in the VM, `podman run` fails on the OCI
sysfs mount (crun limitation, see SKILL.md P5).

## The three pieces

### 1. qemu-x86_64 binary in the rootfs

```bash
# In build-rootfs.sh, after the main apk add block:
apk -X "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_BRANCH}/community" \
    -U --allow-untrusted --root "$ROOTFS" add qemu-x86_64
```

This installs the QEMU user-mode emulator for x86_64 as
`/usr/bin/qemu-x86-64` in the squashfs. ~3.6 MB binary, statically
linked, no shared library deps.

Verify inside the VM:
```
podroid:~# ls -la /usr/bin/qemu-x86_64
-rwxr-xr-x 1 root root 3648944 Apr 29 05:47 /usr/bin/qemu-x86_64
podroid:~# qemu-x86_64 --version
qemu-x86_64 version 10.1.5
```

### 2. binfmt_misc registration

binfmt_misc is a Linux kernel feature that lets the kernel
auto-dispatch execution of recognized binary formats to a
user-space interpreter. The kernel sees an ELF64 LSB executable
with `e_machine = EM_X86_64 (0x3e)`, looks up the registered
interpreter, and invokes it with the binary path.

The registration has FOUR parts that all must be correct:

#### 2a. Mount the binfmt_misc filesystem

```bash
if [ -d /proc/sys/fs/binfmt_misc ] && ! mountpoint -q /proc/sys/fs/binfmt_misc; then
    mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc 2>/dev/null
fi
```

The kernel auto-creates the `/proc/sys/fs/binfmt_misc` directory
but does NOT mount the filesystem on it. If you skip this step,
the next part fails with "No such file or directory".

#### 2b. Register the interpreter

The registration format is a single line written to
`/proc/sys/fs/binfmt_misc/register`:

```
:name:type:offset:magic:mask:interpreter:flags
```

For qemu-x86_64:

| field         | value                                                           |
|---------------|-----------------------------------------------------------------|
| name          | qemu-x86_64                                                     |
| type          | M (magic number match)                                          |
| offset        | 0                                                               |
| magic         | ELF magic + 64-bit LSB exec + OS/ABI 0 + machine EM_X86_64      |
| mask          | mask zeros OS/ABI + ABI version fields                         |
| interpreter   | /usr/bin/qemu-x86_64                                            |
| flags         | O + C + F                                                       |

**The magic bytes:**

```
\x7f ELF \x02 \x01 \x01 \x00 \x00\x00\x00\x00\x00\x00\x00\x00 \x02 \x00 \x3e \x00
  |    |   |    |    |    |     |                              |    |     |     |
  |    |   |    |    |    padding (e_ident[7..15] all zero)      |    |     |     |
  |    |   |    |    EI_VERSION=1 (current ELF)                  EI_OSABI=0
  |    |   |    EI_DATA=1 (LSB)                                  e_type=2 (ET_EXEC)
  |    |   EI_CLASS=2 (64-bit)                                   e_machine=0x3e (EM_X86_64)
  |    e_ident[1..3] = "ELF"
  e_ident[0] = 0x7f
```

As a literal printf string in podroid-bootstrap:

```bash
printf ':qemu-x86_64:M::\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x3e\x00:\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff:/usr/bin/qemu-x86_64:OCF\n'
```

**The mask bytes:**

The mask ANDs with the binary's bytes before comparing to the
magic. The mask is `0xff` (match) for fields you want to check,
`0x00` (ignore) for fields you want to ignore.

We want to:
- MATCH the ELF magic, 64-bit, LSB, version
- IGNORE OS/ABI and ABI version (different libcs set these
  differently)
- MATCH e_type=ET_EXEC
- IGNORE the upper byte of e_machine (some compilers set
  reserved bits)

So the mask is:
```
\xff\xff\xff\xff\xff\xff\xff \x00 \xff\xff\xff\xff\xff\xff\xff\xff \xfe\xff\xff\xff
  |              |        |                              |        |    |
  match all      ignore   match all e_ident[8..15]        |        |    ignore
  e_ident[0..6]  OS/ABI                                   |        |    upper byte
                                                       e_type   |     of e_machine
                                                       match    |
                                                                ignore
                                                                ABI version
```

As a literal string:
```bash
\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xff\xff\xff
```

**Why e_machine=0x3e but mask upper byte=0:**

e_machine is a 16-bit value. EM_X86_64 = 0x003e. The bytes in the
file are 0x3e 0x00 (little-endian). The mask is 0xfe 0xff, meaning
"match the lower 7 bits of the first byte (0x3e & 0xfe = 0x3e) but
ignore the upper bit". This allows the binary to set reserved bits
in e_machine without breaking the match.

#### 2c. Flags `OCF`

| flag | meaning                                                       |
|------|---------------------------------------------------------------|
| O    | open-by-fd-at-clone: kernel opens the interpreter binary once, forks share the fd. Faster exec. |
| C    | credentials: set AT_SECURE for the interpreter, allows setuid binaries to clear AT_SECURE if needed. |
| F    | fix-binary: kernel keeps the interpreter open across forks, prevents a race where a child re-execs before parent's exec completes. |

Without `F`, you can get "exec failed: No such file" with crun in
some race conditions. Always include F.

#### 2d. Make the registration idempotent

```bash
if [ ! -f /proc/sys/fs/binfmt_misc/qemu-x86_64 ]; then
    printf '...' > /proc/sys/fs/binfmt_misc/register
fi
```

If you don't check, a re-run of the init script fails with
"Invalid argument" (binfmt_misc rejects re-registration of the
same name).

### 3. Kernel config: CONFIG_BINFMT_MISC=y

```bash
grep BINFMT_MISC /home/alca/projects/jrwl-messenger/android/podroid/Dockerfile
# 'CONFIG_BINFMT_MISC=y' \
# BINFMT_MISC \
```

The kernel is built with CONFIG_BINFMT_MISC=y (built-in, not a
module). The forced_builtin.config block in the Dockerfile includes
it explicitly because some defconfig setups leave it as a module.

## OpenRC ordering

The binfmt_misc registration must happen BEFORE any service that
might exec an x86_64 binary. The relevant order in the Podroid
default runlevel is:

1. podroid-bootstrap  (registers binfmt_misc)
2. podroid-network
3. podroid-hostd
4. podroid-x11
5. dropbear (SSH — runs aarch64 binaries, doesn't need binfmt_misc)
6. podroid-resize
7. podroid-vsock
8. podroid-ready
9. iris-pod  (uses podman to run an amd64 container — NEEDS binfmt_misc)

In the current Podroid rootfs, podroid-bootstrap has no
`need`/`before` directives, so it runs early. The iris-pod init
has `need net` and `need podman`, so it depends on the network and
podman service. podman itself doesn't depend on podroid-bootstrap
(so the OpenRC graph doesn't enforce the order).

**Robustness fix:** add `before podman` to podroid-bootstrap's
`depend()` so the OpenRC graph enforces the order:

```bash
depend() {
    need localmount
    before podroid-network
    before podman        # ← ensures binfmt_misc is registered
                          #   before podman tries to load/run containers
}
```

## Verifying the setup inside the VM

```bash
# 1. SSH in (once TCG is not saturated)
ssh -o StrictHostKeyChecking=no root@127.0.0.1 -p 9922

# 2. Check binfmt_misc status
cat /proc/sys/fs/binfmt_misc/status
# enabled

# 3. Check the registration
cat /proc/sys/fs/binfmt_misc/qemu-x86_64
# enabled
# interpreter /usr/bin/qemu-x86_64
# flags: OCF
# offset 0
# magic 7f454c4602010100000000000000000002003e00
# mask ffffffff00fffffffffffffffeffffff

# 4. Check qemu-x86_64 binary
ls -la /usr/bin/qemu-x86_64
# -rwxr-xr-x 1 root root 3648944 ...

# 5. Load the image
podman load -i /usr/local/share/iris/iris-messenger-amd64.tar
# Loaded image: localhost/iris-messenger:amd64  (25 sec for 25 MB)

# 6. Run the .bin directly (skips the OCI container)
qemu-x86_64 /usr/local/share/iris/iris-messenger.bin --help
# (this works if /lib64/ld-linux-x86-64.so.2 is on the VM)
```

## What does NOT work (and why)

- **`podman run` on the amd64 image** — fails with "crun: mount
  'sysfs' to 'sys': Operation not permitted: OCI permission denied".
  The cross-arch code path in the kernel's mount syscall returns
  EPERM even for rootless-but-allowed operations. Workaround:
  build the arm64 .bin (the proper fix) or run the .bin directly
  with `qemu-x86_64` (skips podman/crun entirely).

- **`qemu-x86_64 /path/to/.bin` if the .so libs are not at the
  RPATH** — fails with "Error relocating ... unsupported
  relocation type 7" (R_X86_64_JUMP_SLOT). The iris-messenger
  .bin's RPATH is `/usr/lib:/lib:/lib64`. The glibc +
  libssl + libcrypto + libsqlite libs are in the container's
  `/usr/lib/` but NOT in the VM's `/usr/lib/`. Either:
  - Extract them from the container (`podman create` +
    `podman cp`) and place at `/usr/lib/` on the VM
  - Run inside the container (which has them at the right path)

- **SSH into the VM while x86_64 emulation is running** —
  dropbear can't get CPU for the KEX handshake. The TCG-x86
  threads dominate. Use the serial console (console.log) for
  boot-time debug, podroid-forward for runtime API access.

## Performance: TCG-x86-on-aarch64-on-aarch64

The iris-messenger .bin runs as x86_64, emulated by qemu-x86_64
inside the VM, which itself runs as aarch64-on-aarch64 under
QEMU TCG. That's two layers of emulation. Realistic performance:

- `podman load -i` (25 MB tarball): 25 seconds
- x86_64 binary startup: 5-15 seconds
- Iris-messenger Python initialization: 30-60 seconds
- Steady-state CPU usage: 5-15% per TCG thread (both pegged)

For comparison, native arm64 .bin on native arm64 QEMU (AVF/pKVM
when available): the same workload finishes in 1-2 seconds.

## When the iris-android client is the actual user

The iris-android client talks to the iris-messenger REST/WS
endpoints at 127.0.0.1:9091/9092 on the Android device. These
ports are forwarded by podroid-forward (a podroid-hostd IPC
mechanism) from the VM's eth0 to the host's 127.0.0.1. The
forwarding goes through QEMU's main loop, not the TCG threads,
so it isn't starved by the x86 emulation.

End-user UX: tap the iris-android icon, the VM boots, iris-pod
starts, podroid-forward registers, the chat client connects to
127.0.0.1:9091, the user is ready to pair. No SSH required.
