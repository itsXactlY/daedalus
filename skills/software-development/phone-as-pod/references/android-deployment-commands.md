# android-deployment-commands.md

Concrete adb command reference for shipping a phone-as-pod APK to a
real device. Verified on Huawei EML-L29 (P20 Pro, Android 10, arm64-v8a)
with iris-messenger all-in-one APK, 2026-06-20.

## 0. Pre-flight

```bash
# Find your device
adb devices -l
# UBV7N19122000968  device usb:5-4 product:EML-L29 model:EML_L29 ...

# Confirm arch + Android version (matters for ABIs + KeyStore algorithms)
adb shell getprop ro.build.version.release    # e.g. 10
adb shell getprop ro.build.version.sdk        # e.g. 29
adb shell getprop ro.product.cpu.abilist      # e.g. arm64-v8a,armeabi-v7a,armeabi
adb shell getprop ro.product.model            # e.g. EML-L29

# Disk space (APKs are 30-80 MB; VM image extracts another 200 MB)
adb shell df /data | tail -1
```

## 1. Build + install the APKs

```bash
# Build the iris-android APK
cd android/iris-android
export ANDROID_HOME=$HOME/Android/Sdk
./gradlew assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk (~28 MB)

# Build the Podroid APK (NOTE: this is gradle-only — QEMU binary is NOT included)
cd ../podroid
./gradlew assembleDebug
# → app/build/outputs/apk/debug/app-debug.apk (~37 MB without QEMU,
#   ~83 MB with QEMU if you ran ./build-all.sh qemu first)
```

**GOTCHA: QEMU binary is NOT in the gradle-only build.** The QEMU
binary (`libqemu-system-aarch64.so`, ~16 MB) is built by
`./build-all.sh qemu` which uses Docker (or podman) to compile from
source. If you only run `./gradlew assembleDebug`, the APK ships
without it and the VM shows "ERROR: QEMU binary not found." when you
tap "Start VM". The build is 15-30 min the first time. After that,
incremental rebuilds are seconds.

```bash
# Full build (one-time, 15-30 min)
cd android/podroid
./build-all.sh qemu
./gradlew assembleDebug
```

```bash
# Install both APKs
adb install -r android/iris-android/app/build/outputs/apk/debug/app-debug.apk
adb install -r android/podroid/app/build/outputs/apk/debug/app-debug.apk
# → "Performing Streamed Install" / "Success"
```

## 2. Find the correct activity class name

**GOTCHA: the launchable activity class is `<applicationId>.<ClassName>`,
NOT `com.excp.podroid.MainActivity` (which is the source path).**
applicationId for debug builds has `.debug` appended.

```bash
# WRONG (works for source path, fails at runtime):
adb shell am start -n com.excp.podroid/com.excp.podroid.MainActivity
# → Error: Activity class {...} does not exist.

# RIGHT (uses installed package, not source path):
adb shell pm dump com.excp.podroid.debug | grep -A 1 MAIN
# c99e040 dev.itsxactly.iris.debug/dev.itsxactly.iris.MainActivity filter ...

# Or: resolve via cmd package
adb shell cmd package resolve-activity --brief dev.itsxactly.iris.debug
# → dev.itsxactly.iris.debug/dev.itsxactly.iris.MainActivity

# Launch with the correct name
adb shell am start -n dev.itsxactly.iris.debug/dev.itsxactly.iris.MainActivity
```

## 3. Read the live UI (uiautomator dump)

```bash
# Dump the current UI tree to /sdcard/window_dump.xml
adb shell uiautomator dump

# Pull and parse (extract all visible text labels)
adb shell cat /sdcard/window_dump.xml | python3 -c "
import sys, re
xml = sys.stdin.read()
for label in re.findall(r'text=\"([^\"]+)\"', xml):
    if label and label != 'null':
        print(f'  {label}')
"
```

This is the fastest way to verify the app is rendering what you think
without taking a screenshot. Worked when the pairing screen showed:

```
text: Iris Messenger
text: Your Iris-ID
text: 61588d2e
text: Open the local pod and enter the 6-digit pairing code.
text: 6-digit code
text: Pair
text: Or pair via QR code
text: Scan their code
text: Show my code
```

## 4. Capture a screenshot

```bash
# PNG to stdout, redirect to file
adb exec-out screencap -p > /tmp/screen-01.png

# Verify it's a valid PNG
file /tmp/screen-01.png
# → PNG image data, 720 x 1496, 8-bit/color RGBA, non-interlaced

# View it (Hermes vision_analyze can read the PNG and describe what's on screen)
```

## 5. Diagnose a startup crash

Most iris-android crashes are visible in logcat within 5 seconds of
launch. The exact pattern:

