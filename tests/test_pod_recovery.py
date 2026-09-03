import importlib

import pytest


@pytest.fixture
def mz(monkeypatch):
    """A freshly loaded plugin with recovery pointed at a harmless unit."""
    monkeypatch.setenv("MM_RECOVERY_UNIT", "probe-unit.service")
    monkeypatch.setenv("MM_RECOVERY_MIN_INTERVAL_S", "600")
    monkeypatch.setenv("MM_RECOVERY_MAX_ATTEMPTS", "3")
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
        mz._recovery_state["attempts"] = mz._RECOVERY_MAX_ATTEMPTS
        mz._recovery_state["last"] = 0.0
        assert self._run(mz, monkeypatch) is False

    def test_a_failed_restart_is_reported_not_swallowed(self, mz, monkeypatch):
        assert self._run(mz, monkeypatch, result=_Result(5, "no such unit")) is False

    def test_an_empty_unit_disables_it(self, monkeypatch):
        monkeypatch.setenv("MM_RECOVERY_UNIT", "")
        import plugins.memory.mazemaker as M

        importlib.reload(M)
        try:
            assert M._attempt_pod_recovery() is False
        finally:
            importlib.reload(M)

    def test_it_does_nothing_without_systemctl(self, mz, monkeypatch):
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
