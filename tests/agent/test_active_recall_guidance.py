class TestRecallIsAReflexNotAnExcursion:
    def _guidance(self, window=3):
        from agent.prompt_builder import build_mazemaker_guidance

        return build_mazemaker_guidance(window)

    def test_it_names_the_tools_the_model_can_call(self):
        g = self._guidance()
        for tool in ("mazemaker_recall", "mazemaker_think", "mazemaker_get"):
            assert tool in g

    def test_it_demands_retrieval_before_rediscovery(self):
        g = self._guidance().lower()
        assert "recall" in g
        assert "re-reading files" in g or "rediscover" in g

    def test_it_lists_concrete_triggers(self):
        g = self._guidance().lower()
        for trigger in ("continue", "resume", "mid-task", "already built"):
            assert trigger in g

    def test_the_prompt_is_english_only(self):
        """Agent-facing instructions ship in one language: English.

        A trigger list that named a German word steered a multilingual model
        toward that language and made the rule look locale-specific.
        """
        import re

        german = re.compile(
            r"\b(weiter|gefaelligst|gef\u00e4lligst|Datei|Nachricht|m\u00fcssen|"
            r"sollte|damit|deshalb|au\u00dferdem|Verzeichnis)\b", re.I)
        assert not german.findall(self._guidance())

    def test_it_steers_at_think_instead_of_requerying(self):
        g = self._guidance()
        assert "mazemaker_think" in g
        assert "depth=" in g

    def test_it_says_where_bulky_tool_output_lives(self):
        g = self._guidance().lower()
        assert "tmpfs" in g
        assert "not in mazemaker" in g

    def test_it_stays_small_enough_to_ship_every_turn(self):
        assert len(self._guidance()) < 2600


class TestRecallToolsStayOutOfTheDeferralBridge:
    def _cfg(self, always_load=()):
        from tools.tool_search import load_config

        base = load_config()
        return base.__class__(
            **{**base.__dict__, "always_load": tuple(always_load)}
        )

    def test_configured_always_load_names_are_not_deferrable(self):
        from tools.tool_search import is_deferrable_tool_name

        cfg = self._cfg(("mazemaker_recall", "mazemaker_think"))
        assert is_deferrable_tool_name("mazemaker_recall", cfg) is False
        assert is_deferrable_tool_name("mazemaker_think", cfg) is False

    def test_an_unlisted_mcp_tool_is_still_deferrable(self):
        from tools.tool_search import is_deferrable_tool_name

        cfg = self._cfg(("mazemaker_recall",))
        assert is_deferrable_tool_name("mazemaker_recall", cfg) is False

    def test_the_bridge_itself_is_never_deferred(self):
        from tools.tool_search import is_deferrable_tool_name

        cfg = self._cfg(())
        for name in ("tool_search", "tool_describe", "tool_call"):
            assert is_deferrable_tool_name(name, cfg) is False
