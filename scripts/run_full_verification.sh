#!/bin/bash
# Full bench verification chain — waits for a FAST pod window, then runs
# all three continuity arms + the router A/B instrument, logging summaries.
set -u
cd "$(dirname "$(readlink -f "$0")")/.."

echo "[chain] waiting for fast pod window (<7s recall)…"
i=0
until [ "$i" -ge 36 ]; do
    T0=$(date +%s%N)
    R=$(curl -sf -m 8 -X POST http://127.0.0.1:8765/tools/call \
        -H 'Content-Type: application/json' \
        -d '{"name":"mazemaker_recall","arguments":{"query":"health probe","limit":2}}' 2>/dev/null | head -c 20)
    T1=$(date +%s%N)
    MS=$(( (T1-T0)/1000000 ))
    if [ -n "$R" ] && [ "$MS" -lt 7000 ]; then
        echo "[chain] POD FAST (${MS}ms) — starting bench sequence"
        break
    fi
    i=$((i+1)); sleep 40
done
if [ "$i" -ge 36 ]; then echo "[chain] pod never got fast in ~24min — aborting"; exit 1; fi

for ARM in A B C; do
    echo "[chain] === arm $ARM ==="
    timeout 500 python3 scripts/bench_continuity.py --arm "$ARM" --turns 48 --repeats 1 2>&1 | \
        grep -E '===|final-checkpoint|markers at|^    |distiller:|briefing present|wall'
done

echo "[chain] === router A/B (n=15) ==="
timeout 500 python3 scripts/bench_router_ab.py --limit 15 --seed 42 2>&1 | tail -14

echo "[chain] DONE"
