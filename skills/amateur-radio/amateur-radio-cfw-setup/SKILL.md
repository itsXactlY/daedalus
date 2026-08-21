---
name: amateur-radio-cfw-setup
description: "Set up, program, and flash custom firmware (CFW) on amateur radio handhelds — channel programming, build pipelines, CHIRP gaps, and the specific quirks of common CFW variants. Trigger when the operator mentions a Radtel RT-890 / RT-900, Quansheng UV-K5 / K6, Baofeng with community firmware, CHIRP, channel lists, side-key programming, scan lists, or anything along the lines of 'how do I get my radio configured without typing into the keypad'."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [hardware, firmware, amateur-radio, chirp, radtel, baofeng, quansheng, channel-programming]
    related_skills: [systematic-debugging, spike]
---

# Amateur Radio Custom Firmware Setup

## Overview

This skill covers the workflow for configuring and flashing custom firmware (CFW) on amateur radio handhelds when the operator cannot or will not use the on-device menu. The class includes:

- Building CFW from source with embedded channel defaults (Radtel OEFW/fagci-mod, Quansheng egzumer, etc.)
- Programming channels via CSV import (CHIRP, when supported)
- Programming channels via custom Python flasher (when CHIRP has no driver for the radio)
- Flashing firmware with the right bootloader sequence
- Recovering from a bad flash

## When to Use

Use this skill when ANY of the following applies:
- Operator has a CFW-flashed handheld (Radtel RT-890/900, Quansheng UV-K5/K6, Baofeng, TYT, etc.)
- Operator asks to program channels, side-keys, scan lists, or other persistent settings
- Operator says they cannot use the device keypad ("hab keinen einzigen der punkte um das irgendwie selbst einzutragen")
- Operator mentions CHIRP, RT-890-Flasher, or any custom flash tool
- The task is "set up this radio" without a specific scope — channel lists, mode presets, side-key actions, etc.

## Operator Communication Rules (this user)

These are non-negotiable for the operator profile this skill was built from:
- **No Wall-of-Text.** Long bullet lists of menu options or 70-item checklists trigger strong negative feedback. If a step list is longer than ~7 items, split it across turns.
- **Dictate, do not ask exploratorily.** "Go to menu X then Y then Z" is a failure mode. The operator physically cannot or will not execute keypad sequences. Either provide a script that does it, or build the config into the firmware.
- **Automation is expected, not asked about.** "Can you please flash this?" means "do it now". Do not ask for confirmation repeatedly; do one round of safety checks and execute.
- **German when operator writes German.** Code/identifiers/CLI output stay English.
- **If a tool path does not exist, build it.** A patch to CFW source to embed compiled-in channel defaults is a valid answer. "You have to do it manually" is not.

## Pre-Flight Checklist (do before flashing anything)

1. **Identify the exact firmware on the device** — not just the radio model. The display may show a generic version string that survives across CFW replacements (e.g. RT-890 displays "M70CM V2.2.3Q" whether the original Radtel FW or the OEFW fagci-mod is loaded). Cross-check by looking for CFW-specific UI elements (Spectrum/Waterfall/Scan lists/8 lists/etc.) and by reading the SPI backup for version strings.
2. **Identify the hardware revision.** Some CFW builds have a per-revision flag in the Makefile (e.g. `PCB_VER_2_1 ?= 0` for Radtel RT-890). Wrong flag = VHF RX broken, brick-symptom but recoverable.
3. **Confirm the toolchain version.** Many CFWs require a specific compiler version. RT-890 fagci-mod needs arm-none-eabi-gcc 10.3.1 — newer 14.x produces too-large flash binaries. If the Arch package is newer, fall back to 10.3.1 from AUR or ARM.com tarball.
4. **Back up the SPI flash BEFORE the first CFW change**, but be aware that some CFW SPI-read interfaces are incomplete — the dump may be mostly garbage (4MB of pseudo-random data with 4KB-block patterns of 0xFF/0x00). Treat the SPI dump as a debugging artefact, not a recovery image. **Real recovery is the pre-built firmware.bin from the CFW project's GitHub Actions tab.**
5. **Identify the connection state for SPI vs firmware flash** — they need different radio modes. SPI read typically wants the radio in NORMAL operating mode (NOT bootloader). Firmware flash wants bootloader (often PTT+Power on the Radtel, or both side-keys on the Quansheng). Read the tool's source comments — many tools have a `# importante: debe estar en modo NORMAL (no bootloader)` style note that contradicts the obvious assumption.

