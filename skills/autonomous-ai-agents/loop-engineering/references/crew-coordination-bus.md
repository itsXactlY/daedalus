# Crew Coordination Bus — atomic file claims so parallel workers stop colliding

Captured 2026-08-06 from the Cheshire Fall perpetual crew loop. Replace the
`files:`-clause collision deferral in Loop Type 8 with a real coordination bus.

## Why the old way failed (the proof)

The old Loop Type 8 point 3 deferred items whose declared `files:` overlapped an
already-assigned item in the same round. That trusts the worker's self-reported
`files:` clause. It is fiction.

Proof from Cheshire Fall round 1: an item declared `files: src/game/fx.js,
src/game/render.js` actually touched 8 files, and all three concurrent workers
ended up editing `app.js` + `index.html` without knowing it. Conflicts were only
caught AFTER the writes, at merge time — sometimes silently, because the
determinism-guarded merge "succeeded" on the parts that didn't conflict.

Lesson: **never trust a worker's self-reported `files:` list. Coordinate on the
real shared resource (the file on disk) before editing, and measure the truth
with `git diff` after the round.**

## The bus

A single shell script (`crew`) on disk, one shared `COORD_DIR`. Every mutating
call is atomic via `mkdir` (O_EXCL) so three genuinely-concurrent agents can't
both win a file. State:

- `COORD_DIR/claims/<file-key>/owner` — who holds this file (atomic mkdir)
- `COORD_DIR/inbox/<worker_id>` — handoff requests addressed to a worker
- `COORD_DIR/contracts.md` — interfaces published by workers (persists across rounds)
- `COORD_DIR/board.log` — append-only activity ledger

`file-key` = path with `/` → `__` so any filename is a safe dir name.

### Commands workers call
```
crew claim <file> [file...]   # atomic + ALL-OR-NOTHING; REFUSES on any conflict
crew handoff <file> "<text>"  # ask the holder to make the change for you
crew contract <<'EOF' ... EOF # publish an interface others build against
crew board                    # who holds what, right now
crew contracts                # published interfaces
crew inbox                    # requests addressed to you (CHECK THIS)
crew note "<text>"            # broadcast a short status line
crew release                  # free every file you hold
```

### `claim` must be two-phase + all-or-nothing
Check EVERY file in the set first; only if all are free, take them. A partial
claim is worse than none (two workers holding half of each other's sets deadlocks).
Per file: `mkdir "$d" 2>/dev/null` — succeeds for exactly one racer; on failure,
read `owner` and REFUSE the whole set if it's not you.

### Worker order of operations (put this in the worker prompt verbatim)
```
board → inbox → contracts → claim → work → contract (if you added an interface)
→ commit → release
```
On `CLAIM REFUSED`: do NOT edit the file. Options in order:
1. `crew handoff <file> "<exact change>"` — the holder is in that file anyway.
2. Build against a `crew contracts` entry if one already describes the hook.
3. Reshape the work so it doesn't need the contested file (a new module you own
   beats a shared file you fight over).

## Supervisor integration

1. **Per-round reset.** Stale claims from a crashed worker would block the next
   round. At round start: `rm -rf "$COORD_DIR/claims" "$COORD_DIR/inbox"; mkdir -p ...;
   touch board.log contracts.md`. KEEP contracts + board (inter-round continuity).
2. **Pass env to each worker.** `CREW_COORD="$COORD_DIR" CREW_WORKER_ID="$wid"
   CREW_ROUND="$round" hermes -z "$prompt" -m "$M" --provider "$P" --cli`. The
   worker prompt substitutes `{{WORKER_ID}}`/`{{ROUND}}` (Python, NOT sed — queue
   items contain `|` which breaks sed delimiters; see the sed-delimiter pitfall).
