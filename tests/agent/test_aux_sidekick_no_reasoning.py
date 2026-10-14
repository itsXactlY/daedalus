"""Housekeeping calls on the main model's endpoint run with thinking OFF.

Left unset, llama-server's template defaults to xhigh: a 30-token title spent all 30 inside <think>.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent import auxiliary_client as aux

BASE = "http://127.0.0.1:8080/v1"


def _call(single_sequence):
    client = MagicMock()
    client.base_url = BASE
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Title"))])
    with patch.object(aux, "_resolve_task_provider_model", return_value=("custom", "m", BASE, "k")), \
         patch.object(aux, "_get_cached_client", return_value=(client, "m")), \
         patch.object(aux, "_resolve_custom_runtime", return_value=(BASE, "k")), \
         patch.object(aux, "is_single_sequence", return_value=single_sequence), \
         patch.object(aux, "_build_call_kwargs", side_effect=lambda *a, **kw: {"extra_body": kw["extra_body"]}):
        aux.call_llm(task="title_generation", messages=[{"role": "user", "content": "x"}], max_tokens=30)
    return client.chat.completions.create.call_args.kwargs["extra_body"]


def test_llama_server_sidekick_call_sends_reasoning_none():
    body = _call(single_sequence=False)
    assert body["reasoning_effort"] == "none"
    assert body["id_slot"] == aux.get_sidekick_id_slot()


def test_one_conversation_engine_gets_none_too():
    body = _call(single_sequence=True)
    assert body["reasoning_effort"] == "none"
    assert "id_slot" not in body
