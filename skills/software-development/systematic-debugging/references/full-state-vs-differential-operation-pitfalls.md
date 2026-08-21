# Full-State vs Differential Operation Pitfalls

## What this is

When debugging any system where the fix/tool performs a **full-state write** (replaces
all state, not just a delta), a common failure mode is: the write appears to succeed but
silently destroys unrelated state that the operator didn't expect to be touched. The user
sees broken behavior in areas they didn't touch, doesn't connect it to the write, and the
debugging spirals.

This shows up in any domain where the primitive is "write the whole image/backup/registry"
rather than "patch the field". Common cases: CHIRP radio flash, BIOS/UEFI image flash,
firmware OTA, mobile device wipe, registry re-import, container image rebuild, terraform
apply, git push --force.

## Real-world example: Radtel RT-890 + CHIRP

**Setup**: User wanted 48 channels programmed into the radio. CHIRP requires an in-memory
image of the full radio state to operate. The image size is fixed (~40 KB) regardless of
how many channels are actually populated.

**The trap**: Building the in-memory image from scratch with `b"\xff" * size` (FF = erased
flash) leaves all settings fields at FF. Setting the 48 channels in that image and uploading
to the radio writes the ENTIRE 40 KB back. Settings fields that previously held real
values (squelch, display brightness, audio gain, side-key actions, etc.) get overwritten
with FF.

**Why it wasn't caught**: The flash appeared to succeed. The radio booted. The new channels
were visible. But every other setting was reset to default. The user noticed: "in DEINEM
image, haufen settings von der normalen FW NICHT gesetzt sind!" — meaning the settings
that were already on the radio before the flash got wiped because we built the image from
zero instead of from a real read.

**The lesson**: Any full-state write needs the source state to be REAL, not synthetic.

## Diagnostic pattern — recognize this class of bug

Symptom: "I made a small change via tool X, and now unrelated things are broken."

Ask, in order:
1. Does the tool perform a **full state replace** or a **differential update**? (Read the
   docs/source. CHIRP `sync_out` is full clone; OTA updates may be differential but the
   transport layer isn't.)
2. If full-state: what was the **source state** for the write?
3. If the source was a synthetic placeholder (FF/00/empty map/blank config), then **every
   field in the destination that wasn't explicitly populated got zeroed**.
4. The fix is to read the live state first, modify only the fields you intend to change,
   and write back.

## Variation: read-before-write vs write-from-template

Two patterns for full-state operations:

**Read-modify-write** (safe default):
1. Read current state into a working copy.
2. Apply the change.
3. Write the working copy back.

**Template-substitute** (only safe when destination is already a known clean state, e.g.
during manufacturing flash or after a deliberate wipe):
1. Construct target state from a known-good template + changes.
2. Write the target state.

The mistake is mixing the two: treating a template as if it were a read, when the destination
had real prior state.

## Heuristics for "is this tool a full-state operation?"

- The word "image" / "backup" / "snapshot" / "dump" anywhere in the tool name → likely full-state.
- The tool exposes a single "write" verb that takes one big blob → likely full-state.
- The tool exposes per-field setters that internally batch into a single write → still
  full-state under the hood (settings not touched via the setters get reset).
- The tool exposes "apply delta" or "patch" → likely differential.
- When in doubt, **read the source code of the write function** (Phase 1 step 5 of
  systematic-debugging: trace data flow).

## Recovery when damage is done

For hardware: most clone-mode radios have a "factory SPI dump" published by the firmware
author. Restore that first to get known-good settings, then re-apply only the changes.

For software: if the original state was in source control (git/terraform/etc.), revert the
write and start over. If not, look for backups, snapshots, or recovery tools specific to
the subsystem.

## Cross-reference to systematic-debugging skill phases

- Phase 1.4 "Gather Evidence in Multi-Component Systems": the source state of a write is
  one of the components. Verify it's real before debugging downstream symptoms.
- Phase 1.5 "Trace Data Flow": for full-state writes, trace what the source blob actually
  contains field by field before the write.
- Phase 2.3 "Identify Differences": the most important difference between the broken
  and working state is "source blob was synthetic vs source blob was a real read".
- Phase 4 step 5 "Question Architecture": if a class of full-state operations is repeatedly
  causing damage, the right fix is a workflow change (always-read-first) not better
  templates.