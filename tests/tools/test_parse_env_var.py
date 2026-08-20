"""Tests for _parse_env_var and _get_env_config env-var validation."""

import json
from unittest.mock import patch

import pytest

import sys
import tools.terminal_tool  # noqa: F401 -- ensure module is loaded
_tt_mod = sys.modules["tools.terminal_tool"]
from tools.terminal_tool import _parse_env_var


class TestParseEnvVar:
    """Unit tests for _parse_env_var."""

    # -- valid values work normally --

    def test_valid_int(self):
        with patch.dict("os.environ", {"TERMINAL_TIMEOUT": "300"}):
            assert _parse_env_var("TERMINAL_TIMEOUT", "180") == 300

    def test_valid_float(self):
        with patch.dict("os.environ", {"TERMINAL_CONTAINER_CPU": "2.5"}):
            assert _parse_env_var("TERMINAL_CONTAINER_CPU", "1", float, "number") == 2.5

    def test_valid_json(self):
        # _parse_env_var is backend-agnostic; exercise json parsing with a
        # generic var name (docker_volumes json parsing was removed with the
        # docker backend).
        with patch.dict("os.environ", {"TERMINAL_TEST_JSON_VAR": '["/host:/container"]'}):
            result = _parse_env_var("TERMINAL_TEST_JSON_VAR", "[]", json.loads, "valid JSON")
            assert result == ["/host:/container"]

    def test_falls_back_to_default(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove the var if it exists, rely on default
            import os
            env = os.environ.copy()
            env.pop("TERMINAL_TIMEOUT", None)
            with patch.dict("os.environ", env, clear=True):
                assert _parse_env_var("TERMINAL_TIMEOUT", "180") == 180

    # -- invalid int raises ValueError with env var name --

    def test_invalid_int_raises_with_var_name(self):
        with patch.dict("os.environ", {"TERMINAL_TIMEOUT": "5m"}):
            with pytest.raises(ValueError, match="TERMINAL_TIMEOUT"):
                _parse_env_var("TERMINAL_TIMEOUT", "180")

    def test_invalid_int_includes_bad_value(self):
        with patch.dict("os.environ", {"TERMINAL_SSH_PORT": "ssh"}):
            with pytest.raises(ValueError, match="ssh"):
                _parse_env_var("TERMINAL_SSH_PORT", "22")

    # -- invalid JSON raises ValueError with env var name --

    def test_invalid_json_raises_with_var_name(self):
        with patch.dict("os.environ", {"TERMINAL_TEST_JSON_VAR": "/host:/container"}):
            with pytest.raises(ValueError, match="TERMINAL_TEST_JSON_VAR"):
                _parse_env_var("TERMINAL_TEST_JSON_VAR", "[]", json.loads, "valid JSON")

    def test_invalid_json_includes_type_label(self):
        with patch.dict("os.environ", {"TERMINAL_TEST_JSON_VAR": "not json"}):
            with pytest.raises(ValueError, match="valid JSON"):
                _parse_env_var("TERMINAL_TEST_JSON_VAR", "[]", json.loads, "valid JSON")
