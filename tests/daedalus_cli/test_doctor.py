"""Tests for daedalus_cli.doctor."""

import os
import sys
import types
from argparse import Namespace
from types import SimpleNamespace

import pytest

import daedalus_cli.doctor as doctor
import daedalus_cli.gateway as gateway_cli
from daedalus_cli import doctor as doctor_mod
from daedalus_cli.doctor import _has_provider_env_config


class TestProviderEnvDetection:
    def test_detects_openai_api_key(self):
        content = "OPENAI_BASE_URL=http://localhost:1234/v1\nOPENAI_API_KEY=***"
        assert _has_provider_env_config(content)

    def test_detects_custom_endpoint_without_openrouter_key(self):
        content = "OPENAI_BASE_URL=http://localhost:8080/v1\n"
        assert _has_provider_env_config(content)

    def test_returns_false_when_no_provider_settings(self):
        content = "TERMINAL_ENV=local\n"
        assert not _has_provider_env_config(content)


def test_run_doctor_sets_interactive_env_for_tool_checks(monkeypatch, tmp_path):
    """Doctor should present CLI-gated tools as available in CLI context."""
    project_root = tmp_path / "project"
    daedalus_home = tmp_path / ".daedalus"
    project_root.mkdir()
    daedalus_home.mkdir()

    monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(doctor_mod, "DAEDALUS_HOME", daedalus_home)
    monkeypatch.delenv("DAEDALUS_INTERACTIVE", raising=False)

    seen = {}

    def fake_check_tool_availability(*args, **kwargs):
        seen["interactive"] = os.getenv("DAEDALUS_INTERACTIVE")
        raise SystemExit(0)

    fake_model_tools = types.SimpleNamespace(
        check_tool_availability=fake_check_tool_availability,
        TOOLSET_REQUIREMENTS={},
    )
    monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

    with pytest.raises(SystemExit):
        doctor_mod.run_doctor(Namespace(fix=False))

    assert seen["interactive"] == "1"


def test_check_gateway_service_linger_warns_when_disabled(monkeypatch, tmp_path, capsys):
    unit_path = tmp_path / "daedalus-gateway.service"
    unit_path.write_text("[Unit]\n")

    monkeypatch.setattr(gateway_cli, "is_linux", lambda: True)
    monkeypatch.setattr(gateway_cli, "get_systemd_unit_path", lambda: unit_path)
    monkeypatch.setattr(gateway_cli, "get_systemd_linger_status", lambda: (False, ""))

    issues = []
    doctor._check_gateway_service_linger(issues)

    out = capsys.readouterr().out
    assert "Gateway Service" in out
    assert "Systemd linger disabled" in out
    assert "loginctl enable-linger" in out
    assert issues == [
        "Enable linger for the gateway user service: sudo loginctl enable-linger $USER"
    ]


def test_check_gateway_service_linger_skips_when_service_not_installed(monkeypatch, tmp_path, capsys):
    unit_path = tmp_path / "missing.service"

    monkeypatch.setattr(gateway_cli, "is_linux", lambda: True)
    monkeypatch.setattr(gateway_cli, "get_systemd_unit_path", lambda: unit_path)

    issues = []
    doctor._check_gateway_service_linger(issues)

    out = capsys.readouterr().out
    assert out == ""
    assert issues == []


def _write_sqlite_header(path, format_version: int) -> None:
    """Write a minimal valid SQLite file header with the given format-version byte."""
    header = bytearray(100)
    header[0:16] = b"SQLite format 3\x00"
    header[18] = format_version  # write version: 1=rollback, 2=WAL
    header[19] = format_version  # read version
    path.write_bytes(bytes(header))


def test_read_journal_mode_detects_wal(tmp_path):
    db = tmp_path / "state.db"
    _write_sqlite_header(db, 2)
    mode, error = doctor._read_journal_mode(db)
    assert mode == "wal"
    assert error is None


def test_read_journal_mode_detects_rollback(tmp_path):
    db = tmp_path / "state.db"
    _write_sqlite_header(db, 1)
    mode, error = doctor._read_journal_mode(db)
    assert mode == "rollback"
    assert error is None


def test_read_journal_mode_missing_file(tmp_path):
    mode, error = doctor._read_journal_mode(tmp_path / "does_not_exist.db")
    assert mode is None
    assert error is not None


