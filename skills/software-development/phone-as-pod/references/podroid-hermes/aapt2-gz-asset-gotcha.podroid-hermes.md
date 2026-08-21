# AAPT2 auto-decompresses `*.gz` assets (silently corrupts them)

## Symptom
You bundle a gzip file in `app/src/main/assets/...` (e.g. an initramfs
`initramfs.cpio.gz`, 84 MB, valid gzip). After `assembleDebug` the APK contains
an entry named `assets/.../initramfs.cpio` that is **260 MB and UNCOMPRESSED** —
the `.gz` extension is gone and the content is the raw, decompressed stream.

Consequences:
- An app Extractor that opens `".../initramfs.cpio.gz"` gets `FileNotFound`
  (the asset is now named `.cpio`).
- Even if you open the renamed file, the kernel/consumer expecting gzip bytes
  gets the wrong format.
- `noCompress += listOf("...initramfs.cpio.gz")` does NOT prevent this. AAPT2's
  `.gz` auto-decompress runs independently of `aaptOptions.noCompress`.

## Root cause
AAPT2/AGP treats any asset whose name ends in `.gz` as a "compressed asset":
during packaging it decompresses the file and stores the RAW content under the
de-extensionsed name. This is legacy behavior for the obsolete "compressed
asset" feature and is invisible at build time (no warning).

## Fix (used in podroid-hermes)
Drop the `.gz` extension on the bundled asset, KEEP the gzip bytes on disk:
- Rename source `initramfs.cpio.gz` -> `initramfs.cpio` (content unchanged, still
  gzip — verify `file` shows "gzip compressed data", magic `1f 8b`).
- `noCompress += listOf(".../initramfs.cpio", ".../Image", ".../qemu")` so AAPT2
  stores it byte-for-byte (84 MB, gzip).
- Extractor + Supervisor + Service all reference `initramfs.cpio`.
- `qemu -initrd initramfs.cpio` passes the gzip bytes through; the guest kernel
  sees gzip and decompresses fine (filename is irrelevant to the loader).

If the source artifact is produced elsewhere named `.cpio.gz`, the build step
should copy it to `.cpio` (see `build-all.sh` `populate_assets`):
`cp "$SRC/initramfs.cpio.gz" "$ASSETS_DIR/initramfs.cpio"`.

## Verification (proves the fix)
After build, extract the asset from the APK and compare:
```
unzip -o app-debug.apk "assets/.../initramfs.cpio" -d /tmp/check
sha256sum /tmp/check/assets/.../initramfs.cpio   # == source sha256
gzip -t  /tmp/check/assets/.../initramfs.cpio && echo "gzip OK"
```
Both must hold or the VM will not boot.

## General rule (reusable beyond this project)
**Never bundle a gzip/binary asset in an Android app with a `.gz` extension.**
Any `*.gz` asset will be silently mangled at package time. Use `.cpio`, `.bin`,
`.dat`, or append a non-`.gz` suffix and keep the compressed bytes.
