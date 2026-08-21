---
name: linux-optimus-gpu-power
description: Get an NVIDIA Optimus laptop dGPU completely powered off (removed from the PCI bus, ~0W) on Arch/Garuda/i3, fix Maxwell "fallen off the bus" boot failures from wrong NVreg_DynamicPowerManagement, and wire an i3 status-bar click to switch iGPU<->dGPU with a reliable logout in BOTH directions. Use when a user reports an Optimus laptop GPU that won't power down (battery drain/fan/heat), fails to boot after nvidia driver or optimus-manager changes, shows "fallen off the bus", or wants a one-click iGPU/dGPU switch from the bar.
---

# Linux Optimus dGPU Power-Off & Boot Recovery

## Trigger conditions
- User wants the NVIDIA dGPU "completely off / stromlos / dead / 0W" on an Optimus laptop.
- "fallen off the bus" / boot failure after nvidia driver or optimus-manager changes.
- Wants an i3 bar click to switch iGPU<->dGPU and log out reliably in BOTH directions.
- Machine won't boot after GPU driver work — suspect the BIOS Graphics Device setting.

## Mental model
Optimus laptops have an iGPU (Intel) and a dGPU (NVIDIA). "Power off the dGPU" means two different things:
1. Runtime suspend (GPU present on bus, ~1-2W) — usually NOT what the user wants.
2. **Remove the device from the PCI bus** (`pci_remove`) — dGPU gone, nvidia module unloaded, ~0W. This is the "komplett of the system" / "tot" state. Requires optimus-manager with `pci_remove=yes` + `switching=acpi_call` (needs the `acpi_call` module). Maxwell GPUs cannot do RTD3, so pci_remove is the ONLY way to get truly <2W.

## Prerequisites (verify first, before touching configs)
- `optimus-manager` installed; `acpi_call` module present AND loaded: `lsmod | grep acpi_call` and `pacman -Q acpi_call`. Without acpi_call, `switching=acpi_call` + `pci_remove` will fail.
- BIOS Graphics Device = **Hybrid** (not Discrete). Hybrid lets Intel drive the panel with nvidia as offload/secondary. Discrete-only blocks the off-state and can prevent boot after driver changes.

## Steps — canonical "off the system" config
1. **Neutralize the Maxwell DPM killer** (see Pitfalls). Write `/etc/modprobe.d/garuda-nvidia-prime-powersaving.conf`:
   `options nvidia NVreg_DynamicPowerManagement=0x00 NVreg_EnablePCIeGen3=1 NVreg_UsePageAttributeTable=1`
   This shadows Garuda's stock `/usr/lib/modprobe.d/garuda-nvidia-prime-powersaving.conf` which sets `0x02`.
2. Write `/etc/optimus-manager/optimus-manager.conf` — use `templates/optimus-manager.conf` (startup_mode=integrated, pci_remove=yes, switching=acpi_call, auto_logout=no). NOTE: set `startup_auto_extpower_mode=hybrid` instead of `integrated` if the user wants CUDA available on AC (they must then switch manually for CUDA).
3. `systemctl enable optimus-manager.service`.
4. Reboot. After boot, verify with `scripts/verify-dgpu-off.sh`.

## i3 bar click switch (reliable logout in BOTH directions)
- Three scripts in `~/.config/i3/scripts/`: `optimus-status.sh` (mode indicator), `gpu-status.sh` (detects off-bus), `optimus-switcher.sh` (click handler). Use the `templates/` versions.
- Wire in i3status-rust: a `[[block]] block="custom" command="bash ~/.config/i3/scripts/optimus-status.sh"` with `[[block.click]] button="left" cmd="bash ~/.config/i3/scripts/optimus-switcher.sh"`.
- **`auto_logout` MUST be `no`** in optimus-manager.conf. The switcher forces logout itself.
- **The logout MUST be `systemctl restart sddm`, NOT `i3-msg exit`.** `i3-msg exit` logs out but SDDM often REUSES the running X session on re-login, so optimus-manager's Xorg pre-start hook (which removes `01:00.0` from the PCI bus) never re-runs — switching to integrated then leaves BOTH cards running. `systemctl restart sddm` forces a real X restart, replicating the clean boot path. Use `scripts/force-logout-restart-sddm.sh` from the switcher, which falls back to `i3-msg exit` only if the restart is denied. Requires the polkit rule below (passwordless sddm restart).

