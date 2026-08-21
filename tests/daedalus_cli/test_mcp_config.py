"""
Tests for daedalus_cli.mcp_config — ``daedalus mcp`` subcommands.

These tests mock the MCP server connection layer so they run without
any actual MCP servers or API keys.
"""

import argparse
import json
import os
import types
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Redirect all config I/O to a temp directory."""
    monkeypatch.setenv("DAEDALUS_HOME", str(tmp_path))
    monkeypatch.setattr(
        "daedalus_cli.config.get_daedalus_home", lambda: tmp_path
    )
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"
    monkeypatch.setattr(
        "daedalus_cli.config.get_config_path", lambda: config_path
    )
    monkeypatch.setattr(
        "daedalus_cli.config.get_env_path", lambda: env_path
    )
    return tmp_path


def _make_args(**kwargs):
    """Build a minimal argparse.Namespace."""
    defaults = {
        "name": "test-server",
        "url": None,
        "command": None,
        "args": None,
        "auth": None,
        "mcp_action": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _seed_config(tmp_path: Path, mcp_servers: dict):
    """Write a config.yaml with the given mcp_servers."""
    import yaml

    config = {"mcp_servers": mcp_servers, "_config_version": 9}
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)


class FakeTool:
    """Mimics an MCP tool object returned by the SDK."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


# ---------------------------------------------------------------------------
# Tests: cmd_mcp_list
# ---------------------------------------------------------------------------

