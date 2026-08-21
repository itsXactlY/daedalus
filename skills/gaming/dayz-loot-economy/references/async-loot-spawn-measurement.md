# Async Loot Spawn + Dynamic-Bin Measurement (proven 2026-07-18)

## The red herring

After a CORRECT DayZ CE config, the server RPT still shows at boot:

```
[CE][Hive] :: Initializing of spawners done.
  dynamic groups: 0
```

This line is a PRE-SPAWN counter. It does NOT mean loot is broken. DayZ spawns
loot asynchronously ~15-20 min after `Player connect enabled`, driven by spawn
threads as map sectors load / players connect. Concluding "config still wrong"
from `dynamic groups: 0` and patching a guess = the loop that burned ~6
iterations in the Apocalyps3nd session.

## Measure the bins, not the boot line

The storage dynamic bins are the ground truth. Path:
`mpmissions/dayzOffline.chernarusplus/storage_1/data/dynamic_*.bin`

```bash
D=/home/alca/games/DayZ/Server/mpmissions/dayzOffline.chernarusplus/storage_1/data
total=0; cnt=0; n=0
for f in "$D"/dynamic_*.bin; do
  [ -f "$f" ] || continue
  n=$((n+1)); s=$(stat -c %s "$f"); total=$((total+s))
  [ "$s" -gt 100 ] && cnt=$((cnt+1))
done
echo "Total dynamic bytes: $total | bins with loot (>100b): $cnt / $n"
ls -la "$D"/dynamic_*.bin | awk '{print $5, $NF}' | sort -n | tail -5
```

## What the numbers mean (observed this session)

| State | Total dynamic bytes | bins >100b | Interpretation |
|-------|--------------------|-----------|----------------|
| Fresh post-wipe / post-restart, before async spawn | ~1900 | 1 / 12 | NORMAL empty start, NOT a bug |
| Loot spawning (GOOD) | 5000-50000+ | 8-12 / 12 | Loot is on the map |
| `dynamic_001.bin` alone | 9000+ bytes | - | Confirmed item spawn |

In the Apocalyps3nd session: at t+0 after restart total was 1931 (1/12 bins).
At t+~20min total was 12723 (8/12 bins, `dynamic_001.bin` = 9574 bytes). Same
config, same RPT `dynamic groups: 0` at boot - the ONLY difference was time.

## Success signature (do NOT declare failure before this)

1. RPT: `[CE][TypeSetup] :: 5252 classes setuped...` (NOT 885, NOT 0)
2. RPT: `Player connect enabled` + `Mission geladen`
3. Wait >=15 min after (2).
4. `Total dynamic bytes` > ~5000 AND >=8 bins >100 bytes.

If all 4 hold -> LOOT WORKS. Stop patching config.

## When bins stay empty after 20+ min

Then config is genuinely broken - but the RPT would ALSO show `885 classes`
(vanilla only) or `0 root classes` in `[CE][TypeSetup]`, not `5252`. That is the
real tell (see SKILL.md section 9 FILE-LOCATION + FORMAT TRAP). `dynamic groups: 0`
alone is never the diagnosis.

## Process-kill note

Restarting to test requires killing DayZServer_x64. Under Proton this kills the
agent's own terminal (exit -15) if done via `kill`/`pkill` from the agent shell.
Use the detached subshell pattern from SKILL.md section 11, or let the user close it.
A background `terminal(background=true)` launch of `start_server.sh` works and
survives - but do not `kill` the resulting PID from a foreground shell.
