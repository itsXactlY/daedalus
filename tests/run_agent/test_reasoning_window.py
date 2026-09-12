"""Reasoning has a TTL: past it, the block is spilled, not deleted.

Preserved thinking is worth having -- it is why the model does not re-derive
a conclusion it already reached. It is just not worth re-sending for the life
of the session: across four ten-hour session logs it was 22-30% of the entire
payload (150k-240k tokens), the largest single thing being re-read on every
call, and nothing pruned it the way tool results are pruned.

So it expires the way a bulky tool result does. Past the TTL the bytes go to
RAM-backed tmpfs and the message carries a short handle naming the path, so
the model can read the thinking back. Deleting it would be amnesia; carrying
it forever is the KV cache problem; a path is neither.

The transcript is never touched -- `reasoning` stays on every message for the
session log, /resume and mazemaker. Only the request thins.
"""

import run_agent

_RealAIAgent = run_agent.AIAgent


class _Compressor:
    """Stands in for ContextCompressor.spill_reasoning."""

    def __init__(self, works=True):
        self.works = works
        self.spilled = []

    def spill_reasoning(self, content, label=""):
        self.spilled.append(content)
        if not self.works:
            return None
        return f"[offloaded: reasoning ({len(content)} chars) -> /dev/shm/r{len(self.spilled)}]"


