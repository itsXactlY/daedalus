#!/usr/bin/env bash
# diagnose-kde-openwith.sh — one-shot triage for "Dolphin Öffnen mit → Andere…
# shows empty dropdown" or any "KDE app returns empty app list" report.
#
# Does NOT modify anything. Read-only. Safe to run anytime.
# Prints PASS / WARN / FAIL with a one-line summary, then detailed
# diagnostic output the agent can paste back.
#
# Usage:  bash diagnose-kde-openwith.sh
# Exit:   0 = all green, 1 = one or more WARN/FAIL

set -u

PASS=0
WARN=0
FAIL=0

note() { printf '%-7s %s\n' "$1" "$2"; }
detail() { printf '         %s\n' "$1"; }

check_pass() { note "PASS" "$1"; PASS=$((PASS+1)); }
check_warn() { note "WARN" "$1"; WARN=$((WARN+1)); }
check_fail() { note "FAIL" "$1"; FAIL=$((FAIL+1)); }

echo "=== diagnose-kde-openwith.sh ==="
echo "i3 + KDE app discovery smoke test"
echo

# --- Layer 1: environment.d ---
echo "[Layer 1: ~/.config/environment.d/]"
if [[ -f "$HOME/.config/environment.d/10-i3-kde.conf" ]]; then
    if grep -qE "XDG_CURRENT_DESKTOP.*=.*KDE" "$HOME/.config/environment.d/10-i3-kde.conf"; then
        check_pass "10-i3-kde.conf present and XDG_CURRENT_DESKTOP contains KDE"
    else
        check_fail "10-i3-kde.conf exists but XDG_CURRENT_DESKTOP not set to KDE"
        detail "got: $(grep XDG_CURRENT_DESKTOP "$HOME/.config/environment.d/10-i3-kde.conf" || echo '(unset)')"
    fi
else
    check_warn "10-i3-kde.conf missing — systemd user services won't have XDG_CURRENT_DESKTOP=KDE"
fi
if [[ -f "$HOME/.config/environment.d/15-kde-menu-prefix.conf" ]]; then
    PREFIX=$(grep XDG_MENU_PREFIX "$HOME/.config/environment.d/15-kde-menu-prefix.conf" | cut -d= -f2)
    PREFIX="${PREFIX%-}"   # strip trailing dash
    if [[ -n "$PREFIX" && -f "/etc/xdg/menus/${PREFIX}-applications.menu" ]]; then
        check_pass "15-kde-menu-prefix.conf: XDG_MENU_PREFIX=${PREFIX}- and /etc/xdg/menus/${PREFIX}-applications.menu exists"
    elif [[ -n "$PREFIX" ]]; then
        check_fail "15-kde-menu-prefix.conf: XDG_MENU_PREFIX=${PREFIX}- but /etc/xdg/menus/${PREFIX}-applications.menu MISSING"
        detail "available menus: $(ls /etc/xdg/menus/ 2>/dev/null | tr '\n' ' ')"
    fi
else
    check_warn "15-kde-menu-prefix.conf missing — kbuildsycoca6 will use the default prefix, likely 'applications.menu' which may not exist"
    detail "available menus: $(ls /etc/xdg/menus/ 2>/dev/null | tr '\n' ' ')"
fi
echo

# --- Layer 2: .xprofile ---
echo "[Layer 2: ~/.xprofile]"
if [[ -f "$HOME/.xprofile" ]]; then
    if grep -qE "XDG_CURRENT_DESKTOP.*=.*KDE" "$HOME/.xprofile"; then
        check_pass ".xprofile sets XDG_CURRENT_DESKTOP to KDE"
    else
        check_fail ".xprofile does NOT set XDG_CURRENT_DESKTOP to KDE (login shell + all children see i3)"
        detail "got: $(grep XDG_CURRENT_DESKTOP "$HOME/.xprofile" || echo '(unset)')"
    fi
    if grep -qE "XDG_MENU_PREFIX" "$HOME/.xprofile"; then
        check_pass ".xprofile sets XDG_MENU_PREFIX"
    else
        check_warn ".xprofile does NOT set XDG_MENU_PREFIX — kbuildsycoca6 from any spawned shell will use the default (likely broken)"
    fi
