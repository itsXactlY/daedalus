"""Tests for named custom provider and 'main' alias resolution in auxiliary_client."""

import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Redirect DAEDALUS_HOME and clear module caches."""
    daedalus_home = tmp_path / ".daedalus"
    daedalus_home.mkdir()
    monkeypatch.setenv("DAEDALUS_HOME", str(daedalus_home))
    (daedalus_home / "config.yaml").write_text("model:\n  default: test-model\n")


def _write_config(tmp_path, config_dict):
    """Write a config.yaml to the test DAEDALUS_HOME."""
    import yaml
    config_path = tmp_path / ".daedalus" / "config.yaml"
    config_path.write_text(yaml.dump(config_dict))


class TestNormalizeVisionProvider:
    """_normalize_vision_provider should resolve 'main' to actual main provider."""

    def test_main_resolves_to_named_custom(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [{"name": "beans", "base_url": "http://localhost/v1"}],
        })
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "custom:beans"

    def test_main_resolves_to_openrouter(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "anthropic/claude-sonnet-4", "provider": "openrouter"},
        })
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "openrouter"

    def test_main_resolves_to_deepseek(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "deepseek-chat", "provider": "deepseek"},
        })
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "deepseek"

    def test_main_falls_back_to_custom_when_no_provider(self, tmp_path):
        _write_config(tmp_path, {"model": {"default": "gpt-4o"}})
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("main") == "custom"

    def test_bare_provider_name_unchanged(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("beans") == "beans"
        assert _normalize_vision_provider("deepseek") == "deepseek"

    def test_codex_alias_still_works(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("codex") == "openai-codex"

    def test_auto_unchanged(self):
        from agent.auxiliary_client import _normalize_vision_provider
        assert _normalize_vision_provider("auto") == "auto"
        assert _normalize_vision_provider(None) == "auto"


class TestResolveProviderClientMainAlias:
    """resolve_provider_client('main', ...) should resolve to actual main provider."""

    def test_main_resolves_to_named_custom_provider(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "beans"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("main", "override-model")
        assert client is not None
        assert model == "override-model"
        assert "beans.local" in str(client.base_url)

    def test_main_with_custom_colon_prefix(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "my-model", "provider": "custom:beans"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("main", "test")
        assert client is not None
        assert "beans.local" in str(client.base_url)


class TestResolveProviderClientNamedCustom:
    """resolve_provider_client should resolve named custom providers directly."""

    def test_named_custom_provider(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test-model"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("beans", "my-model")
        assert client is not None
        assert model == "my-model"
        assert "beans.local" in str(client.base_url)

    def test_named_custom_provider_default_model(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "main-model"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1", "api_key": "k"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("beans")
        assert client is not None
        assert model == "main-model"

    def test_named_custom_no_api_key_uses_fallback(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test"},
            "custom_providers": [
                {"name": "local", "base_url": "http://localhost:8080/v1"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("local", "test")
        assert client is not None

    def test_nonexistent_named_custom_falls_through(self, tmp_path):
        _write_config(tmp_path, {
            "model": {"default": "test"},
            "custom_providers": [
                {"name": "beans", "base_url": "http://beans.local/v1"},
            ],
        })
        from agent.auxiliary_client import resolve_provider_client
        client, model = resolve_provider_client("coffee", "test")
        assert client is None


class TestMainModelResolution:
    def test_the_active_provider_default_model_is_used_when_model_default_is_unset(
        self, monkeypatch
    ):
        from agent import auxiliary_client as AC

        monkeypatch.setattr(
            "daedalus_cli.config.load_config",
            lambda: {
                "model": {"provider": "custom", "base_url": "http://x/v1"},
                "providers": {"custom": {"default_model": "Qwen3.8-27B-IQ4-XS"}},
            },
        )
        assert AC._read_main_model() == "Qwen3.8-27B-IQ4-XS"

    def test_model_default_still_wins_when_it_is_set(self, monkeypatch):
        from agent import auxiliary_client as AC

        monkeypatch.setattr(
            "daedalus_cli.config.load_config",
            lambda: {
                "model": {"default": "explicit/model", "provider": "custom"},
                "providers": {"custom": {"default_model": "other"}},
            },
        )
        assert AC._read_main_model() == "explicit/model"

    def test_a_plain_model_key_on_the_provider_is_accepted_too(self, monkeypatch):
        from agent import auxiliary_client as AC

        monkeypatch.setattr(
            "daedalus_cli.config.load_config",
            lambda: {
                "model": {"provider": "p"},
                "providers": {"p": {"model": "from-model-key"}},
            },
        )
        assert AC._read_main_model() == "from-model-key"

    def test_nothing_resolvable_returns_empty_rather_than_a_guess(self, monkeypatch):
        from agent import auxiliary_client as AC

        monkeypatch.setattr(
            "daedalus_cli.config.load_config",
            lambda: {"model": {"provider": "p"}, "providers": {}},
        )
        assert AC._read_main_model() == ""


class TestAuxiliaryRetryBudget:
    def test_both_entry_points_accept_max_retries(self):
        import inspect
        from agent.auxiliary_client import call_llm, async_call_llm

        for fn in (call_llm, async_call_llm):
            assert "max_retries" in inspect.signature(fn).parameters

    def test_the_memory_flush_asks_for_no_retries(self):
        import inspect
        import run_agent

        src = inspect.getsource(run_agent.AIAgent.flush_memories)
        assert "max_retries=0" in src, (
            "flush_memories is best effort; retrying against a busy single-slot "
            "endpoint multiplies the wait instead of helping"
        )