## Workflow Phases

### Phase 1: Identify the model + firmware + hardware revision

If unclear, ask one focused question. Do not enumerate a 70-item menu checklist. The CFW almost always has an "About" or "Version" entry — find it.

### Phase 2: Decide the channel-programming path

Pick exactly one of:

| Path | When to use | Pros | Cons |
|------|-------------|------|------|
| **CHIRP direct** | CHIRP has a native driver for the radio (Quansheng UV-K5/K6, Baofeng UV-5R, RT-880G, RT-900, etc.) | GUI, reversible, well-tested | CHIRP does NOT have drivers for many CFW-specific radios. RT-890 has no driver in kk7ds/chirp master as of 2026-06-12. |
| **CHIRP Generic CSV** | You need to author/edit the channel list, and you'll handle flashing another way | Lets you use CHIRP's spreadsheet-style editor | No radio-side operations — purely a CSV editor |
| **Custom Python flasher (CSV → SPI binary)** | CHIRP has no driver, but the radio's CFW has a known channel structure (ChannelInfo_t or similar) and an open-source flasher tool that handles SPI write | Full automation, repeatable | You write/maintain the converter; brick risk if SPI write is interrupted |
| **Rebuild CFW with embedded channel defaults** | The CFW source has a default-channels array pattern (Radtel OEFW has `gNoaaDefaultChannels[11]`; pattern extends cleanly to 48+ user channels) | Channels survive factory reset; clean; no runtime SPI editor needed | Requires build toolchain; one CFW rebuild per channel-list change; long build times |

For this operator, prefer the rebuild-CFW-with-defaults path or the custom Python flasher path. Avoid paths that ask the operator to enter data on the device keypad.

### Phase 3: Author the channel list as CSV

Use the standard CHIRP CSV header regardless of which flash path you take. Having the data in CSV keeps it portable and editable:

```
Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,DtcsCode,DtcsPolarity,Mode,Power,Comment
```

