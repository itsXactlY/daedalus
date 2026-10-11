"""Tests for banner toolset name normalization and skin color usage."""

from unittest.mock import patch

from rich.console import Console

import daedalus_cli.banner as banner
import model_tools
import tools.mcp_tool


def test_display_toolset_name_strips_legacy_suffix():
    assert banner._display_toolset_name("homeassistant_tools") == "homeassistant"
    assert banner._display_toolset_name("honcho_tools") == "honcho"
    assert banner._display_toolset_name("web_tools") == "web"


def test_display_toolset_name_preserves_clean_names():
    assert banner._display_toolset_name("browser") == "browser"
    assert banner._display_toolset_name("file") == "file"
    assert banner._display_toolset_name("terminal") == "terminal"


def test_display_toolset_name_handles_empty():
    assert banner._display_toolset_name("") == "unknown"
    assert banner._display_toolset_name(None) == "unknown"


def test_build_welcome_banner_uses_normalized_toolset_names():
    """Unavailable toolsets should not have '_tools' appended in banner output."""
    with (
        patch.object(
            model_tools,
            "check_tool_availability",
            return_value=(
                ["web"],
                [
                    {"name": "homeassistant", "tools": ["ha_call_service"]},
                    {"name": "honcho", "tools": ["honcho_conclude"]},
                ],
            ),
        ),
        patch.object(banner, "get_available_skills", return_value={}),
        patch.object(banner, "get_update_result", return_value=None),
        patch.object(tools.mcp_tool, "get_mcp_status", return_value=[]),
    ):
        console = Console(
            record=True, force_terminal=False, color_system=None, width=160
        )
        banner.build_welcome_banner(
            console=console,
            model="anthropic/test-model",
            cwd="/tmp/project",
            tools=[
                {"function": {"name": "web_search"}},
                {"function": {"name": "read_file"}},
            ],
            get_toolset_for_tool=lambda name: {
                "web_search": "web_tools",
                "read_file": "file",
            }.get(name),
        )

    output = console.export_text()
    assert "homeassistant:" in output
    assert "honcho:" in output
    assert "web:" in output
    assert "homeassistant_tools:" not in output
    assert "honcho_tools:" not in output
    assert "web_tools:" not in output


def _render_banner(monkeypatch, mode=None):
    if mode is None:
        monkeypatch.delenv("DAEDALUS_BANNER_SKILLS", raising=False)
    else:
        monkeypatch.setenv("DAEDALUS_BANNER_SKILLS", mode)
    skills = {f"cat{i}": [f"skill-{i}-{j}" for j in range(5)] for i in range(12)}
    with (
        patch.object(model_tools, "check_tool_availability", return_value=(["web"], [])),
        patch.object(banner, "get_available_skills", return_value=skills),
        patch.object(banner, "get_update_result", return_value=None),
        patch.object(tools.mcp_tool, "get_mcp_status", return_value=[]),
    ):
        console = Console(record=True, force_terminal=False, color_system=None, width=160)
        banner.build_welcome_banner(
            console=console, model="qwen3.8-flash-next-coder-iq1_m", cwd="/tmp/project",
            tools=[{"function": {"name": "web_search"}}],
            get_toolset_for_tool=lambda name: "web",
        )
    return console.export_text()


def test_banner_skills_are_one_line_by_default(monkeypatch):
    out = _render_banner(monkeypatch)
    assert "60 skills in 12 groups" in out
    assert "skill-3-2" not in out and "Available Skills" not in out


def test_banner_full_skill_list_is_opt_in(monkeypatch):
    out = _render_banner(monkeypatch, "full")
    assert "Available Skills" in out and "cat3:" in out and "skill-3-0" in out


def test_banner_skills_none_hides_the_count(monkeypatch):
    assert "skills" not in _render_banner(monkeypatch, "none")


def test_banner_does_not_label_a_local_model_with_a_vendor(monkeypatch):
    assert "Nous Research" not in _render_banner(monkeypatch)
