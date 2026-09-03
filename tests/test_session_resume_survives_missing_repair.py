import builtins

import pytest


class TestResumeNeverLosesTheTranscript:
    """A missing optional helper must not read as 'session has no messages'.

    agent.agent_runtime_helpers does not exist in the tree, so every resume
    raised ModuleNotFoundError out of get_messages_as_conversation. The CLI
    treats an empty result as an empty session and starts fresh -- total
    amnesia on every resume (observed 2026-09-03).
    """

    def _db(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DAEDALUS_HOME", str(tmp_path))
        import importlib

        import daedalus_state

        importlib.reload(daedalus_state)
        return daedalus_state.SessionDB()

    def _seed(self, db, session_id="s1"):
        db.create_session(session_id, "cli")
        db.append_message(session_id, "user", "hello")
        db.append_message(session_id, "assistant", "hi")
        db.append_message(session_id, "user", "again")
        db.append_message(session_id, "assistant", "sure")
        return session_id

    def test_repair_missing_still_returns_every_message(self, tmp_path, monkeypatch):
        db = self._db(tmp_path, monkeypatch)
        sid = self._seed(db)

        real_import = builtins.__import__

        def no_helpers(name, *args, **kwargs):
            if name == "agent.agent_runtime_helpers":
                raise ImportError("gone")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_helpers)
        out = db.get_messages_as_conversation(sid, repair_alternation=True)
        assert len(out) == 4
        assert [m["role"] for m in out] == ["user", "assistant", "user", "assistant"]

    def test_repair_missing_matches_the_unrepaired_result(self, tmp_path, monkeypatch):
        db = self._db(tmp_path, monkeypatch)
        sid = self._seed(db)
        plain = db.get_messages_as_conversation(sid, repair_alternation=False)

        real_import = builtins.__import__

        def no_helpers(name, *args, **kwargs):
            if name == "agent.agent_runtime_helpers":
                raise ImportError("gone")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_helpers)
        assert db.get_messages_as_conversation(sid, repair_alternation=True) == plain

    def test_an_empty_session_is_still_empty(self, tmp_path, monkeypatch):
        db = self._db(tmp_path, monkeypatch)
        db.create_session("empty", "cli")
        assert db.get_messages_as_conversation("empty", repair_alternation=True) == []
