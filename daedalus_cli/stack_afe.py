"""The mazemaker AFE model, owned by ``daedalus doctor`` like every other model.

mazemaker's nightly fact extraction (AFE Stage C) needs an LLM on
host :8888. That server used to be a hand-made systemd unit; when the unit
went, nothing served :8888 any more. Every extraction call then waited out a
420-second readiness poll, logged a warning and failed, and the pass burned
its whole two-hour window with zero facts. Nothing ever surfaced as an error.

This module makes the doctor the one place that knows about every model on
the card, so it can enforce the rules the card actually imposes:

* Never two models. AFE does not start while the daedalus stack (main, aux,
  vis) is serving, and ``daedalus doctor start`` does not start while AFE is.
* No AFE when the card is already taken: something answering on the main
  port, or more than AFE_VRAM_BLOCK_MIB (default 10 GiB) of VRAM in use.
* The model is downloaded beforehand (``daedalus doctor setup`` or
  ``daedalus doctor afe fetch``), never discovered missing mid-pass.

mazemaker cannot run host commands from inside its pod. It drops
``~/.mazemaker/sockets/llm-on-demand.request``, and a systemd path unit on
the host calls ``daedalus doctor afe wake``. When the doctor refuses or the
server fails, the reason is written to ``llm-on-demand.failed`` next to the
request. The in-pod caller reads that file and fails immediately with the
real reason, instead of polling a port that is never going to open.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from daedalus_cli import stack as S

NAME = "afe"

DEFAULTS = {
    "AFE_ENABLED": "1",
    "AFE_REPO": "unsloth/Qwen3.6-35B-A3B-MTP-GGUF",
    "AFE_FILE": "Qwen3.6-35B-A3B-UD-IQ3_XXS.gguf",
    # The name mazemaker's engine release was measured against
    # (llm_defaults.DEFAULT_LLM_MODEL). llama-server serves one model and
    # ignores the requested name, so this is a label, not a switch.
    "AFE_ALIAS": "qwen3.6-35b-a3b",
    # 0.0.0.0 because the caller is inside a podman pod and reaches the host
    # as host.containers.internal; the llm.toml API key guards it.
    "AFE_HOST": "0.0.0.0",
    "AFE_PORT": "8888",
    "AFE_CTX": "16384",
    "AFE_SLOTS": "1",
    "AFE_NGL": "99",
    # Experts of the first N layers stay in system RAM. Fully offloaded the
    # 35B-A3B needed 15.7 GiB with the pod up — under 1 GiB left, below the
    # 1 GiB mazemaker's recall reranker needs. MEASURED 2026-09-16, RTX 16 GiB,
    # ctx 16384, 1 slot: N=12 holds 10616 MiB, leaves 4376 MiB free, loads in
    # 80 s and decodes at 23.9 tok/s.
    "AFE_N_CPU_MOE": "12",
    "AFE_VRAM_BLOCK_MIB": "10240",
    "AFE_READY_TIMEOUT": "420",
    "AFE_IDLE_SECONDS": "600",
}


def _get(conf: S.StackConf, key: str) -> str:
    return conf.str(key, DEFAULTS[key])


def _int(conf: S.StackConf, key: str) -> int:
    return conf.int(key, int(DEFAULTS[key]))


def enabled(conf: S.StackConf) -> bool:
    return conf.flag("AFE_ENABLED", DEFAULTS["AFE_ENABLED"] == "1")


def host_port(conf: S.StackConf) -> tuple:
    return _get(conf, "AFE_HOST"), _int(conf, "AFE_PORT")


def probe_host(conf: S.StackConf) -> str:
    host = _get(conf, "AFE_HOST")
    return "127.0.0.1" if host in ("0.0.0.0", "::", "") else host


def model(conf: S.StackConf) -> str:
    return S.model_path(_get(conf, "AFE_REPO"), _get(conf, "AFE_FILE"))


# ------------------------------------------------------- mazemaker protocol --

def mazemaker_sockets() -> Path:
    base = os.environ.get("MAZEMAKER_DIR") or str(Path.home() / ".mazemaker")
    return Path(base) / "sockets"


def request_file() -> Path:
    return mazemaker_sockets() / "llm-on-demand.request"


def failed_file() -> Path:
    return mazemaker_sockets() / "llm-on-demand.failed"


def last_used_file() -> Path:
    return mazemaker_sockets() / "llm-last-used"


def _write(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def report_failure(reason: str) -> None:
    _write(failed_file(), f"{int(time.time())} {reason}\n")


def clear_failure() -> None:
    failed_file().unlink(missing_ok=True)


def _api_key() -> str:
    for path in (Path.home() / ".mazemaker" / "llm.toml",):
        try:
            import tomllib
            with path.open("rb") as fh:
                key = (tomllib.load(fh).get("llm") or {}).get("api_key")
            if key:
                return str(key).strip()
        except (OSError, ValueError):
            continue
    return ""


def share_key_with_pod() -> None:
    """Put the llm.toml credential where the AFE container can read it.

    The server binds 0.0.0.0 because the pod reaches the host as
    host.containers.internal, which maps to a host interface, not loopback
    (measured: a 127.0.0.1-bound server refuses the pod). Without a key that
    would be an unauthenticated LLM on the LAN. But the AFE window container
    mounts only specific children of ~/.mazemaker, never llm.toml, so its
    calls arrived without the key and got HTTP 401 — observed on the first
    real pass. sockets/ is the directory every pod member already mounts, and
    llm_transport also reads the key from there.
    """
    source = Path.home() / ".mazemaker" / "llm.toml"
    target = mazemaker_sockets() / "llm.toml"
    try:
        data = source.read_bytes()
    except OSError:
        return
    try:
        if target.exists() and target.read_bytes() == data:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    except OSError:
        pass


# ----------------------------------------------------------------- gating ----

def vram_used_mib() -> Optional[int]:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        line = out.stdout.strip().splitlines()[0] if out.returncode == 0 else ""
        return int(line) if line.strip().isdigit() else None
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return None


def stack_serving(conf: S.StackConf) -> List[str]:
    """Which daedalus-stack models are up, as human-readable descriptions."""
    serving = []
    for name in S.SERVERS:
        if not conf.enabled(name):
            continue
        host, port = conf.host_port(name)
        if S.alive(S.pid_of(name)):
            serving.append(f"{name} (pid {S.pid_of(name)}, {host}:{port})")
        elif S.port_up(host, port):
            serving.append(f"{name} ({host}:{port} answering, not started by daedalus)")
    return serving


def afe_serving(conf: S.StackConf) -> bool:
    host, port = probe_host(conf), _int(conf, "AFE_PORT")
    return S.alive(S.pid_of(NAME)) or S.port_up(host, port)


def blockers(conf: S.StackConf) -> List[str]:
    """Every reason AFE must not start now. Empty means go."""
    reasons = []
    if not enabled(conf):
        reasons.append("AFE_ENABLED=0 in stack.conf")
    if not os.access(conf.server, os.X_OK):
        reasons.append(f"llama-server not built ({conf.server}) — run: daedalus doctor setup")
    if not model(conf):
        reasons.append(
            f"AFE model not on disk: {_get(conf, 'AFE_REPO')} / {_get(conf, 'AFE_FILE')} "
            f"— run: daedalus doctor afe fetch")
    serving = stack_serving(conf)
    if serving:
        reasons.append("never two models — daedalus stack is serving: " + ", ".join(serving)
                       + " — stop it first: daedalus doctor stop")
    used = vram_used_mib()
    block = _int(conf, "AFE_VRAM_BLOCK_MIB")
    if used is not None and block > 0 and used > block and not S.alive(S.pid_of(NAME)):
        reasons.append(f"{used} MiB VRAM already in use (> {block} MiB) — the card is taken")
    return reasons


# ------------------------------------------------------------------- launch --

def argv(conf: S.StackConf, gguf: str) -> List[str]:
    host, port = host_port(conf)
    cmd = [
        str(conf.server), "--model", gguf,
        "-a", _get(conf, "AFE_ALIAS"),
        "--host", host, "--port", str(port),
        "--ctx-size", str(_int(conf, "AFE_CTX")),
        "-ngl", str(_int(conf, "AFE_NGL")),
        "-np", str(_int(conf, "AFE_SLOTS")),
        "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0",
        "--jinja", "--reasoning-format", "deepseek",
        "--spec-type", "draft-mtp",
        "--temp", "0.6", "--top-p", "0.95", "--top-k", "20",
    ]
    n_cpu_moe = _int(conf, "AFE_N_CPU_MOE")
    if n_cpu_moe > 0:
        cmd += ["--n-cpu-moe", str(n_cpu_moe)]
    key = _api_key()
    if key:
        cmd += ["--api-key", key]
    return cmd


UNIT = "daedalus-afe"


def launch(cmd: List[str]) -> bool:
    """Start the server as its own transient systemd user unit when possible.

    `wake` runs inside mazemaker-llm-watch.service, a oneshot. A plain child
    process lives in that unit's cgroup, and when the oneshot finished systemd
    SIGKILLed everything left in it — including the model it had just loaded.
    Observed live: "afe wake: started", then "Killing process (llama-server)
    with signal SIGKILL", and the caller got RemoteDisconnected. A new session
    does not leave a cgroup; a unit of its own does, and it also shows up in
    `systemctl --user status daedalus-afe`. Without a user systemd (a
    container, a CI box) it falls back to the plain detached child.
    """
    if shutil.which("systemd-run") and shutil.which("systemctl"):
        log = S.log_file(NAME)
        log.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["systemctl", "--user", "reset-failed", UNIT],
                       capture_output=True, timeout=10)
        run = subprocess.run(
            ["systemd-run", "--user", "--unit", UNIT, "--collect", "--quiet",
             "-p", f"StandardOutput=append:{log}", "-p", f"StandardError=append:{log}",
             "--", *cmd],
            capture_output=True, text=True, timeout=30,
        )
        if run.returncode == 0:
            for _ in range(50):
                show = subprocess.run(
                    ["systemctl", "--user", "show", "-p", "MainPID", "--value", UNIT],
                    capture_output=True, text=True, timeout=10,
                )
                pid = show.stdout.strip()
                if pid.isdigit() and int(pid) > 0:
                    S.pid_file(NAME).write_text(pid, encoding="utf-8")
                    S.dim(f"{NAME} starting as {UNIT}.service (pid {pid})…")
                    return True
                time.sleep(0.1)
            S.warn(f"{UNIT}.service started but reported no MainPID")
            return False
        S.warn("systemd-run failed, starting as a plain child",
               f"({(run.stderr or '').strip()[:120]})")
    return S.start_one(NAME, cmd)


def healthy(conf: S.StackConf) -> bool:
    """/health answers 200 — loaded and able to take work.

    S.port_up deliberately counts any HTTP answer as "up", which is right for
    "is something on this port" but wrong here: llama-server answers 503 for
    the whole time it is still loading the model, and a caller told "ready"
    then gets its first request refused.
    """
    import urllib.error
    import urllib.request
    url = f"http://{probe_host(conf)}:{_int(conf, 'AFE_PORT')}/health"
    try:
        with urllib.request.urlopen(url, timeout=2.0) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def wait_healthy(conf: S.StackConf, seconds: int) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if healthy(conf):
            return True
        if not S.alive(S.pid_of(NAME)):
            return False
        time.sleep(2)
    return False


def start(conf: S.StackConf, ready_timeout: Optional[int] = None) -> tuple:
    """(ok, reason). Never starts a second model; never starts blind."""
    if afe_serving(conf):
        timeout = ready_timeout if ready_timeout is not None else _int(conf, "AFE_READY_TIMEOUT")
        if healthy(conf) or wait_healthy(conf, timeout):
            return True, "already serving"
        return False, "AFE server is up but not healthy — daedalus doctor logs afe"
    reasons = blockers(conf)
    if reasons:
        return False, "; ".join(reasons)
    gguf = model(conf)
    share_key_with_pod()
    if not launch(argv(conf, gguf)):
        return False, "llama-server failed to launch — daedalus doctor logs afe"
    timeout = ready_timeout if ready_timeout is not None else _int(conf, "AFE_READY_TIMEOUT")
    if not wait_healthy(conf, timeout):
        died = not S.alive(S.pid_of(NAME))
        S.stop_one(NAME)
        what = "died while loading" if died else f"was not healthy within {timeout}s"
        return False, (f"AFE server {what} (CUDA OOM? raise AFE_N_CPU_MOE) "
                       f"— daedalus doctor logs afe")
    return True, "started"


# ----------------------------------------------------------------- commands --

def cmd_start(args=None) -> int:
    conf = S.load_conf()
    S.section("AFE model")
    ok_, reason = start(conf)
    if ok_:
        host, port = host_port(conf)
        S.ok(f"afe serving {_get(conf, 'AFE_ALIAS')} on {host}:{port}", f"({reason})")
        return 0
    for part in reason.split("; "):
        S.bad("AFE not started", f"— {part}")
    return 1


def cmd_stop(args=None) -> int:
    S.section("AFE model")
    if not S.alive(S.pid_of(NAME)):
        S.dim("afe not running")
        return 0
    S.stop_one(NAME)
    return 0


def cmd_status(args=None, conf: S.StackConf = None) -> int:
    conf = conf or S.load_conf(create=False)
    host, port = host_port(conf)
    gguf = model(conf)
    if not enabled(conf):
        S.dim("afe  disabled (AFE_ENABLED=0)")
        return 0
    if gguf:
        S.ok(f"afe model: {os.path.basename(gguf)}", f"({S._human_size(gguf)})")
    else:
        S.bad("afe model missing", f"— {_get(conf, 'AFE_REPO')} — run: daedalus doctor afe fetch")
    pid = S.pid_of(NAME)
    if S.alive(pid):
        if S.port_up(probe_host(conf), port):
            S.ok(f"afe  {host}:{port}  pid {pid}")
        else:
            S.warn(f"afe  pid {pid}", "— process up, port not answering yet")
    elif S.port_up(probe_host(conf), port):
        S.warn(f"afe  {host}:{port} answering", "— not started by daedalus (no pid file)")
    else:
        why = blockers(conf)
        S.dim("afe  stopped" + (f" — would refuse to start: {why[0]}" if why else " — ready to start"))
    if failed_file().exists():
        try:
            S.warn("last AFE wake failed", f"— {failed_file().read_text().strip()}")
        except OSError:
            pass
    return 0


def cmd_fetch(args=None) -> int:
    conf = S.load_conf()
    S.section("AFE model")
    repo, name = _get(conf, "AFE_REPO"), _get(conf, "AFE_FILE")
    if model(conf):
        S.ok("afe model present", f"— {name}")
        return 0
    if not shutil.which("hf"):
        S.bad("hf CLI missing", "— pip install huggingface_hub[cli]")
        return 1
    print(f"  fetching {repo} / {name}…")
    if subprocess.run(["hf", "download", repo, name]).returncode != 0 or not model(conf):
        S.bad("AFE model download failed", f"— {repo} / {name}")
        return 1
    S.ok("afe model downloaded", f"— {name}")
    return 0


def cmd_wake(args=None) -> int:
    """Host side of mazemaker's on-demand request (mazemaker-llm-watch.service)."""
    conf = S.load_conf()
    now = str(int(time.time()))
    _write(last_used_file(), now)
    # Consume the request first. The path unit re-fires for as long as the
    # file exists, so a request left behind during a slow load, or after a
    # refusal that cannot change on its own, loops forever.
    request_file().unlink(missing_ok=True)
    ok_, reason = start(conf)
    if ok_:
        clear_failure()
        _write(last_used_file(), str(int(time.time())))
        print(f"afe wake: {reason}")
        return 0
    report_failure(reason)
    print(f"afe wake REFUSED: {reason}", flush=True)
    return 1


