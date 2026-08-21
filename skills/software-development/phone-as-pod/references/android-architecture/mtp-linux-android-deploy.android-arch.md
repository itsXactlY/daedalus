# MTP / ADB Device Connectivity on Linux (KDE + Android)

## Common Setup

- **ADB**: Part of `android-platform-tools` — `pacman -S android-tools` or via SDK platform-tools
- **libmtp**: Provides `mtp-detect`, `mtp-sendfile`, `mtp-connect` — `pacman -S libmtp`
- **KIO MTP**: Part of `kio-extras` (KDE) — automatically handles MTP in Dolphin via `kioworker mtp.so`
- **kioclient5**: CLI for KIO operations — `pacman -S kde-cli-tools`

## The Two Phone Modes

### 1. MTP / File Transfer Mode (Standard)
- USB notification on phone says "File Transfer" or "MTP"
- Standard `libmtp` tools work: `mtp-detect`, `mtp-sendfile`
- `adb devices` must show the device for ADB install
- KIO Dolphin access: `mtp://HUAWEI%20P20/Internal%20storage/Download/`

### 2. HiSuite Mode (Huawei Proprietary)
- USB notification says "HiSuite"
- Phone acts as a "Linux File-CD Gadget" — not standard MTP
- `mtp-detect` sees the device but `mtp-sendfile` hangs or times out
- KIO `kioclient5` operations fail with "cannot write file"
- **Only Huawei HiSuite software can access this mode**
- **Fix**: Switch phone USB to "File Transfer (MTP)" mode

## When ADB Doesn't See The Device

```
$ adb devices
List of devices attached
(empty)
```

Even though `lsusb` shows the phone:
```
Bus 005 Device X: ID 12d1:107e Huawei Technologies Co., Ltd.
```

**Causes**:
1. USB debugging not enabled (Settings → Developer Options → USB Debugging)
2. RSA key not authorized (phone prompts to accept — must unlock screen)
3. USB mode set to "Charging only" instead of "File Transfer"

**Fixes**:
- User must unlock phone and check USB notification
- Switch to "File Transfer (MTP)" mode
- Accept RSA fingerprint prompt on phone
- Re-run: `adb kill-server && adb start-server && adb devices`

## APK Delivery Workarounds (When ADB/MTP Both Fail)

### HTTP Server (Most Reliable)
```bash
cd /path/to/apk-dir/
python3 -m http.server 8768 --bind 0.0.0.0
# Phone browser: http://<PC-LAN-IP>:8768/app-debug.apk
```

### Auto-Install Script
```bash
#!/bin/bash
adb wait-for-device
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell monkey -p dev.mazemaker.mobile -c android.intent.category.LAUNCHER 1
timeout 30 adb logcat --pid=$(adb shell pidof -s dev.mazemaker.mobile) -v time
```

## Killing Stuck KIO MTP Workers

When `mtp-sendfile` or `libmtp` hangs with "device is busy by GVFS or KDE":

```bash
# Find the culprit
fuser /dev/bus/usb/<bus>/<dev>
# e.g.: fuser /dev/bus/usb/005/005 → kiod6 PID

# Kill the workers
kill <kiod6-pid>
killall kioworker  # or kill specific MTP kioworker PIDs

# Then use mtp-sendfile before kiod6 respawns
timeout 15 mtp-sendfile /path/to/file.apk "Name.apk"
```
