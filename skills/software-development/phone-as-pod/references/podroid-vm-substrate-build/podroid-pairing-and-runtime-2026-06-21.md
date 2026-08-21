# Podroid + iris-messenger: end-to-end pairing transcript (2026-06-21)

Reference session log. Captures the exact commands, error messages,
and verification that confirmed the full stack works on the Huawei
P20 Pro (UBV7N19122000968, Android 10, EML-L29). Use this when
debugging a similar chain or when onboarding a new device.

## Context

State at start of session:
- Podroid APK installed (com.excp.podroid.debug v1.2.5-debug)
- iris-android APK installed (dev.itsxactly.iris.debug v1.0.0-debug)
- Desktop pod `boring_dirac` running on host at 192.168.0.2:9091
  (NOT the target — the architecture is phone→Podroid→Podman→.bin)
- Podroid VM had been previously running, iris-pod service started
  with `[ok]`, but the system was in a regressed state after a
  force-stop+restart during a prior session

## Initial failures

1. **Pre-Reset state**: `iris-pod` service in `rc-status` showed
   `crashed` after a prior force-stop. `podman ps` showed
   `iris-messenger` container in `Status: created` (never reached
   `Up`). `podman inspect` showed error:
   `crun: mount 'sysfs' to 'sys': Operation not permitted: OCI permission denied`