else
    check_warn ".xprofile missing — login session has no KDE-aware env"
fi
echo

# --- Layer 3: running shell ---
echo "[Layer 3: current shell]"
if [[ "${XDG_CURRENT_DESKTOP:-}" == *KDE* ]]; then
    check_pass "shell XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
else
    check_fail "shell XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP (does NOT contain KDE)"
fi
if [[ -n "${XDG_MENU_PREFIX:-}" ]]; then
    check_pass "shell XDG_MENU_PREFIX=$XDG_MENU_PREFIX"
else
    check_warn "shell XDG_MENU_PREFIX unset — kbuildsycoca6 from this shell will not find /etc/xdg/menus/applications.menu"
fi
echo

# --- ksycoca6 cache health ---
echo "[Cache health]"
CACHE=$(ls "$HOME"/.cache/ksycoca6_* 2>/dev/null | head -1)
if [[ -z "$CACHE" ]]; then
    check_fail "no ksycoca6 cache found at ~/.cache/ksycoca6_*"
else
    SIZE=$(stat -c%s "$CACHE")
    MTIME=$(stat -c%y "$CACHE")
    if [[ $SIZE -lt 400000 ]]; then
        check_fail "ksycoca6 cache is $SIZE bytes — TOO SMALL. Cache was likely built under wrong env. Healthy range 500KB–2MB"
        detail "cache: $CACHE"
        detail "mtime: $MTIME"
        detail "fix: rebuild with correct env: kbuildsycoca6 --noincremental (run with XDG_MENU_PREFIX and XDG_CURRENT_DESKTOP set)"
    elif [[ $SIZE -lt 600000 ]]; then
        check_warn "ksycoca6 cache is $SIZE bytes — small but possibly OK. Healthy range 500KB–2MB"
        detail "cache: $CACHE  mtime: $MTIME"
    else
        check_pass "ksycoca6 cache is $SIZE bytes (healthy range)"
        detail "cache: $CACHE  mtime: $MTIME"
    fi
fi
echo

# --- Running dolphin env ---
echo "[Running Dolphin env]"
DPID=$(pgrep -n dolphin 2>/dev/null | head -1)
if [[ -z "$DPID" ]]; then
    echo "         (no dolphin process running — skip)"
else
    DENV=$(cat /proc/"$DPID"/environ 2>/dev/null | tr '\0' '\n')
    if echo "$DENV" | grep -qE "XDG_CURRENT_DESKTOP=.*KDE"; then
        check_pass "dolphin PID $DPID has XDG_CURRENT_DESKTOP containing KDE"
    else
        check_fail "dolphin PID $DPID has XDG_CURRENT_DESKTOP=$(echo "$DENV" | grep ^XDG_CURRENT_DESKTOP= | cut -d= -f2)"
        detail "fix: close dolphin and relaunch with: XDG_CURRENT_DESKTOP=KDE:i3 XDG_MENU_PREFIX=gnome- dolphin &"
    fi
    if echo "$DENV" | grep -qE "XDG_MENU_PREFIX="; then
        check_pass "dolphin PID $DPID has XDG_MENU_PREFIX set"
    else
        check_warn "dolphin PID $DPID has no XDG_MENU_PREFIX — will use default"
    fi
fi
echo

# --- Summary ---
echo "=== Summary ==="
printf "  PASS: %d   WARN: %d   FAIL: %d\n" "$PASS" "$WARN" "$FAIL"
echo
if [[ $FAIL -gt 0 ]]; then
    echo "Action required: one or more FAIL items above."
    echo "Most common fix: see SKILL.md 'KDE Apps Running Under i3' section."
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo "No failures, but warnings. The Open-With dialog may work but env is fragile."
    exit 0
else
    echo "All checks passed. If the Open-With dialog is still empty, the problem is NOT env-related."
    echo "Next: try 'kcm_filetypes' (System Settings → File Associations) to verify .desktop files are registered."
    exit 0
fi
