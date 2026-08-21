# CFW Channel Data Structures — How Channels Are Stored in Memory

Different custom firmwares store channels in different binary formats. This reference documents the structures for the most common CFWs and how to convert between them. If you are working with a CFW not listed here, find the channel struct in the source (usually `radio/channels.h` or `app/memory.h`) and document the field offsets in the same format.

## OEFW fagci-mod (Radtel RT-890)

Source: `radio/channels.h` in https://github.com/itsXactlY/rt890-fagci-mod

```
ChannelInfo_t — 22 bytes packed, little-endian (C bit-field layout on AT32):

Offset  Size  Field
0x00    4B    RX.Frequency          (uint32, in 10 Hz units)
0x04    2B    RX.Code              (uint12 CTCSS/DCS code)
0x06    2B    RX.CodeType          (uint4; 0=OFF, others per driver)
0x08    4B    TX.Frequency          (uint32, in 10 Hz units)
0x0C    2B    TX.Code              (uint12)
0x0E    2B    TX.CodeType          (uint4)
0x10    1B    bitfield byte:
              bit 0     Available:1     (1 = slot in use)
              bits 1-2  gModulationType:2   (0=FM, 1=AM, 2=LSB, 3=USB)
              bits 3-4  BCL:2
              bit 5     ScanAdd:1        (1 = include in scan)
              bit 6     bIsLowPower:1
              bit 7     bIsNarrow:1      (0=wide, 1=narrow)
0x11    1B    _0x11                 (default 0x11)
0x12    1B    Scramble              (default 0)
0x13    1B    IsInscanList          (8 bits, one per scan list; 0xFF = all)
0x14    1B    _0x14                 (default 0xFF)
0x15    1B    _0x15                 (default 0xFF)
0x16    10B   Name                  (ASCII, NUL-padded)
```

Default channel array pattern: `gNoaaDefaultChannels[11]` in `radio/channels.c:94`. Extend to 48 user channels as `gUserDefaultChannels[48]` and wire it into the factory-reset / first-boot path.

## Quansheng UV-K5 (egzumer / IJV / others)

The UV-K5 family has multiple CFWs (egzumer's, IJV's, n0jyx's). They use a similar 16-byte channel struct (smaller because no AM/SSB). The struct is in `app/memory.h` or `radio/channels.h` depending on the fork. Field offsets are different; do not assume the same layout as the RT-890.

## CHIRP CSV ↔ CFW binary conversion

For any CFW, the conversion is the same shape:

1. Read CSV row: `Location,Name,Frequency,Mode,Power,...`
2. Map `Frequency` (Hz in CSV) → CFW's native unit (10 Hz units for OEFW; Hz for some others).
3. Map `Mode` string to CFW's modulation code (0/1/2/3 for OEFW; different numbers elsewhere).
4. Encode name as ASCII bytes, truncate/pad to struct field length.
5. Pack the bitfield byte (or bytes) with the right field order — C bit-fields are endian-sensitive and CFW codebases differ.
6. Pad to struct size; concatenate.

The `scripts/csv-to-rt890-bin.py` in this skill implements the OEFW mapping. For other CFWs, copy the script and adjust the field layout, frequency unit, and modulation codes. Do not try to be generic — the field-ordering gotchas bite you.

## Why per-CFW scripts are better than generic ones

A "generic" channel converter sounds nice but is a maintenance trap. Different CFWs disagree on:
- Frequency unit (10 Hz, Hz, kHz, BCD)
- Bitfield byte order
- Name length and encoding
- Whether TX.Frequency defaults to RX.Frequency or 0
- Modulation code numbering

Worth a one-time per-CFW script. Use the CSV as the canonical source of truth, generate the CFW-specific binary on demand.
