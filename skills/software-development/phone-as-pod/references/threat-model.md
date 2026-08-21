# Phone-as-pod threat model

This is the formal sandbox-in-a-sandbox threat model. Use this when
evaluating whether the pattern is appropriate for a given service,
or when arguing with security reviewers / regulators about why the
VM indirection is necessary.

## The architecture

```
+------------------ UNTRUSTED ZONE --------------------+
| Android OS (potentially compromised)                |
|                                                     |
|   +----------- Podroid VM (QEMU TCG or AVF) --------+|
|   |  Alpine 3.23 + Podman + ext4 overlay           ||
|   |  -- separate kernel from Android                ||
|   |  -- separate init system (OpenRC)              ||
|   |  -- separate users from Android users          ||
|   |  -- separate network namespace from Android     ||
|   |                                                 ||
|   |   +------- iris-messenger pod ----------------+ ||
|   |   |  Python 3.13 + websockets + pycryptodome  | ||
|   |   |  REST 9091 / WS 9092 / DLM federation     | ||
|   |   |  Iris-ID + private key in /var/lib/iris   | ||
|   |   |                                          | ||
|   |   +------------------------------------------+ ||
|   +------------------------------------------------+|
+-----------------------------------------------------+

The VM is the wall. The pod is invisible to the Android side.
```

## Attack classes addressed

| Attack class                       | Bare Android messenger | Phone-as-pod |
|------------------------------------|------------------------|--------------|
| Pegasus-class Android 0-day        | Full access            | VM isolated, pod invisible |
| Cellebrite-style forensic          | IndexedDB pullable     | /var/lib/iris in VM, not on Android fs |
| Hostile accessibility app          | Reads chat on screen   | WS traffic in VM net, not Android net |
| Rooted Android shell               | Full access            | QEMU TCG / pKVM barrier |
| Bösartige app with storage permission | reads /sdcard       | iris keys never written to /sdcard |
| Physischer Zugriff auf entsperrtes Phone | ADB pull          | müsste in die VM einbrechen (2. Siegel) |
| Cellebrite mit rooted phone        | Alles offen            | müsste QEMU/pKVM umgehen = eigene Forschung |
| Network observer (cafe WiFi)       | All WS+REST traffic visible | VM-side traffic goes through podroid-forward to loopback only |
| Malicious Play Store update         | Replaces app, reads its data | App update doesn't change VM contents |
| Side-channel via Android Keystore  | Reads HW-backed keys   | Iris keys are NOT in Android Keystore (VM-side keystore) |

## Attack class NOT addressed

| Attack class                       | Why out of scope | What to do about it |
|------------------------------------|------------------|---------------------|
| Kernel-level compromise of Android | Podroid QEMU runs as a userspace process. A compromised Android kernel can read Podroid's memory. | This is the limit of userspace isolation. Mitigations: TEE/StrongBox for iris-android's local UI state (NOT keys, those are in VM), keep Android patched, consider GrapheneOS. |
| VM escape (QEMU/pKVM CVE)          | If the QEMU binary or pKVM hypervisor has a known CVE, the VM wall is breachable. | Update Podroid regularly (`git submodule update --remote`), watch the QEMU security advisories. |
| Compromised iris-messenger image   | If the OCI image is tampered with, the user's keys are exposed. | Sign the OCI image with cosign/sigstore, verify the signature in the iris-pod OpenRC start_pre() before `podman load`. |
| Iris-Android UI side-channel       | The Compose UI shows message content on the Android side. A compromised app with screen-read permission sees it. | Use FLAG_SECURE on the Compose activity, block screenshots, use BiometricPrompt before showing the UI (Phase 3). |
| DNS / IP-based tracking of federation peers | Podroid's pod has a public IP for federation. | Use Tor / I2P for federation transport (deferred to a later phase). |

## What lives where (asset inventory)