class TestMcpList:
    def test_list_empty_config(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import cmd_mcp_list

        cmd_mcp_list()
        out = capsys.readouterr().out
        assert "No MCP servers configured" in out

    def test_list_with_servers(self, tmp_path, capsys):
        _seed_config(tmp_path, {
            "ink": {
                "url": "https://mcp.ml.ink/mcp",
                "enabled": True,
                "tools": {"include": ["create_service", "get_service"]},
            },
            "github": {
                "command": "npx",
                "args": ["@mcp/github"],
                "enabled": False,
            },
        })
        from daedalus_cli.mcp_config import cmd_mcp_list

        cmd_mcp_list()
        out = capsys.readouterr().out
        assert "ink" in out
        assert "github" in out
        assert "2 selected" in out  # ink has 2 in include
        assert "disabled" in out  # github is disabled

    def test_list_enabled_default_true(self, tmp_path, capsys):
        """Server without explicit enabled key defaults to enabled."""
        _seed_config(tmp_path, {
            "myserver": {"url": "https://example.com/mcp"},
        })
        from daedalus_cli.mcp_config import cmd_mcp_list

        cmd_mcp_list()
        out = capsys.readouterr().out
        assert "myserver" in out
        assert "enabled" in out


# ---------------------------------------------------------------------------
# Tests: cmd_mcp_remove
# ---------------------------------------------------------------------------

class TestMcpRemove:
    def test_remove_existing_server(self, tmp_path, capsys, monkeypatch):
        _seed_config(tmp_path, {
            "myserver": {"url": "https://example.com/mcp"},
        })
        monkeypatch.setattr("builtins.input", lambda _: "y")
        from daedalus_cli.mcp_config import cmd_mcp_remove

        cmd_mcp_remove(_make_args(name="myserver"))

        out = capsys.readouterr().out
        assert "Removed" in out

        # Verify config updated
        from daedalus_cli.config import load_config

        config = load_config()
        assert "myserver" not in config.get("mcp_servers", {})

    def test_remove_nonexistent(self, tmp_path, capsys):
        _seed_config(tmp_path, {})
        from daedalus_cli.mcp_config import cmd_mcp_remove

        cmd_mcp_remove(_make_args(name="ghost"))
        out = capsys.readouterr().out
        assert "not found" in out

    def test_remove_cleans_oauth_tokens(self, tmp_path, capsys, monkeypatch):
        _seed_config(tmp_path, {
            "oauth-srv": {"url": "https://example.com/mcp", "auth": "oauth"},
        })
        monkeypatch.setattr("builtins.input", lambda _: "y")
        # Also patch get_daedalus_home in the mcp_config module namespace
        monkeypatch.setattr(
            "daedalus_cli.mcp_config.get_daedalus_home", lambda: tmp_path
        )

        # Create a fake token file
        token_dir = tmp_path / "mcp-tokens"
        token_dir.mkdir()
        token_file = token_dir / "oauth-srv.json"
        token_file.write_text("{}")

        from daedalus_cli.mcp_config import cmd_mcp_remove

        cmd_mcp_remove(_make_args(name="oauth-srv"))
        assert not token_file.exists()


# ---------------------------------------------------------------------------
# Tests: cmd_mcp_add
# ---------------------------------------------------------------------------

class TestMcpAdd:
    def test_add_no_transport(self, capsys):
        """Must specify --url or --command."""
        from daedalus_cli.mcp_config import cmd_mcp_add

        cmd_mcp_add(_make_args(name="bad"))
        out = capsys.readouterr().out
        assert "Must specify" in out

    def test_add_http_server_all_tools(self, tmp_path, capsys, monkeypatch):
        """Add an HTTP server, accept all tools."""
        fake_tools = [
            FakeTool("create_service", "Deploy from repo"),
            FakeTool("list_services", "List all services"),
        ]

        def mock_probe(name, config, **kw):
            return [(t.name, t.description) for t in fake_tools]

        monkeypatch.setattr(
            "daedalus_cli.mcp_config._probe_single_server", mock_probe
        )
        # No auth, accept all tools
        inputs = iter(["n", ""])  # no auth needed, enable all
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from daedalus_cli.mcp_config import cmd_mcp_add

        cmd_mcp_add(_make_args(name="ink", url="https://mcp.ml.ink/mcp"))
        out = capsys.readouterr().out
        assert "Saved" in out
        assert "2/2 tools" in out

        # Verify config written
        from daedalus_cli.config import load_config

        config = load_config()
        assert "ink" in config.get("mcp_servers", {})
        assert config["mcp_servers"]["ink"]["url"] == "https://mcp.ml.ink/mcp"

    def test_add_stdio_server(self, tmp_path, capsys, monkeypatch):
        """Add a stdio server."""
        fake_tools = [FakeTool("search", "Search repos")]

        def mock_probe(name, config, **kw):
            return [(t.name, t.description) for t in fake_tools]

        monkeypatch.setattr(
            "daedalus_cli.mcp_config._probe_single_server", mock_probe
        )
        inputs = iter([""])  # accept all tools
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from daedalus_cli.mcp_config import cmd_mcp_add

        cmd_mcp_add(_make_args(
            name="github",
            command="npx",
            args=["@mcp/github"],
        ))
        out = capsys.readouterr().out
        assert "Saved" in out

        from daedalus_cli.config import load_config

        config = load_config()
        srv = config["mcp_servers"]["github"]
        assert srv["command"] == "npx"
        assert srv["args"] == ["@mcp/github"]

    def test_add_connection_failure_save_disabled(
        self, tmp_path, capsys, monkeypatch
    ):
        """Failed connection → option to save as disabled."""

        def mock_probe_fail(name, config, **kw):
            raise ConnectionError("Connection refused")

        monkeypatch.setattr(
            "daedalus_cli.mcp_config._probe_single_server", mock_probe_fail
        )
        inputs = iter(["n", "y"])  # no auth, yes save disabled
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        from daedalus_cli.mcp_config import cmd_mcp_add

        cmd_mcp_add(_make_args(name="broken", url="https://bad.host/mcp"))
        out = capsys.readouterr().out
        assert "disabled" in out

        from daedalus_cli.config import load_config

        config = load_config()
        assert config["mcp_servers"]["broken"]["enabled"] is False


# ---------------------------------------------------------------------------
# Tests: cmd_mcp_test
# ---------------------------------------------------------------------------

class TestMcpTest:
    def test_test_not_found(self, tmp_path, capsys):
        _seed_config(tmp_path, {})
        from daedalus_cli.mcp_config import cmd_mcp_test

        cmd_mcp_test(_make_args(name="ghost"))
        out = capsys.readouterr().out
        assert "not found" in out

    def test_test_success(self, tmp_path, capsys, monkeypatch):
        _seed_config(tmp_path, {
            "ink": {"url": "https://mcp.ml.ink/mcp"},
        })

        def mock_probe(name, config, **kw):
            return [("create_service", "Deploy"), ("list_services", "List all")]

        monkeypatch.setattr(
            "daedalus_cli.mcp_config._probe_single_server", mock_probe
        )
        from daedalus_cli.mcp_config import cmd_mcp_test

        cmd_mcp_test(_make_args(name="ink"))
        out = capsys.readouterr().out
        assert "Connected" in out
        assert "Tools discovered: 2" in out


# ---------------------------------------------------------------------------
# Tests: env var interpolation
# ---------------------------------------------------------------------------

class TestEnvVarInterpolation:
    def test_interpolate_simple(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret123")
        from tools.mcp_tool import _interpolate_env_vars

        result = _interpolate_env_vars("Bearer ${MY_KEY}")
        assert result == "Bearer secret123"

    def test_interpolate_missing_var(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        from tools.mcp_tool import _interpolate_env_vars

        result = _interpolate_env_vars("Bearer ${MISSING_VAR}")
        assert result == "Bearer ${MISSING_VAR}"

    def test_interpolate_nested_dict(self, monkeypatch):
        monkeypatch.setenv("API_KEY", "abc")
        from tools.mcp_tool import _interpolate_env_vars

        result = _interpolate_env_vars({
            "url": "https://example.com",
            "headers": {"Authorization": "Bearer ${API_KEY}"},
        })
        assert result["headers"]["Authorization"] == "Bearer abc"
        assert result["url"] == "https://example.com"

    def test_interpolate_list(self, monkeypatch):
        monkeypatch.setenv("ARG1", "hello")
        from tools.mcp_tool import _interpolate_env_vars

        result = _interpolate_env_vars(["${ARG1}", "static"])
        assert result == ["hello", "static"]

    def test_interpolate_non_string(self):
        from tools.mcp_tool import _interpolate_env_vars

        assert _interpolate_env_vars(42) == 42
        assert _interpolate_env_vars(True) is True
        assert _interpolate_env_vars(None) is None


# ---------------------------------------------------------------------------
# Tests: config helpers
# ---------------------------------------------------------------------------

class TestConfigHelpers:
    def test_save_and_load_mcp_server(self, tmp_path):
        from daedalus_cli.mcp_config import _save_mcp_server, _get_mcp_servers

        _save_mcp_server("mysvr", {"url": "https://example.com/mcp"})
        servers = _get_mcp_servers()
        assert "mysvr" in servers
        assert servers["mysvr"]["url"] == "https://example.com/mcp"

    def test_remove_mcp_server(self, tmp_path):
        from daedalus_cli.mcp_config import (
            _save_mcp_server,
            _remove_mcp_server,
            _get_mcp_servers,
        )

        _save_mcp_server("s1", {"command": "test"})
        _save_mcp_server("s2", {"command": "test2"})
        result = _remove_mcp_server("s1")
        assert result is True
        assert "s1" not in _get_mcp_servers()
        assert "s2" in _get_mcp_servers()

    def test_remove_nonexistent(self, tmp_path):
        from daedalus_cli.mcp_config import _remove_mcp_server

        assert _remove_mcp_server("ghost") is False

    def test_env_key_for_server(self):
        from daedalus_cli.mcp_config import _env_key_for_server

        assert _env_key_for_server("ink") == "MCP_INK_API_KEY"
        assert _env_key_for_server("my-server") == "MCP_MY_SERVER_API_KEY"


# ---------------------------------------------------------------------------
# Tests: dispatcher
# ---------------------------------------------------------------------------

class TestDispatcher:
    def test_no_action_shows_list(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import mcp_command

        _seed_config(tmp_path, {})
        mcp_command(_make_args(mcp_action=None))
        out = capsys.readouterr().out
        assert "Commands:" in out or "No MCP servers" in out


# ---------------------------------------------------------------------------
# daedalus mcp login / reauth
# ---------------------------------------------------------------------------

class TestOauthTokensPresent:
    def test_false_when_no_token_file(self, tmp_path, monkeypatch):
        from daedalus_cli.mcp_config import _oauth_tokens_present
        monkeypatch.setattr("tools.mcp_oauth._get_token_dir", lambda: tmp_path / "mcp-tokens")
        assert _oauth_tokens_present("nope") is False

    def test_true_when_token_file_exists(self, tmp_path, monkeypatch):
        from daedalus_cli.mcp_config import _oauth_tokens_present
        token_dir = tmp_path / "mcp-tokens"
        token_dir.mkdir(parents=True)
        (token_dir / "myserver.json").write_text("{}")
        monkeypatch.setattr("tools.mcp_oauth._get_token_dir", lambda: token_dir)
        assert _oauth_tokens_present("myserver") is True


class TestReauthOauthServer:
    def test_rejects_non_oauth_server(self, tmp_path):
        from daedalus_cli.mcp_config import _reauth_oauth_server
        ok = _reauth_oauth_server("s", {"url": "https://x", "auth": "header"})
        assert ok is False

    def test_rejects_server_without_url(self, tmp_path):
        from daedalus_cli.mcp_config import _reauth_oauth_server
        ok = _reauth_oauth_server("s", {"auth": "oauth"})
        assert ok is False

    def test_reports_failure_when_no_token_lands(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import _reauth_oauth_server
        with patch("daedalus_cli.mcp_config._probe_single_server", return_value=[("t", "d")]), \
             patch("daedalus_cli.mcp_config._oauth_tokens_present", return_value=False), \
             patch("tools.mcp_oauth_manager.get_manager") as mock_mgr:
            ok = _reauth_oauth_server("s", {"url": "https://x", "auth": "oauth"})
        assert ok is False
        assert "no OAuth token was obtained" in capsys.readouterr().out
        mock_mgr.return_value.remove.assert_called_once_with("s")

    def test_succeeds_when_token_lands(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import _reauth_oauth_server
        with patch("daedalus_cli.mcp_config._probe_single_server", return_value=[("t", "d")]), \
             patch("daedalus_cli.mcp_config._oauth_tokens_present", return_value=True), \
             patch("tools.mcp_oauth_manager.get_manager"):
            ok = _reauth_oauth_server("s", {"url": "https://x", "auth": "oauth"})
        assert ok is True
        assert "Authenticated" in capsys.readouterr().out

    def test_probe_exception_reports_failure(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import _reauth_oauth_server
        with patch("daedalus_cli.mcp_config._probe_single_server", side_effect=RuntimeError("boom")), \
             patch("tools.mcp_oauth_manager.get_manager"):
            ok = _reauth_oauth_server("s", {"url": "https://x", "auth": "oauth"})
        assert ok is False
        assert "Authentication failed" in capsys.readouterr().out


class TestCmdMcpLogin:
    def test_unknown_server(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import cmd_mcp_login
        _seed_config(tmp_path, {})
        cmd_mcp_login(_make_args(name="ghost"))
        assert "not found" in capsys.readouterr().out

    def test_delegates_to_reauth_helper(self, tmp_path):
        from daedalus_cli.mcp_config import cmd_mcp_login
        _seed_config(tmp_path, {"s": {"url": "https://x", "auth": "oauth"}})
        with patch("daedalus_cli.mcp_config._reauth_oauth_server", return_value=True) as mock_reauth:
            cmd_mcp_login(_make_args(name="s"))
        mock_reauth.assert_called_once_with("s", {"url": "https://x", "auth": "oauth"})


class TestCmdMcpReauth:
    def test_no_name_no_all_errors(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import cmd_mcp_reauth
        _seed_config(tmp_path, {})
        cmd_mcp_reauth(_make_args(name=None, all=False))
        assert "Specify a server name" in capsys.readouterr().out

    def test_unknown_server(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import cmd_mcp_reauth
        _seed_config(tmp_path, {})
        cmd_mcp_reauth(_make_args(name="ghost", all=False))
        assert "not found" in capsys.readouterr().out

    def test_all_with_no_oauth_servers(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import cmd_mcp_reauth
        _seed_config(tmp_path, {"s": {"url": "https://x", "auth": "header"}})
        cmd_mcp_reauth(_make_args(name=None, all=True))
        assert "No OAuth-based MCP servers" in capsys.readouterr().out

    def test_all_reauths_each_oauth_server_serially(self, tmp_path, capsys):
        from daedalus_cli.mcp_config import cmd_mcp_reauth
        _seed_config(tmp_path, {
            "a": {"url": "https://a", "auth": "oauth"},
            "b": {"url": "https://b", "auth": "oauth"},
            "c": {"url": "https://c", "auth": "header"},
        })
        with patch("daedalus_cli.mcp_config._reauth_oauth_server", return_value=True) as mock_reauth:
            cmd_mcp_reauth(_make_args(name=None, all=True))
        assert mock_reauth.call_count == 2
        called_names = {call.args[0] for call in mock_reauth.call_args_list}
        assert called_names == {"a", "b"}
        assert "Re-authenticated 2/2" in capsys.readouterr().out

    def test_single_name_delegates(self, tmp_path):
        from daedalus_cli.mcp_config import cmd_mcp_reauth
        _seed_config(tmp_path, {"s": {"url": "https://x", "auth": "oauth"}})
        with patch("daedalus_cli.mcp_config._reauth_oauth_server", return_value=True) as mock_reauth:
            cmd_mcp_reauth(_make_args(name="s", all=False))
        mock_reauth.assert_called_once_with("s", {"url": "https://x", "auth": "oauth"})


class TestMcpCommandDispatchLoginReauth:
    def test_dispatches_login(self, tmp_path):
        from daedalus_cli.mcp_config import mcp_command
        _seed_config(tmp_path, {"s": {"url": "https://x", "auth": "oauth"}})
        with patch("daedalus_cli.mcp_config.cmd_mcp_login") as mock_login:
            mcp_command(_make_args(mcp_action="login", name="s"))
        mock_login.assert_called_once()

    def test_dispatches_reauth(self, tmp_path):
        from daedalus_cli.mcp_config import mcp_command
        _seed_config(tmp_path, {"s": {"url": "https://x", "auth": "oauth"}})
        with patch("daedalus_cli.mcp_config.cmd_mcp_reauth") as mock_reauth:
            mcp_command(_make_args(mcp_action="reauth", name="s", all=False))
        mock_reauth.assert_called_once()
