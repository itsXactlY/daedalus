"""Shared fixtures for the daedalus test suite."""

import asyncio
import os
import signal
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Point DAEDALUS_HOME at a throwaway home before any module is imported.

    The per-test fixture runs too late for import-time side effects: cli.py
    calls setup_logging() while it is being imported during collection, and
    that handler is already writing to the operator's real agent.log by the
    time the first fixture executes.
    """
    import os
    import tempfile

    session_home = tempfile.mkdtemp(prefix="daedalus-test-home-")
    os.environ["DAEDALUS_HOME"] = session_home
    for sub in ("sessions", "cron", "memories", "skills", "logs"):
        os.makedirs(os.path.join(session_home, sub), exist_ok=True)
    _detach_foreign_file_handlers(session_home)
    config._daedalus_session_home = session_home


def _detach_foreign_file_handlers(fake_home):
    """Drop root log handlers that write outside the test's DAEDALUS_HOME.

    cli.py calls setup_logging() at import time with no home argument, so the
    first test that imports it attaches a RotatingFileHandler to the operator's
    real ~/.daedalus/logs/agent.log — and every later test keeps writing there.
    A regression run left 906 lines of test-model and test.example.com in a live
    agent.log this way. Redirecting DAEDALUS_HOME is not enough because the
    handler already holds an open path.
    """
    import logging
    from logging.handlers import RotatingFileHandler

    root = logging.getLogger()
    keep = str(fake_home)
    for handler in list(root.handlers):
        target = getattr(handler, "baseFilename", None)
        if not target:
            continue
        if not str(target).startswith(keep):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


@pytest.fixture(autouse=True)
def _isolate_daedalus_home(tmp_path, monkeypatch):
    """Redirect DAEDALUS_HOME to a temp dir so tests never write to ~/.daedalus/."""
    fake_home = tmp_path / "daedalus_test"
    fake_home.mkdir()
    (fake_home / "sessions").mkdir()
    (fake_home / "cron").mkdir()
    (fake_home / "memories").mkdir()
    (fake_home / "skills").mkdir()
    monkeypatch.setenv("DAEDALUS_HOME", str(fake_home))
    _detach_foreign_file_handlers(fake_home)
    try:
        import daedalus_cli.plugins as _plugins_mod
        monkeypatch.setattr(_plugins_mod, "_plugin_manager", None)
    except Exception:
        pass
    monkeypatch.delenv("DAEDALUS_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("DAEDALUS_SESSION_CHAT_ID", raising=False)
    monkeypatch.delenv("DAEDALUS_SESSION_CHAT_NAME", raising=False)
    monkeypatch.delenv("DAEDALUS_GATEWAY_SESSION", raising=False)


@pytest.fixture()
def tmp_dir(tmp_path):
    """Provide a temporary directory that is cleaned up automatically."""
    return tmp_path


@pytest.fixture()
def mock_config():
    """Return a minimal daedalus config dict suitable for unit tests."""
    return {
        "model": "test/mock-model",
        "toolsets": ["terminal", "file"],
        "max_turns": 10,
        "terminal": {
            "backend": "local",
            "cwd": "/tmp",
            "timeout": 30,
        },
        "compression": {"enabled": False},
        "memory": {"memory_enabled": False, "user_profile_enabled": False},
        "command_allowlist": [],
    }



def _timeout_handler(signum, frame):
    raise TimeoutError("Test exceeded 30 second timeout")

@pytest.fixture(autouse=True)
def _ensure_current_event_loop(request):
    """Provide a default event loop for sync tests that call get_event_loop().

    Python 3.11+ no longer guarantees a current loop for plain synchronous tests.
    A number of gateway tests still use asyncio.get_event_loop().run_until_complete(...).
    Ensure they always have a usable loop without interfering with pytest-asyncio's
    own loop management for @pytest.mark.asyncio tests.
    """
    if request.node.get_closest_marker("asyncio") is not None:
        yield
        return

    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        loop = None

    created = loop is None or loop.is_closed()
    if created:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        yield
    finally:
        if created and loop is not None:
            try:
                loop.close()
            finally:
                asyncio.set_event_loop(None)


@pytest.fixture(autouse=True)
def _enforce_test_timeout():
    """Kill any individual test that takes longer than 30 seconds.
    SIGALRM is Unix-only; skip on Windows."""
    if sys.platform == "win32":
        yield
        return
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(30)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, old)



_OS_MARKS = {
    "linux_only": (
        lambda: sys.platform.startswith("linux"),
        "Linux",
    ),
    "macos_only": (
        lambda: sys.platform == "darwin",
        "macOS",
    ),
    "windows_only": (
        lambda: sys.platform == "win32",
        "native Windows",
    ),
}


def pytest_collection_modifyitems(config, items):  # noqa: D401 — pytest hook
    """Skip tests marked for a host OS other than the one running the suite."""
    for mark_name, (is_host, label) in _OS_MARKS.items():
        if is_host():
            continue
        skip_os = pytest.mark.skip(
            reason=f"{label}-only test (marked {mark_name}); host is {sys.platform}"
        )
        for item in items:
            if item.get_closest_marker(mark_name) is not None:
                item.add_marker(skip_os)
