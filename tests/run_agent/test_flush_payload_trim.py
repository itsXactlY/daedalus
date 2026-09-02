import json


def _size(messages):
    return sum(
        len(str(m.get("content") or ""))
        + sum(len(str((c.get("function") or {}).get("arguments") or ""))
              for c in (m.get("tool_calls") or ()))
        for m in messages
    )


class _Agent:
    def __init__(self, budget=16000):
        from run_agent import AIAgent

        self._memory_flush_max_chars = budget
        self._trim = AIAgent._trim_for_flush.__get__(self, _Agent)

    def trim(self, messages):
        return self._trim(messages)


def _long_conversation(turns=40, tool_chars=4000):
    messages = [{"role": "user", "content": "start"}]
    for i in range(turns):
        messages.append({"role": "assistant", "tool_calls": [
            {"id": f"t{i}", "function": {"name": "read_file",
                                         "arguments": json.dumps({"file_path": f"/src/f{i}.py"})}}]})
        messages.append({"role": "tool", "tool_call_id": f"t{i}", "content": "X" * tool_chars})
        messages.append({"role": "assistant", "content": f"step {i}"})
    messages.append({"role": "user", "content": "wrap up"})
    return messages


class TestFlushPayloadStaysInsideTheSlot:
    def test_a_long_conversation_is_brought_under_budget(self):
        messages = _long_conversation()
        assert _size(messages) > 100_000
        out = _Agent().trim(messages)
        assert _size(out) <= 16000

    def test_the_newest_message_survives(self):
        out = _Agent().trim(_long_conversation())
        assert out[-1]["content"] == "wrap up"

    def test_a_short_payload_is_returned_unchanged(self):
        messages = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}]
        assert _Agent().trim(messages) == messages

    def test_it_never_starts_on_an_orphaned_tool_result(self):
        out = _Agent().trim(_long_conversation())
        assert out[0]["role"] != "tool"

    def test_bulky_tool_output_is_elided_before_messages_are_dropped(self):
        messages = _long_conversation(turns=4, tool_chars=9000)
        out = _Agent().trim(messages)
        assert len(out) == len(messages)
        assert any("omitted for the memory flush" in str(m.get("content") or "") for m in out)

    def test_a_zero_budget_disables_trimming(self):
        messages = _long_conversation()
        assert _Agent(budget=0).trim(messages) is messages

    def test_an_empty_payload_is_safe(self):
        assert _Agent().trim([]) == []

    def test_something_is_always_returned(self):
        messages = [{"role": "user", "content": "x" * 500_000},
                    {"role": "assistant", "content": "y" * 500_000}]
        assert _Agent().trim(messages)
