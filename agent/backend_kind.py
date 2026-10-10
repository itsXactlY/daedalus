"""Does the local endpoint hold ONE conversation at a time (Strata), or several?

Strata has no concurrent slots. Any second conversation makes it park the main
one first, measured 32-38 s for a ~30k-token tape (strata-daedalus.log: "parked
30562 tokens in 38523.1 ms"), so a 13-token title request cost 39 s. A
llama-server with -np 2 has a sidekick slot and does not pay that.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Dict, Tuple

from agent.kv_watermarks import server_root

_TTL_S = 60.0
_cache: Dict[str, Tuple[float, bool]] = {}


def is_single_sequence(base_url: str, timeout: float = 1.5) -> bool:
    """True for a local Strata endpoint. DAEDALUS_SINGLE_SEQUENCE=1/0 overrides."""
    forced = os.environ.get("DAEDALUS_SINGLE_SEQUENCE", "").strip().lower()
    if forced in ("1", "true", "yes"):
        return True
    if forced in ("0", "false", "no"):
        return False
    root = server_root(base_url)
    if not root:
        return False
    now = time.monotonic()
    hit = _cache.get(root)
    if hit and now - hit[0] < _TTL_S:
        return hit[1]
    found = False
    try:
        with urllib.request.urlopen(root + "/metrics", timeout=timeout) as r:
            eng = (json.loads(r.read().decode("utf-8", "replace")) or {}).get("engine")
            found = isinstance(eng, dict) and "expert_slots" in eng
    except Exception:
        found = hit[1] if hit else False   # a failed probe keeps the last answer
    _cache[root] = (now, found)
    return found
