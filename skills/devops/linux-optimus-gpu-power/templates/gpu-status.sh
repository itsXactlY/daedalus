#!/bin/bash
# GPU status for i3status-rust — robust, independent of optimus-manager state file.
# Shows when the NVIDIA dGPU is completely off the system (removed from PCI bus).
DEV=/sys/bus/pci/devices/0000:01:00.0
if [ ! -d "$DEV" ]; then
    echo " dGPU off (removed)"
    exit 0
fi
if ! lsmod 2>/dev/null | grep -q '^nvidia '; then
    echo " dGPU off"
    exit 0
fi
RESULT=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>/dev/null)
if [ -n "$RESULT" ]; then
    echo "$RESULT" | awk -F', ' '{
        gsub(/ %/,"",$1); gsub(/ MiB/,"",$2); gsub(/ MiB/,"",$3); gsub(/ C/,"",$4)
        printf " GPU %s%% | %s/%sMiB | %sC", $1,$2,$3,$4
    }'
else
    echo " dGPU idle"
fi
