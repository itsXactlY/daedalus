"""reasoning_effort "none" in the config means OFF at the endpoint: it is sent, never left to a default.

It used to mean "send nothing", so the endpoint's own default decided; when Strata's shared default was removed
(35095d3) reasoning came back on although the user had set none.
"""

import pytest

import run_agent
from cli import _parse_reasoning_config

_RealAIAgent = run_agent.AIAgent


def _agent(cfg, base="http://127.0.0.1:8080/v1"):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.base_url = base
    a.reasoning_config = cfg
    return a


def _strata(monkeypatch, value=True):
    monkeypatch.setattr("agent.backend_kind.is_single_sequence", lambda base_url, timeout=1.5: value)


class TestExplicitOff:
    def test_none_in_the_config_is_sent_as_none_to_strata(self, monkeypatch):
        _strata(monkeypatch)
        assert _agent(_parse_reasoning_config("none"))._local_reasoning_effort() == "none"

    def test_disabled_is_not_overridden_by_the_auto_gauge(self, monkeypatch):
        # task_intensity leaves {"enabled": False} alone (agent.reasoning_auto on or off) and the helper sends none
        _strata(monkeypatch)
        from agent.task_intensity import adjust_agent_reasoning
        a = _agent({"enabled": False})
        a.reasoning_auto = True
        a.reasoning_floor = "low"
        adjust_agent_reasoning(a, [{"role": "user", "content": "refactor the whole gateway and fix every failing test"}])
        assert a.reasoning_config == {"enabled": False}
        assert a._local_reasoning_effort() == "none"

    def test_llama_server_gets_none_too(self, monkeypatch):
        # sending nothing left the fork's template at its xhigh default; the server maps "none" to
        # enable_thinking=false before the template runs
        _strata(monkeypatch, False)
        assert _agent({"enabled": False})._local_reasoning_effort() == "none"


class TestOtherLevelsUnchanged:
    @pytest.mark.parametrize("effort,sent", [("low", "low"), ("medium", "medium"), ("xhigh", "xhigh"),
                                             ("high", "xhigh"), ("max", "xhigh"), ("ultra", "xhigh")])
    def test_levels_are_rounded_to_the_templates_ceiling(self, monkeypatch, effort, sent):
        _strata(monkeypatch)
        assert _agent({"enabled": True, "effort": effort})._local_reasoning_effort() == sent

    def test_no_config_defaults_to_medium(self, monkeypatch):
        _strata(monkeypatch)
        assert _agent(None)._local_reasoning_effort() == "medium"
        assert _agent({"enabled": True})._local_reasoning_effort() == "medium"


def test_both_request_builders_take_the_value_from_the_helper():
    import inspect
    src = inspect.getsource(run_agent)
    assert src.count("self._local_reasoning_effort()") == 2
    assert 'reasoning_config.get("enabled") is not False:\n                    _local_effort' not in src
