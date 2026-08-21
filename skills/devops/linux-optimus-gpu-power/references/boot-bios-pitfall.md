# Boot Failure After GPU Driver Changes — BIOS Graphics Device

## Symptom
Machine won't boot (black screen after Lenovo logo, no GRUB, or kernel panic)
after nvidia driver / optimus-manager changes.

## Root cause
The BIOS "Graphics Device" setting (F1 -> Config -> Display -> Graphics Device)
was left on the wrong mode for the current driver stack:
- **Discrete Graphics**: panel hard-wired to the dGPU. If the nvidia driver is
  removed / pci_remove'd / blacklisted, the display has no driver -> no boot.
- **Hybrid Graphics**: Intel drives the panel, nvidia is offload/secondary.
  Required for the "dGPU off the system" (pci_remove) state and for Intel
  display + nvidia offload (prime-run).

A wrong setting (e.g. Discrete with a config that removes the dGPU, or an
optimus-manager config that conflicts with the BIOS mode) prevents boot.

## Fix / check
1. Reboot, enter BIOS (F1), set Config -> Display -> Graphics Device = **Hybrid**.
2. If you only need the iGPU and want the dGPU fully dead, Hybrid + integrated
   mode (pci_remove) achieves it without risking the display.
3. If unsure which mode broke it: try Hybrid first; it is the safe default for
   Optimus + i3.

## Note
Backlight device depends on this setting: Discrete -> `/sys/class/backlight/nvidia_0`,
Hybrid -> `intel_backlight`. Set the i3status-rust backlight block `device`
accordingly or it shows "no backlight devices".
