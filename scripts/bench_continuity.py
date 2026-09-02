#!/usr/bin/env python3
"""Continuity bench ("inception") — does the memory plane hold a mission
together for an extra-long horizon with zero carried history?

Simulates multi-week missions through the REAL provider plane (soak,
pre-compression archive carrying REAL recent exchanges, session rotation,
prefetch, briefing — no orchestrator LLM), planting goals / decisions /
needles, then scores what a fresh turn would SEE at checkpoints using
MARKER-FREE organic queries (verify pass 2026-08-25: marker-bearing queries
made earlier scoring retrieval-by-echo, not survival).

Arms (run separately; each run pins its own mission key so neither scoring
nor briefing can bleed across arms):
  A  legacy        flags off                              (pre-upgrade baseline)
  B  mission-ctrl  REAL router-endpoint distiller + deterministic briefing
  C  marker-oracle rule extractor + briefing — an UPPER BOUND that exploits
                   the generator's literal markers; NOT achievable on prose

Usage: python3 scripts/bench_continuity.py --arm B --turns 48 --repeats 2
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import statistics
import sys
import time
from collections import deque

sys.path.insert(0, "/home/alca/.daedalus")

import plugins.memory.mazemaker as mz
from plugins.memory.mazemaker.distiller import distill_stats

GOALS = ["ship the router bench", "close the credit gap", "stabilize the pod"]
NEEDLE_TOPICS = ["api key rotation", "backup cadence", "quota ceiling", "oncall path"]
DISTRACTIONS = [
    "what is your favourite colour",
    "tell me about the weather today",
    "write a haiku about terminals",
    "summarise nothing in particular",
]
ORGANIC_QUERIES = [
    "Where do we stand on the overall mission right now?",
    "What are our current open questions and blockers?",
    "Which standing decisions should I respect going forward?",
]


def build_script(arm: str, turns: int, rng: random.Random):
    tag = lambda name: f"{name}-{arm}"          # noqa: E731
    script = []
    for t in range(1, turns + 1):
        if t == 1:
            g = "; ".join(f"{tag('GOAL-' + chr(97+i))}: {goal}" for i, goal in enumerate(GOALS))
            u = f"New mission. Our goals for the coming weeks: {g}. Acknowledge and remember."
            a = f"Mission accepted. Goals locked: {g}."
        elif t % 7 == 0:
            i = (t // 7 - 1) % len(GOALS)
            d = tag(f"DECISION-{chr(100+i)}")
            u = f"We decided now ({d}): prefer postgres over sqlite for anything long-lived."
            a = f"Noted as standing decision {d}: postgres wins for long-lived state."
        elif t % 5 == 0:
            i = (t // 5 - 1) % len(NEEDLE_TOPICS)
            n = tag(f"NEEDLE-{chr(122-i%4)}{i}")
            u = f"For your notes only ({n}): the {NEEDLE_TOPICS[i]} policy is quarterly review."
            a = f"Recorded {n}: {NEEDLE_TOPICS[i]} follows quarterly review."
        elif t % 3 == 0:
            u = rng.choice(DISTRACTIONS)
            a = "Happy to chat, but keeping focus on the mission."
        else:
            gi = t % len(GOALS)
            g = tag("GOAL-" + chr(97 + gi))
            u = f"Status check on {g} — where do we stand?"
            a = f"{g} is progressing; next step queued."
        script.append((u, a))
    return script


def is_expected_empty(t: int) -> bool:
    """Distractor turns where a CORRECT distiller verdict is empty lists."""
    return t % 3 == 0 and t % 5 != 0 and t % 7 != 0


def run_rep(arm: str, turns: int, seed: int, rep: int, rule_mode: bool):
    rng = random.Random(seed * 101 + rep)
    flags = {"A": (False, False, 1200),
             "B": (True, True, 1200),
             "C": (True, True, 1200)}[arm]
    mz._mc_flags_override = tuple(flags)

    sid = f"2099{int(time.time())%10000000:07d}_{arm}{rep}"
    p = mz.MazemakerMemoryProvider()
    p.initialize(session_id=sid)
    p._mission_key = f"mk-bench-{arm}-{rep}"

    if arm == "C":
        def rule_distill(user, asst, **kw):
            writes, key = [], p._mission_key
            tsx = f"{int(time.time()*10):x}"
            for idx, text in enumerate((user, asst)):
                m = re.search(r"(?:GOAL|DECISION|NEEDLE)-[a-z0-9]+[^.;]*", text or "")
                if not m:
                    continue
                sent = m.group(0).strip()[:300]
                prefix = ("decision:" if sent.startswith("DECISION")
                          else "open:" if sent.startswith("GOAL")
                          else "fact:")
                writes.append((prefix, sent))
            return [(pf, c) for idx, (pf, c) in enumerate(writes)] or None

        real_distill = mz.distill_turn
        mz.distill_turn = rule_distill

    window = deque(maxlen=12)
    script = build_script(arm, turns, rng)
    checkpoint_every = 12
    checkpoints, ever = [], {}
    junk_turns = expected_empty = parsed_ok = 0
    t_wall0 = time.perf_counter()

    for t, (u, a) in enumerate(script, 1):
        p.sync_turn(u, a)
        window.append({"role": "user", "content": u})
        window.append({"role": "assistant", "content": a})
        if arm == "B" and is_expected_empty(t):
            expected_empty += 1

        if t % checkpoint_every == 0 or t == turns:
            p.on_pre_compress(list(window))
            p.on_session_switch(p._session_id, reset=False)

            q = ORGANIC_QUERIES[(t // checkpoint_every) % len(ORGANIC_QUERIES)]
            block = p.prefetch(q, session_id=p._session_id)
            found = sorted(set(re.findall(r"(?:GOAL|DECISION|NEEDLE)-[a-z0-9]+-" + arm, block)))
            ever.update({m: min(ever.get(m, 10**9), t) for m in found})
            checkpoints.append({
                "after_turn": t,
                "query": q[:60],
                "block_chars": len(block),
                "briefing_present": "MISSION STATE" in block,
                "markers_visible": found,
                "block_tail": block[-200:],
            })

    wall = time.perf_counter() - t_wall0
    if arm == "C":
        mz.distill_turn = real_distill

    st = dict(distill_stats()) if arm == "B" else {}
    true_junk = max(0, st.get("junk", 0) - expected_empty) if st else 0
    res = {
        "arm": arm, "turns": turns, "seed": seed, "rep": rep, "sid": sid,
        "checkpoints": checkpoints,
        "final_checkpoint_markers": checkpoints[-1]["markers_visible"],
        "distinct_ever_visible": sorted(ever),
        "first_seen": ever,
        "briefing_checkpoints": sum(1 for c in checkpoints if c["briefing_present"]),
        "block_chars_mean": round(statistics.mean(c["block_chars"] for c in checkpoints)),
        "wall_s": round(wall, 1),
        "distiller_stats": st,
        "honesty": {
            "expected_empty_verdicts": expected_empty,
            "reported_junk_includes_correct_empties": True,
            "junk_minus_expected_empty": true_junk,
            "note_arm_C": "marker-oracle upper bound; exploits generator's literal tags",
        } if arm != "A" else None,
    }
    if arm == "B":
        res["honesty"]["true_failure_rate"] = (
            round(true_junk / max(1, turns - expected_empty - st.get("parsed", 0)), 2))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=list("ABC"))
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    runs = [run_rep(args.arm, args.turns, args.seed, r, args.arm == "C")
            for r in range(args.repeats)]

    finals = [len(r["final_checkpoint_markers"]) for r in runs]
    briefs = [f"{r['briefing_checkpoints']}/{len(r['checkpoints'])}" for r in runs]
    chars = [r["block_chars_mean"] for r in runs]
    print(f"\n=== ARM {args.arm} · {args.turns} turns × {args.repeats} reps ===")
    print("final-checkpoint markers visible per rep:", finals)
    print("markers at final checkpoint (last rep):")
    for m in runs[-1]["final_checkpoint_markers"]:
        print("   ", m)
    print(f"briefing present: {briefs} | injected block mean chars: {chars}")
    if runs[0]["distiller_stats"]:
        h = runs[-1]["honesty"]
        print(f"distiller: {runs[-1]['distiller_stats']}")
        print(f"honesty: {h}")
    print(f"wall per rep: {[r['wall_s'] for r in runs]}s")

    import datetime
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    rdir = pathlib.Path(__file__).parent / "continuity_bench_results"
    rdir.mkdir(exist_ok=True)
    out = rdir / f"{ts}-arm{args.arm}-x{args.repeats}.json"
    out.write_text(json.dumps({"arm": args.arm, "repeats": runs}, indent=1))
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
