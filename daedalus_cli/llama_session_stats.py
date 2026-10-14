"""Whole-session llama-server statistics, from its own cumulative counters.

The status bar used to show two throughput numbers, and neither covered the
session. Live tok/s comes from /slots deltas and exists only while a slot is
generating. The idle "~avg" was llama-server's `predicted_tokens_seconds`
gauge, a bucket the server resets on every /metrics read; with the one-second
poller it was barely more than another live sample.

llama-server also exports monotonically increasing counters: prompt tokens
processed, prompt tokens reused from cache, and the seconds spent on each,
generated tokens and their seconds, draft tokens proposed and accepted.
Subtract a baseline taken when the session starts and every session average
is exact, not sampled.

Counters restart at zero when the server restarts (`daedalus doctor restart`,
the watchdog). A counter going backwards is treated as exactly that: what had
accumulated is kept and counting continues from the new process, so a restart
never erases or inflates the session.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

COUNTERS = (
    "prompt_tokens_total",
    "prompt_tokens_cached_total",
    "prompt_seconds_total",
    "tokens_predicted_total",
    "tokens_predicted_seconds_total",
    "spec_decode_num_draft_tokens_total",
    "spec_decode_num_accepted_tokens_total",
    "spec_decode_num_drafts_total",
)

_LINE = re.compile(r"^llamacpp:([A-Za-z0-9_]+)\s+([0-9.eE+-]+)\s*$")


def parse_metrics(text: str) -> Dict[str, float]:
    """llama-server's Prometheus text -> {name: value}, labelled series ignored."""
    out: Dict[str, float] = {}
    for line in (text or "").splitlines():
        m = _LINE.match(line)
        if m:
            try:
                out[m.group(1)] = float(m.group(2))
            except ValueError:
                continue
    return out


def strata_snapshot(payload) -> tuple:
    """Strata's JSON /metrics -> (counters in llama-server's names, the one slot as the status bar wants it).

    (None, None) for anything that is not a Strata payload. Strata has one conversation at a time, so its
    single slot is main; it has no per-step draft count, so draft_per_step stays unknown."""
    if not isinstance(payload, dict) or not isinstance(payload.get("totals"), dict):
        return None, None
    t, live = payload["totals"], payload.get("live") or {}
    prompt, reused = float(t.get("prompt_tokens") or 0), float(t.get("reused") or 0)
    counters = {
        "prompt_tokens_total": max(0.0, prompt - reused),
        "prompt_tokens_cached_total": reused,
        "prompt_seconds_total": float(t.get("prompt_ms") or 0) / 1000.0,
        "tokens_predicted_total": float(t.get("output_tokens") or 0),
        "tokens_predicted_seconds_total": float(t.get("decode_ms") or 0) / 1000.0,
        "spec_decode_num_draft_tokens_total": float(t.get("drafts_offered") or 0),
        "spec_decode_num_accepted_tokens_total": float(t.get("drafts_accepted") or 0),
        "spec_decode_num_drafts_total": 0.0,
    }
    state = live.get("state")
    phase = {"reading": "prefill", "generating": "decode"}.get(state, "idle")
    slot = {"id": 0, "phase": phase,
            "n_ctx": int((payload.get("engine") or {}).get("max_context") or 0),
            "tape": int((live.get("prompt_tokens") or 0) + (live.get("generated") or 0)) if phase != "idle" else 0}
    if phase == "decode" and live.get("tok_s"):
        slot["decode_tps"] = float(live["tok_s"])
    if phase == "prefill":
        slot["prompt_processed"] = int(live.get("prompt_read") or 0)
        if live.get("prefill_tok_s_mean"):
            slot["prefill_tps"] = float(live["prefill_tok_s_mean"])
    return counters, slot


class SessionCounters:
    """Session totals of llama-server counters, across server restarts."""

    def __init__(self) -> None:
        self._base: Optional[Dict[str, float]] = None
        self._last: Optional[Dict[str, float]] = None
        self._carried: Dict[str, float] = {k: 0.0 for k in COUNTERS}
        self.restarts = 0
        self.kv_now_pct: Optional[float] = None
        self.kv_peak_pct = 0.0
        self._kv_sum = 0.0
        self._kv_samples = 0

    @property
    def has_baseline(self) -> bool:
        return self._base is not None

    def update(self, metrics: Dict[str, float]) -> Dict[str, float]:
        cur = {k: float(metrics.get(k, 0.0) or 0.0) for k in COUNTERS}
        if self._base is None:
            self._base = dict(cur)
            self._last = dict(cur)
            return self.totals()
        if any(cur[k] < self._last[k] for k in COUNTERS):
            for k in COUNTERS:
                self._carried[k] += self._last[k] - self._base[k]
            self._base = {k: 0.0 for k in COUNTERS}
            self.restarts += 1
        self._last = cur
        return self.totals()

    def totals(self) -> Dict[str, float]:
        if self._base is None or self._last is None:
            return {k: 0.0 for k in COUNTERS}
        return {k: self._carried[k] + self._last[k] - self._base[k] for k in COUNTERS}

    def observe_kv(self, used: int, ctx: int) -> None:
        """One KV-fill sample while a slot is busy."""
        if not ctx:
            return
        pct = used / ctx * 100.0
        self.kv_now_pct = pct
        self.kv_peak_pct = max(self.kv_peak_pct, pct)
        self._kv_sum += pct
        self._kv_samples += 1

    def summary(self) -> Dict[str, Optional[float]]:
        t = self.totals()

        def ratio(num: float, den: float, scale: float = 1.0) -> Optional[float]:
            return num / den * scale if den > 0 else None

        prompt, cached = t["prompt_tokens_total"], t["prompt_tokens_cached_total"]
        return {
            "gen_tokens": t["tokens_predicted_total"],
            "gen_tps": ratio(t["tokens_predicted_total"], t["tokens_predicted_seconds_total"]),
            "prompt_tokens": prompt,
            "prompt_cached": cached,
            "prefill_tps": ratio(prompt, t["prompt_seconds_total"]),
            "cache_hit_pct": ratio(cached, cached + prompt, 100.0),
            "draft_tokens": t["spec_decode_num_draft_tokens_total"],
            "draft_accepted": t["spec_decode_num_accepted_tokens_total"],
            "draft_pct": ratio(t["spec_decode_num_accepted_tokens_total"],
                               t["spec_decode_num_draft_tokens_total"], 100.0),
            # tokens one verify pass yields: the sampled one plus the accepted draft
            "draft_per_step": (1.0 + t["spec_decode_num_accepted_tokens_total"] / t["spec_decode_num_drafts_total"]
                               if t["spec_decode_num_drafts_total"] > 0 else None),
            "kv_now_pct": self.kv_now_pct,
            "kv_avg_pct": ratio(self._kv_sum, float(self._kv_samples)),
            "kv_peak_pct": self.kv_peak_pct if self._kv_samples else None,
            "restarts": float(self.restarts),
        }