def _unit_active(unit: str) -> bool:
    try:
        return subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit],
                              timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def cmd_idle_check(args=None) -> int:
    """Stop an AFE server nobody has used for AFE_IDLE_SECONDS."""
    conf = S.load_conf()
    if not S.alive(S.pid_of(NAME)):
        return 0
    if _unit_active("mazemaker-afe-window.service"):
        return 0
    try:
        last = float(last_used_file().read_text().strip())
    except (OSError, ValueError):
        return 0
    idle = time.time() - last
    if idle >= _int(conf, "AFE_IDLE_SECONDS"):
        print(f"afe idle {int(idle)}s — stopping")
        S.stop_one(NAME)
    return 0


def register(subs) -> None:
    p = subs.add_parser("afe", help="mazemaker's AFE model on :8888 — never beside the daedalus stack")
    afe_subs = p.add_subparsers(dest="afe_command", metavar="ACTION")
    p.set_defaults(func=cmd_status)
    afe_subs.add_parser("status", help="Model on disk, server state, why it would refuse").set_defaults(func=cmd_status)
    afe_subs.add_parser("fetch", help="Download the AFE model from Hugging Face").set_defaults(func=cmd_fetch)
    afe_subs.add_parser("start", help="Serve it — refuses beside another model or on a taken card").set_defaults(func=cmd_start)
    afe_subs.add_parser("stop", help="Stop the AFE server").set_defaults(func=cmd_stop)
    afe_subs.add_parser("wake", help="mazemaker on-demand request (called by systemd)").set_defaults(func=cmd_wake)
    afe_subs.add_parser("idle-check", help="Stop it after AFE_IDLE_SECONDS unused (called by systemd)").set_defaults(func=cmd_idle_check)
