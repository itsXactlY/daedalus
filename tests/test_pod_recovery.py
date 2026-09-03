import importlib

import pytest


@pytest.fixture
def mz(monkeypatch):
    """A freshly loaded plugin with recovery pointed at a harmless unit."""
    monkeypatch.setenv("MM_RECOVERY_UNIT", "probe-unit.service")
    monkeypatch.setenv("MM_RECOVERY_MIN_INTERVAL_S", "600")
    monkeypatch.setenv("MM_RECOVERY_MAX_ATTEMPTS", "3")
    # The recovery refuses to spawn anything while PYTEST_CURRENT_TEST is set,
    # which is exactly what we want everywhere except in the tests that check
    # the real path. Those clear it deliberately.
    import plugins.memory.mazemaker as M

    importlib.reload(M)
    yield M
    importlib.reload(M)


class _Result:
    def __init__(self, rc=0, err=""):
        self.returncode = rc
        self.stderr = err
        self.stdout = ""


class TestAWedgedPodGetsRestarted:
    """A wedged pod is invisible to every supervisor it has.

    The container stays Up, the unit stays active, the socket stays open, and
    the front accepts connections it never finishes. Four hours of that were
    observed on 2026-09-03 with everything reporting healthy. The only layer
    that can tell is the one making the calls.
    """

    def _run(self, mz, monkeypatch, result=None, calls=None):
        import subprocess

        # pytest re-sets PYTEST_CURRENT_TEST before every phase, so the guard
        # has to come off here in the body rather than in the fixture.
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        def fake(cmd, **kw):
            if calls is not None:
                calls.append(cmd)
            return result or _Result()

        monkeypatch.setattr(subprocess, "run", fake)
        monkeypatch.setattr("shutil.which", lambda _n: "/usr/bin/systemctl")
        return mz._attempt_pod_recovery()

    def test_it_restarts_the_configured_unit(self, mz, monkeypatch):
        calls = []
        assert self._run(mz, monkeypatch, calls=calls) is True
        assert calls and "probe-unit.service" in calls[0]
        assert "restart" in calls[0]

    def test_a_second_attempt_waits_for_the_interval(self, mz, monkeypatch):
        assert self._run(mz, monkeypatch) is True
        assert self._run(mz, monkeypatch) is False

    def test_it_gives_up_rather_than_looping(self, mz, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        mz._recovery_state["attempts"] = mz._RECOVERY_MAX_ATTEMPTS
        mz._recovery_state["last"] = 0.0
        assert self._run(mz, monkeypatch) is False

    def test_a_failed_restart_is_reported_not_swallowed(self, mz, monkeypatch):
        assert self._run(mz, monkeypatch, result=_Result(5, "no such unit")) is False

    def test_an_empty_unit_disables_it(self, monkeypatch):
        monkeypatch.setenv("MM_RECOVERY_UNIT", "")
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        import plugins.memory.mazemaker as M

        importlib.reload(M)
        try:
            assert M._attempt_pod_recovery() is False
        finally:
            importlib.reload(M)

    def test_it_does_nothing_without_systemctl(self, mz, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setattr("shutil.which", lambda _n: None)
        assert mz._attempt_pod_recovery() is False

    def test_declaring_a_wedge_triggers_it(self, mz, monkeypatch):
        fired = []
        monkeypatch.setattr(mz, "_attempt_pod_recovery", lambda: fired.append(1) or True)
        health = mz._PodHealth()
        for _ in range(mz._WEDGE_FAIL_THRESHOLD):
            health.record_fail("mazemaker_recall", TimeoutError("timed out"))
        assert fired, "a confirmed wedge must attempt recovery"

    def test_a_single_failure_does_not_trigger_it(self, mz, monkeypatch):
        fired = []
        monkeypatch.setattr(mz, "_attempt_pod_recovery", lambda: fired.append(1) or True)
        mz._PodHealth().record_fail("mazemaker_recall", TimeoutError("timed out"))
        assert not fired


class TestTheTestSuiteCannotTouchTheMachine:
    """Detection is what the tests are for. The side effect is not theirs.

    Driving record_fail past the wedge threshold used to restart a real
    systemd unit, which brought a deliberately stopped pod back up mid-run.
    """

    def test_recovery_is_inert_under_pytest(self, mz, monkeypatch):
        import subprocess

        calls = []
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd))
        monkeypatch.setattr("shutil.which", lambda _n: "/usr/bin/systemctl")
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_x (call)")
        assert mz._attempt_pod_recovery() is False
        assert not calls, "no process may be spawned from a test run"

    def test_a_wedge_still_reports_under_pytest(self, mz, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_x (call)")
        health = mz._PodHealth()
        for _ in range(mz._WEDGE_FAIL_THRESHOLD):
            health.record_fail("mazemaker_recall", TimeoutError("timed out"))
        assert health.is_wedged(), "detection must keep working, only the restart is suppressed"
