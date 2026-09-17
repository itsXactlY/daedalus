"""Append-only request payload.

On the hybrid main model (qwen35: no context shift, no cache reuse, recurrent
state that only truncates at the tail) llama-server reuses a prompt only when
the previous prompt is an exact prefix of the new one. Every earlier byte that
changes sends it back to the last checkpoint that still matches -- in practice
the one right after the system prompt and tool schemas.

Rewriting earlier messages was the payload's normal mode: the reasoning TTL
swapped the 4th-newest reasoning for a handle, the tool-group TTL collapsed the
9th-newest exchange, stale results were pruned, the head window moved each
turn, and turn injections vanished from last turn's user message. Measured
2026-09-17: every call reused exactly 12,363 tokens (system + tools) and
re-read the whole conversation after them, 60-70% of each prompt.

The tape freezes what was sent. The first call of an epoch renders the whole
view with every hygiene layer applied; after that a message is rendered once,
the first time it enters the payload, and every later call reuses that
rendering byte for byte. A new epoch starts only when the history under the
tape is replaced -- a compaction -- where one full prefill is unavoidable.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Sequence


class PayloadTape:
    """Rendered payload blocks, each keyed by the source messages it covers.

    The first block of an epoch covers the whole initial view, because the
    hygiene layers do not map sources to output one-to-one (a collapsed tool
    group turns several messages into one line). Every later block covers
    exactly one source message.
    """

    def __init__(self) -> None:
        self._blocks: List[tuple] = []  # (sources tuple, rendered list)
        self.generation: Optional[int] = None

    def __bool__(self) -> bool:
        return bool(self._blocks)

    @property
    def first_source(self) -> Optional[Dict[str, Any]]:
        if not self._blocks or not self._blocks[0][0]:
            return None
        return self._blocks[0][0][0]

    def reset(self) -> None:
        self._blocks = []
        self.generation = None

    def start(self, sources: Sequence[Dict[str, Any]], rendered: List[Dict[str, Any]],
              generation: int) -> None:
        self._blocks = [(tuple(sources), copy.deepcopy(rendered))]
        self.generation = generation

    def matched_blocks(self, view: Sequence[Dict[str, Any]], generation: int) -> tuple:
        """Return (blocks, sources) of the longest tape prefix ``view`` still starts with.

        A block matches only when every source it covers is the same object at
        the same position. Identity, not equality: a compaction copies messages,
        and a copy is a different history even when it looks the same.
        """
        if generation != self.generation:
            return 0, 0
        blocks = 0
        pos = 0
        for sources, _ in self._blocks:
            end = pos + len(sources)
            if end > len(view):
                break
            if any(view[pos + i] is not src for i, src in enumerate(sources)):
                break
            blocks += 1
            pos = end
        return blocks, pos

    def truncate(self, blocks: int) -> None:
        del self._blocks[blocks:]

    def append(self, source: Dict[str, Any], rendered: List[Dict[str, Any]]) -> None:
        self._blocks.append(((source,), copy.deepcopy(rendered)))

    def payload(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for _, rendered in self._blocks:
            out.extend(copy.deepcopy(rendered))
        return out