- Frequency in Hz (e.g. 156800000 for 156.800 MHz)
- Mode: one of FM, AM, WFM, USB, LSB, CW, RTTY, DV (matches the radio's mode set)
- Power: 1/5/8 etc. — whatever the radio's CHIRP driver expects, often watts
- Power=0 means slot inactive (useful for placeholder/reserve channels)
- Tone fields stay empty for plain FM/AM/SSB channels; populate only for repeaters with CTCSS/DCS

For RT-890 OEFW specifically, mode mapping is:
- CSV `FM` → CFW gModulationType=0
- CSV `AM` → CFW gModulationType=1
- CSV `LSB` → CFW gModulationType=2
- CSV `USB` → CFW gModulationType=3
- `bIsNarrow` (0=wide, 1=narrow) is a separate flag, not in the CSV by default — encode it in the Comment field or the post-processor if needed.

### Phase 4: Convert CSV to whatever the flash path needs

- For CHIRP direct: just `File → Import` the CSV in the GUI.
- For Generic CSV editing: same as above but the radio is virtual.
- For custom Python flasher: write a converter that takes the CSV and emits a binary block matching the CFW's `ChannelInfo_t` layout. See `references/cfw-channel-structures.md` for the RT-890 OEFW layout.
- For CFW rebuild: convert the CSV to a C array literal that gets included in the source. Recommend generating this with a small Python script — do not hand-author 48 channel entries, typos in C structs are a brick risk.

### Phase 5: Flash

Each path has a different flashing sequence. Read the tool's documentation or source comments before flashing. The Radtel RT-890 specifically:

- **Firmware flash** (full `firmware.bin`): radio in bootloader (PTT+Power). Use `rt890-flash /dev/ttyUSB0 firmware.bin` from rampa069/rt890-flasher. CLI has Windows-original and Python-native options. Native Python is preferred on Linux.
- **SPI write** (channels only): radio in NORMAL mode, then `rt890-restore /dev/ttyUSB0 channel-block.bin` (note: SPI write is best-effort given the incomplete CFW SPI-read interface — flashing the full firmware is safer).
- **CHIRP via cable**: requires a CHIRP-supported radio model. For RT-890 this path is not available.

If the flash hangs (no progress for >30s), power-cycle the radio and re-attempt. Do not retry endlessly — investigate the tool output first.

### Phase 6: Verify

After flashing:
1. Power-cycle the radio (full off-on, not just standby).
2. Check the channel list via the device's memory menu — but remember the operator may not be able to do this. If they cannot, write a small Python script that reads back the SPI and prints a channel summary.
3. Try receiving on a known-active frequency (Seefunk Ch16 156.800 MHz FM near a coast, or 145.500 MHz FM for 2m amateur) to confirm RX is still working.
4. If RX is dead after flashing, the build flag for the hardware revision is the most likely culprit (RT-890 V2.1 needs `PCB_VER_2_1=1`).

## Pitfalls

1. **Wrong compiler version.** RT-890 fagci-mod needs arm-none-eabi-gcc 10.3.1. Arch's `extra/arm-none-eabi-gcc` is 14.2.0 — binaries come out too large, build fails with "region 'flash' overflowed". Fix: install 10.3.1 from AUR or use a Docker image with the pinned toolchain.
2. **Wrong hardware-revision flag.** `PCB_VER_2_1=0` on V2.1 hardware = broken VHF RX. Always set per-revision flags.
3. **SPI read in bootloader mode.** Many tools look like they should work in bootloader mode (because the bootloader is "where you flash stuff") but the SPI read protocol is implemented by the running firmware, not the bootloader. If SPI reads return zeros or hang, switch the radio to NORMAL mode and retry.
4. **CHIRP has no driver for the radio.** Do not pretend it does. Confirm with `grep -i <model> chirp/drivers/*.py` before promising the operator CHIRP can flash their radio.
5. **Sudo-requiring AUR helpers in non-tty sessions.** `paru -S` and `yay -S` need an askpass for sudo. In a non-interactive shell they fail. Fall back to `pip install` in a venv (works for most Python-based radio tools including CHIRP).
6. **Trusting a partial SPI dump as a recovery image.** The CFW's SPI-read interface is often incomplete, returning mostly-pseudo-random data. Do not lean on it for recovery. The pre-built `firmware.bin` from the CFW project's GitHub Actions tab is the real recovery image.
7. **Asking the operator to enter data on the device keypad.** For the operator profile this skill was built from, this is a hard failure mode. The operator said "hab keinen einzigen der punkte um das irgendwie selbst einzutragen". Always automate.
8. **Long Wall-of-Text menu checklists.** "70 punkte bestimmt nicht" was direct pushback. Keep step lists to ~7 items or fewer per turn; split across turns if needed.

## Recovery from a Bad Flash

1. **Power cycle the radio** (battery out, count to 5, battery back in). Many bad flashes look like bricks but the radio recovers.
2. **Re-flash from the pre-built firmware.bin** on the CFW project's GitHub Actions tab. This is the canonical recovery image.
3. **If the radio is fully unresponsive**: short the SPI flash's WP (write-protect) pin if applicable, or use an SPI programmer (CH341A, Bus Pirate, etc.) to read the flash and confirm contents. With the right adapter, you can re-flash the chip out-of-band.
4. **If you have a working SPI dump** (rare — CFW SPI reads are usually incomplete): use `rt890-restore` to write it back. Verify the checksum of the dump before writing.
5. **If the dump is suspicious** (looks like 4MB of pseudo-random data with FF/00 patterns): discard it and use the firmware.bin from the GitHub Actions tab.

## References

- `references/rt890-oefw.md` — Radtel RT-890 + OEFW fagci-mod specifics: build flags, channel structure, modulation values, known-good frequencies for the operator's region.
- `references/chirp-installation.md` — Installing CHIRP on Arch Linux without sudo, pip-venv path, troubleshooting the wxPython build.
- `references/cfw-channel-structures.md` — ChannelInfo_t layouts for OEFW fagci-mod and similar CFWs; how to convert between CSV and packed-binary.
- `references/recovery-flows.md` — Detailed brick-recovery flows per radio, including SPI out-of-band recovery with CH341A.

## Templates

- `templates/chirp-csv-template.csv` — Standard CHIRP CSV header with the column ordering expected by every flash path in this skill.
- `templates/rt890-c-channel-array.c` — C array template for embedding channel defaults into a CFW build (e.g. an OEFW `gUserDefaultChannels[48]`).

## Scripts

- `scripts/csv-to-rt890-bin.py` — Convert CHIRP-format CSV to a packed binary block matching the OEFW `ChannelInfo_t` layout (22 bytes per channel, little-endian, frequency in 10Hz units).
- `scripts/rt890-spi-probe.py` — Diagnostic probe for the SPI interface; sends a few representative commands and reports what comes back. Use to determine whether the radio is in bootloader or NORMAL mode, and whether the CFW's SPI-read interface is responding.
