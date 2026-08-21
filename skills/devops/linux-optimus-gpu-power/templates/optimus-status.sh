#!/bin/bash
# optimus-manager mode indicator for the i3status-rust custom block.
#   integrated = Intel only, dGPU pci_remove'd off the bus (~0W)
#   hybrid     = Intel display + nvidia PRIME offload (prime-run)
#   nvidia     = full dGPU
MODE=$(optimus-manager --print-mode 2>/dev/null | grep -oE 'integrated|hybrid|nvidia' | tail -1)
case "$MODE" in
    integrated) echo "iGPU" ;;
    hybrid)     echo "Hybrid" ;;
    nvidia)     echo "dGPU" ;;
    *)          echo "GPU ?" ;;
esac
