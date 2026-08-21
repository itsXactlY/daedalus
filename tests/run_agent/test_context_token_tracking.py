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


# -- Anthropic: cached tokens must be included --

def test_anthropic_cache_read_and_creation_added(monkeypatch):
    agent = _make_agent(monkeypatch, "anthropic_messages", "anthropic",
                        lambda: _anthropic_resp(3, 10, cache_read=15000, cache_creation=2000))
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 17003  # 3+15000+2000
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
    assert agent.context_compressor.last_prompt_tokens == 17686  # 5+17666+15


# -- OpenAI: prompt_tokens already total --

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


# -- Codex: no cache fields, getattr returns 0 --

def test_codex_no_cache_fields(monkeypatch):
    resp = lambda: SimpleNamespace(
        output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text="ok")])],
        usage=SimpleNamespace(input_tokens=3000, output_tokens=50, total_tokens=3050),
        status="completed", model="gpt-5-codex",
    )
    agent = _make_agent(monkeypatch, "codex_responses", "openai-codex", resp)
    agent.run_conversation("hi")
    assert agent.context_compressor.last_prompt_tokens == 3000


# -- Session-cumulative counters must not silently under-add when a response's
# usage object is present but omits prompt_tokens (regression: previously
# added 0 for that call, permanently losing that call's contribution from
# session_prompt_tokens/session_total_tokens with no way to recover it later,
# unlike the display-only last_prompt_tokens which self-corrects on the next
# fully-populated response). --

def test_openai_missing_prompt_tokens_estimates_instead_of_zeroing_session_total(monkeypatch):
    calls = {"n": 0}

    def resp():
        calls["n"] += 1
        if calls["n"] == 1:
            usage = SimpleNamespace(prompt_tokens=4000, completion_tokens=100, total_tokens=4100)
        else:
            # Second call: usage object present, prompt_tokens field absent
            # entirely (the observed DeepSeek behavior) — completion_tokens
            # still reported.
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

    # The display value must not have been wiped to 0 (context_compressor's
    # own guard, tested separately in tests/agent/test_context_compressor.py).
    assert agent.context_compressor.last_prompt_tokens == 4000

    # The session-cumulative total must have grown by an ESTIMATE (the last
    # known-good prompt size) rather than staying flat at 4000 (which would
    # mean this call's prompt contribution was silently dropped) or crashing.
    assert agent.session_prompt_tokens == 4000 + 4000  # estimate == last known-good
    assert agent.session_completion_tokens == 100 + 50  # completion side unaffected
    assert agent.session_total_tokens == 4100 + (4000 + 50)

    # Sibling regression: session_input_tokens (and the same value fed into
    # cost estimation / DB persistence via `billed_usage`) must also grow by
    # the estimate, not the raw canonical_usage.input_tokens (which is
    # provably 0 here too -- normalize_usage() derives it from the same
    # missing prompt_tokens field). Before the fix this stayed flat at 4000.
    assert agent.session_input_tokens == 4000 + 4000
    # completion-side sibling counter is unaffected by this bug class --
    # OpenAI-mode output_tokens comes from a separate, present field.
    assert agent.session_output_tokens == 100 + 50


# -- Activity touch between tool completion and the next API call. Without
# it, gateway/run.py's DAEDALUS_AGENT_TIMEOUT inactivity monitor has no signal
# during context compression + the follow-up API call setup, and can kill a
# long-running turn mid-flight as falsely "idle" (see run_agent.py's
# _touch_activity call sites). --

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
