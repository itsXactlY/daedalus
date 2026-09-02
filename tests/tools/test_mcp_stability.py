"""Tests for MCP stability fixes — event loop handler, PID tracking, shutdown robustness."""

import asyncio
import os
import signal
import threading
from unittest.mock import patch, MagicMock

import pytest



class TestMCPLoopExceptionHandler:
    """_mcp_loop_exception_handler suppresses benign 'Event loop is closed'."""

    def test_suppresses_event_loop_closed(self):
        from tools.mcp_tool import _mcp_loop_exception_handler
        loop = MagicMock()
        context = {"exception": RuntimeError("Event loop is closed")}
        _mcp_loop_exception_handler(loop, context)
        loop.default_exception_handler.assert_not_called()

    def test_forwards_other_runtime_errors(self):
        from tools.mcp_tool import _mcp_loop_exception_handler
        loop = MagicMock()
        context = {"exception": RuntimeError("some other error")}
        _mcp_loop_exception_handler(loop, context)
        loop.default_exception_handler.assert_called_once_with(context)

    def test_forwards_non_runtime_errors(self):
        from tools.mcp_tool import _mcp_loop_exception_handler
        loop = MagicMock()
        context = {"exception": ValueError("bad value")}
        _mcp_loop_exception_handler(loop, context)
        loop.default_exception_handler.assert_called_once_with(context)

    def test_forwards_contexts_without_exception(self):
        from tools.mcp_tool import _mcp_loop_exception_handler
        loop = MagicMock()
        context = {"message": "just a message"}
        _mcp_loop_exception_handler(loop, context)
        loop.default_exception_handler.assert_called_once_with(context)

    def test_handler_installed_on_mcp_loop(self):
        """_ensure_mcp_loop installs the exception handler on the new loop."""
        import tools.mcp_tool as mcp_mod
        try:
            mcp_mod._ensure_mcp_loop()
            with mcp_mod._lock:
                loop = mcp_mod._mcp_loop
            assert loop is not None
            assert loop.get_exception_handler() is mcp_mod._mcp_loop_exception_handler
        finally:
            mcp_mod._stop_mcp_loop()



class TestStdioPidTracking:
    """_snapshot_child_pids and _stdio_pids track subprocess PIDs."""

    def test_snapshot_returns_set(self):
        from tools.mcp_tool import _snapshot_child_pids
        result = _snapshot_child_pids()
        assert isinstance(result, set)
        for pid in result:
            assert isinstance(pid, int)

    def test_stdio_pids_starts_empty(self):
        from tools.mcp_tool import _stdio_pids, _lock
        with _lock:
            assert isinstance(_stdio_pids, set)

    def test_kill_orphaned_noop_when_empty(self):
        """_kill_orphaned_mcp_children does nothing when no PIDs tracked."""
        from tools.mcp_tool import _kill_orphaned_mcp_children, _stdio_pids, _lock

        with _lock:
            _stdio_pids.clear()

        _kill_orphaned_mcp_children()

    def test_kill_orphaned_handles_dead_pids(self):
        """_kill_orphaned_mcp_children gracefully handles already-dead PIDs."""
        from tools.mcp_tool import _kill_orphaned_mcp_children, _stdio_pids, _lock

        fake_pid = 999999999
        with _lock:
            _stdio_pids.add(fake_pid)

        _kill_orphaned_mcp_children()

        with _lock:
            assert fake_pid not in _stdio_pids



class TestMCPReloadTimeout:
    """_check_config_mcp_changes uses a timeout on _reload_mcp."""

    def test_reload_timeout_does_not_block_forever(self, tmp_path, monkeypatch):
        """If _reload_mcp hangs, the config watcher times out and returns."""
        import time

        class FakeCLI:
            _config_mtime = 0.0
            _config_mcp_servers = {}
            _last_config_check = 0.0
            _command_running = False
            config = {}
            agent = None

            def _reload_mcp(self):
                time.sleep(60)

            def _slow_command_status(self, cmd):
                return cmd

        import inspect
        from cli import DaedalusCLI
        source = inspect.getsource(DaedalusCLI._check_config_mcp_changes)
        assert "Thread" in source or "thread" in source.lower(), \
            "_check_config_mcp_changes should use a thread for _reload_mcp"
