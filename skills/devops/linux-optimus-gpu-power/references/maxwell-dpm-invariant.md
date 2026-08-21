# Maxwell/Kepler DPM Invariant — "fallen off the bus"

## Symptom
After nvidia driver or optimus-manager changes the dGPU disappears and the
system won't use it (no module loaded, nvidia-smi fails, or no boot). Kernel log:

    NVRM: GPU 0000:01:00.0 has fallen off the bus and is not responding
    NVRM: ... probe failed error -1
    modprobe nvidia -> "No such device"

`lspci -vvs 01:00.0` can no longer read LnkSta/LnkCap (device unresponsive
to PCIe config reads) — below the driver/config layer.

## Root cause
`NVreg_DynamicPowerManagement=0x02` enables fine-grained runtime-D3, a
Turing+ feature. Old Maxwell/Kepler GPUs (GM107 / Quadro M2000M / 10de:13b0)
DO NOT support it and fall off the bus.

Garuda's stock `/usr/lib/modprobe.d/garuda-nvidia-prime-powersaving.conf`
sets `options nvidia "NVreg_DynamicPowerManagement=0x02"`. Any config that
ends up applying 0x02 to a Maxwell/Kepler GPU triggers the fall-off.

## Fix
Shadow the stock file in /etc (which wins over /usr/lib):

    /etc/modprobe.d/garuda-nvidia-prime-powersaving.conf
    options nvidia NVreg_DynamicPowerManagement=0x00 NVreg_EnablePCIeGen3=1 NVreg_UsePageAttributeTable=1

Also avoid conflicting double-values: only ONE DPM value must be present. If
`/etc/modprobe.d/` also has a file setting a different DPM value, remove the
conflict. Two contradictory options crash optimus-manager's X pre-start hook
(modprobe conflict), which then prevents boot.

## Invariant
Maxwell/Kepler GPUs: ALWAYS NVreg_DynamicPowerManagement=0x00.
0x02 is ONLY for Turing+. Never set 0x02 on old GPUs.