3. **Measure real overlap post-round** (replaces trusting `files:`):
```python
import subprocess, sys, itertools
fork, rnd, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
touched = {}
for w in range(1, n + 1):
    br = f"crew/r{rnd}-w{w}"
    r = subprocess.run(["git","-C",fork,"diff","--name-only",f"master...{br}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        fs = {x for x in r.stdout.split() if x}
        if fs: touched[w] = fs
pairs = []
for a, b in itertools.combinations(sorted(touched), 2):
    both = touched[a] & touched[b]
    if both: pairs.append(f"w{a}+w{b}:{','.join(sorted(both))}")
print("; ".join(pairs) if pairs else "none")
```
Log it as `file overlap between workers: <result>`. `none` = the bus worked.

## Race test (run this before trusting it)
Launch 20 background `crew claim <same file>` processes concurrently. Assert:
exactly 1 winner, 19 refused, owner recorded, no partial claims, handoff reaches
the holder, `release` frees the name, another worker can then claim it, and a
published contract is visible to a different worker. All PASS on the Cheshire
Fall deployment.

## Cheshire Fall result
After the bus went live: w1 atomically claimed `fx.js`+`render.js`+`app.js` and
broadcast its plan; w2 saw Q5 already done (`.item-done` honored) and released 0
— zero collisions, measured overlap `none`.

## The `crew` script (copy verbatim)

Deployed at `/home/alca/projects/cheshire-fall/loop/crew`. `chmod +x`, point
`CREW_COORD` at a shared dir (the supervisor exports it per round). Workers call
it with `CREW_WORKER_ID` / `CREW_ROUND` set.

```bash
#!/usr/bin/env bash
# crew — the coordination bus for parallel workers.
# Every mutating op is atomic (mkdir / O_EXCL): three agents run genuinely
# concurrently and a lost update here means two workers editing the same file.
set -u

COORD="${CREW_COORD:-/home/alca/projects/cheshire-fall/loop/coordination}"
ME="${CREW_WORKER_ID:-unknown}"
ROUND="${CREW_ROUND:-0}"

CLAIMS="$COORD/claims"
BOARD="$COORD/board.log"
CONTRACTS="$COORD/contracts.md"
INBOX="$COORD/inbox"

mkdir -p "$CLAIMS" "$INBOX" 2>/dev/null
touch "$BOARD" "$CONTRACTS" 2>/dev/null

ts() { date +%H:%M:%S; }
key() { echo "$1" | sed 's|^\./||; s|/|__|g'; }

case "${1:-help}" in

  claim)
    shift
    [ $# -gt 0 ] || { echo "usage: crew claim <file> [file...]" >&2; exit 2; }
    # Two-phase: check every file first, then take them. A partial claim is
    # worse than none — it deadlocks two workers holding half of each other's set.
    conflicts=""
    for f in "$@"; do
      d="$CLAIMS/$(key "$f")"
      if [ -d "$d" ]; then
        holder=$(cat "$d/owner" 2>/dev/null || echo '?')
        [ "$holder" = "$ME" ] && continue
        conflicts="$conflicts$f (held by worker $holder)\n"
      fi
    done
    if [ -n "$conflicts" ]; then
      echo "CLAIM REFUSED:" >&2
      printf "$conflicts" >&2
      echo "" >&2
      echo "Do NOT edit these files. Your options, in order of preference:" >&2
      echo "  1. crew handoff <file> \"<the exact change you need>\"  — ask the holder" >&2
      echo "  2. crew contracts   — build against their published interface instead" >&2
      echo "  3. reshape your work so it does not need the file at all" >&2
      exit 1
    fi
    taken=""
    for f in "$@"; do
      d="$CLAIMS/$(key "$f")"
      if mkdir "$d" 2>/dev/null; then          # atomic: only one worker wins
        echo "$ME" > "$d/owner"; echo "$f" > "$d/path"; echo "$ROUND" > "$d/round"
        taken="$taken $f"
      elif [ "$(cat "$d/owner" 2>/dev/null)" = "$ME" ]; then
        taken="$taken $f"
      else
        echo "CLAIM REFUSED: $f taken by worker $(cat "$d/owner" 2>/dev/null) mid-claim" >&2
        exit 1
      fi
    done
    echo "[$(ts)] w$ME CLAIMED$taken" >> "$BOARD"
    echo "CLAIMED:$taken"
    ;;

  release)
    n=0
    for d in "$CLAIMS"/*/; do
      [ -d "$d" ] || continue
      if [ "$(cat "$d/owner" 2>/dev/null)" = "$ME" ]; then rm -rf "$d"; n=$((n+1)); fi
    done
    echo "[$(ts)] w$ME released $n file(s)" >> "$BOARD"
    echo "released $n"
    ;;

  owner)
    d="$CLAIMS/$(key "${2:-}")"
    [ -d "$d" ] && cat "$d/owner" || echo "free"
    ;;

  board)
    echo "=== WHO HOLDS WHAT (round $ROUND) ==="
    found=0
    for d in "$CLAIMS"/*/; do
      [ -d "$d" ] || continue
      printf "  %-34s worker %s\n" "$(cat "$d/path" 2>/dev/null)" "$(cat "$d/owner" 2>/dev/null)"
      found=1
    done
    [ "$found" -eq 0 ] && echo "  (nothing claimed yet)"
    echo ""
    echo "=== RECENT CREW ACTIVITY ==="
    tail -25 "$BOARD" 2>/dev/null | sed 's/^/  /'
    ;;

  contract)
    body=$(cat)
    {
      echo ""
      echo "### worker $ME · round $ROUND · $(ts)"
      echo "$body"
    } >> "$CONTRACTS"
    echo "[$(ts)] w$ME published a contract" >> "$BOARD"
    echo "contract published"
    ;;

  contracts)
    cat "$CONTRACTS"
    ;;

  note)
    shift
    echo "[$(ts)] w$ME: $*" >> "$BOARD"
    echo "noted"
    ;;

  handoff)
    f="${2:-}"; shift 2 2>/dev/null || true
    d="$CLAIMS/$(key "$f")"
    holder=$(cat "$d/owner" 2>/dev/null || echo "")
    [ -n "$holder" ] || { echo "nobody holds $f — just claim it" >&2; exit 1; }
    printf '[%s] FROM worker %s — %s\n  %s\n' "$(ts)" "$ME" "$f" "$*" >> "$INBOX/$holder"
    echo "[$(ts)] w$ME asked w$holder for a change in $f" >> "$BOARD"
    echo "handoff sent to worker $holder"
    ;;

  inbox)
    if [ -s "$INBOX/$ME" ]; then cat "$INBOX/$ME"; else echo "(empty)"; fi
    ;;

  *)
    sed -n '4,20p' "$0"
    ;;
esac
```