## Pitfalls
- **Maxwell/Kepler DPM invariant**: `NVreg_DynamicPowerManagement=0x02` (fine-grained runtime-D3, Turing+ only) makes old Maxwell/Kepler GPUs **fall off the bus** ("NVRM: GPU 0000:01:00.0 has fallen off the bus and is not responding; probe failed error -1"). ALWAYS 0x00 for Maxwell/Kepler. Garuda stock sets 0x02 — shadow it in /etc. Detail + kernel proof in `references/maxwell-dpm-invariant.md`.
- **optimus-manager auto_logout asymmetry**: never rely on it for uniform logout. Set `auto_logout=no` and force logout in the switcher.
- **SDDM X-reuse breaks dGPU removal on live switch**: `i3-msg exit` logs out but SDDM often REUSES the existing X session on re-login, so optimus-manager's Xorg pre-start hook (which removes `01:00.0` from the PCI bus via `pci_remove`) never re-runs. Symptom: after switching to integrated, BOTH cards still run. Fix: the switcher must force a real X restart via `systemctl restart sddm` (see the bar-click section). This requires a polkit rule so the user can restart sddm WITHOUT a password:
  `/etc/polkit-1/rules.d/50-optimus-switch.rules`:
  ```js
  polkit.addRule(function(action, subject) {
      if (subject.user == "alca" && (action.id == "org.freedesktop.systemd1.manage-units" ||
          action.id == "org.freedesktop.systemd1.manage-unit" ||
          action.id == "org.freedesktop.login1.session.terminate" ||
          action.id == "org.freedesktop.login1.session.terminate-others")) {
          return polkit.Result.YES;
      }
  });
  ```
  Boot works because X starts fresh and the hook runs; the live switch must replicate that via `scripts/force-logout-restart-sddm.sh`. If you skip the polkit rule, the switcher falls back to `i3-msg exit` (old broken behavior).
- **No root on the target laptop**: if the agent lacks sudo on the laptop, write the helper scripts to `~/` itself and hand the user a sudo one-liner for the /etc + systemctl edits. Do NOT try `sudo` over non-TTY SSH — it fails with "a terminal is required to read the password".
- **Wrong BIOS Graphics Device**: after driver changes the machine may not boot — check BIOS F1 -> Config -> Display -> Graphics Device. Hybrid is required for Intel display + nvidia offload. Detail in `references/boot-bios-pitfall.md`.
- **Backlight device flips with BIOS**: Discrete -> `nvidia_0`; Hybrid -> `intel_backlight`. Set the i3status-rust backlight block `device` to match or it shows "no backlight devices".
- **Bar does not auto-respawn status_command**: after editing a script, reload with `i3-msg -s $(ls /run/user/1000/i3/ipc-socket.*|head -1) restart` (layout is preserved). Killing i3status-rs alone leaves the bar empty.

## Verification
- `bash scripts/verify-dgpu-off.sh`: in integrated mode `lspci | grep 01:00` is EMPTY, `lsmod | grep '^nvidia'` empty, bar shows `dGPU off (removed)`.
- Switching to nvidia: after logout+login, `lspci` shows 01:00.0, nvidia module loaded, bar shows live stats.

## Support files
- `templates/optimus-manager.conf` — known-good off-state config.
- `templates/optimus-switcher.sh`, `templates/gpu-status.sh`, `templates/optimus-status.sh` — i3 bar scripts.
- `scripts/verify-dgpu-off.sh` — post-boot check.
- `scripts/force-logout-restart-sddm.sh` — forced X restart for the bar-switch (fixes SDDM X-reuse leaving both cards on).
- `references/maxwell-dpm-invariant.md`, `references/boot-bios-pitfall.md` — root-cause detail.
