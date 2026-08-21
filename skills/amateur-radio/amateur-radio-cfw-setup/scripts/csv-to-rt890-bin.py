#!/usr/bin/env python3
"""
csv-to-rt890-bin.py — Convert a CHIRP-format CSV to a packed binary block
matching the OEFW fagci-mod ChannelInfo_t layout (22 bytes per channel,
little-endian, frequency in 10 Hz units).

Usage:
  python3 csv-to-rt890-bin.py input.csv output.bin

Output is raw bytes; concatenate to whatever offset the CFW's SPI layout
expects for user channels. For OEFW fagci-mod that is typically after the
NOAA defaults and the VFO state block, in the 0x1000-0x4000 range, but
read the source to confirm before flashing.
"""

import csv
import struct
import sys

MODULATION = {"FM": 0, "AM": 1, "LSB": 2, "USB": 3, "WFM": 0, "CW": 1}

def make_channel(name: str, freq_hz: int, mode: str, narrow: bool) -> bytes:
    freq_10hz = freq_hz // 10
    if freq_hz == 0:
        return b"\x00" * 22  # inactive slot

    modulation = MODULATION.get(mode.upper(), 0)
    narrow_bit = 1 if narrow else 0
    available = 1

    # Pack the bitfield at 0x10
    # Available:1, gModulationType:2, BCL:2, ScanAdd:1, bIsLowPower:1, bIsNarrow:1
    # LSB first per C bit-field layout on AT32 (little-endian)
    byte_0x10 = (
        (available & 0x01)
        | ((modulation & 0x03) << 1)
        | (0 << 3)        # BCL = 0
        | (1 << 5)        # ScanAdd = 1
        | (0 << 6)        # bIsLowPower = 0
        | ((narrow_bit & 0x01) << 7)
    )
    byte_0x11 = 0x11  # default sentinel

    name_bytes = name.encode("ascii", errors="replace")[:10].ljust(10, b" ")

    # 8-byte RX FrequencyInfo_t
    rx = struct.pack("<IH", freq_10hz, 0)  # Frequency 4B, Code:12 + CodeType:4 = 4B
    tx = struct.pack("<IH", freq_10hz, 0)
    # 0x0C..0x0F: Golay 24 + Unknown0 4 + bIs24Bit 1 + bMuteEnabled 1 + Encrypt 2
    field_0c = b"\x00\x00\x00\x00"
    # 0x10: the bitfield byte
    # 0x11..0x15: _0x11, Scramble, IsInscanList, _0x14, _0x15
    field_11 = struct.pack("5B", byte_0x11, 0, 0xFF, 0xFF, 0xFF)
    # 0x16..0x1F: Name[10]
    return rx + tx + field_0c + bytes([byte_0x10]) + field_11 + name_bytes


def main():
    if len(sys.argv) != 3:
        print("Usage: csv-to-rt890-bin.py input.csv output.bin", file=sys.stderr)
        sys.exit(1)
    in_csv, out_bin = sys.argv[1], sys.argv[2]

    with open(in_csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    out = bytearray()
    for row in rows:
        try:
            freq = int(row["Frequency"])
        except (KeyError, ValueError):
            freq = 0
        name = row.get("Name", "").strip() or "         "
        mode = row.get("Mode", "FM")
        # CHIRP CSV does not carry narrow/wide per default. Treat WFM as wide, all
        # others as narrow. Override per-row via "Comment" containing the string
        # "wide" or "narrow" if you need finer control.
        comment = row.get("Comment", "").lower()
        if "wide" in comment:
            narrow = False
        elif "narrow" in comment:
            narrow = True
        else:
            narrow = mode.upper() != "WFM"
        out += make_channel(name, freq, mode, narrow)

    with open(out_bin, "wb") as f:
        f.write(out)
    print(f"Wrote {len(out)} bytes ({len(out)//22} channels of 22 bytes each) to {out_bin}")


if __name__ == "__main__":
    main()
