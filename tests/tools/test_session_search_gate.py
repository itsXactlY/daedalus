import json


class TestSessionSearchYieldsToTheMemoryGraph:
    def _chk(self):
        from tools.session_search_tool import check_session_search_requirements

        return check_session_search_requirements()

    def _config(self, monkeypatch, cfg):
        import tools.session_search_tool as SST

        monkeypatch.setattr(SST, "_GRAPH_MEMORY_PROVIDERS", SST._GRAPH_MEMORY_PROVIDERS)
        import daedalus_cli.config as C

        monkeypatch.setattr(C, "load_config", lambda *a, **k: cfg)

    def test_off_when_a_graph_provider_is_active(self, monkeypatch, tmp_path):
        self._config(monkeypatch, {"memory": {"provider": "mazemaker"}})
        assert self._chk() is False

    def test_off_for_the_legacy_provider_name(self, monkeypatch):
        self._config(monkeypatch, {"memory": {"provider": "neural-memory"}})
        assert self._chk() is False

    def test_on_without_a_graph_provider(self, monkeypatch):
        self._config(monkeypatch, {"memory": {"provider": "sqlite"}})
        assert self._chk() is True

    def test_on_when_no_provider_is_configured(self, monkeypatch):
        self._config(monkeypatch, {})
        assert self._chk() is True

    def test_force_enable_overrides_the_graph(self, monkeypatch):
        self._config(monkeypatch, {
            "memory": {"provider": "mazemaker"},
            "tools": {"session_search": {"force_enable": True}},
        })
        assert self._chk() is True

    def test_a_broken_config_does_not_hide_the_tool(self, monkeypatch):
        import daedalus_cli.config as C

        def boom(*a, **k):
            raise RuntimeError("no config")

        monkeypatch.setattr(C, "load_config", boom)
        assert self._chk() is True

    def test_the_prompt_no_longer_points_at_a_missing_tool(self):
        from agent.prompt_builder import MEMORY_GUIDANCE

        assert "session_search" not in MEMORY_GUIDANCE
