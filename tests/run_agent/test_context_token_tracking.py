"""Tests for context token tracking in run_agent.py's usage extraction.

The context counter (status bar) must show the TOTAL prompt tokens including
Anthropic's cached portions. This is an integration test for the token
extraction in run_conversation(), not the ContextCompressor itself (which
is tested in tests/agent/test_context_compressor.py).
"""

import sys
import types
from types import SimpleNamespace

sys.modules.setdefault("fire", types.SimpleNamespace(Fire=lambda *a, **k: None))
sys.modules.setdefault("firecrawl", types.SimpleNamespace(Firecrawl=object))
sys.modules.setdefault("fal_client", types.SimpleNamespace())

import run_agent


def _patch_bootstrap(monkeypatch):
    monkeypatch.setattr(run_agent, "get_tool_definitions", lambda **kwargs: [{
        "type": "function",
        "function": {"name": "t", "description": "t", "parameters": {"type": "object", "properties": {}}},
    }])
    monkeypatch.setattr(run_agent, "check_toolset_requirements", lambda: {})


class _FakeAnthropicClient:
    def close(self):
        pass


class _FakeOpenAIClient:
    """Fake OpenAI client returned by mocked resolve_provider_client."""
    api_key = "fake-codex-key"
    base_url = "https://api.openai.com/v1"
    _default_headers = None


def _make_agent(monkeypatch, api_mode, provider, response_fn):
    _patch_bootstrap(monkeypatch)
    if api_mode == "anthropic_messages":
        monkeypatch.setattr("agent.anthropic_adapter.build_anthropic_client", lambda k, b=None: _FakeAnthropicClient())
    if provider == "openai-codex":
        monkeypatch.setattr(
            "agent.auxiliary_client.resolve_provider_client",
            lambda *a, **kw: (_FakeOpenAIClient(), "test-model"),
        )

    class _A(run_agent.AIAgent):
        def __init__(self, *a, **kw):
            kw.update(skip_context_files=True, skip_memory=True, max_iterations=4)
            super().__init__(*a, **kw)
            self._cleanup_task_resources = self._persist_session = lambda *a, **k: None
            self._save_trajectory = self._save_session_log = lambda *a, **k: None

        def run_conversation(self, msg, conversation_history=None, task_id=None):
            self._interruptible_api_call = lambda kw: response_fn()
            return super().run_conversation(msg, conversation_history=conversation_history, task_id=task_id)

    return _A(model="test-model", api_key="test-key", provider=provider, api_mode=api_mode)


def _anthropic_resp(input_tok, output_tok, cache_read=0, cache_creation=0):
    usage_fields = {"input_tokens": input_tok, "output_tokens": output_tok}
    if cache_read:
        usage_fields["cache_read_input_tokens"] = cache_read
    if cache_creation:
        usage_fields["cache_creation_input_tokens"] = cache_creation
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text="ok")],
        stop_reason="end_turn",
        usage=SimpleNamespace(**usage_fields),
        model="claude-sonnet-4-6",
    )



def test_anthropic_cache_read_and_creation_added(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(3, 10, cache_read=15000, cache_creation=2000))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 17003
    assert agent.session_prompt_tokens == 17003


def test_anthropic_no_cache_fields(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(500, 20))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 500


def test_anthropic_cache_read_only(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(5, 15, cache_read=17666, cache_creation=15))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 17686



def test_openai_prompt_tokens_unchanged(monkeypatch):
    resp = lambda: SimpleNamespace(
        choices=[SimpleNamespace(index=0, message=SimpleNamespace(
            role="assistant", content="ok", tool_calls=None, reasoning_content=None,
        ), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=5000, completion_tokens=100, total_tokens=5100),
        model="gpt-4o",
    )
    agent = _make_agent(monkeypatch, "chat_completions", "openrouter", resp)
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 5000



def test_codex_no_cache_fields(monkeypatch):
    resp = lambda: SimpleNamespace(
        output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text="ok")])],
        usage=SimpleNamespace(input_tokens=3000, output_tokens=50, total_tokens=3050),
        status="completed", model="gpt-5-codex",
    )
    agent = _make_agent(monkeypatch, "codex_responses", "openai-codex", resp)
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 3000



