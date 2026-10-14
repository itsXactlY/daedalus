"""Housekeeping calls on the main model's endpoint run with thinking OFF and free their slot after.

Left unset, llama-server's template defaults to xhigh: a 30-token title spent all 30 inside <think>.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent import auxiliary_client as aux
from agent.sidekick_queue import SidekickGate

BASE = "http://127.0.0.1:8080/v1"


def _call(single_sequence, erased=None, task="title_generation", gate=None):
    gate = gate or SidekickGate()
    client = MagicMock()
    client.base_url = BASE
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Title"))])
    with patch.object(aux, "_resolve_task_provider_model", return_value=("custom", "m", BASE, "k")), \
         patch.object(aux, "_get_cached_client", return_value=(client, "m")), \
         patch.object(aux, "_resolve_custom_runtime", return_value=(BASE, "k")), \
         patch.object(aux, "sidekick_gate", gate), \
         patch.object(aux, "is_single_sequence", return_value=single_sequence), \
         patch.object(aux, "_build_call_kwargs", side_effect=lambda *a, **kw: {"extra_body": kw["extra_body"]}), \
         patch("agent.kv_watermarks.erase_slot", side_effect=lambda base, slot, timeout=5.0: (erased if erased is not None else []).append(slot)):
        aux.call_llm(task=task, messages=[{"role": "user", "content": "x"}], max_tokens=30)
    return client.chat.completions.create.call_args.kwargs["extra_body"]


def test_llama_server_sidekick_call_sends_reasoning_none():
    body = _call(single_sequence=False)
    assert body["reasoning_effort"] == "none"
    assert body["id_slot"] == aux.get_sidekick_id_slot()


def test_one_conversation_engine_gets_none_too():
    body = _call(single_sequence=True)
    assert body["reasoning_effort"] == "none"
    assert "id_slot" not in body


def test_one_shot_sidekick_call_frees_its_slot():
    erased = []
    _call(single_sequence=False, erased=erased)
    assert erased == [aux.get_sidekick_id_slot()]


def test_a_prewarmed_sidekick_is_not_freed():
    # only hygiene gets the slot while it carries a prewarmed epoch, and it must not drop it
    gate = SidekickGate()
    gate.reserve(30)
    erased = []
    _call(single_sequence=False, erased=erased, task="compression", gate=gate)
    assert erased == []


def test_one_conversation_engine_frees_nothing():
    erased = []
    _call(single_sequence=True, erased=erased)
    assert erased == []
