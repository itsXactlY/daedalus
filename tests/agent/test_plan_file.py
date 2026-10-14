"""The plan file is pinned onto each turn while active, and only then.

Two agents in one folder is the case that produced the clobber: the plan is
per TASK, and ownership is per SESSION with the writer's pid deciding whether
a claim is still alive.
"""

import json
import os

from agent.plan_file import (
    PLAN_MAX_CHARS,
    PlanInfo,
    bind_plan,
    hand_over_plans,
    list_plans,
    new_plan_path,
    plan_focus,
    plan_path,
    plan_write_conflict,
    render_plan_block,
    resolve_plan,
    slugify_plan_name,
)


def _write(tmp_path, text, name="PLAN.md"):
    p = tmp_path / ".daedalus" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def test_no_plan_no_block(tmp_path):
    assert render_plan_block(str(tmp_path)) == ""


def test_active_plan_is_pinned(tmp_path):
    p = _write(tmp_path, "# fix recall\nStatus: active\n- [ ] 1. probe")
    block = render_plan_block(str(tmp_path), session_id="s1")
    assert block.startswith(f'<active-plan path="{p}"')
    assert "- [ ] 1. probe" in block
    assert "first unchecked step" in block


def test_closed_plan_is_only_pointed_at(tmp_path):
    _write(tmp_path, "# fix recall\nStatus: done\n- [x] 1. probe")
    block = render_plan_block(str(tmp_path), session_id="s1")
    assert "<active-plan" not in block
    assert "No active plan" in block and "not the current task" in block


def test_oversized_plan_is_truncated(tmp_path):
    _write(tmp_path, "# big\nStatus: active\n" + "x" * (PLAN_MAX_CHARS * 2))
    block = render_plan_block(str(tmp_path), session_id="s1")
    assert "plan truncated" in block
    assert len(block) < PLAN_MAX_CHARS + 600


def test_plan_focus_is_title_and_current_step(tmp_path):
    _write(tmp_path, "# fix recall\nStatus: active\n- [x] 1. probe\n- [ ] 2. patch plugin\n")
    assert plan_focus(str(tmp_path), session_id="s1") == "fix recall — 2. patch plugin"


def test_short_message_is_anchored(tmp_path, monkeypatch):
    from agent.turn_context import anchored_recall_query

    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    msgs = [{"role": "user", "content": "rewrite the recall pipeline of the mazemaker plugin"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "weiter"}]
    assert anchored_recall_query("weiter", msgs, 2) == (
        "rewrite the recall pipeline of the mazemaker plugin\nweiter")
    _write(tmp_path, "# fix recall\nStatus: active\n- [ ] 1. probe\n")
    assert anchored_recall_query("weiter", msgs, 2, session_id="s1") == (
        "fix recall — 1. probe\nweiter")
    long_q = "what did we decide about the plan file format yesterday"
    assert anchored_recall_query(long_q, msgs, 2, session_id="s1") == long_q


def test_workdir_from_terminal_cwd(tmp_path, monkeypatch):
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    assert plan_path() == tmp_path / ".daedalus" / "PLAN.md"


# --- one plan per task -------------------------------------------------


def test_new_plan_path_is_named_after_the_task_and_never_clobbers(tmp_path):
    first = new_plan_path("Fix boot MCP timeout", str(tmp_path))
    assert first.name == "PLAN-fix-boot-mcp-timeout.md"
    assert not first.exists()
    first.parent.mkdir(parents=True)
    first.write_text("# a\nStatus: active\n")
    second = new_plan_path("Fix boot MCP timeout", str(tmp_path))
    assert second.name == "PLAN-fix-boot-mcp-timeout-2.md"


def test_slug_is_filesystem_safe():
    assert slugify_plan_name("PLAN.md überschrieben?!") == "plan-md-berschrieben"
    assert slugify_plan_name("") == "task"


def test_task_plans_are_discovered(tmp_path):
    _write(tmp_path, "# one\nStatus: active\n- [ ] 1. a\n", name="PLAN-one.md")
    _write(tmp_path, "# two\nStatus: active\n- [ ] 1. b\n", name="PLAN-two.md")
    _write(tmp_path, "# not a plan\n", name="NOTES.md")
    names = {i.path.name for i in list_plans(str(tmp_path))}
    assert names == {"PLAN-one.md", "PLAN-two.md"}


# --- the clobber itself ------------------------------------------------


def _claim_as_live_agent(plan, session_id, pid=None):
    """Write the ownership record a live agent would have written."""
    of = plan.parent / ".owners" / f"{plan.name}.json"
    of.parent.mkdir(parents=True, exist_ok=True)
    of.write_text(json.dumps({
        "session_id": session_id,
        "pid": pid if pid is not None else os.getpid(),
        "host": os.uname().nodename,
        "claimed": "2026-09-28T16:00:00",
    }))


