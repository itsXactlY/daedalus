# Root-less log rotation: copytruncate user script + systemd user timer

Use when a long-running process (e.g. `daedalus mcp serve`) appends to a log
unbounded and you have NO sudo. The process holds the fd open, so `mv` +
recreate breaks the writer — snapshot + truncate in place instead.

## Script (~/.local/bin/<name>-logrotate.sh)
```bash
#!/usr/bin/env bash
LOG="$HOME/.daedalus/logs/mcp-stderr.log"
MAX_BYTES=10485760   # 10M
KEEP=5
[ -f "$LOG" ] || exit 0
SIZE=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
[ "$SIZE" -lt "$MAX_BYTES" ] && exit 0
for i in $(seq "$KEEP" -1 2); do
  prev=$((i - 1))
  [ -f "$LOG.$prev.gz" ] && mv -f "$LOG.$prev.gz" "$LOG.$i.gz" 2>/dev/null || true
done
cp "$LOG" "$LOG.1"     # snapshot
: > "$LOG"             # truncate in place — fd stays valid
gzip -f "$LOG.1" 2>/dev/null || true
```

## Service + timer (~/.config/systemd/user/)
`<name>-logrotate.service`:
```
[Unit]
Description=Rotate <log> if it exceeds 10M
[Service]
Type=oneshot
ExecStart=%h/.local/bin/<name>-logrotate.sh
```
`<name>-logrotate.timer`:
```
[Unit]
Description=Hourly rotation check for <log>
[Timer]
OnBootSec=5min
OnUnitActiveSec=1h
AccuracySec=1min
[Install]
WantedBy=timers.target
```
```bash
chmod +x ~/.local/bin/<name>-logrotate.sh
systemctl --user daemon-reload
systemctl --user enable --now <name>-logrotate.timer
~/.local/bin/<name>-logrotate.sh   # run once immediately
ls -la ~/.daedalus/logs/*.gz         # verify .1.gz appeared, live log is 0
```
Verified 2026-08-07: 12MB log → 150KB .gz in one run; timer active.
