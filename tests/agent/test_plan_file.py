"""The plan file is pinned onto each turn while active, and only then."""

from agent.plan_file import PLAN_MAX_CHARS, plan_focus, plan_path, render_plan_block
from agent.turn_context import anchored_recall_query


def _write(tmp_path, text):
    p = tmp_path / ".daedalus" / "PLAN.md"
    p.parent.mkdir()
    p.write_text(text)
    return p


def test_no_plan_no_block(tmp_path):
    assert render_plan_block(str(tmp_path)) == ""


def test_active_plan_is_pinned(tmp_path):
    p = _write(tmp_path, "# fix recall\nStatus: active\n- [ ] 1. probe")
    block = render_plan_block(str(tmp_path))
    assert block.startswith(f'<active-plan path="{p}"')
    assert "- [ ] 1. probe" in block
    assert "first unchecked step" in block


def test_closed_plan_is_only_pointed_at(tmp_path):
    _write(tmp_path, "# fix recall\nStatus: done\n- [x] 1. probe")
    block = render_plan_block(str(tmp_path))
    assert "<active-plan" not in block
    assert "closed" in block


def test_oversized_plan_is_truncated(tmp_path):
    _write(tmp_path, "# big\nStatus: active\n" + "x" * (PLAN_MAX_CHARS * 2))
    block = render_plan_block(str(tmp_path))
    assert "plan truncated" in block
    assert len(block) < PLAN_MAX_CHARS + 600


def test_plan_focus_is_title_and_current_step(tmp_path):
    _write(tmp_path, "# fix recall\nStatus: active\n- [x] 1. probe\n- [ ] 2. patch plugin\n")
    assert plan_focus(str(tmp_path)) == "fix recall — 2. patch plugin"


def test_short_message_is_anchored(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    msgs = [{"role": "user", "content": "rewrite the recall pipeline of the mazemaker plugin"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "weiter"}]
    assert anchored_recall_query("weiter", msgs, 2) == (
        "rewrite the recall pipeline of the mazemaker plugin\nweiter")
    _write(tmp_path, "# fix recall\nStatus: active\n- [ ] 1. probe\n")
    assert anchored_recall_query("weiter", msgs, 2) == "fix recall — 1. probe\nweiter"
    long_q = "what did we decide about the plan file format yesterday"
    assert anchored_recall_query(long_q, msgs, 2) == long_q


def test_workdir_from_terminal_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    assert plan_path() == tmp_path / ".daedalus" / "PLAN.md"
