#!/bin/bash
# Force a FULL display-manager restart after an optimus switch so the dGPU
# is actually removed/loaded.
#
# WHY this exists: `i3-msg exit` logs you out and back to SDDM, but SDDM
# often REUSES the running X session on re-login (same VT, no new X process).
# optimus-manager removes the dGPU from the PCI bus in its Xorg PRE-START
# hook, which only runs when X actually RESTARTS. Reused X => hook never
# re-runs => switching to integrated leaves the dGPU physically on the bus
# ("both cards still running" after the switch).
#
# `systemctl restart sddm` forces SDDM to tear down and restart X, so the
# pre-start hook runs and the requested mode is applied cleanly. This is the
# exact mechanism that works at boot (fresh X start) — we just replicate it
# on every live switch.
#
# Requires a polkit rule allowing the user to restart sddm without a password
# (see SKILL.md Pitfalls: "SDDM X-reuse on i3-msg exit"). Fallback keeps the
# old i3-msg exit behavior if the restart is denied.

if command -v systemctl >/dev/null 2>&1 && systemctl restart sddm 2>/dev/null; then
    exit 0
fi
# Fallback (no polkit rule): may reuse X, dGPU may stay on bus.
SOCK=$(ls /run/user/1000/i3/ipc-socket.* 2>/dev/null | head -1)
if [ -n "$SOCK" ]; then
    i3-msg -s "$SOCK" exit
else
    i3-msg exit
fi