def test_report_database_journal_modes_warns_when_wal_and_vulnerable(tmp_path, capsys):
    _write_sqlite_header(tmp_path / "state.db", 2)
    # (0, 0, 0) sorts below every fixed version -- always vulnerable per
    # is_sqlite_wal_reset_vulnerable's own version comparison.
    doctor._report_database_journal_modes(tmp_path, version_info=(3, 45, 0))
    out = capsys.readouterr().out
    assert "state.db is in WAL mode" in out
    assert "WAL-reset bug" in out


def test_report_database_journal_modes_quiet_when_not_vulnerable(tmp_path, capsys):
    _write_sqlite_header(tmp_path / "state.db", 2)
    doctor._report_database_journal_modes(tmp_path, version_info=(3, 51, 3))
    out = capsys.readouterr().out
    assert "WAL journal mode" in out
    assert "exposed" not in out


def test_check_certificates_ok(monkeypatch, capsys):
    import agent.ssl_guard as ssl_guard_mod
    monkeypatch.setattr(ssl_guard_mod, "verify_ca_bundle_with_fallback", lambda: None)
    doctor.check_certificates(should_fix=False, issues=[])
    out = capsys.readouterr().out
    assert "SSL CA certificate bundle is valid" in out


def test_check_certificates_broken_no_fix_appends_issue(monkeypatch, capsys):
    import agent.ssl_guard as ssl_guard_mod
    from agent.errors import SSLConfigurationError

    def _raise():
        raise SSLConfigurationError("cacert.pem missing")

    monkeypatch.setattr(ssl_guard_mod, "verify_ca_bundle_with_fallback", _raise)
    issues = []
    doctor.check_certificates(should_fix=False, issues=issues)
    out = capsys.readouterr().out
    assert "SSL CA certificate bundle is broken" in out
    assert len(issues) == 1
    assert "daedalus doctor --fix" in issues[0]


# ── Memory provider section (doctor should only check the *active* provider) ──


class TestDoctorMemoryProviderSection:
    """The ◆ Memory Provider section should respect memory.provider config."""

    def _make_daedalus_home(self, tmp_path, provider=""):
        """Create a minimal DAEDALUS_HOME with config.yaml."""
        home = tmp_path / ".daedalus"
        home.mkdir(parents=True, exist_ok=True)
        import yaml
        config = {"memory": {"provider": provider}} if provider else {"memory": {}}
        (home / "config.yaml").write_text(yaml.dump(config))
        return home

    def _run_doctor_and_capture(self, monkeypatch, tmp_path, provider=""):
        """Run doctor and capture stdout."""
        home = self._make_daedalus_home(tmp_path, provider)
        monkeypatch.setattr(doctor_mod, "DAEDALUS_HOME", home)
        monkeypatch.setattr(doctor_mod, "PROJECT_ROOT", tmp_path / "project")
        monkeypatch.setattr(doctor_mod, "_DHH", str(home))
        (tmp_path / "project").mkdir(exist_ok=True)

        # Stub tool availability (returns empty) so doctor runs past it
        fake_model_tools = types.SimpleNamespace(
            check_tool_availability=lambda *a, **kw: ([], []),
            TOOLSET_REQUIREMENTS={},
        )
        monkeypatch.setitem(sys.modules, "model_tools", fake_model_tools)

        # Stub auth checks to avoid real API calls
        try:
            from daedalus_cli import auth as _auth_mod
            monkeypatch.setattr(_auth_mod, "get_nous_auth_status", lambda: {})
            monkeypatch.setattr(_auth_mod, "get_codex_auth_status", lambda: {})
        except Exception:
            pass

        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            doctor_mod.run_doctor(Namespace(fix=False))
        return buf.getvalue()

    def test_no_provider_shows_builtin_ok(self, monkeypatch, tmp_path):
        out = self._run_doctor_and_capture(monkeypatch, tmp_path, provider="")
        assert "Memory Provider" in out
        assert "Built-in memory active" in out
        # Should NOT mention Honcho or Mem0 errors
        assert "Honcho API key" not in out
        assert "Mem0" not in out

    def test_builtin_provider_active(self, monkeypatch, tmp_path):
        out = self._run_doctor_and_capture(monkeypatch, tmp_path, provider="builtin")
        assert "Memory Provider" in out
        assert "Built-in memory active" in out
