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
            "kv_now_pct": self.kv_now_pct,
            "kv_avg_pct": ratio(self._kv_sum, float(self._kv_samples)),
            "kv_peak_pct": self.kv_peak_pct if self._kv_samples else None,
            "restarts": float(self.restarts),
        }
