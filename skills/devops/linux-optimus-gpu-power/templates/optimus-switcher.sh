#!/bin/bash
# Left-click handler for the optimus bar block.
# rofi menu -> pick target mode -> confirm -> switch -> FORCE logout.
# Logout is forced here (optimus-manager.conf has auto_logout=no) so BOTH
# directions (->nvidia AND ->integrated) log out identically.
CUR=$(optimus-manager --print-mode 2>/dev/null | grep -oE 'integrated|hybrid|nvidia' | tail -1)
CHOICE=$(printf 'integrated\nhybrid\nnvidia\ncancel' \
    | rofi -dmenu -i -p "optimus [now: ${CUR:-?}]" -no-custom)
[ -z "$CHOICE" ] && exit 0
case "$CHOICE" in
    integrated|hybrid|nvidia) TARGET="$CHOICE" ;;
    *) exit 0 ;;
esac
if [ "$TARGET" = "$CUR" ]; then
    notify-send -t 3000 "optimus" "already in $TARGET"
    exit 0
fi
CONFIRM=$(printf 'no\nyes - switch to %s (LOGOUT!)' "$TARGET" \
    | rofi -dmenu -i -p "confirm? you WILL be logged out" -no-custom)
case "$CONFIRM" in
    yes*) ;;
    *) exit 0 ;;
esac
notify-send -t 4000 "optimus" "switching to $TARGET - logging out..."
optimus-manager --switch "$TARGET" --no-confirm
sleep 1
# Force a FULL display-manager restart (passwordless via polkit rule) so X
# restarts and optimus-manager re-runs its pre-start hook. Plain "i3-msg exit"
# can reuse the existing X session and skip the hook -> dGPU stays on bus.
if command -v systemctl >/dev/null && systemctl restart sddm 2>/dev/null; then
    exit 0
fi
# Fallback if polkit rule missing: just exit i3 (may reuse X).
SOCK=$(ls /run/user/1000/i3/ipc-socket.* 2>/dev/null | head -1)
if [ -n "$SOCK" ]; then i3-msg -s "$SOCK" exit; else i3-msg exit; fi