```bash
adb shell am force-stop dev.itsxactly.iris.debug
adb logcat -c                                # clear logcat
adb shell am start -n dev.itsxactly.iris.debug/dev.itsxactly.iris.MainActivity
sleep 5

# Find the crash — the trace ends with "FATAL EXCEPTION: main"
adb logcat -d 2>&1 | grep -E "FATAL|AndroidRuntime" | head -20
```

Output is a 3-deep exception chain. **The actionable line is the
innermost `Caused by:`**:

```
java.lang.RuntimeException: java.lang.reflect.InvocationTargetException
    at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(...)
Caused by: java.lang.reflect.InvocationTargetException
    at java.lang.reflect.Method.invoke(Native Method)
Caused by: java.security.NoSuchAlgorithmException: no such algorithm: EC
  for provider AndroidKeyStore
    at javax.crypto.KeyGenerator.getInstance(...)
    at dev.itsxactly.iris.data.IdentityStore.createIdentity(IdentityStore.kt:87)
    at dev.itsxactly.iris.ui.screens.PairingViewModel.ensureIdentity(PairingScreen.kt:48)
```

Read this as: `IdentityStore.createIdentity` at line 87 calls
`KeyGenerator.getInstance("EC", "AndroidKeyStore")` and the device's
AndroidKeyStore doesn't support EC. Fix: see the Huawei AndroidKeyStore
pitfall in SKILL.md.

```bash
# Even faster: pull just the lines that name YOUR class
adb logcat -d 2>&1 | grep "dev.itsxactly.iris" | grep -E "Caused by|at dev\." | head -20
```

## 6. The Huawei AndroidKeyStore EC NoSuchAlgorithmException

**Symptom:** app crashes on launch with `NoSuchAlgorithmException: no
such algorithm: EC for provider AndroidKeyStore`.

**Root cause:** the device's TEE-backed AndroidKeyStore only supports
RSA. Some Huawei (EML-L29/P20 Pro) and older Samsung devices fall in
this category. `KeyGenerator.getInstance("EC", "AndroidKeyStore")`
throws and the app dies at the first Compose render that calls
`IdentityStore.createIdentity()`.

**Fix:** try the AndroidKeyStore first, fall back to a software EC
keypair from the default JCA provider. The Iris-ID and prefs are
identical either way; only the hardware-backing guarantee changes.

```kotlin
// IdentityStore.kt
fun createIdentity(): String {
    val keypairGenerated = try {
        generateInAndroidKeyStore()
    } catch (e: Exception) {
        Log.w("IdentityStore", "AndroidKeyStore EC failed, falling back to software KeyStore", e)
        generateInSoftwareKeyStore()
    }
    // ... rest unchanged (generate Iris-ID, save to prefs)
}

private fun generateInSoftwareKeyStore(): Boolean {
    val kpg = java.security.KeyPairGenerator.getInstance("EC")
    kpg.initialize(java.security.spec.ECGenParameterSpec("secp256r1"))
    val kp = kpg.generateKeyPair()
    Log.i("IdentityStore", "Software fallback keypair generated: pub=${kp.public.encoded.size} bytes")
    return true
}
```

After this fix, logcat shows the fallback working:

```
W IdentityStore: AndroidKeyStore EC failed (NoSuchAlgorithmException:
  no such algorithm: EC for provider AndroidKeyStore), falling back
  to software KeyStore
I IdentityStore: Software fallback keypair generated: pub=91 bytes
```

The app launches, the pairing screen renders, the Iris-ID is shown.
**No regression on devices that DO have TEE EC** — the try block
succeeds and the fallback never runs.

## 7. /dev/kvm is usually missing on phones

QEMU TCG (software emulation) is the only option on most phones. No
hardware virt, no pKVM unless you're on a Pixel-class device with
AVF enabled and the `MANAGE_VIRTUAL_MACHINE` permission granted.

```bash
adb shell "ls -la /dev/kvm" 2>&1
# → "No such file or directory" (expected on most phones)

adb shell "cat /proc/cpuinfo | grep -E 'vmx|svm'"
# → empty (no hardware virt exposed to userspace)
```

The QEMU TCG path is slow (boot is 5-10s, container start 1-3s) but
it works. The whole point of phone-as-pod is to be phone-agnostic.

## 8. Persistent install state

```bash
# What survived a reboot?
adb shell pm list packages | grep -iE "iris|podroid"
adb shell pm path com.excp.podroid.debug
# → /data/app/com.excp.podroid.debug-XXXXX==/base.apk

# What got installed in the Podroid APK's assets?
adb shell "unzip -l $(adb shell pm path com.excp.podroid.debug | sed 's/package://')" \
    | grep iris-messenger
# → assets/iris-messenger/iris-messenger-amd64.tar
# → assets/iris-messenger/iris-messenger.bin
```