2. **lxc relocation errors** appeared in `console.log`:
   `Error relocating /usr/lib/libgcc_s.so.1: unsupported relocation type 6`
   (this was actually a downstream effect of iris-pod never
   starting — podroid-network then failed because it depends on
   iris-pod's network namespace setup)

3. **VM settings had been mis-set** (2 GB RAM / 4 CPU instead of
   512 MB / 2 CPU) — likely from a UI mis-click on a prior RAM/CPU
   button. The settings persisted across the force-stop.

## Recovery sequence

### Step 1: full Reset Everything

In Podroid Settings → scroll down → "Reset VM (deletes all data)"
→ confirm "Reset Everything". Returns to fresh-install wizard
("STEP 1 OF 4: Persistent Storage").

Went through 4 steps with defaults:
- STEP 1: 8 GB storage (default, already selected)
- STEP 2: 2 CPU + 512 MB RAM (defaults were correct)
- STEP 3: downloads sharing OFF (default)
- STEP 4: USB passthrough OFF (default)

After "Get Started", the app returned to a clean main view.

### Step 2: Start VM (clean state)

Tapped "Start VM". Booted through:
- init-podroid → podroid-bootstrap → podroid-network → podroid-x11
  → dropbear (SSH [ok]) → lxc → dnsmasq.lxcbr0
- iris-pod loaded the vendor tarball:
  - `Loading iris-messenger image from vendor tarball (the .bin)`
  - `Getting image source signatures`
  - `Writing manifest to image destination`
  - `Loaded image: localhost/iris-messenger:amd64`
  - `Starting iris-pod ... [ok]`

podroid-ready hit its 50s timeout (TCG is slow) but iris-pod
continued loading in the background.

### Step 3: SSH into VM, diagnose

```bash
ssh -p 9922 root@127.0.0.1    # password: podroid
podroid:~# rc-status
podroid:~# podman ps -a
# CONTAINER iris-messenger, STATUS=created, not Up
podroid:~# podman inspect iris-messenger --format '{{.State.Error}}'
# crun: mount 'sysfs' to 'sys': Operation not permitted: OCI permission denied
```

### Step 4: identify root cause (empty subuid/subgid)

```bash
podroid:~# cat /etc/subuid /etc/subgid
# BOTH EMPTY
```

This is the regression. Pre-Reset, both files contained
`root:100000:65536` (set by `podroid-bootstrap`). The Reset
Everything action wiped the persistent ext4 layer, taking these
files with it. The iris-pod-start.sh wrapper uses
`--userns=keep-id`, which requires subuid/subgid to be populated.

### Step 5: fix

Two options. The sed fix is fastest and simplest:

```bash
podroid:~# rc-service iris-pod stop
podroid:~# sed -i 's/--userns=keep-id //' /usr/local/bin/iris-pod-start.sh
podroid:~# rc-service iris-pod start
podroid:~# sleep 12
podroid:~# podman ps
# CONTAINER iris-messenger  Up 10 seconds  9091-9092/tcp
```

Alternative (preserve keep-id):
```bash
podroid:~# echo "root:100000:65536" > /etc/subuid
podroid:~# echo "root:100000:65536" > /etc/subgid
podroid:~# rc-service iris-pod restart
```

### Step 6: wait for TCG x86_64 emulation

Critical timing: from `rc-service iris-pod start` to 9091 listening
inside the VM is ~5 minutes on the Huawei P20 Pro (the .bin is a
Nuitka onefile that runs through a `qemu-x86_64` user-mode
emulation wrapper). During this time:

```bash
podroid:~# podman top iris-messenger
# USER  PID  PPID  %CPU  ELAPSED         TTY  TIME  COMMAND
# 0     1    0     13    5m33s           ?    46s   /usr/bin/qemu-x86_64 /usr/local/bin/iris-messenger --host 0.0.0.0 --port 9091
# 0     3    1     77    4m39s           ?    3m36s /usr/bin/qemu-x86_64 /tmp/onefile_1_426767_Fe4d-HqcLpY/iris-messenger.bin --host 0.0.0.0 --port 9091
```

When `ss -tlnp | grep 9091` shows the listener, the .bin is up:

```bash
podroid:~# ss -tlnp | grep 9091
# LISTEN 0 5 0.0.0.0:9091 0.0.0.0:*  users:(("iris-messenger.",pid=1827,fd=6))
# LISTEN 0 100 0.0.0.0:9092 0.0.0.0:*  users:(("iris-messenger.",pid=1827,fd=7))
```

### Step 7: podroid-forward 9091/9092 to phone's loopback

The Podroid Settings UI has the "Port forwards" section under
NETWORK. The QEMU engine stores rules in a DataStore; the
`EngineHolder` reconciles them at runtime via the QMP monitor
(see `addPortForward` in `QemuEngine.kt`). Adding a rule via
the UI calls QMP `hostfwd_add` on the live QEMU process.

Procedure (UI form, with the position corrections from P-AdbInput
in the phone-as-pod skill):
1. Podroid main view → Settings (gear icon, top right) — note
   that the "Settings" button on the Terminal toolbar opens the
   terminal settings, not the VM settings. Look for the gear icon
   on the home screen.
2. Scroll to NETWORK → Port forwards → "+ Add"
3. **Android port field center is at (360, 429)** on the
   720x1600 P20 Pro display, NOT (360, 606) which is the field
   label position. (See phone-as-pod P-AdbInput for the regex
   that finds the actual EditText center.)
4. Tap → type 9091
5. **VM port field center is at (360, 585)**
6. Tap → type 9091
7. Tap Add

Verify:
```bash
adb -s UBV7N19122000968 shell ss -tln | grep -E '9091|9092'
# LISTEN 0 0 0.0.0.0:9091 0.0.0.0:*
# LISTEN 0 0 0.0.0.0:9092 0.0.0.0:*
```

### Step 8: verify via adb forward

```bash
adb -s UBV7N19122000968 forward tcp:9099 tcp:9091
curl -s -w '\nHTTP %{http_code} (%{time_total}s)\n' http://127.0.0.1:9099/health
# {"error": "authentication required"}
# HTTP 401 (1.2s)  <-- proves phone:9091 -> QEMU hostfwd -> VM iris-messenger
```

### Step 9: pair iris-android

```bash
# iris-android's Iris-ID is "61588d2e" (8 hex chars, on the phone)
# Step 9a: create identity on the pod
curl -s -X POST http://127.0.0.1:9099/api/identity/create \
  -H 'Content-Type: application/json' \
  -d '{"name":"61588d2e"}'
# {"id": "da6a1f93", "display_name": "61588d2e", "fingerprint": "DA:6A:1F:93:...",
#  "public_key": "...", "x3dh_identity_key_pub": "..."}

# Step 9b: generate pairing token
curl -s -X POST http://127.0.0.1:9099/api/pairing/create \
  -H 'Content-Type: application/json' \
  -d '{"identity_id":"da6a1f93"}'
# {"pairing_token": "ZNLI9YFX", "my_id": "da6a1f93", "expires_in": 600}
```

Note: the iris-android "6-digit code" field actually accepts the
8-character alphanumeric `pairing_token` from the API (the label
in the UI is misleading — it's 8 chars from
`generate_pairing_token()` in `crypto.py:190`, not 6).

Then on the phone:
1. Launch iris-android (`am start dev.itsxactly.iris.debug/dev.itsxactly.iris.MainActivity`)
2. PairingScreen shows: "Your Iris-ID: 61588d2e" +
   "6-digit code" input field + "Pair" button
3. Tap the 6-digit code field, type `ZNLI9YFX`
4. Tap "Pair"

iris-android switches to "No chats yet. Pair with a peer to start."
— the full stack is operational.

## Verification checklist (use after a similar recovery)

- [ ] VM is Running (uptime ticking) on 512 MB / 2 CPU
- [ ] console.log shows: `Loaded image: localhost/iris-messenger:amd64`
      then `Starting iris-pod ... [ok]`
- [ ] `rc-status` shows `iris-pod [started]`, not `[crashed]`
- [ ] `podman ps` shows iris-messenger `Up`, not `created`
- [ ] `podman top` shows the `qemu-x86_64` wrapper process running
- [ ] `ss -tlnp` shows 9091 and 9092 listening inside the VM
- [ ] Phone `ss -tln` shows 9091 and 9092 listening on phone (podroid-forward)
- [ ] `curl http://127.0.0.1:9099/health` (via adb forward) returns
      HTTP 401 with `{"error": "authentication required"}`
- [ ] iris-android PairingScreen accepts the pairing token, transitions
      to the chat list with "No chats yet"
- [ ] `/etc/subuid` and `/etc/subgid` are non-empty in the VM
      (or `--userns=keep-id` has been removed from iris-pod-start.sh)

## Time budget (Huawei P20 Pro, reference)

| Step | Time |
|------|------|
| Reset Everything → wizard → Start VM tap | 30s |
| VM boot to "Ready!" in Podroid UI | 90s |
| iris-pod service start to `podman ps` showing Up | 12s |
| .bin to bind 9091 inside the VM (TCG) | ~5 min |
| podroid-forward to phone's 9091 listener | 5s |
| `curl` response to adb-forwarded 9099 | 1-7s |
| Identity create + pairing create | 15s |
| iris-android tap-and-pair | 5s |
| **Total time from clean Reset to iris-android "No chats yet"** | **~8 min** |

The 5-minute TCG-x86_64 wait is the dominant cost. It scales with
the device's ARM CPU. On a Snapdragon 8 Gen 2 device, expect
~30-60s. On a slower device (e.g. Kirin 970 in the P20 Pro),
expect up to 10 min.
