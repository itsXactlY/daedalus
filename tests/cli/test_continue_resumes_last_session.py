""""continue" as the first message of a fresh session resumes the last real session.

2026-10-14: each new process opened an empty session, so "continue" made the
model guess the task from recall and an old closed plan; three "continue"
sessions in a row drifted further from the request given in the first.
"""

from cli import DaedalusCLI


class _DB:
    def __init__(self, sessions):
        self.sessions = sessions  # newest first: (id, [user messages])

    def list_sessions_rich(self, **kw):
        assert kw.get("order_by_last_active") and kw.get("min_message_count") == 1
        return [{"id": sid} for sid, _ in self.sessions]

    def get_messages_as_conversation(self, sid):
        users = dict(self.sessions)[sid]
        return [{"role": "user", "content": u} for u in users]


def _cli(sessions, current="20261014_170255_616bfc"):
    c = DaedalusCLI.__new__(DaedalusCLI)
    c.conversation_history = []
    c._resumed = False
    c.session_id = current
    c._session_db = _DB(sessions)
    c.resumed = []
    c._handle_resume_command = lambda cmd: c.resumed.append(cmd.split()[1])
    return c


SESSIONS = [
    ("20261014_170255_616bfc", ["continue"]),
    ("20261014_164351_451552", ["continue", "stop larping!"]),
    ("20261014_155834_ff904c", ["gather the optuna work from all branches"]),
]


def test_continue_resumes_the_last_session_with_real_work():
    c = _cli(SESSIONS)
    c._auto_resume_for_continue("weiter")
    assert c.resumed == ["20261014_155834_ff904c"]


def test_anything_else_starts_fresh():
    c = _cli(SESSIONS)
    c._auto_resume_for_continue("continue with the optuna db test")
    assert c.resumed == []


def test_only_on_an_empty_session():
    c = _cli(SESSIONS)
    c.conversation_history = [{"role": "user", "content": "hi"}]
    c._auto_resume_for_continue("continue")
    assert c.resumed == []
