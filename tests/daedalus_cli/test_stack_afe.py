"""The doctor's AFE rules: never two models, never on a taken card, and a
refusal mazemaker can read instead of a port that never opens.

Real stack/stack_afe code against a scratch DAEDALUS_HOME and MAZEMAKER_DIR.
`sleep` processes stand in for servers. Launching anything real is replaced
by a guard that fails the test, so a gate bug cannot load a model.
"""

import subprocess
import time

import pytest

from daedalus_cli import stack as S
from daedalus_cli import stack_afe as A


@pytest.fixture
def mm_dir(tmp_path, monkeypatch):
    d = tmp_path / "mazemaker"
    monkeypatch.setenv("MAZEMAKER_DIR", str(d))
    return d


@pytest.fixture
def no_launch(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a model server was launched")
    monkeypatch.setattr(S, "start_one", refuse)


@pytest.fixture
def fake_server():
    procs = []

    def spawn(name):
        S.run_dir().mkdir(parents=True, exist_ok=True)
        p = subprocess.Popen(["sleep", "60"])
        procs.append(p)
        S.pid_file(name).write_text(str(p.pid))
        return p

    yield spawn
    for p in procs:
        p.kill()
        p.wait()


def _conf(**over):
    values = S._parse_conf(S.DEFAULT_CONF)
    values.update({k: str(v) for k, v in over.items()})
    return S.StackConf(values)


def test_afe_refuses_beside_the_daedalus_stack(fake_server, monkeypatch):
    monkeypatch.setattr(A, "vram_used_mib", lambda: 500)
    monkeypatch.setattr(A, "model", lambda conf: "/models/afe.gguf")
    fake_server("main")
    reasons = A.blockers(_conf(AUX_ENABLED=0))
    assert any(r.startswith("never two models") and "main" in r for r in reasons)


def test_afe_refuses_when_the_card_is_already_taken(monkeypatch):
    monkeypatch.setattr(A, "vram_used_mib", lambda: 12000)
    monkeypatch.setattr(A, "model", lambda conf: "/models/afe.gguf")
    monkeypatch.setattr(S, "port_up", lambda *a, **k: False)
    reasons = A.blockers(_conf(AFE_VRAM_BLOCK_MIB=10240))
    assert any("12000 MiB VRAM already in use" in r for r in reasons)


def test_afe_refuses_without_the_model_on_disk(monkeypatch):
    monkeypatch.setattr(A, "vram_used_mib", lambda: 500)
    monkeypatch.setattr(S, "port_up", lambda *a, **k: False)
    monkeypatch.setattr(A, "model", lambda conf: "")
    reasons = A.blockers(_conf())
    assert any("AFE model not on disk" in r and "daedalus doctor afe fetch" in r for r in reasons)


def test_nothing_blocks_a_free_card_with_the_model_present(monkeypatch):
    monkeypatch.setattr(A, "vram_used_mib", lambda: 1400)
    monkeypatch.setattr(S, "port_up", lambda *a, **k: False)
    monkeypatch.setattr(A, "model", lambda conf: "/models/afe.gguf")
    monkeypatch.setattr(S.os, "access", lambda *a, **k: True)
    assert A.blockers(_conf()) == []


def test_main_stack_refuses_while_afe_serves(fake_server, no_launch, monkeypatch, capsys):
    fake_server("afe")
    assert S.cmd_start() == 1
    assert "never two models" in capsys.readouterr().out


def test_wake_refusal_is_written_where_mazemaker_reads_it(mm_dir, no_launch, monkeypatch):
    monkeypatch.setattr(A, "vram_used_mib", lambda: 14000)
    monkeypatch.setattr(A, "afe_serving", lambda conf: False)
    A.request_file().parent.mkdir(parents=True, exist_ok=True)
    A.request_file().write_text("")

    assert A.cmd_wake() == 1

    assert not A.request_file().exists(), "request must be consumed or the path unit loops"
    reason = A.failed_file().read_text()
    assert "14000 MiB VRAM already in use" in reason
    assert A.last_used_file().exists()


def test_a_successful_wake_clears_an_old_refusal(mm_dir, monkeypatch):
    A.report_failure("stale refusal")
    monkeypatch.setattr(A, "start", lambda conf, ready_timeout=None: (True, "started"))
    assert A.cmd_wake() == 0
    assert not A.failed_file().exists()


def test_idle_check_stops_only_an_idle_afe(mm_dir, fake_server, monkeypatch):
    p = fake_server("afe")
    monkeypatch.setattr(A, "_unit_active", lambda unit: False)
    A.last_used_file().parent.mkdir(parents=True, exist_ok=True)

    A.last_used_file().write_text(str(time.time()))
    A.cmd_idle_check()
    assert p.poll() is None, "a recently used AFE server was stopped"

    A.last_used_file().write_text(str(time.time() - 3600))
    A.cmd_idle_check()
    p.wait(timeout=15)
    assert not S.pid_file("afe").exists()


def test_idle_check_never_stops_it_during_the_afe_window(mm_dir, fake_server, monkeypatch):
    p = fake_server("afe")
    monkeypatch.setattr(A, "_unit_active", lambda unit: unit == "mazemaker-afe-window.service")
    A.last_used_file().parent.mkdir(parents=True, exist_ok=True)
    A.last_used_file().write_text(str(time.time() - 3600))
    A.cmd_idle_check()
    assert p.poll() is None
