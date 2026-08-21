"""Tests for agent/skill_preprocessing.py — SKILL.md template + inline-shell preprocessing.

Ported from upstream daedalus 0.20 (tests/agent/test_skill_commands.py:
TestTemplateVarSubstitution / TestInlineShellExpansion) and adapted to the
0.8.0 wiring point: preprocessing runs inside tools.skills_tool.skill_view,
which is the shared choke point for the skill_view tool path, the /command
invocation path (agent/skill_commands._load_skill_payload), and bundles
(agent/skill_bundles).
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from agent.skill_preprocessing import (
    expand_inline_shell,
    preprocess_skill_content,
    substitute_template_vars,
)
from tools.skills_tool import skill_view


def _make_skill(skills_dir, name, body="Step 1: Do the thing.", extra_frontmatter=""):
    """Helper to create a minimal skill directory (mirrors tests/tools/test_skills_tool)."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = f"""\
---
name: {name}
description: Description for {name}.
{extra_frontmatter}---

# {name}

{body}
"""
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


class TestSubstituteTemplateVars:
    def test_skill_dir_resolves(self):
        skill_dir = Path("/tmp/some-skill")
        content = "Run: node ${DAEDALUS_SKILL_DIR}/scripts/foo.js"
        out = substitute_template_vars(content, skill_dir, None)
        assert out == f"Run: node {skill_dir}/scripts/foo.js"
        assert "${DAEDALUS_SKILL_DIR}" not in out

    def test_session_id_resolves(self):
        content = "Session: ${DAEDALUS_SESSION_ID}"
        out = substitute_template_vars(content, None, "sess-123")
        assert out == "Session: sess-123"

    def test_unresolved_skill_dir_stays_as_is(self):
        """A token with no concrete value must be left untouched."""
        content = "Run: node ${DAEDALUS_SKILL_DIR}/scripts/foo.js"
        out = substitute_template_vars(content, None, None)
        assert out == content
        assert "${DAEDALUS_SKILL_DIR}/scripts/foo.js" in out

    def test_unresolved_session_id_stays_as_is(self):
        content = "Sess: ${DAEDALUS_SESSION_ID}"
        out = substitute_template_vars(content, Path("/d"), None)
        assert out == content

    def test_unknown_token_not_touched(self):
        content = "${DAEDALUS_OTHER}/x"
        assert substitute_template_vars(content, Path("/d"), "s") == content

    def test_empty_content(self):
        assert substitute_template_vars("", Path("/d"), "s") == ""


class TestInlineShellExpansion:
    def test_expand_inline_shell_runs_command(self, monkeypatch):
        captured = {}

        def fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs
            result = subprocess.CompletedProcess(argv, 0)
            result.stdout = "hi"
            result.stderr = ""
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        out = expand_inline_shell("Hello !`echo hi`", Path("/d"), timeout=10)
        assert out == "Hello hi"
        # Runs via bash -c with the skill dir as CWD and stdin closed.
        assert captured["argv"][:2] == ["bash", "-c"]
        assert captured["argv"][2] == "echo hi"
        assert captured["kwargs"]["cwd"] == "/d"
        assert captured["kwargs"]["stdin"] == subprocess.DEVNULL
        assert captured["kwargs"]["timeout"] == 10

    def test_inline_shell_output_cap_enforced(self, monkeypatch):
        """Output longer than 4000 chars is truncated with a marker."""
        long_output = "x" * 5000

        def fake_run(argv, **kwargs):
            result = subprocess.CompletedProcess(argv, 0)
            result.stdout = long_output
            result.stderr = ""
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        out = expand_inline_shell("!`long`", Path("/d"), timeout=10)
        assert out == "x" * 4000 + "...[truncated]"
        assert len(out) == 4000 + len("...[truncated]")

    def test_inline_shell_error_returns_marker(self, monkeypatch):
        def fake_run(argv, **kwargs):
            raise FileNotFoundError()

        monkeypatch.setattr(subprocess, "run", fake_run)
        out = expand_inline_shell("!`nope`", Path("/d"), timeout=10)
        assert out == "[inline-shell error: bash not found]"

    def test_no_marker_short_circuits(self, monkeypatch):
        def fake_run(argv, **kwargs):
            raise AssertionError("should not be called")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert expand_inline_shell("no snippets here", Path("/d"), 10) == "no snippets here"

    def test_preprocess_skips_inline_shell_when_disabled(self, monkeypatch):
        def fake_run(argv, **kwargs):
            raise AssertionError("should not be called")

        monkeypatch.setattr(subprocess, "run", fake_run)
        out = preprocess_skill_content(
            "Hi !`echo hi`",
            Path("/d"),
            skills_cfg={"template_vars": True, "inline_shell": False},
        )
        assert out == "Hi !`echo hi`"

    def test_preprocess_runs_inline_shell_when_enabled(self, monkeypatch):
        def fake_run(argv, **kwargs):
            result = subprocess.CompletedProcess(argv, 0)
            result.stdout = "hi"
            result.stderr = ""
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        out = preprocess_skill_content(
            "Hi !`echo hi` ${DAEDALUS_SKILL_DIR}",
            Path("/d"),
            skills_cfg={"template_vars": True, "inline_shell": True, "inline_shell_timeout": 5},
        )
        assert out == "Hi hi /d"


class TestSkillViewPath:
    """Preprocessing runs through the real skill-view path."""

    def test_skill_view_resolves_tokens(self, tmp_path):
        skill_dir = _make_skill(
            tmp_path,
            "templated",
            body="Run: node ${DAEDALUS_SKILL_DIR}/scripts/foo.js\nSess: ${DAEDALUS_SESSION_ID}",
        )
        with (
            patch("tools.skills_tool.SKILLS_DIR", tmp_path),
            patch(
                "agent.skill_preprocessing.load_skills_config",
                return_value={"template_vars": True, "inline_shell": False},
            ),
        ):
            raw = skill_view("templated", task_id="sess-abc")
        result = json.loads(raw)
        assert result["success"] is True
        content = result["content"]
        assert f"node {skill_dir}/scripts/foo.js" in content
        assert "Sess: sess-abc" in content
        # Literal template tokens must not leak through.
        assert "${DAEDALUS_SKILL_DIR}" not in content
        assert "${DAEDALUS_SESSION_ID}" not in content

    def test_skill_view_leaves_unresolved_token_as_is(self, tmp_path):
        _make_skill(
            tmp_path,
            "no-sess",
            body="Run: node ${DAEDALUS_SKILL_DIR}/x\nSess: ${DAEDALUS_SESSION_ID}",
        )
        with (
            patch("tools.skills_tool.SKILLS_DIR", tmp_path),
            patch(
                "agent.skill_preprocessing.load_skills_config",
                return_value={"template_vars": True, "inline_shell": False},
            ),
        ):
            # No task_id -> session id unavailable; skill dir still resolves.
            raw = skill_view("no-sess")
        result = json.loads(raw)
        assert result["success"] is True
        content = result["content"]
        assert "${DAEDALUS_SKILL_DIR}" not in content
        assert "${DAEDALUS_SESSION_ID}" in content

    def test_skill_view_runs_inline_shell_when_enabled(self, tmp_path, monkeypatch):
        def fake_run(argv, **kwargs):
            result = subprocess.CompletedProcess(argv, 0)
            result.stdout = "hi"
            result.stderr = ""
            return result

        monkeypatch.setattr(subprocess, "run", fake_run)
        _make_skill(
            tmp_path,
            "dyn",
            body="Greeting: !`echo hi`",
        )
        with (
            patch("tools.skills_tool.SKILLS_DIR", tmp_path),
            patch(
                "agent.skill_preprocessing.load_skills_config",
                return_value={"template_vars": True, "inline_shell": True, "inline_shell_timeout": 5},
            ),
        ):
            raw = skill_view("dyn")
        result = json.loads(raw)
        assert result["success"] is True
        assert "Greeting: hi" in result["content"]
        assert "!`echo hi`" not in result["content"]
