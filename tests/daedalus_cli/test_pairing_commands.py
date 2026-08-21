"""Tests for daedalus_cli/pairing.py — CLI-level pairing command output."""

from unittest.mock import patch

from gateway.pairing import PairingStore, MAX_FAILED_ATTEMPTS
from daedalus_cli.pairing import _cmd_approve


class TestCmdApproveLockoutMessage:
    def test_unknown_code_gives_generic_not_found_message(self, tmp_path, capsys):
        with patch("gateway.pairing.PAIRING_DIR", tmp_path):
            store = PairingStore()
            store.generate_code("telegram", "user1")

            _cmd_approve(store, "telegram", "WRONGCODE")

        out = capsys.readouterr().out
        assert "not found or expired" in out
        assert "locked out" not in out

    def test_lockout_gives_disambiguated_message_not_generic_not_found(self, tmp_path, capsys):
        with patch("gateway.pairing.PAIRING_DIR", tmp_path):
            store = PairingStore()
            store.generate_code("telegram", "user1")

            for _ in range(MAX_FAILED_ATTEMPTS):
                _cmd_approve(store, "telegram", "WRONGCODE")

        out = capsys.readouterr().out
        assert "locked out" in out
        assert "minute" in out
        # The final call must NOT still say "not found or expired" — that's
        # the misleading message this fix replaces once a lockout is active.
        last_call_output = out.strip().splitlines()[-3:]
        assert not any("not found or expired" in line for line in last_call_output)

    def test_valid_code_approves_normally(self, tmp_path, capsys):
        with patch("gateway.pairing.PAIRING_DIR", tmp_path):
            store = PairingStore()
            code = store.generate_code("telegram", "user1")

            _cmd_approve(store, "telegram", code)

        out = capsys.readouterr().out
        assert "Approved!" in out