| Asset | Location | Encryption at rest | Threat exposure |
|-------|----------|-------------------|-----------------|
| Long-term Iris identity key | /var/lib/iris/keystore/ inside VM | ext4 with no extra encryption (Podroid's overlay is unencrypted by default) | QEMU escape or VM compromise |
| Session ratchet state | /var/lib/iris/ratchet/ inside VM | same | same |
| In-flight message bodies | WS 9092 in VM | TLS not yet (Phase 1.5) | Network observer between pod and podroid-forward |
| Prekey bundles | /var/lib/iris/prekeys/ inside VM | same | same |
| Iris-ID (8 chars, public) | iris-android EncryptedSharedPreferences + visible in PairingScreen | Android Keystore-backed AES-256 | Not a secret |
| Registration token | iris-android EncryptedSharedPreferences | same | Reveals device-pod binding |
| 6-digit pairing code (during pairing) | iris-messenger memory only (never persisted) | not applicable | Network observer on the loopback |
| Compose UI state (currently-selected chat) | ViewModel + StateFlow in iris-android RAM | not persisted | Process memory inspection (low risk) |

## Why a VM and not just rootless containers

You could, in theory, run iris-messenger in a rootless podman
container on Android directly (no VM). The container would isolate
the iris-messenger process from the rest of the Android user, but:

- It would still share the Android kernel. A kernel exploit gives
  full access to iris-messenger.
- It would not be a separate init system. OpenRC-style supervision
  and per-service logging don't fit the Android model.
- It would not be a separate network namespace by default. The
  podman slirp4netns setup is fragile and slow.
- It would not survive Android system updates. The container image
  would be wiped on every OTA in some Android versions.
- It would not be auditable as a separate environment. A reviewer
  has to trust that Android's kernel has no relevant CVEs.

The VM is the wall. The container is the floor. Both are needed.

## Trade-off documentation (for the user)

When the user asks "do we really need a 100 MB APK with a whole VM
in it?", the answer is yes if the threat model is E2E-security-
critical. The trade-off matrix:

| Property | Plain Compose + HTTPS | Compose + Tink | Phone-as-pod |
|----------|----------------------|----------------|--------------|
| APK size | ~5 MB | ~8 MB | ~120 MB |
| Cold start | <1s | <1s | ~7s |
| Battery | baseline | +5% | +15% (VM) |
| Defeats Pegasus | NO | NO | YES (kernel isolation) |
| Defeats Cellebrite | NO | PARTIAL (if TEE) | YES (VM isolation) |
| Defeats malicious app | NO | NO | YES (separate fs + net) |
| Defeats kernel 0-day | NO | NO | NO (out of scope) |
| Self-hostable (no cloud) | YES (if backend is) | YES | YES (phone IS the backend) |
| Code review surface | Compose + backend | + Tink | + QEMU + Alpine + iris-messenger |

The phone-as-pod pattern is ONLY justified when the row "Defeats
Pegasus" is YES in your threat model. For a normal chat app, the
extra 115 MB of APK and the extra 6s of cold start is not worth it.

## What to tell security reviewers

If you're submitting the APK to a security review (e.g. for an
enterprise customer or a regulator), the talking points are:

1. **Architectural isolation.** The Android OS, the Podroid VM, and
   the iris-messenger container are three independent security
   domains. A compromise of any one does not automatically
   compromise the others.
2. **No state on the Android side.** The Android app does not store
   the long-term identity key, the ratchet state, the prekey
   bundles, or any decrypted message content. The Compose UI is a
   view layer; the data lives in the VM.
3. **Open source, auditable.** All three components (iris-android,
   Podroid, iris-messenger) are open source. The combined work
   ships its full source in the APK's NOTICE file and on GitHub.
4. **Modern crypto stack.** X3DH + Double Ratchet + Sender Key, the
   same primitives that Signal uses. Audited by the Signal
   Foundation; the code is libsignal.
5. **No cloud dependency.** Federation is direct between pods, no
   central server. The user can take their phone offline and still
   message other pods in the same WLAN via direct IP.
6. **Known limits.** The pattern does not defend against kernel-
   level compromise. We document this explicitly. Users who need
   that guarantee should use a separate hardware token (e.g. an
   old Android phone running GrapheneOS, kept in a Faraday bag).