def test_openai_missing_prompt_tokens_estimates_instead_of_zeroing_session_total(monkeypatch):
    calls = {"n": 0}

    def resp():
        calls["n"] += 1
        if calls["n"] == 1:
            usage = SimpleNamespace(prompt_tokens=4000, completion_tokens=100, total_tokens=4100)
        else:
            usage = SimpleNamespace(completion_tokens=50)
        return SimpleNamespace(
            choices=[SimpleNamespace(index=0, message=SimpleNamespace(
                role="assistant", content="ok", tool_calls=None, reasoning_content=None,
            ), finish_reason="stop")],
            usage=usage,
            model="deepseek-chat",
        )

    agent = _make_agent(monkeypatch, "chat_completions", "openrouter", resp)
    agent.run_conversation("first")
    assert agent.session_prompt_tokens == 4000
    assert agent.context_compressor.last_prompt_tokens == 4000

    agent.run_conversation("second")

    assert agent.context_compressor.last_prompt_tokens == 4000

    assert agent.session_prompt_tokens == 4000 + 4000
    assert agent.session_completion_tokens == 100 + 50
    assert agent.session_total_tokens == 4100 + (4000 + 50)

    assert agent.session_input_tokens == 4000 + 4000
    assert agent.session_output_tokens == 100 + 50



def test_touch_activity_between_tool_results_and_next_api_call(monkeypatch):
    touches = []
    calls = {"n": 0}

    def resp():
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(
                choices=[SimpleNamespace(index=0, message=SimpleNamespace(
                    role="assistant", content=None,
                    tool_calls=[SimpleNamespace(id="call1", type="function",
                        function=SimpleNamespace(name="t", arguments="{}"))],
                    reasoning_content=None,
                ), finish_reason="tool_calls")],
                usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10, total_tokens=110),
                model="test-model",
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(index=0, message=SimpleNamespace(
                role="assistant", content="done", tool_calls=None, reasoning_content=None,
            ), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=5, total_tokens=125),
            model="test-model",
        )

    agent = _make_agent(monkeypatch, "chat_completions", "openrouter", resp)
    orig_touch = agent._touch_activity
    def spy(desc):
        touches.append(desc)
        return orig_touch(desc)
    agent._touch_activity = spy

    agent.run_conversation("hi")

    tool_done_idx = next(i for i, d in enumerate(touches) if d.startswith("tool completed"))
    next_call_idx = next(i for i, d in enumerate(touches) if d.startswith("starting API call #2"))
    between = touches[tool_done_idx + 1:next_call_idx]
    assert any(d.startswith("tool results posted") for d in between), (
        f"expected a 'tool results posted' activity touch between tool completion "
        f"and the next API call, got: {touches}"
    )


class _NoUsageResponse:
    class _Msg:
        content = "x" * 400
        tool_calls = None

    class _Choice:
        message = _NoUsageResponse._Msg() if False else None

    def __init__(self):
        msg = type("M", (), {"content": "x" * 400, "tool_calls": None})()
        self.choices = [type("C", (), {"message": msg})()]
        self.usage = None


def test_a_response_without_usage_still_advances_the_counters(monkeypatch):
    import run_agent as RA

    agent = RA.AIAgent.__new__(RA.AIAgent)
    agent.log_prefix = ""
    agent.quiet_mode = True
    agent._vprint = lambda *a, **k: None
    agent.session_prompt_tokens = 1000
    agent.session_completion_tokens = 200
    agent.session_total_tokens = 1200
    agent.session_input_tokens = 1000
    agent.session_output_tokens = 200
    agent.session_api_calls = 3
    agent.session_cost_status = "unknown"
    agent.session_cost_source = "none"

    est = agent._estimate_completion_tokens(_NoUsageResponse())
    assert est == 100

    before = agent.session_total_tokens
    agent.session_prompt_tokens += 500
    agent.session_total_tokens += 500 + est
    assert agent.session_total_tokens > before


def test_completion_estimate_counts_tool_call_payloads():
    import run_agent as RA

    agent = RA.AIAgent.__new__(RA.AIAgent)
    fn = type("F", (), {"name": "terminal", "arguments": '{"command": "ls -la"}'})()
    call = type("T", (), {"function": fn})()
    msg = type("M", (), {"content": "", "tool_calls": [call]})()
    resp = type("R", (), {"choices": [type("C", (), {"message": msg})()], "usage": None})()

    assert agent._estimate_completion_tokens(resp) > 1


