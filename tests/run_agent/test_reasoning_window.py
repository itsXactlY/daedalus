"""Reasoning rides along in the request until it ages out.

Assistant reasoning is re-sent as reasoning_content on every assistant
message in the payload, and nothing ever pruned it -- unlike tool results,
which spill to tmpfs once they age. Measured across four long sessions it was
22-30% of the entire payload (150k-240k tokens), the largest single thing
being re-read on every call, and the most disposable: it is the thinking that
produced a tool call, and the call's result is already in hand.

The transcript keeps all of it. Only the request thins.
"""

import run_agent

_RealAIAgent = run_agent.AIAgent


def _agent(model="qwen3.8-27b", **over):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.model = model
    for k, v in over.items():
        setattr(a, k, v)
    return a


def _msgs(n_assistant, with_reasoning=True):
    out = []
    for i in range(n_assistant):
        out.append({"role": "assistant", "content": f"a{i}",
                    "reasoning": f"thought-{i}" if with_reasoning else ""})
        out.append({"role": "tool", "content": f"result-{i}"})
    return out


class TestWindow:
    def test_keeps_only_the_newest_few(self):
        a = _agent()
        msgs = _msgs(10)
        keep = a._reasoning_window_indices(msgs)
        assert len(keep) == 3
        # assistant messages live at even indices; newest three are 14, 16, 18
        assert keep == {14, 16, 18}

    def test_everything_older_is_dropped(self):
        a = _agent()
        msgs = _msgs(10)
        keep = a._reasoning_window_indices(msgs)
        dropped = [i for i, m in enumerate(msgs)
                   if m.get("role") == "assistant" and i not in keep]
        assert len(dropped) == 7

    def test_a_short_conversation_keeps_everything(self):
        a = _agent()
        msgs = _msgs(2)
        assert a._reasoning_window_indices(msgs) == {0, 2}

    def test_messages_without_reasoning_do_not_consume_the_window(self):
        """A run of content-only assistant turns must not push the genuinely
        recent thinking out of the window."""
        a = _agent()
        msgs = _msgs(3) + [{"role": "assistant", "content": "no thinking"}] * 4
        keep = a._reasoning_window_indices(msgs)
        assert keep == {0, 2, 4}

    def test_window_is_configurable(self):
        a = _agent(_reasoning_window=1)
        assert len(a._reasoning_window_indices(_msgs(10))) == 1

    def test_zero_drops_all_reasoning(self):
        a = _agent(_reasoning_window=0)
        assert a._reasoning_window_indices(_msgs(10)) == set()

    def test_empty_history(self):
        assert _agent()._reasoning_window_indices([]) == set()


class TestAnthropicIsExempt:
    """Anthropic thinking blocks are signed; dropping one mid-turn
    invalidates the exchange rather than merely shortening it."""

    def test_claude_keeps_every_assistant_message(self):
        a = _agent(model="claude-opus-5")
        msgs = _msgs(10)
        keep = a._reasoning_window_indices(msgs)
        assert keep == {i for i, m in enumerate(msgs) if m["role"] == "assistant"}

    def test_anthropic_in_the_name_also_exempt(self):
        a = _agent(model="us.anthropic.something")
        assert len(a._reasoning_window_indices(_msgs(10))) == 10


class TestTheTranscriptIsNotTouched:
    def test_window_selection_does_not_mutate_messages(self):
        a = _agent()
        msgs = _msgs(6)
        before = [dict(m) for m in msgs]
        a._reasoning_window_indices(msgs)
        assert msgs == before, (
            "the session log, /resume and mazemaker all read this list; "
            "thinning belongs to the request, not the transcript"
        )


class TestWiredIntoThePayload:
    """Structural: the payload build must consult the window before attaching
    reasoning_content, or the saving never reaches an actual request."""

    def _source(self):
        import inspect
        return open(inspect.getsourcefile(run_agent), encoding="utf-8").read().splitlines()

    def test_attach_site_is_gated_by_the_window(self):
        lines = self._source()
        sites = [i for i, l in enumerate(lines) if 'api_msg["reasoning_content"] = reasoning_text' in l]
        assert sites, "reasoning_content attach site not found"
        for site in sites:
            window = "\n".join(lines[max(0, site - 12): site + 1])
            assert "_reasoning_keep" in window, (
                f"line {site+1} attaches reasoning without consulting the window"
            )

    def test_the_window_is_computed_outside_the_message_loop(self):
        lines = self._source()
        calls = [i for i, l in enumerate(lines)
                 if "_reasoning_window_indices(" in l and "def " not in l]
        assert calls, "no call site"
        for c in calls:
            indent = len(lines[c]) - len(lines[c].lstrip())
            nxt = [l for l in lines[c + 1:c + 6] if "for idx, msg in enumerate" in l]
            if nxt:
                assert indent <= len(nxt[0]) - len(nxt[0].lstrip()), (
                    "recomputed per message; it is O(n) and belongs above the loop"
                )
