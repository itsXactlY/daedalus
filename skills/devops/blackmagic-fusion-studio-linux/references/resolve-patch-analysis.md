# Blackmagic Fusion Studio Linux - Additional License Offsets (2026 Session)

## Fusion 21 GA Linux License Check Patterns

Found via objdump + grep for `test al,al; je +0x11` near "Checking for licenses" string.

### Primary DoLicensing Patches (resolve.py targets)

| Offset | Status | Context |
|--------|--------|---------|
| 0x1f3b24b | 74 11 -> EB 11 | resolve.py patch[0] target |
| 0x1f3b282 | 74 11 -> EB 11 | resolve.py patch[1] target |

### Additional License Check Patches

These were found near the "Checking for licenses" string and license-related error handling:

| Offset | Context |
|--------|---------|
| 0x73a459 | `84 c0 74 11` - test al,al; je (license error branch) |
| 0x73a539 | `84 c0 74 11` - test al,al; je (license error branch) |
| 0x73d2a5 | `84 c0 74 11` - test al,al; je (license error branch) |
| 0x78d8d8 | `84 c0 74 11` - test al,al; je (license error branch) |

### Qt Fatal Offset (DO NOT PATCH)

| Offset | Function | Status |
|--------|----------|--------|
| 0x784960 | `basic_ostringstream::~basic_ostringstream` | Qt destructor - NOP causes SIGABRT |

**Verification**:
```bash
# Before patching - Qt function intact:
xxd -s 0x784960 -l 12 /opt/BlackmagicDesign/Fusion21/libfusionsystem.so
# Should show: 55415741564154534883ec20  (push rbp; push r15; ...)

# After patching all offsets:
xxd -s 0x1f3b24b -l 2 /opt/BlackmagicDesign/Fusion21/libfusionsystem.so
# Should show: eb11
```

### Debugging Notes

- fuscript (script interpreter) works without GUI because it skips Qt initialization
- Fusion server starts but socket binding fails if license bypass incomplete
- QWidget::setLayout errors cascade from incomplete license bypass
- Frida authorization fails in containerized/non-TTY environments