The .tar and .bin are BUNDLED inside the installed APK at
`assets/iris-messenger/`. They survive app updates but get wiped if
the user uninstalls.

## 9. After the VM boots: smoke test from inside the device

Once the Podroid VM is up and the iris-pod container is running, you
can curl the local pod from inside the device:

```bash
# Run curl AS the podroid package (it can see its own loopback)
adb shell run-as com.excp.podroid.debug \
  curl -s http://127.0.0.1:9091/api/v1/health
# expect: {"status": "ok", "iris_id": "..."}

# Or via logcat for the podroid-forward registration
adb logcat -d -s podroid-forward:V 2>&1 | tail -20
```

If the curl returns `connection refused`:
- VM is still booting (wait, retry)
- iris-pod service didn't start (check `adb logcat -s OpenRC:V` or similar)
- podroid-forward registration didn't run (check your MainActivity wiring)

## 10. Driving Compose `OutlinedTextField` dialogs via adb input

Use this when you need to add a Podroid Port Forward (or any
Compose dialog) without rebuilding the APK. This is a recipe, not
a guess.

**Anti-pattern (causes silent failures):** tap the label TEXT
("Android port") position. The label and the actual `EditText`
are at different y-coordinates. Worse: tapping the same x at
the wrong y often focuses the wrong field, and a subsequent
`adb shell input text "9091"` ends up in the wrong field, OR
appends to text that's already there (producing values like
"90919091" or "9091000000009091p").

**Correct pattern:**

```bash
# 1. Open the dialog (e.g. Podroid Settings → NETWORK →
#    Port forwards → "+ Add")

# 2. Dump the UI tree
adb shell uiautomator dump
adb pull /sdcard/window_dump.xml /tmp/dump.xml

# 3. Find the actual EditText center (NOT the label)
python3 -c "
import re
xml = open('/tmp/dump.xml').read()
for m in re.finditer(
    r'class=\"android\.widget\.EditText\"[^>]*?text=\"([^\"]*)\"'
    r'[^>]*?bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml):
    x = (int(m.group(2)) + int(m.group(4))) // 2
    y = (int(m.group(3)) + int(m.group(5))) // 2
    print(f'  value={m.group(1)!r} center=({x},{y})')
"
# → for the Podroid "Add port forward" dialog on the P20 Pro
#   (720x1600): Android port = (360, 429), VM port = (360, 585)

# 4. Tap the EditText, type, verify, then re-dump to find the
#    Add button (Add button position moves when the soft keyboard
#    is up)
adb shell input tap 360 429
adb shell input text 9091
adb shell uiautomator dump && adb pull /sdcard/window_dump.xml /tmp/dump.xml
# Verify value before tapping Add:
python3 -c "
import re
xml = open('/tmp/dump.xml').read()
for m in re.finditer(r'class=\"android\.widget\.EditText\"[^>]*?text=\"([^\"]*)\"', xml):
    print(f'  EditText value: {m.group(1)!r}')
"

# 5. Tap Add (its position changed because the keyboard is up)
ADD_XY=$(python3 -c "
import re
xml = open('/tmp/dump.xml').read()
m = re.search(r'text=\"Add\"[^>]*?bounds=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\"', xml)
if m:
    print(f'{(int(m.group(1))+int(m.group(3)))//2} {(int(m.group(2))+int(m.group(4)))//2}')
")
adb shell input tap $ADD_XY
```

**If a field already has stale text** (from a prior failed tap
that closed the dialog and reopened it), clear before typing:

```bash
# Focus the field, then delete until empty
adb shell input tap 360 429
for i in 1 2 3 4 5 6 7 8 9 10; do
  adb shell input keyevent KEYCODE_DEL
done
adb shell input text 9091
```

**Numeric alternative to `input text`** (avoids IME quirks):

```bash
adb shell input keyevent KEYCODE_9 KEYCODE_0 KEYCODE_9 KEYCODE_1
```

**Two important navigation traps** (both wasted many tool calls
in the 2026-06-21 session):

1. The "Settings" button in the Terminal toolbar opens the
   *terminal* settings (display, font, extra keys), not the Podroid
   *VM* settings. The VM settings gear icon is on the home screen,
   at the top right.

2. Back-keyevent from a deeply-nested screen (like a dialog)
   might exit the whole app to the Android home screen rather
   than closing the dialog. Check the current `dumpsys window |
   grep mCurrentFocus` before assuming back did what you want.

See `references/podroid-pairing-and-runtime-2026-06-21.md` Step 7
for the verified full sequence on a real device.
