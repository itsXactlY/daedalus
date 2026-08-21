# Radtel RT-890 + OEFW fagci-mod — Specific Reference

This is the reference for the most common CFW setup the operator profile runs: a Radtel RT-890 (M70CM V2.1 hardware revision) running the OEFW fagci-mod custom firmware.

## Hardware Identification

- **Model name as printed on case**: Radtel RT-890
- **Hardware codename shown in display**: M70CM (the "newer" revision with the AT32F421 chip)
- **PCB revision**: V2.1 (shown in display as `HWR PCB V2.1`)
- **Display version string**: `M70CM V2.2.3Q` — this string is preserved by the fagci-mod CFW from the original Radtel stock firmware, so seeing it does NOT mean the stock FW is running. Cross-check by looking for CFW-specific UI (Spectrum/Waterfall, 8 scan lists, side-key action menu, dBM display).

## Repository and Source

- Upstream OEFW: https://github.com/DualTachyon/radtel-rt-890-oefw (reverse-engineered 1.34 stock FW, no customisations)
- Fagci-mod fork: https://github.com/itsXactlY/rt890-fagci-mod (active development, all the customisations)
- Pre-built firmware.bin: `https://github.com/OEFW-community/RT-890-custom-firmware/actions` (GitHub Actions artifacts; the canonical recovery image)
- Telegram group: https://t.me/RT890_OEFW

## Build Pipeline

### Compiler

- Required: `arm-none-eabi-gcc` 10.3.1 (the GitHub Actions workflow uses `carlosperate/arm-none-eabi-gcc-action@v1` with `release: '10.3-2021.10'`)
- Newer compilers (Arch `extra/arm-none-eabi-gcc` 14.2.0, for example) produce too-large flash binaries. The build fails with `region 'flash' overflowed`.
- Fallback: install 10.3.1 from AUR or the ARM.com tarball, or use the GitHub Actions artifact directly.

### Makefile flags that must be set correctly

- `PCB_VER_2_1 ?= 0` — **MUST be set to 1** for V2.1 hardware. Leaving it at 0 breaks VHF RX. Confirmed by commit `b0ee604 Fix VHF RX on PCB V2.1`.
- `ENABLE_AM_FIX ?= 1` — default 1, ported from Quansheng UV-K5 work by @OneOfEleven. Keep on.
- `ENABLE_FM_RADIO ?= 1` — default 1, needed for the WFM broadcast receiver.
- `ENABLE_SPECTRUM ?= 1` — default 1, enables the Spectrum/Waterfall view.
- `ENABLE_SPECTRUM_PRESETS ?= 1` — saves 1.4 kB, presets for spectrum band selection.
- `ENABLE_NOAA ?= 1` — enables the 11 NOAA weather channel defaults.
- `ENABLE_LTO ?= 0` — Link-Time Optimisation. Saves flash space. Safe at 0.
- `ENABLE_OPTIMIZED ?= 1` — aggressive size optimisation.

### Build command

```
cd ~/rt890/oefw-fagci
git submodule update --init --recursive --depth=1
make PCB_VER_2_1=1 ENABLE_OPTIMIZED=1
```

Output: `firmware.bin` and `firmware.elf` in the source root.

### Build-check post-step

After the build, check the size with `arm-none-eabi-size firmware` and confirm the `flash` region is below the 256 kB or 512 kB limit of the AT32F421. If it overflows, the build will have failed already, but worth confirming.

## Channel Data Structure

`ChannelInfo_t` from `radio/channels.h` — 22 bytes, `__attribute__((packed))`:

```c
typedef struct __attribute__((packed)) {
    FrequencyInfo_t RX;    // 8 bytes
    FrequencyInfo_t TX;    // 8 bytes
    // 0x0C
    uint32_t Golay:24;
    uint32_t Unknown0:4;
    uint32_t bIs24Bit:1;
    uint32_t bMuteEnabled:1;
    uint32_t Encrypt:2;
    // 0x10
    uint8_t Available:1;        // 1 = channel exists in memory
    uint8_t gModulationType:2;  // 0=FM, 1=AM, 2=LSB, 3=USB
    uint8_t BCL:2;
    uint8_t ScanAdd:1;
    uint8_t bIsLowPower:1;
    uint8_t bIsNarrow:1;        // 0=wide, 1=narrow
    // 0x11
    uint8_t _0x11;
    uint8_t Scramble;
    uint8_t IsInscanList;       // 8 bits, one per scan list
    uint8_t _0x14;
    uint8_t _0x15;
    char Name[10];
} ChannelInfo_t;
```

