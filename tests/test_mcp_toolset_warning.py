class TestConfiguredMcpToolsetsAreNotTypos:
    """Toolsets are validated before MCP servers connect.

    Every configured MCP toolset therefore looked unknown at startup. Warning
    about those trains the eye to ignore the line, which is when a real typo
    slips through unnoticed.
    """

    def _patch(self, monkeypatch, cfg):
        import daedalus_cli.config as C

        monkeypatch.setattr(C, "load_config", lambda *a, **k: cfg)

    def test_a_configured_mcp_server_is_expected(self, monkeypatch):
        from model_tools import _is_pending_mcp_toolset

        self._patch(monkeypatch, {"mcp_servers": {"mazemaker": {}, "pulse": {}}})
        assert _is_pending_mcp_toolset("mazemaker") is True
        assert _is_pending_mcp_toolset("pulse") is True

    def test_a_real_typo_still_warns(self, monkeypatch):
        from model_tools import _is_pending_mcp_toolset

        self._patch(monkeypatch, {"mcp_servers": {"mazemaker": {}}})
        assert _is_pending_mcp_toolset("mazemakr") is False

    def test_the_nested_layout_is_understood_too(self, monkeypatch):
        from model_tools import _is_pending_mcp_toolset

        self._patch(monkeypatch, {"mcp": {"servers": {"pulse": {}}}})
        assert _is_pending_mcp_toolset("pulse") is True

    def test_no_config_means_no_silence(self, monkeypatch):
        from model_tools import _is_pending_mcp_toolset

        self._patch(monkeypatch, {})
        assert _is_pending_mcp_toolset("anything") is False

    def test_a_broken_config_never_raises(self, monkeypatch):
        import daedalus_cli.config as C

        from model_tools import _is_pending_mcp_toolset

        def boom(*a, **k):
            raise RuntimeError("no config")

        monkeypatch.setattr(C, "load_config", boom)
        assert _is_pending_mcp_toolset("mazemaker") is False