def test_agent_b_cannot_overwrite_agent_as_live_plan(tmp_path):
    a = _write(tmp_path, "# agent A task\nStatus: active\n- [ ] 1. a step\n", name="PLAN-a.md")
    _claim_as_live_agent(a, "session-A", pid=os.getpid())

    conflict = plan_write_conflict(str(a), session_id="session-B", workdir=str(tmp_path))
    assert conflict is not None
    assert "REFUSED" in conflict
    assert "session-A" in conflict
    # A's plan is untouched and A still owns it.
    assert a.read_text().endswith("- [ ] 1. a step\n")
    assert plan_write_conflict(str(a), session_id="session-A", workdir=str(tmp_path)) is None


def test_write_gate_binds_a_free_plan_to_the_writer(tmp_path):
    free = _write(tmp_path, "# free\nStatus: active\n- [ ] 1. probe\n", name="PLAN-free.md")
    assert plan_write_conflict(str(free), session_id="session-B", workdir=str(tmp_path)) is None
    owner = json.loads((tmp_path / ".daedalus" / ".owners" / "PLAN-free.md.json").read_text())
    assert owner["session_id"] == "session-B"
    # ...and now it belongs to B.
    assert plan_write_conflict(str(free), session_id="session-C", workdir=str(tmp_path))


def test_write_gate_ignores_ordinary_files(tmp_path):
    (tmp_path / "code.py").write_text("x = 1\n")
    assert plan_write_conflict(str(tmp_path / "code.py"), session_id="s1", workdir=str(tmp_path)) is None
    assert plan_write_conflict(str(tmp_path / ".daedalus" / "NOTES.md"),
                               session_id="s1", workdir=str(tmp_path)) is None


def test_gate_follows_the_file_not_the_cwd(tmp_path):
    """A plan in ANOTHER folder is still protected.

    The gate identifies a plan by the file (PLAN*.md in a .daedalus dir), not by
    the current working directory: a write arriving over an ssh-style backend
    resolves to a path the local cwd knows nothing about.
    """
    other = _write(tmp_path, "# other\nStatus: active\n- [ ] 1. x\n", name="PLAN-other.md")
    _claim_as_live_agent(other, "session-A")
    err = plan_write_conflict(str(other), session_id="session-B",
                              workdir=str(tmp_path / "elsewhere"))
    assert err is not None and "REFUSED" in err


def test_relative_plan_path_is_resolved_against_cwd(tmp_path, monkeypatch):
    p = _write(tmp_path, "# rel\nStatus: active\n- [ ] 1. x\n", name="PLAN-rel.md")
    _claim_as_live_agent(p, "session-A")
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    err = plan_write_conflict(".daedalus/PLAN-rel.md", session_id="session-B")
    assert err is not None and "REFUSED" in err


def test_dead_owner_is_adopted_not_refused(tmp_path):
    """A crashed agent's plan must not lock the folder forever."""
    stale = _write(tmp_path, "# crashed\nStatus: active\n- [ ] 1. x\n", name="PLAN-stale.md")
    _claim_as_live_agent(stale, "session-dead", pid=999999)
    assert plan_write_conflict(str(stale), session_id="session-B", workdir=str(tmp_path)) is None
    block = render_plan_block(str(tmp_path), session_id="session-B")
    assert f'<active-plan path="{stale}"' in block


# --- resolution with two agents in one folder --------------------------


def test_two_live_agents_each_keep_their_own_plan(tmp_path):
    """The reported incident, end to end: A writes a plan, B writes one too."""
    a = _write(tmp_path, "# agent A\nStatus: active\n- [ ] 1. a\n", name="PLAN-a.md")
    b = _write(tmp_path, "# agent B\nStatus: active\n- [ ] 1. b\n", name="PLAN-b.md")
    # Each agent's first write binds the file to it (what the gate does).
    assert plan_write_conflict(str(a), session_id="A", workdir=str(tmp_path)) is None
    assert plan_write_conflict(str(b), session_id="B", workdir=str(tmp_path)) is None

    assert render_plan_block(str(tmp_path), session_id="A").startswith(f'<active-plan path="{a}"')
    assert render_plan_block(str(tmp_path), session_id="B").startswith(f'<active-plan path="{b}"')
    # B's plan existing does not move A's plan, and A's turn is unaffected.
    assert render_plan_block(str(tmp_path), session_id="A").startswith(f'<active-plan path="{a}"')
    assert a.read_text().endswith("- [ ] 1. a\n")
    # ...and B still cannot reach into A's plan.
    assert "REFUSED" in (plan_write_conflict(str(a), session_id="B", workdir=str(tmp_path)) or "")


def test_ambiguous_folder_gets_an_index_not_a_guess(tmp_path):
    _write(tmp_path, "# first\nStatus: active\n- [ ] 1. a\n", name="PLAN-one.md")
    _write(tmp_path, "# second\nStatus: active\n- [ ] 1. b\n", name="PLAN-two.md")
    block = render_plan_block(str(tmp_path), session_id="newcomer")
    assert "<plan-index>" in block
    assert "<active-plan" not in block
    assert "PLAN-one.md" in block and "PLAN-two.md" in block
    assert "Do NOT overwrite" in block


