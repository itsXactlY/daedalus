"""Tests for _install_hangup_protection / _finalize_update_output (daedalus_cli/main.py).

Regression coverage for: daedalus update had no SIGHUP protection, so a
dropped SSH/terminal session mid-update could kill the process (default
SIGHUP disposition) and leave the venv/checkout half-updated.
"""

import signal
import sys

from daedalus_cli.main import (
    _install_hangup_protection,
    _finalize_update_output,
    _UpdateOutputStream,
)


class TestInstallHangupProtection:
    def test_ignores_sighup_in_non_gateway_mode(self):
        prev = signal.getsignal(signal.SIGHUP)
        try:
            state = _install_hangup_protection(gateway_mode=False)
            assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
            _finalize_update_output(state)
        finally:
            signal.signal(signal.SIGHUP, prev)

    def test_wraps_and_restores_stdio(self):
        orig_stdout, orig_stderr = sys.stdout, sys.stderr
        prev_sighup = signal.getsignal(signal.SIGHUP)
        try:
            state = _install_hangup_protection(gateway_mode=False)
            assert isinstance(sys.stdout, _UpdateOutputStream)
            assert isinstance(sys.stderr, _UpdateOutputStream)
            _finalize_update_output(state)
            assert sys.stdout is orig_stdout
            assert sys.stderr is orig_stderr
        finally:
            sys.stdout, sys.stderr = orig_stdout, orig_stderr
            signal.signal(signal.SIGHUP, prev_sighup)

    def test_gateway_mode_is_a_no_op(self):
        """Gateway-spawned updates are already detached from a terminal."""
        prev_sighup = signal.getsignal(signal.SIGHUP)
        orig_stdout = sys.stdout
        try:
            state = _install_hangup_protection(gateway_mode=True)
            assert signal.getsignal(signal.SIGHUP) is prev_sighup
            assert sys.stdout is orig_stdout
            assert state.get("installed") is False
            _finalize_update_output(state)
        finally:
            signal.signal(signal.SIGHUP, prev_sighup)
            sys.stdout = orig_stdout


class TestUpdateOutputStream:
    def test_write_mirrors_to_log_and_original(self, tmp_path):
        log_path = tmp_path / "update.log"
        log_file = open(log_path, "a", encoding="utf-8")
        captured = []

        class _Fake:
            def write(self, data):
                captured.append(data)

        stream = _UpdateOutputStream(_Fake(), log_file)
        stream.write("hello\n")
        log_file.flush()

        assert captured == ["hello\n"]
        assert log_path.read_text() == "hello\n"
        log_file.close()

    def test_broken_original_pipe_does_not_raise(self, tmp_path):
        log_path = tmp_path / "update.log"
        log_file = open(log_path, "a", encoding="utf-8")

        class _Broken:
            def write(self, data):
                raise BrokenPipeError()

        stream = _UpdateOutputStream(_Broken(), log_file)
        # Must not raise, and must still record to the log.
        stream.write("still logged\n")
        log_file.flush()
        assert log_path.read_text() == "still logged\n"
        log_file.close()
