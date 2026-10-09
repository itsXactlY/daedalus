#!/usr/bin/env python3
"""Read the prompt trace and answer: is the window bounded, and what is filling it.

The session totals in state.db answer "how much"; this answers "how big was each request's
prompt, how much of it was the reused prefix, and which of the three levers -- system prompt,
tool schemas, conversation -- grew it". A window that only ever grows is a hygiene failure, and
this is where it shows up before the context length surprises someone.

    tools/prompt_trace_report.py [--trace PATH] [--session ID] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

DEFAULT_TRACE = Path(os.environ.get("DAEDALUS_HOME", str(Path.home() / ".daedalus"))) / "logs" / "prompt-trace.jsonl"


def load(path: Path, session: str | None) -> list[dict]:
    if not path.exists():
        sys.exit(f"no prompt trace at {path} - run a turn first (DAEDALUS_PROMPT_TRACE=0 disables it)")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if session and row.get("session") != session:
            continue
        rows.append(row)
    return rows


def human(n: float) -> str:
    for unit, div in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(n) >= div:
            return f"{n / div:.2f}{unit}"
    return f"{n:.0f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trace", default=str(DEFAULT_TRACE), type=Path)
    ap.add_argument("--session", default=None)
    ap.add_argument("--limit", type=int, default=12, help="rows in the growth curve")
    args = ap.parse_args()

    rows = load(args.trace, args.session)
    if not rows:
        print("no matching rows")
        return 1

    prompt = sum(r.get("prompt", 0) for r in rows)
    fresh = sum(r.get("fresh", 0) for r in rows)
    reused = sum(r.get("reused", 0) for r in rows)
    out = sum(r.get("output", 0) for r in rows)
    calls = len(rows)

    print(f"trace      : {args.trace}")
    print(f"calls      : {calls:,}")
    print(f"prompt     : {human(prompt)} total   {human(prompt / calls)} per call")
    print(f"  reused   : {human(reused)} ({100 * reused / prompt:.1f}%)")
    print(f"  fresh    : {human(fresh)} ({100 * fresh / prompt:.1f}%)")
    print(f"output     : {human(out)}")
    if out:
        print(f"bloat      : {prompt / out:.0f} prompt tokens per output token")
        print(f"fresh cost : {fresh / out:.1f} fresh prompt tokens per output token")

    last = rows[-1]
    print("\nlast request:")
    print(f"  prompt {last.get('prompt', 0):,} = {last.get('fresh', 0):,} fresh + {last.get('reused', 0):,} reused"
          f"   window {last.get('window', 0):,}")
    for key, label in (("sys", "system prompt"), ("tools", "tool schemas"), ("history", "conversation")):
        v = last.get(key, 0) or 0
        share = 100 * v / last["prompt"] if last.get("prompt") else 0
        print(f"  {label:<14} {v:>9,}  {share:5.1f}%")
    print(f"  messages {last.get('messages', 0):,}   compressions so far {last.get('compressions', 0)}")

    print(f"\ngrowth curve (last {args.limit} calls):")
    for r in rows[-args.limit:]:
        pct = 100 * r.get("prompt", 0) / r["window"] if r.get("window") else 0
        bar = "#" * int(pct / 2)
        print(f"  turn {r.get('turn', 0):<4} call {r.get('call', 0):<4} "
              f"{r.get('prompt', 0):>8,} {pct:5.1f}% {bar}")

    # The question that started this: does the window ever run away, or does hygiene hold it?
    per_turn: dict[int, int] = defaultdict(int)
    for r in rows:
        per_turn[r.get("turn", 0)] = max(per_turn[r.get("turn", 0)], r.get("prompt", 0))
    curve = [per_turn[t] for t in sorted(per_turn)]
    if len(curve) >= 3:
        grew = curve[-1] - curve[0]
        peak = max(curve)
        print(f"\nturn peaks  : {human(curve[0])} -> {human(curve[-1])} "
              f"({grew:+,}), highest {human(peak)}")
        compressions = rows[-1].get("compressions", 0)
        if grew > 0 and compressions == 0 and peak > 0.5 * (rows[-1].get("window") or 1):
            print("VERDICT     : growing with no compression and past half the window - hygiene is not firing")
        elif compressions:
            print(f"VERDICT     : hygiene fired {compressions}x; the window is bounded by rebase, not by growth")
        else:
            print("VERDICT     : bounded so far (no runaway, no compression needed yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())