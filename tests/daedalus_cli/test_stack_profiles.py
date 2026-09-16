"""`daedalus doctor start a3b` serves the MoE; anything else serves the dense model.

Real stack code against a scratch DAEDALUS_HOME. Nothing here launches a model:
start_one is replaced by a guard that fails the test.
"""

import argparse
import subprocess

import pytest

from daedalus_cli import stack as S


def _conf(**over):
    values = S._parse_conf(S.DEFAULT_CONF)
    values.update({k: str(v) for k, v in over.items()})
    return S.StackConf(values)


def _parser():
    p = argparse.ArgumentParser()
    S.register_cli(p)
    return p


@pytest.fixture
def no_launch(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("a model server was launched")
    monkeypatch.setattr(S, "start_one", refuse)


@pytest.fixture
def fake_main():
    S.run_dir().mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(["sleep", "60"])
    S.pid_file("main").write_text(str(p.pid))
    yield p
    p.kill()
    p.wait()


def test_start_defaults_to_dense_and_accepts_a3b():
    p = _parser()
    assert p.parse_args(["start"]).model is None
    assert p.parse_args(["start", "a3b"]).model == "a3b"
    assert p.parse_args(["restart", "dense"]).model == "dense"
    with pytest.raises(SystemExit):
        p.parse_args(["start", "gpt-5"])


def test_a3b_argv_is_the_moe_on_the_main_port_and_context():
    argv = S._a3b_argv(_conf(MAIN_PORT=8080, MAIN_CTX=262144, MAIN_SLOTS=2), "/m/a3b.gguf")
    joined = " ".join(argv)
    assert argv[argv.index("--model") + 1] == "/m/a3b.gguf"
    assert argv[argv.index("--port") + 1] == "8080"
    assert argv[argv.index("--ctx-size") + 1] == "262144"
    assert argv[argv.index("--n-cpu-moe") + 1] == "18"
    assert "draft-mtp" in joined
    assert "-kvu" in argv and "--no-cache-idle-slots" in argv
    # Dense-only machinery must not leak into the MoE launch.
    assert "--kv-stream-stage-mib" not in argv
    assert "--model-draft" not in argv


def test_a3b_moe_offload_is_configurable():
    argv = S._a3b_argv(_conf(A3B_N_CPU_MOE=24), "/m/a3b.gguf")
    assert argv[argv.index("--n-cpu-moe") + 1] == "24"


def test_main_launch_picks_the_argv_for_the_profile(monkeypatch):
    monkeypatch.setattr(S, "profile_model", lambda conf, profile: (f"/m/{profile}.gguf", ""))
    _m, dense_argv, _e = S.main_launch(_conf(), "dense")
    _m, a3b_argv, _e = S.main_launch(_conf(), "a3b")
    assert "--n-cpu-moe" not in dense_argv
    assert "--n-cpu-moe" in a3b_argv


def test_start_refuses_a_different_model_while_main_runs(fake_main, no_launch, monkeypatch, capsys):
    monkeypatch.setattr(S, "profile_model", lambda conf, profile: (f"/m/{profile}.gguf", ""))
    monkeypatch.setattr(S.os, "access", lambda *a, **k: True)
    S.profile_file().write_text("dense")
    assert S.cmd_start(argparse.Namespace(model="a3b")) == 1
    out = capsys.readouterr().out
    assert "already serving dense" in out and "daedalus doctor restart a3b" in out


def test_restart_without_a_model_keeps_the_running_one(monkeypatch):
    S.run_dir().mkdir(parents=True, exist_ok=True)
    S.profile_file().write_text("a3b")
    seen = {}
    monkeypatch.setattr(S, "cmd_stop", lambda args=None: 0)
    monkeypatch.setattr(S, "cmd_start", lambda args=None: seen.setdefault("model", args.model) and 0)
    S.cmd_restart(argparse.Namespace(model=None))
    assert seen["model"] == "a3b"


def test_restart_with_a_model_switches(monkeypatch):
    S.run_dir().mkdir(parents=True, exist_ok=True)
    S.profile_file().write_text("a3b")
    seen = {}
    monkeypatch.setattr(S, "cmd_stop", lambda args=None: 0)
    monkeypatch.setattr(S, "cmd_start", lambda args=None: seen.setdefault("model", args.model) and 0)
    S.cmd_restart(argparse.Namespace(model="dense"))
    assert seen["model"] == "dense"


def test_status_names_the_running_model(fake_main, monkeypatch, capsys):
    monkeypatch.setattr(S, "port_up", lambda *a, **k: True)
    S.profile_file().write_text("a3b")
    S.cmd_status(conf=_conf(AUX_ENABLED=0))
    assert "main (a3b)" in capsys.readouterr().out


def test_status_reports_a_port_sharing_aux_as_slot_zero(fake_main, monkeypatch, capsys):
    monkeypatch.setattr(S, "port_up", lambda *a, **k: True)
    S.cmd_status(conf=_conf(AUX_ENABLED=1, MAIN_PORT=8080, AUX_PORT=8080))
    out = capsys.readouterr().out
    assert "aux  slot 0 of main" in out
    assert "not started by daedalus" not in out


def test_stop_forgets_the_profile(monkeypatch):
    S.run_dir().mkdir(parents=True, exist_ok=True)
    S.profile_file().write_text("a3b")
    S.cmd_stop()
    assert S.running_profile() == ""


def test_wait_ready_does_not_accept_a_loading_server(monkeypatch):
    # llama-server answers 503 while loading; that is not ready.
    monkeypatch.setattr(S, "health_ok", lambda *a, **k: False)
    monkeypatch.setattr(S, "alive", lambda pid: True)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    assert S.wait_ready("main", "127.0.0.1", 8080, seconds=4) is False
