"""_spawn_background_review must not contend with the live main turn.

Regression for 2026-09-11: every AIAgent instance hardcoded
extra_body["id_slot"] = 0 in its own completion-call path. The background
memory/skill review forks a full second AIAgent (up to 8 iterations) in a
daemon thread every _memory_nudge_interval turns -- the one piece of
substantial background LLM work in the codebase -- but it inherited that
same hardcoded 0, so it queued behind (or contended with) the live main
conversation on the same slot instead of running beside it.

2026-09-12: fixed once already (main=0, sidekick=1), then flipped again --
llama-server fills its shared per-iteration batch by walking slots in index
order and stops at the first one that would overflow n_batch, skipping every
later slot that round entirely. Main's prefill is usually the big one (tens
of thousands of tokens after a compaction); on slot 0 it could occupy the
whole batch budget for many consecutive iterations, starving the sidekick's
slot completely even though it was "pinned" to run beside main. Main now
defaults to slot 1; the sidekick claims slot 0 so its small prompts always
get scheduled promptly instead of queuing behind main's prefill.
"""

import threading

import run_agent

_RealAIAgent = run_agent.AIAgent  # captured before any test monkeypatches the symbol


def _bare_agent():
    """A real AIAgent instance without running __init__ (no client, no I/O)."""
    agent = _RealAIAgent.__new__(_RealAIAgent)
    agent.model = "test-model"
    agent.platform = "test"
    agent.provider = "custom"
    agent._memory_store = object()
    agent._memory_enabled = True
    agent._user_profile_enabled = True
    agent._pinned_id_slot = 1
    agent.background_review_callback = None
    agent._safe_print = lambda *a, **k: None
    return agent


class _StubReviewAgent:
    """Captures construction + attribute overrides; never actually runs."""

    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._pinned_id_slot = 1  # the class default every real instance starts with
        self._session_messages = []
        type(self).instances.append(self)

    def run_conversation(self, user_message=None, conversation_history=None):
        return {"final_response": ""}

    def _close_openai_client(self, *a, **k):
        pass


def test_review_agent_gets_pinned_to_the_sidekick_slot(monkeypatch):
    _StubReviewAgent.instances = []
    monkeypatch.setattr(run_agent, "AIAgent", _StubReviewAgent)

    agent = _bare_agent()
    agent._spawn_background_review([{"role": "user", "content": "hi"}], review_memory=True)
    agent._bg_review_thread.join(timeout=5)

    assert len(_StubReviewAgent.instances) == 1
    review_agent = _StubReviewAgent.instances[0]
    assert review_agent._pinned_id_slot == 0, (
        "background review must run on the sidekick's slot (0), not inherit "
        "main's slot (1) and queue behind its prefill"
    )


def test_main_agent_slot_pin_is_unaffected(monkeypatch):
    """Spawning a review must never mutate the caller's own slot pin."""
    _StubReviewAgent.instances = []
    monkeypatch.setattr(run_agent, "AIAgent", _StubReviewAgent)

    agent = _bare_agent()
    assert agent._pinned_id_slot == 1
    agent._spawn_background_review([{"role": "user", "content": "hi"}], review_memory=True)
    agent._bg_review_thread.join(timeout=5)

    assert agent._pinned_id_slot == 1


def test_default_pinned_id_slot_is_main_slot_for_a_fresh_instance():
    """Every AIAgent starts pinned to main's slot (1) unless overridden."""
    agent = _bare_agent()
    assert agent._pinned_id_slot == 1
