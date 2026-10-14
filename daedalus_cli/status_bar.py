"""The TUI's one-line status bar.

Each segment has a priority and its renderings from full to compact. fit()
spends the terminal width on what matters first: the model, the context and
the live rate stay; VRAM and the slot map go first. Colours are style classes
the active skin fills in (skin_engine.get_prompt_toolkit_style_overrides).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

Frag = Tuple[str, str]

PLAIN = "class:status-bar"
STRONG = "class:status-bar-strong"
DIM = "class:status-bar-dim"
LABEL = "class:status-bar-label"
ACCENT = "class:status-bar-accent"
GOOD = "class:status-bar-good"
WARN = "class:status-bar-warn"
BAD = "class:status-bar-bad"
CRITICAL = "class:status-bar-critical"

_SEP: Frag = (DIM, " │ ")
_EIGHTHS = "▏▎▍▌▋▊▉"


def cell_width(text: str) -> int:
    try:
        from prompt_toolkit.utils import get_cwidth
        return get_cwidth(text or "")
    except Exception:
        return len(text or "")


def gauge(percent: Optional[float], width: int = 10) -> str:
    """A bar with eighth-cell resolution: 80 steps at width 10, not 10."""
    eighths = round(max(0.0, min(100.0, percent or 0.0)) / 100.0 * width * 8)
    full, part = divmod(eighths, 8)
    text = "█" * full + (_EIGHTHS[part - 1] if part else "")
    return text + "░" * (width - full - (1 if part else 0))


def tokens(n: float) -> str:
    n = float(n or 0)
    if n < 1000:
        return f"{n:.0f}"
    if n < 1_000_000:
        return f"{n / 1000:.1f}K"
    return f"{n / 1_000_000:.2f}M"


def work_time(seconds: float) -> str:
    """Seconds while short, then minutes:seconds, then hours:minutes: it ticks visibly."""
    seconds = int(max(0.0, seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def load_style(percent: Optional[float], warn: float, bad: float, critical: float) -> str:
    """Higher is worse: context, VRAM."""
    if percent is None:
        return DIM
    if percent >= critical:
        return CRITICAL
    if percent >= bad:
        return BAD
    if percent >= warn:
        return WARN
    return GOOD


def yield_style(percent: Optional[float], good: float, warn: float) -> str:
    """Higher is better: draft acceptance, cache reuse."""
    if percent is None:
        return DIM
    if percent >= good:
        return GOOD
    if percent >= warn:
        return WARN
    return BAD


def _segment(prio: int, *variants: List[Frag], droppable: bool = True) -> Dict[str, Any]:
    return {"prio": prio, "variants": [v for v in variants if v], "droppable": droppable}


def _model(name: str) -> Dict[str, Any]:
    def cut(n: int) -> str:
        return name if len(name) <= n else name[: n - 1] + "…"
    return _segment(0, [(PLAIN, "⚕ "), (STRONG, cut(40))], [(PLAIN, "⚕ "), (STRONG, cut(26))],
                    [(PLAIN, "⚕ "), (STRONG, cut(14))], droppable=False)


def _tape(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """The epoch on its way to the next rebase; the window behind it no longer matters."""
    pct = snapshot["tape_percent"]
    style = load_style(pct, 80, 95, 101)
    used, at = snapshot["context_used_label"], snapshot["rebase_at_label"]
    epoch = snapshot.get("epoch") or 1
    tag = [(DIM, f" e{epoch}")] if epoch > 1 else []
    return _segment(
        2,
        [(LABEL, "tape "), (style, gauge(pct)), (PLAIN, f" {used}→{at} "), (style, f"{pct}%")] + tag,
        [(style, gauge(pct, 5)), (PLAIN, " "), (style, f"{pct}%")] + tag,
        [(style, f"{pct}%")],
        droppable=False,
    )


def _context(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    if snapshot.get("rebase_at") and snapshot.get("tape_percent") is not None \
            and snapshot.get("context_used_label"):
        return _tape(snapshot)
    pct = snapshot.get("context_percent")
    if not snapshot.get("context_length") or pct is None:
        return _segment(2, [(LABEL, "ctx "), (DIM, "--")], droppable=False)
    style = load_style(pct, 50, 80.5, 95)
    used, total = snapshot["context_used_label"], snapshot["context_total_label"]
    return _segment(
        2,
        [(LABEL, "ctx "), (style, gauge(pct)), (PLAIN, f" {used}/{total} "), (style, f"{pct}%")],
        [(style, gauge(pct, 5)), (PLAIN, " "), (style, f"{pct}%")],
        [(style, f"{pct}%")],
        droppable=False,
    )


def _main_slot(telemetry: Dict[str, Any], main_slot: int) -> Dict[str, Any]:
    slots = telemetry.get("slots") or []
    if len(slots) == 1:
        return slots[0]  # one conversation (Strata, -np 1): that slot is main
    for slot in slots:
        if slot.get("id") == main_slot:
            return slot
    return {}


def _generation(main: Dict[str, Any], session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    live = main.get("decode_tps") if main.get("phase") == "decode" else None
    avg = session.get("gen_tps")
    if not live and not avg:
        return None
    full: List[Frag] = [(LABEL, "gen ")]
    if live:
        full.append((STRONG, f"{live:.1f}"))
    if avg:
        full += [(DIM, " ⌀" if live else "⌀"), (PLAIN, f"{avg:.1f}")]
    full.append((DIM, " t/s"))
    return _segment(3, full, [(STRONG if live else PLAIN, f"{(live or avg):.1f}"), (DIM, " t/s")])


def _prefill(main: Dict[str, Any], session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if main.get("phase") == "prefill":
        done, rate = main.get("prompt_processed") or 0, main.get("prefill_tps")
        full: List[Frag] = [(LABEL, "prefill "), (ACCENT, f"+{tokens(done)}")]
        if rate:
            full += [(PLAIN, f" {rate:.0f}"), (DIM, " t/s")]
        return _segment(3, full, [(LABEL, "pp "), (ACCENT, f"+{tokens(done)}")])
    avg = session.get("prefill_tps")
    if not avg:
        return None
    return _segment(6, [(LABEL, "pp "), (DIM, "⌀"), (PLAIN, f"{avg:.0f}"), (DIM, " t/s")])


def _draft(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pct = session.get("draft_pct")
    if pct is None:
        return None
    style = yield_style(pct, 60, 35)
    full: List[Frag] = [(LABEL, "draft "), (style, f"{pct:.0f}%")]
    if session.get("draft_per_step"):
        # tokens one target pass yields: 1 sampled + the accepted draft
        full += [(DIM, " ×"), (PLAIN, f"{session['draft_per_step']:.1f}")]
    return _segment(5, full, [(LABEL, "dr "), (style, f"{pct:.0f}%")])


def _cache(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pct = session.get("cache_hit_pct")
    if pct is None:
        return None
    return _segment(6, [(LABEL, "cache "), (yield_style(pct, 80, 50), f"{pct:.0f}%")])


def _slots(telemetry: Dict[str, Any], main_slot: int) -> Optional[Dict[str, Any]]:
    slots = telemetry.get("slots") or []
    if len(slots) < 2:
        return None
    full: List[Frag] = [(LABEL, "slots")]
    compact: List[Frag] = [(LABEL, "slots ")]
    for slot in slots:
        is_main = slot.get("id") == main_slot
        glyph = "◆" if is_main else "◇"
        if slot.get("phase") in ("prefill", "decode"):
            style = STRONG if is_main else ACCENT
        else:
            style = PLAIN if slot.get("tape") else DIM
        tape = slot.get("tape") or 0
        full += [(PLAIN, " "), (style, glyph + (tokens(tape) if tape else ""))]
        compact.append((style, glyph))
    return _segment(7, full, compact)


def _vram(telemetry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    vram = telemetry.get("vram")
    if not vram or not vram[1]:
        return None
    used, total = vram
    pct = used / total * 100.0
    style = load_style(pct, 85, 92, 97)
    return _segment(8, [(LABEL, "vram "), (style, f"{used / 1024:.1f}/{total / 1024:.1f}G")],
                    [(LABEL, "vram "), (style, f"{pct:.0f}%")])


def _background(snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    parts = [f"{glyph} {snapshot[key]}" for key, glyph in (
        ("active_background_tasks", "▶"), ("active_background_processes", "⚙"),
        ("active_background_subagents", "⛓")) if snapshot.get(key)]
    return _segment(4, [(ACCENT, "  ".join(parts))]) if parts else None


def segments(snapshot: Dict[str, Any], main_slot: int = 1) -> List[Dict[str, Any]]:
    telemetry = snapshot.get("llama_telemetry") or {}
    session = telemetry.get("session") or {}
    main = _main_slot(telemetry, main_slot)
    out = [
        _model(snapshot.get("model_label") or snapshot.get("model_short") or "?"),
        _context(snapshot),
        _generation(main, session),
        _prefill(main, session),
        _draft(session),
        _cache(session),
        _slots(telemetry, main_slot),
        _vram(telemetry),
        _background(snapshot),
        # turn time only: the clock stops at the idle prompt
        _segment(1, [(LABEL, "work "), (PLAIN, snapshot.get("duration") or "")],
                 [(PLAIN, snapshot.get("duration") or "")], droppable=False),
    ]
    return [s for s in out if s and s["variants"]]


def _render(segs: Sequence[Dict[str, Any]], levels: Sequence[int]) -> List[Frag]:
    frags: List[Frag] = [(PLAIN, " ")]
    first = True
    for seg, level in zip(segs, levels):
        if level >= len(seg["variants"]):
            continue
        if not first:
            frags.append(_SEP)
        frags += seg["variants"][level]
        first = False
    frags.append((PLAIN, " "))
    return [f for f in frags if f[1]]


def fit(segs: Sequence[Dict[str, Any]], width: int) -> List[Frag]:
    """Shorten the optional segments, then drop them, then shorten the rest.

    Each pass takes the least important segment first, so a terse VRAM and
    slot map outlive the full gen label, and context loses its token counts
    only once everything optional is gone.
    """
    levels = [0] * len(segs)

    def can_compact(i: int) -> bool:
        return levels[i] < len(segs[i]["variants"]) - 1

    passes = (
        lambda i: segs[i]["droppable"] and can_compact(i),
        lambda i: segs[i]["droppable"] and levels[i] < len(segs[i]["variants"]),
        lambda i: not segs[i]["droppable"] and can_compact(i),
    )
    while True:
        frags = _render(segs, levels)
        if sum(cell_width(t) for _, t in frags) <= width:
            return frags
        for allowed in passes:
            candidates = [i for i in range(len(segs)) if allowed(i)]
            if candidates:
                levels[max(candidates, key=lambda i: (segs[i]["prio"], i))] += 1
                break
        else:
            return frags
