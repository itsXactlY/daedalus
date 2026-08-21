#!/bin/bash
# Verify the NVIDIA dGPU is completely off the system (integrated mode).
# Exit 0 = off the system, 1 = still present.
DEV=/sys/bus/pci/devices/0000:01:00.0
ok=0
if [ ! -d "$DEV" ]; then
    echo "OK: 01:00.0 removed from PCI bus (dGPU off the system)"
else
    echo "WARN: 01:00.0 still present:"
    lspci -nn 2>/dev/null | grep -iE "01:00|nvidia|quadro"
    ok=1
fi
if lsmod 2>/dev/null | grep -q '^nvidia '; then
    echo "WARN: nvidia module still loaded"
    ok=1
else
    echo "OK: nvidia module not loaded"
fi
MODE=$(optimus-manager --print-mode 2>/dev/null | grep -oE 'integrated|hybrid|nvidia' | tail -1)
echo "optimus mode: ${MODE:-unknown}"
exit $ok