def test_held_plan_is_not_offered_as_adoptable(tmp_path):
    a = _write(tmp_path, "# busy\nStatus: active\n- [ ] 1. a\n", name="PLAN-a.md")
    b = _write(tmp_path, "# idle\nStatus: active\n- [ ] 1. b\n", name="PLAN-b.md")
    _claim_as_live_agent(a, "session-A")
    res = resolve_plan(str(tmp_path), session_id="session-C")
    assert res.owned == b
    assert [f.path.name for f in res.foreign] == ["PLAN-a.md"]
    block = render_plan_block(str(tmp_path), session_id="session-C")
    assert "Other agents are working PLAN-a.md" in block
    assert "never to write" in block


def test_free_plan_is_adopted_once_then_stays_with_the_adopter(tmp_path):
    p = _write(tmp_path, "# solo\nStatus: active\n- [ ] 1. a\n", name="PLAN-solo.md")
    res = resolve_plan(str(tmp_path), session_id="session-B")
    assert res.owned == p and res.adopted
    # Same session keeps it; a second session cannot steal it.
    assert resolve_plan(str(tmp_path), session_id="session-B").owned == p
    assert resolve_plan(str(tmp_path), session_id="session-C").owned is None


def test_closed_plans_are_not_resurrected(tmp_path):
    _write(tmp_path, "# done\nStatus: done\n- [x] 1. a\n", name="PLAN-done.md")
    _write(tmp_path, "# abandoned\nStatus: abandoned\n", name="PLAN-old.md")
    assert resolve_plan(str(tmp_path), session_id="s1").owned is None
    assert render_plan_block(str(tmp_path), session_id="s1") == ""


def test_empty_workdir_is_not_an_error(tmp_path):
    assert list_plans(str(tmp_path)) == []
    assert resolve_plan(str(tmp_path), session_id="s1").reason == "no plans in this folder"
    assert render_plan_block(str(tmp_path), session_id="s1") == ""


def test_bind_plan_refuses_a_live_holder(tmp_path):
    p = _write(tmp_path, "# contested\nStatus: active\n- [ ] 1. a\n", name="PLAN-c.md")
    _claim_as_live_agent(p, "session-A")
    assert bind_plan(p, "session-B") is False
    assert bind_plan(p, "session-A") is True


def test_no_session_id_claims_nothing(tmp_path):
    """An empty holder would read as 'alive' to every later session."""
    p = _write(tmp_path, "# anonymous\nStatus: active\n- [ ] 1. a\n", name="PLAN-anon.md")
    assert plan_write_conflict(str(p), session_id="", workdir=str(tmp_path)) is None
    assert not (tmp_path / ".daedalus" / ".owners" / "PLAN-anon.md.json").exists()
    # ...and it stays free for the next real session.
    res = resolve_plan(str(tmp_path), session_id="session-real")
    assert res.owned == p


def test_rebase_hands_the_plan_to_the_new_session(tmp_path):
    # A rebase mints a new session id in the SAME live process; the plan must follow.
    p = _write(tmp_path, "# tor\nStatus: active\n- [ ] 1. frame cap", name="PLAN-tor.md")
    _write(tmp_path, "# other\nStatus: active\n- [ ] 1. x", name="PLAN-other.md")
    assert bind_plan(p, "old")
    assert hand_over_plans("old", "new", str(tmp_path)) == 1
    res = resolve_plan(str(tmp_path), "new")
    assert res.owned == p and not res.foreign


def test_without_hand_over_the_agent_adopts_a_different_plan(tmp_path):
    # What the missing hand-over did: the held plan reads as foreign, so the
    # resolver binds the only other open plan instead.
    p = _write(tmp_path, "# tor\nStatus: active\n- [ ] 1. a", name="PLAN-tor.md")
    q = _write(tmp_path, "# other\nStatus: active\n- [ ] 1. b", name="PLAN-other.md")
    bind_plan(p, "old")
    assert resolve_plan(str(tmp_path), "new").owned == q


def test_hand_over_leaves_other_sessions_plans_alone(tmp_path):
    a = _write(tmp_path, "# a\nStatus: active\n- [ ] 1. x", name="PLAN-a.md")
    b = _write(tmp_path, "# b\nStatus: active\n- [ ] 1. x", name="PLAN-b.md")
    bind_plan(a, "old"); bind_plan(b, "someone-else")
    assert hand_over_plans("old", "new", str(tmp_path)) == 1
    assert json.loads((tmp_path / ".daedalus/.owners/PLAN-b.md.json").read_text())["session_id"] == "someone-else"
    assert hand_over_plans("", "new", str(tmp_path)) == 0