def _agent(model="qwen3.8-27b", **over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.model = model
    a.context_compressor = _Compressor()
    for k, v in over.items():
        setattr(a, k, v)
    return a


def _msgs(n_assistant, with_reasoning=True, size=2000):
    """size defaults above _REASONING_SPILL_MIN_CHARS so blocks are spillable."""
    out = []
    for i in range(n_assistant):
        out.append({"role": "assistant", "content": f"a{i}",
                    "reasoning": (f"thought-{i} " + "x" * size) if with_reasoning else ""})
        out.append({"role": "tool", "content": f"result-{i}"})
    return out


def _is_handle(v):
    return isinstance(v, str) and v.startswith("[offloaded: reasoning")


class TestTTL:
    def test_newest_few_keep_their_text_verbatim(self):
        a = _agent()
        msgs = _msgs(10)
        out = a._reasoning_payload(msgs)
        for i in (14, 16, 18):                     # newest three assistants
            assert out[i] == msgs[i]["reasoning"]

    def test_everything_older_becomes_a_handle_not_a_hole(self):
        a = _agent()
        msgs = _msgs(10)
        out = a._reasoning_payload(msgs)
        aged = [i for i in out if i not in (14, 16, 18)]
        assert len(aged) == 7
        for i in aged:
            assert _is_handle(out[i]), "expired reasoning must be replaced, not dropped"
            assert "read_file" in out[i] or "/dev/shm" in out[i]

    def test_a_short_conversation_keeps_everything(self):
        a = _agent()
        out = a._reasoning_payload(_msgs(2))
        assert set(out) == {0, 2}
        assert a.context_compressor.spilled == []

    def test_messages_without_reasoning_do_not_consume_the_ttl(self):
        a = _agent()
        msgs = _msgs(3) + [{"role": "assistant", "content": "no thinking"}] * 4
        out = a._reasoning_payload(msgs)
        assert set(out) == {0, 2, 4}
        assert a.context_compressor.spilled == []

    def test_ttl_is_configurable(self):
        a = _agent(_reasoning_window=1)
        out = a._reasoning_payload(_msgs(10))
        verbatim = [i for i, v in out.items() if not _is_handle(v)]
        assert len(verbatim) == 1

    def test_zero_expires_everything_immediately(self):
        a = _agent(_reasoning_window=0)
        out = a._reasoning_payload(_msgs(10))
        assert out and all(_is_handle(v) for v in out.values())

    def test_empty_history(self):
        assert _agent()._reasoning_payload([]) == {}


class TestSpillingIsDoneOnce:
    def test_the_handle_is_cached_on_the_message(self):
        a = _agent()
        msgs = _msgs(10)
        a._reasoning_payload(msgs)
        cached = [m for m in msgs if m.get("_reasoning_spill")]
        assert len(cached) == 7

    def test_a_later_turn_reuses_the_same_path(self):
        a = _agent()
        msgs = _msgs(10)
        first = a._reasoning_payload(msgs)
        spilled_after_first = len(a.context_compressor.spilled)
        second = a._reasoning_payload(msgs)
        assert len(a.context_compressor.spilled) == spilled_after_first, (
            "re-spilling the same block every turn would write a new tmpfs "
            "file per call and change the payload each time"
        )
        aged = [i for i in first if _is_handle(first[i])]
        for i in aged:
            assert second[i] == first[i]


class TestNotWorthSpilling:
    def test_small_blocks_keep_their_text(self):
        """The handle naming the path is ~150 chars. Spilling a block barely
        larger than that trades bytes for a read_file round-trip."""
        a = _agent()
        msgs = _msgs(10, size=50)
        out = a._reasoning_payload(msgs)
        assert all(not _is_handle(v) for v in out.values())
        assert a.context_compressor.spilled == []

    def test_a_failed_spill_carries_the_text_rather_than_losing_it(self):
        a = _agent()
        a.context_compressor = _Compressor(works=False)
        msgs = _msgs(10)
        out = a._reasoning_payload(msgs)
        assert all(not _is_handle(v) for v in out.values())
        assert all(out[i] == msgs[i]["reasoning"] for i in out)

    def test_a_raising_compressor_is_non_fatal(self):
        class _Boom:
            def spill_reasoning(self, content, label=""):
                raise OSError("tmpfs full")

        a = _agent()
        a.context_compressor = _Boom()
        out = a._reasoning_payload(_msgs(6))
        assert len(out) == 6


class TestAnthropicIsExempt:
    """Anthropic thinking blocks are signed; replacing one mid-turn
    invalidates the exchange rather than merely shortening it."""

    def test_claude_keeps_every_block_verbatim(self):
        a = _agent(model="claude-opus-5")
        msgs = _msgs(10)
        out = a._reasoning_payload(msgs)
        assert len(out) == 10
        assert all(not _is_handle(v) for v in out.values())
        assert a.context_compressor.spilled == []

    def test_anthropic_in_the_name_also_exempt(self):
        a = _agent(model="us.anthropic.something")
        assert len(a._reasoning_payload(_msgs(10))) == 10


class TestTheTranscriptIsNotTouched:
    def test_reasoning_itself_is_never_removed(self):
        a = _agent()
        msgs = _msgs(10)
        originals = [m.get("reasoning") for m in msgs]
        a._reasoning_payload(msgs)
        assert [m.get("reasoning") for m in msgs] == originals, (
            "the session log, /resume and mazemaker all read this list; "
            "expiry belongs to the request, not the transcript"
        )


class TestWiredIntoThePayload:
    """Structural: the payload build must consult the TTL map before
    attaching reasoning_content, or none of this reaches a real request."""

    def _source(self):
        import inspect
        return open(inspect.getsourcefile(run_agent), encoding="utf-8").read().splitlines()

    def test_attach_site_is_gated_by_the_map(self):
        lines = self._source()
        sites = [i for i, l in enumerate(lines)
                 if 'api_msg["reasoning_content"] = reasoning_text' in l]
        assert sites, "reasoning_content attach site not found"
        for site in sites:
            window = "\n".join(lines[max(0, site - 12): site + 1])
            assert "_reasoning_keep" in window, (
                f"line {site+1} attaches reasoning without consulting the TTL map"
            )

    def test_the_transient_key_never_reaches_the_api(self):
        lines = self._source()
        assert any('api_msg.pop("_reasoning_spill", None)' in l for l in lines), (
            "the cached handle is a transient bookkeeping key; sending it "
            "would put an unknown field on every assistant message"
        )

    def test_the_map_is_computed_outside_the_message_loop(self):
        lines = self._source()
        calls = [i for i, l in enumerate(lines)
                 if "_reasoning_payload(" in l and "def " not in l]
        assert calls, "no call site"
        for c in calls:
            indent = len(lines[c]) - len(lines[c].lstrip())
            nxt = [l for l in lines[c + 1:c + 6] if "for idx, msg in enumerate" in l]
            if nxt:
                assert indent <= len(nxt[0]) - len(nxt[0].lstrip()), (
                    "recomputed per message; it walks the whole list and "
                    "belongs above the loop"
                )