def test_completion_estimate_never_returns_zero():
    import run_agent as RA

    agent = RA.AIAgent.__new__(RA.AIAgent)
    empty = type("R", (), {"choices": [], "usage": None})()
    assert agent._estimate_completion_tokens(empty) == 1
    assert agent._estimate_completion_tokens(object()) == 1


class TestCallLedger:
    def _agent(self):
        import run_agent as RA
        a = RA.AIAgent.__new__(RA.AIAgent)
        a.session_api_calls = 0
        a._user_turn_count = 0
        a.call_ledger = []
        a.model_ledger = {}
        return a

    def test_a_call_lands_in_both_ledgers(self):
        a = self._agent()
        a.session_api_calls = 1
        a._record_call_ledger(model="m/x", provider="p", input_tokens=100,
                              output_tokens=20, cache_read=80, cost_usd=0.5,
                              duration_s=1.5)
        assert len(a.call_ledger) == 1
        e = a.call_ledger[0]
        assert (e["input"], e["output"], e["cache_read"]) == (100, 20, 80)
        assert a.model_ledger["m/x"]["calls"] == 1
        assert a.model_ledger["m/x"]["input"] == 100

    def test_per_model_rows_accumulate_and_stay_separate(self):
        a = self._agent()
        for model, tok in (("m/a", 100), ("m/b", 50), ("m/a", 25)):
            a._record_call_ledger(model=model, provider="p", input_tokens=tok,
                                  output_tokens=1)
        assert a.model_ledger["m/a"]["input"] == 125
        assert a.model_ledger["m/a"]["calls"] == 2
        assert a.model_ledger["m/b"]["input"] == 50
        assert len(a.call_ledger) == 3

    def test_the_ledger_is_capped_and_keeps_the_newest(self):
        import run_agent as RA
        a = self._agent()
        for i in range(RA.AIAgent._LEDGER_MAX_CALLS + 25):
            a.session_api_calls = i
            a._record_call_ledger(model="m", provider="p", input_tokens=i,
                                  output_tokens=0)
        assert len(a.call_ledger) == RA.AIAgent._LEDGER_MAX_CALLS
        assert a.call_ledger[-1]["input"] == RA.AIAgent._LEDGER_MAX_CALLS + 24
        assert a.model_ledger["m"]["calls"] == RA.AIAgent._LEDGER_MAX_CALLS + 25

    def test_a_broken_entry_never_breaks_the_api_call(self):
        a = self._agent()
        a.call_ledger = None
        a.model_ledger = None
        a._record_call_ledger(model=None, provider=None, input_tokens="x",
                              output_tokens=None)


class TestContextComposition:
    def _agent(self, prompt, tools, window=128000, used=0):
        import run_agent as RA
        a = RA.AIAgent.__new__(RA.AIAgent)
        a._cached_system_prompt = prompt
        a.tools = tools
        a.context_compressor = type("C", (), {
            "context_length": window, "last_prompt_tokens": used})()
        return a

    def test_the_three_parts_sum_to_the_reported_total(self):
        a = self._agent("You are daedalus." + "x" * 400,
                        [{"type": "function", "function": {"name": "t",
                          "description": "d" * 200, "parameters": {}}}])
        msgs = [{"role": "user", "content": "q" * 800}]
        c = a.context_composition(msgs)
        assert c["total"] == c["system_prompt"] + c["tools"] + c["history"]
        assert c["tool_count"] == 1
        assert c["message_count"] == 1

    def test_prompt_parts_sum_to_the_whole_prompt(self):
        import run_agent as RA
        from agent.model_metadata import estimate_tokens_rough

        prompt = ("You are daedalus, the Architects Anomaly.\n"
                  "## Skills (mandatory)\n" + "s" * 600 + "\n"
                  "You have persistent memory across sessions.\n" + "m" * 300)
        parts = RA.AIAgent._system_prompt_parts(prompt)
        assert sum(parts.values()) == estimate_tokens_rough(prompt)
        assert "skills" in parts and "memory" in parts

    def test_an_empty_agent_reports_zeroes_rather_than_raising(self):
        a = self._agent("", [])
        c = a.context_composition([])
        assert c["total"] == 0
        assert c["parts"] == {}