`FrequencyInfo_t` is also 8 bytes packed:
```c
typedef struct __attribute__((packed)) {
    uint32_t Frequency;       // in 10Hz units. 145.500 MHz = 1455000
    uint16_t Code:12;         // CTCSS/DCS code
    uint16_t CodeType:4;      // 0=OFF, etc.
} FrequencyInfo_t;
```

### Modulation codes (confirmed from `ui/menu.c:431-440`)

| Code | Mode |
|------|------|
| 0 | FM |
| 1 | AM |
| 2 | LSB |
| 3 | USB |

### Bandwidth (`bIsNarrow`)

- 0 = wide (25 kHz typical for 2m/70cm amateur, 100 kHz for WFM broadcast)
- 1 = narrow (12.5 kHz typical for Seefunk and 2m/70cm when channel is congested)

### Default-channel pattern

The CFW has `gNoaaDefaultChannels[11]` (in `radio/channels.c:94`) as a compiled-in default array. The same pattern can be extended to a 48-entry `gUserDefaultChannels[48]` that the boot/factory-reset code copies into the SPI flash. The exact code path that does the copy for the NOAA array is at `radio/channels.c:716` (`gVfoState[2] = gNoaaDefaultChannels[Channel];`) — that is for live NOAA cycling, not factory-reset defaults. The factory-reset / first-boot copy path is in `CHANNELS_CheckFreeChannels` or similar; investigate before patching.

## SPI Flash Tool

Tool: `rampa069/rt890-flasher` on GitHub. Install in a Python venv:

```
python -m venv ~/rt890/rt890-flasher/.venv
~/rt890/rt890-flasher/.venv/bin/pip install -e ~/rt890/rt890-flasher
```

CLI commands:
- `rt890-backup /dev/ttyUSB0 out.bin` — SPI dump
- `rt890-restore /dev/ttyUSB0 in.bin` — SPI write
- `rt890-flash /dev/ttyUSB0 firmware.bin` — full firmware flash

### Mode for SPI read (the non-obvious bit)

The tool requires the **radio in NORMAL operating mode** (powered on, displaying a frequency). It does NOT work in bootloader mode. The source comment at `rt890_flasher/flasher.py:446` literally says "Check radio communication - importante: debe estar en modo NORMAL (no bootloader)".

For firmware flash the inverse is true: PTT+Power to enter bootloader, then `rt890-flash`.

### Known issue: CFW SPI-read is incomplete

The CFW's SPI-read handshake responds with valid bytes for the first block but returns mostly pseudo-random data for the rest. 4 MB dumps are typically 25 % 0x00, 35 % 0xFF, 40 % pseudo-random, with a 4 KB block pattern. Do not treat the dump as a reliable recovery image. The pre-built `firmware.bin` from the GitHub Actions tab is the recovery path.

## Operator-relevant Frequencies (Rügen / Ostsee region)

6 banks of 8 channels = 48 channels, all in `~/rt890/channels-ruegen.txt` and `~/rt890/channels-chirp.csv`:

- Bank 1 Seefunk FM 25 kHz: Ch16, Ch13, Ch10-12, Ch67, Ch14, DWD Seewetter 147.300
- Bank 2 Flugfunk AM 25 kHz: Tower Rügen 118.785, Berlin Info/App, Hamburg App, AFIS, Mayday 121.500, München App
- Bank 3 2m Amateur FM/USB 12.5 kHz: 145.500 FM Anruf, 144.300 USB SSB, DM0RUG 145.625, Relais 145.650/675/700/725, Notruf DE 145.750
- Bank 4 70cm Amateur FM/USB 12.5 kHz: 432.500 USB, 438.500/439.500/430.500, 433.000/050/100/150
- Bank 5 Rundfunk WFM 100 kHz: NDR Kultur 88.2, DLR 90.7, NDR Info 91.5, NDR 2 93.3, NDR 1 MV 98.5, R3 100.8, Ostseewelle 102.8, Reserve 104.0
- Bank 6 Notfall/Allgemein: CB K9 27.065 AM, CB K19 27.205 FM, PMR 1-3, Freenet 1-3

## Known Issues and Quirks

- **TX stings tube amp**: stock antenna radiates harmonics that disturb a sensitive HF tube amp in the same shack. Common-mode choke on supply or shielded feedline is the fix. See skill-level notes.
- **Display says M70CM V2.2.3Q even with CFW**: this is a version-string carryover from the original Radtel FW. Do not conclude the stock FW is loaded just from this.
- **Channel 16 in original FW was hard-coded to 156.000 MHz or similar garbage** in older fagci-mod versions; the current builds are correct.
- **Scan lists default to 1**: every new channel is automatically added to scan list 1. Adjust `IsInscanList` per channel if you want a curated scan setup.
