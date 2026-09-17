import pytest


@pytest.fixture
def mz():
    import plugins.memory.mazemaker as M

    return M


class _Result:
    def __init__(self, rc=0, err="", out=""):
        self.returncode = rc
        self.stderr = err
        self.stdout = out


class TestAWedgedPodIsReportedNeverRestarted:
    """A wedge names the broken unit. Nothing gets restarted.

    Restarting wonderland on a wedge never fixed one. On 2026-09-17 the fault
    was inside mcp, and each restart only dropped every other client's MCP
    session ("Session not found") while the pod stayed broken.
    """

    def _run(self, mz, monkeypatch, states):
        import subprocess

        # pytest re-sets PYTEST_CURRENT_TEST before every phase, so the guard
        # has to come off here in the body rather than in a fixture.
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            return _Result(out=states.get(cmd[-1], "active") + "\n")

        monkeypatch.setattr(subprocess, "run", fake)
        monkeypatch.setattr("shutil.which", lambda _n: "/usr/bin/systemctl")
        return mz._report_pod_fault(), calls

    def test_it_never_restarts_anything(self, mz, monkeypatch):
        _, calls = self._run(mz, monkeypatch, {"mazemaker-mcp.service": "failed"})
        assert calls
        assert all("is-active" in c for c in calls)
        assert not any(v in c for c in calls for v in ("restart", "start", "stop"))

    def test_it_names_the_unit_that_is_down(self, mz, monkeypatch):
        report, _ = self._run(mz, monkeypatch, {"mazemaker-mcp.service": "failed"})
        assert "mazemaker-mcp.service=failed" in report
        assert "wonderland" not in report
        assert "systemctl --user status mazemaker-mcp.service" in report

    def test_a_deliberately_stopped_pod_reads_as_inactive(self, mz, monkeypatch):
        states = {u: "inactive" for u in mz._POD_UNITS}
        report, _ = self._run(mz, monkeypatch, states)
        for unit in mz._POD_UNITS:
            assert f"{unit}=inactive" in report

    def test_all_units_active_points_inside_mcp(self, mz, monkeypatch):
        report, _ = self._run(mz, monkeypatch, {})
        assert "every unit is active" in report
        assert "podman logs" in report

    def test_it_does_nothing_without_systemctl(self, mz, monkeypatch):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setattr("shutil.which", lambda _n: None)
        assert mz._report_pod_fault() is None

    def test_declaring_a_wedge_triggers_it(self, mz, monkeypatch):
        fired = []
        monkeypatch.setattr(mz, "_report_pod_fault", lambda: fired.append(1))
        health = mz._PodHealth()
        for _ in range(mz._WEDGE_FAIL_THRESHOLD):
            health.record_fail("mazemaker_recall", TimeoutError("timed out"))
        assert fired, "a confirmed wedge must report the fault"

    def test_a_single_failure_does_not_trigger_it(self, mz, monkeypatch):
        fired = []
        monkeypatch.setattr(mz, "_report_pod_fault", lambda: fired.append(1))
        mz._PodHealth().record_fail("mazemaker_recall", TimeoutError("timed out"))
        assert not fired


class TestTheTestSuiteCannotTouchTheMachine:
    """Detection is what the tests are for. Spawning processes is not."""

    def test_report_is_inert_under_pytest(self, mz, monkeypatch):
        import subprocess

        calls = []
        monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: calls.append(cmd))
        monkeypatch.setattr("shutil.which", lambda _n: "/usr/bin/systemctl")
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_x (call)")
        assert mz._report_pod_fault() is None
        assert not calls, "no process may be spawned from a test run"

    def test_a_wedge_still_reports_under_pytest(self, mz, monkeypatch):
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_x (call)")
        health = mz._PodHealth()
        for _ in range(mz._WEDGE_FAIL_THRESHOLD):
            health.record_fail("mazemaker_recall", TimeoutError("timed out"))
        assert health.is_wedged(), "detection must keep working"