### Worker-prompt section (verbatim, drop into `crew-worker-prompt.md`)

~~~markdown
## YOU ARE NOT ALONE — COORDINATE BEFORE YOU EDIT

Two other workers are editing this same codebase **right now**, in their own
worktrees, and everything merges into one master at the end of the round. The
`files:` line in your focus is a hint, not a contract.

There is a coordination bus. Use it:

```bash
CREW="/path/to/crew"
export CREW_WORKER_ID={{WORKER_ID}} CREW_ROUND={{ROUND}}

$CREW board                 # what everyone holds, right now
$CREW contracts             # interfaces colleagues published
$CREW inbox                 # requests addressed to you — CHECK THIS
```

**Claim every file before you edit it — including files you discover you need
halfway through.**

```bash
$CREW claim src/game/fx.js src/game/render.js
```

Atomic and all-or-nothing: either you get every file in the set or none. If it
prints `CLAIM REFUSED`, **do not edit that file**. In order:
1. `crew handoff <file> "<exact change>"` — the holder is in that file anyway.
2. Build against a `crew contracts` entry if one describes the hook.
3. Reshape the work so it does not need the contested file.

Publish what you add so the next worker builds *on* it:

```bash
$CREW contract <<'EOF'
`src/game/fx.js` exports `burst(ctx, x, y, mult)` — particle burst. No-ops under
prefers-reduced-motion.
EOF
```

**Order of operations, every single time:** `board` → `inbox` → `contracts` →
`claim` → work → `contract` (if you added an interface) → commit → `release`.
Forgetting `release` blocks your colleagues for the rest of the round.
~~~
