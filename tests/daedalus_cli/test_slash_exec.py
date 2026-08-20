"""Tests for the minimal daedalus_cli/slash_exec.py /bundles executor."""

from daedalus_cli.slash_exec import CommandContext, CommandReply, EXECUTORS, execute_command, resolve_executor, run_execute


def test_bundles_registered_in_executors():
    assert "bundles" in EXECUTORS


def test_execute_command_bundles_returns_reply(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.skill_bundles.list_bundles", lambda: [])
    monkeypatch.setattr("agent.skill_bundles._bundles_dir", lambda: tmp_path)

    reply = execute_command("bundles", CommandContext(surface="cli"))

    assert isinstance(reply, CommandReply)
    assert "No skill bundles installed" in reply.text
    assert reply.data["bundles"] == []
    assert reply.data["dir"] == str(tmp_path)


def test_execute_command_bundles_lists_installed(monkeypatch, tmp_path):
    fake_bundles = [
        {"slug": "review-stack", "description": "Code review skills", "skills": ["code-audit", "security"]},
    ]
    monkeypatch.setattr("agent.skill_bundles.list_bundles", lambda: fake_bundles)
    monkeypatch.setattr("agent.skill_bundles._bundles_dir", lambda: tmp_path)

    reply = execute_command("bundles", CommandContext(surface="cli"))

    assert "review-stack" in reply.text
    assert "code-audit" in reply.text
    assert reply.data["bundles"] == fake_bundles


def test_execute_command_unknown_raises_lookup_error():
    import pytest
    with pytest.raises(LookupError):
        execute_command("not-a-real-command", CommandContext(surface="cli"))


def test_resolve_executor_returns_none_without_execute_key():
    from daedalus_cli.commands import CommandDef

    cmd = CommandDef("new", "Start a new session", "Session")
    assert resolve_executor(cmd) is None


def test_run_execute_returns_none_for_unmigrated_command():
    from daedalus_cli.commands import CommandDef

    cmd = CommandDef("new", "Start a new session", "Session")
    assert run_execute(cmd, CommandContext(surface="cli")) is None
