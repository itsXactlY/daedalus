"""fast_layer_tokens is this box's KV pool, so it only arms when the box serves.

Against a remote provider it would cap a real, mostly empty window and make the
harness count a different budget than the server. The compressor owns the
local/remote verdict; _setup_fast_layer_watermarks must follow it instead of
re-deciding from the URL alone.
"""

import run_agent
from agent.context_compressor import ContextCompressor
from agent.kv_watermarks import Watermarks

_RealAIAgent = run_agent.AIAgent

FAST_LAYER = 40_192
CTX = 262_144
COMP_CFG = {"fast_layer_tokens": FAST_LAYER, "watermarks": {}}


def _agent(compressor):
    a = _RealAIAgent.__new__(_RealAIAgent)
    a.base_url = compressor.base_url
    a.context_compressor = compressor
    a._watermarks = None
    a._hot_swap_prep_ratio = None
    return a


def _compressor(base_url, provider):
    return ContextCompressor(
        model="test/model",
        threshold_percent=0.95,
        base_url=base_url,
        provider=provider,
        config_context_length=CTX,
        quiet_mode=True,
    )


class TestWatermarksFollowTheEndpoint:
    def test_armed_for_the_local_doctor(self, monkeypatch):
        monkeypatch.setattr(
            "agent.context_compressor.get_model_context_length", lambda *a, **k: CTX,
        )
        a = _agent(_compressor("http://127.0.0.1:8080/v1", "local"))
        a._setup_fast_layer_watermarks(COMP_CFG)
        assert a._watermarks is not None
        assert a.context_compressor.max_tokens == a._watermarks.hard_tokens
        assert a.context_compressor.threshold_tokens == a._watermarks.hard_tokens

    def test_left_off_for_a_remote_provider(self, monkeypatch):
        monkeypatch.setattr(
            "agent.context_compressor.get_model_context_length", lambda *a, **k: CTX,
        )
        a = _agent(_compressor("https://api.openai.com/v1", "openai"))
        a._setup_fast_layer_watermarks(COMP_CFG)
        assert a._watermarks is None
        assert a.context_compressor.max_tokens is None
        assert a.context_compressor.threshold_tokens == int(CTX * 0.95)

    def test_local_provider_name_over_a_foreign_url_still_arms(self, monkeypatch):
        monkeypatch.setattr(
            "agent.context_compressor.get_model_context_length", lambda *a, **k: CTX,
        )
        a = _agent(_compressor("http://doctor.internal.lan:9090/v1", "llamacpp"))
        a._setup_fast_layer_watermarks(COMP_CFG)
        assert a._watermarks is not None

    def test_no_fast_layer_configured_is_a_no_op(self, monkeypatch):
        monkeypatch.setattr(
            "agent.context_compressor.get_model_context_length", lambda *a, **k: CTX,
        )
        a = _agent(_compressor("http://127.0.0.1:8080/v1", "local"))
        a._setup_fast_layer_watermarks({})
        assert a._watermarks is None
        assert a.context_compressor.max_tokens is None

    def test_the_two_agree_on_the_same_hard_line(self, monkeypatch):
        """A remote run must not be capped where the local one is."""
        monkeypatch.setattr(
            "agent.context_compressor.get_model_context_length", lambda *a, **k: CTX,
        )
        local = _agent(_compressor("http://127.0.0.1:8080/v1", "local"))
        local._setup_fast_layer_watermarks(COMP_CFG)
        remote = _agent(_compressor("https://api.openai.com/v1", "openai"))
        remote._setup_fast_layer_watermarks(COMP_CFG)
        assert isinstance(local._watermarks, Watermarks)
        assert remote._watermarks is None
        assert local.context_compressor.should_compress(
            local._watermarks.hard_tokens) is True
        assert remote.context_compressor.should_compress(
            local._watermarks.hard_tokens) is False


class TestFastLayerNeverExceedsTheSlotWindow:
    """2026-10-14: fast_layer_tokens 65536 over a 57344-token slot (--kv-unified-per-slot)
    put the rebase point past the slot's wall; one turn filled the slot and died."""

    def test_clamped_to_the_slot_window(self, monkeypatch):
        monkeypatch.setattr(
            "agent.context_compressor.get_model_context_length", lambda *a, **k: 57_344,
        )
        a = _agent(_compressor("http://127.0.0.1:8080/v1", "local"))
        a._setup_fast_layer_watermarks({"fast_layer_tokens": 65_536, "watermarks": {"hard": 0.95}})
        assert a._watermarks.fast_layer_tokens == 57_344
        assert a.context_compressor.max_tokens == int(57_344 * 0.95)
