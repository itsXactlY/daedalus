"""KV watermarks: the harness and llama-server agree on how full the fast layer is.

With block KV streaming the GPU holds a fixed number of 256-token pages per
layer; everything past that is demoted to host RAM and decode slows. Under a
unified KV cache every slot's cached tokens share those pages, so the number
that matters is the whole pool -- main's conversation plus whatever the
sidekick slot still holds -- not main's prompt alone.

Levels, as fractions of the fast layer:

    low   free what pays no rent: erase an idle sidekick slot's leftover KV
    high  prewarm the next epoch's turn 0 on the sidekick slot
    hard  rebase: swap main onto the prewarmed slot, erase the old one

All numbers come from the server (/slots), never from a character estimate.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

OK, LOW, HIGH, HARD = "ok", "low", "high", "hard"


@dataclass(frozen=True)
class Watermarks:
    fast_layer_tokens: int
    low: float = 0.60
    high: float = 0.80
    hard: float = 0.90

    def level(self, pool_tokens: int) -> str:
        if self.fast_layer_tokens <= 0:
            return OK
        fill = pool_tokens / self.fast_layer_tokens
        if fill >= self.hard:
            return HARD
        if fill >= self.high:
            return HIGH
        if fill >= self.low:
            return LOW
        return OK

    @property
    def hard_tokens(self) -> int:
        return int(self.fast_layer_tokens * self.hard)

    @property
    def high_ratio_of_hard(self) -> float:
        return self.high / self.hard if self.hard else 0.0


def server_root(base_url: str) -> Optional[str]:
    """The llama-server root for a local base_url, or None for anything remote."""
    base = (base_url or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    low = base.lower()
    if "127.0.0.1" not in low and "localhost" not in low:
        return None
    return base


def read_slots(base_url: str, timeout: float = 1.5) -> List[Dict]:
    root = server_root(base_url)
    if not root:
        return []
    try:
        with urllib.request.urlopen(f"{root}/slots", timeout=timeout) as r:
            data = json.loads(r.read())
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.debug("watermarks: /slots unavailable: %s", exc)
        return []


def slot_tokens(slots: List[Dict], slot_id: int) -> int:
    for s in slots:
        if s.get("id") == slot_id:
            return int(s.get("n_prompt_tokens") or 0)
    return 0


def slot_busy(slots: List[Dict], slot_id: int) -> bool:
    for s in slots:
        if s.get("id") == slot_id:
            return bool(s.get("is_processing"))
    return False


def erase_slot(base_url: str, slot_id: int, timeout: float = 5.0) -> bool:
    """Drop a slot's KV. Needs llama-server started with --slot-save-path."""
    root = server_root(base_url)
    if not root:
        return False
    req = urllib.request.Request(
        f"{root}/slots/{int(slot_id)}?action=erase", data=b"{}",
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception as exc:
        logger.info("watermarks: erasing slot %s failed (start llama-server with "
                    "--slot-save-path to allow it): %s", slot_id, exc)
        return False
