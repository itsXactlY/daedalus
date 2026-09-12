"""The local inference stack, owned by ``daedalus doctor``.

This is the lifecycle of the machine's own llama.cpp servers — the main
model, the CPU-only helper, and the optional vision endpoint — expressed as
subcommands of the command that already reports on them::

    daedalus doctor              # everything, including what is running
    daedalus doctor status       # just the servers: ports, pids, VRAM
    daedalus doctor setup        # clone + build llama.cpp, fetch the models
    daedalus doctor start        # bring the servers up, in the right order
    daedalus doctor stop
    daedalus doctor restart
    daedalus doctor pause        # freeze them, weights stay loaded
    daedalus doctor resume
    daedalus doctor logs [main|aux|vis]

Everything is driven by ``$DAEDALUS_HOME/stack.conf``, written on first use.
Edit that rather than this module: nothing about one particular machine is
baked in here, the defaults are simply the numbers that were measured on the
card this was developed against.

The configuration file is shell syntax because it predates this module and is
still readable by hand; it is parsed here rather than sourced, so running
``daedalus doctor`` can never execute whatever a conf file happens to contain.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from daedalus_cli.colors import Colors, color

# Names are the pid-file / log-file stems as well as the user-facing labels.
SERVERS = ("main", "aux", "vis")


# --------------------------------------------------------------- output -----
# Deliberately the same glyphs run_doctor() uses, so a stack section reads as
# part of the same report rather than a bolted-on second one.

def ok(text: str, detail: str = "") -> None:
    print(f"  {color('✓', Colors.GREEN)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))


def warn(text: str, detail: str = "") -> None:
    print(f"  {color('⚠', Colors.YELLOW)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))


def bad(text: str, detail: str = "") -> None:
    print(f"  {color('✗', Colors.RED)} {text}" + (f" {color(detail, Colors.DIM)}" if detail else ""))


def dim(text: str) -> None:
    print(f"  {color('·', Colors.DIM)} {color(text, Colors.DIM)}")


def note(text: str) -> None:
    print(f"    {color(text, Colors.DIM)}")


def section(text: str) -> None:
    print()
    print(color(f"◆ {text}", Colors.CYAN, Colors.BOLD))


# ---------------------------------------------------------------- paths -----

def daedalus_home() -> Path:
    return Path(os.environ.get("DAEDALUS_HOME") or (Path.home() / ".daedalus"))


def conf_path() -> Path:
    return daedalus_home() / "stack.conf"


def run_dir() -> Path:
    return daedalus_home() / "run"


def log_dir() -> Path:
    return daedalus_home() / "logs"


# ----------------------------------------------------------------- conf -----

DEFAULT_CONF = '''\
# Daedalus local stack. Paths are absolute; ~ is expanded on load.

# --- where the llama.cpp fork lives and gets built ---------------------------
# Adaptive KV streaming keeps the KV cache in pinned host memory, which is what
# lets a 27B model hold a six-figure context on a 16 GB card.
LLAMA_DIR="$HOME/projects/llama.cpp-adaptive-kv-streaming"
LLAMA_REPO="https://github.com/RaymondHuang210129/llama.cpp-adaptive-kv-streaming"
LLAMA_BRANCH="feature/adaptive-kv-stream"

# --- main model --------------------------------------------------------------
MAIN_REPO="ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF"
MAIN_FILE="Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
MAIN_PORT=8080
MAIN_HOST="127.0.0.1"
MAIN_CTX=262144
# --gpu-layers all + --ctx-size 0 skips llama.cpp's memory fit and lands on
# the model's full context; -ngl 99 (an exact count) lets the fit run instead.
# Either is fine as long as this number and config.yaml's model.context_length
# both match what /slots reports. Never write 0: it is not a fixed value.
# The pinned host KV buffer this reserves is sized to MAIN_CTX for the whole
# process lifetime regardless of how much of it is ever actually live -- pick
# a real ceiling above your compaction target, not headroom you'll never use.
# Resident KV pool in VRAM, MiB. Raise it while watching peak VRAM; the rest of
# the cache streams from host memory. Leave EMPTY to drop block KV streaming
# entirely, which is what frees you to run more than one slot.
MAIN_KV_POOL=2048
# Prompt-cache budget in host RAM, MiB. llama-server defaults to 8192, which
# is a lot to hand a machine that is also holding a multi-GiB pinned KV
# buffer: the prompt cache is swappable, so it does not fail when RAM runs
# short, it pages, and throughput decays over hours instead of stopping.
# 0 disables the prompt cache; -1 is llama.cpp's "no limit".
MAIN_CACHE_RAM=2048
MAIN_NGL=99
MAIN_THREADS=8
MAIN_REASONING_BUDGET=12000
# KV cache quantization. q8_0/q4_0 matches the benchmarked config
# (~/projects/specbench/campaign/GOAT.sh) -- K-cache is more sensitive to
# attention accuracy than V, so don't drop MAIN_CTK below q8_0 to save VRAM
# without re-benchmarking; that trade was never actually validated.
MAIN_CTK="q8_0"
MAIN_CTV="q4_0"

# Server slots. Block KV streaming needs a single KV *stream*, not literally
# one sequence (llama.cpp-adaptive-kv-streaming commit 002b6bce1, 2026-09-11):
# a unified KV buffer collapses any slot count to one stream, so MAIN_SLOTS>1
# with MAIN_KV_POOL set works now. `start` auto-adds -kvu whenever both are
# true; MAIN_KV_UNIFIED below is only for forcing it in the plain multi-slot
# case (no KV pool). Verified running two real parallel slots on this fork:
# main conversation on slot 1, auxiliary_client.py's hygiene/compression
# calls on slot 0 (AUX_PORT == MAIN_PORT below shares this server's slot
# instead of spawning a second process). Sidekick gets slot 0, not main,
# because llama-server fills its shared batch in slot-index order each
# iteration and stops at the first slot that would overflow it -- main's
# prefill is usually the big one, so putting it on 0 let it starve the
# sidekick's slot for many consecutive iterations (fixed 2026-09-12).
#
# Old builds without that patch refuse to start instead of degrading:
#   E llama_init_from_model: failed to initialize the context:
#     block KV streaming requires exactly one sequence (-np 1)
# — that means `daedalus doctor setup` needs to rebuild the fork.
MAIN_SLOTS=2
# Only meaningful for MAIN_SLOTS>1 with MAIN_KV_POOL empty; see above.
MAIN_KV_UNIFIED=0

# --- speculative decoding (DFlash2) -------------------------------------------
# A real second model, not the target's own MTP head -- benchmarked in
# ~/projects/specbench (GOAT.sh is the winning config; n-max/n-min below match
# it). Leave both empty to fall back to draft-mtp,ngram-mod (no extra VRAM, no
# extra file, untuned) -- `start` degrades to that automatically rather than
# failing when no draft model is configured.
#
# MAIN_DRAFT_FILE also takes a plain path (a locally built GGUF outside any HF
# cache); MAIN_DRAFT_REPO is then irrelevant and setup skips the download.
# Do not economise on the drafter's quantization: a Q2 draft proposes badly
# enough that acceptance collapses, and you pay for it in both speed and
# output quality. Q4_K_M is the floor that held up here.
MAIN_DRAFT_REPO="HermiHg/Qwen3.8-27B-DFlash2-Q2_K_S-MIX-GGUF"
MAIN_DRAFT_FILE="Qwen3.8-27B-DFlash2-Q2_K_S-MIX.gguf"
MAIN_DRAFT_N_MAX=4
MAIN_DRAFT_N_MIN=1

# --- vision -------------------------------------------------------------------
# The projector is a SEPARATE artifact from the model GGUF. The text weights
# carry no vision tensors at all, which is exactly what llama-server means by
#   "image input is not supported - hint: ... you may need to provide the mmproj"
# — the model is fine, the tower simply was not loaded.
#
# Resolved out of the HF cache like every other weight: leave MMPROJ empty and
# MAIN_MMPROJ_FILE is looked up inside MAIN_REPO, so `daedalus doctor setup`
# fetches it and `start` finds it with no absolute path to keep in sync. Set
# MMPROJ to an absolute path ONLY to override with a file outside the cache.
#
# The tower must match the model: this one reports projection_dim 5120. The
# Qwen3.6-35B-A3B projector (dim 2048) also on this box will not pair with it.
# `daedalus doctor` checks that rather than letting the server fail at runtime.
MAIN_MMPROJ_FILE="mmproj-Qwen3.8-27B-BF16.gguf"
MMPROJ=""
# Off by default: the ~890MB tower is real VRAM competing with the draft
# model + slots on a 16GB card, for a capability most turns never use.
# `setup` still fetches the projector either way -- set this to 1 to load it.
MAIN_VISION=0

# --- all-in-one alternative --------------------------------------------------
# golden-agent-cpp clones and builds the same adaptive-KV server this module
# uses, fetches the model, supervises the process and falls back GPU -> CPU on
# its own. No Python, no venv, one binary -- the same context, none of the
# assembly. Point it at an existing checkout with GA_LLAMA_SRC.
GOLDEN_AGENT_REPO="https://github.com/itsXactlY/golden-agent-cpp"
GOLDEN_AGENT_DIR="$HOME/projects/golden-agent-cpp"

# --- auxiliary model ---------------------------------------------------------
# Small, CPU-only, on its own port so background work never queues behind the
# main model. -ngl 0 is deliberate: it costs no VRAM and runs truly in parallel.
AUX_REPO="ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF"
AUX_FILE="Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
AUX_PORT=8080
AUX_HOST="127.0.0.1"
AUX_CTX=12096
AUX_THREADS=6
AUX_ENABLED=1

# --- vision endpoint ----------------------------------------------------------
# OFF by default. The main model can see (MAIN_MMPROJ_FILE), so leaving this
# off is correct and costs nothing extra.
#
# Turn it on when a vision call must not QUEUE. The main server runs -np 1 by
# hard requirement of block KV streaming, so every request to it is serialised:
# an image sent while a long turn is generating is not answered until that turn
# ends, and a client with a fixed timeout gives up having never been served.
# That is the "waited two minutes for nothing" case, and no flag on the main
# server fixes it — the second slot the fix would need is exactly what the
# fork forbids.
#
# Two ways out, pick one:
#   1. VIS_ENABLED=1 here, on its own port, -ngl 0 so it costs NO VRAM next to
#      the 27B (same trick the aux model already uses). Point the harness's
#      auxiliary.vision.base_url at http://127.0.0.1:$VIS_PORT/v1. Needs a
#      small VL model + its projector; set VIS_REPO/VIS_FILE/VIS_MMPROJ_FILE
#      and run `daedalus doctor setup`.
#   2. Keep vision on the main model and accept the queue, but give the client
#      a timeout longer than your longest turn, so it waits and is answered
#      instead of timing out for nothing.
VIS_ENABLED=0
VIS_REPO=""
VIS_FILE=""
VIS_MMPROJ_FILE=""
VIS_PORT=8082
VIS_HOST="127.0.0.1"
VIS_CTX=16384
VIS_THREADS=4
'''

_ASSIGN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_THREAD_KEY = re.compile(r"^(MAIN|AUX|VIS)_THREADS\s*=\s*(\d+)\s*(#.*)?$")


def _physical_core_count() -> int:
    """Count distinct (physical id, core id) pairs from /proc/cpuinfo.

    ``nproc`` and ``os.cpu_count()`` both report logical CPUs (cores * threads),
    which on a hyperthreaded Ryzen double-counts. llama-server's ``-t`` should
    reflect PHYSICAL cores, so three servers each set to the logical count
    will oversubscribe the box and thrash.
    """
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return max(1, os.cpu_count() or 1)
    pairs: set[tuple[str, str]] = set()
    phys, core = None, None
    for line in text.splitlines():
        if line.startswith("physical id"):
            phys = line.split(":", 1)[1].strip()
        elif line.startswith("core id"):
            core = line.split(":", 1)[1].strip()
            if phys is not None and core is not None:
                pairs.add((phys, core))
                phys, core = None, None
    if pairs:
        return max(1, len(pairs))
    # Fallback: some virtualised kernels don't emit "core id". Trust "cpu cores".
    cores_per_pkg: dict[str, int] = {}
    pkg = None
    for line in text.splitlines():
        if line.startswith("physical id"):
            pkg = line.split(":", 1)[1].strip()
        elif line.startswith("cpu cores"):
            val = line.split(":", 1)[1].strip()
            if val.isdigit() and pkg is not None:
                cores_per_pkg[pkg] = int(val)
    if cores_per_pkg:
        return max(1, sum(cores_per_pkg.values()))
    return max(1, os.cpu_count() or 1)


def _propose_threads(physical: int) -> tuple[int, int, int]:
    """Split the physical-core budget across the three llama-server processes.

    The intent is "pure cores only" — the sum never exceeds the physical count,
    regardless of how many threads per core the silicon exposes. Main is
    typically GPU-offloaded so it only needs a few CPU threads for prompt
    eval; aux and vis are CPU-only and stay small. Any leftover is given to
    main, which is the latency-sensitive one.
    """
    if physical <= 0:
        return 1, 1, 1
    if physical <= 4:
        main, aux, vis = max(2, physical - 2), 1, 1
    elif physical <= 8:
        # 8 cores -> 4/2/2; 6 cores -> 3/2/1; 5 cores -> 3/1/1
        main = max(2, physical - 4)
        aux = 2 if physical >= 6 else 1
        vis = 2 if physical >= 8 else 1
    else:
        # 16 -> 8/4/4; 12 -> 6/3/3; 10 -> 5/3/2
        main = physical // 2
        aux = max(2, physical // 4)
        vis = max(2, physical // 4)
    # Floor the total at the physical count — never oversubscribe.
    while main + aux + vis > physical and main > 1:
        main -= 1
    return main, aux, vis


def _patch_threads_in_conf(target: Path, main: int, aux: int, vis: int) -> bool:
    """Rewrite MAIN/AUX/VIS_THREADS in stack.conf without touching the rest.

    Existing lines are updated in place (preserving any trailing comment and
    indentation). Missing keys are appended at the end so the audit trail in
    the conf matches what the setup actually intended.

    Returns True iff at least one line actually changed.
    """
    wanted = {"MAIN_THREADS": main, "AUX_THREADS": aux, "VIS_THREADS": vis}
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return False
    trailing_nl = text.endswith("\n")
    out: list[str] = []
    seen: set[str] = set()
    changed = False
    for line in text.splitlines():
        m = _THREAD_KEY.match(line)
        if not m:
            out.append(line)
            continue
        key, current, comment = m.group(1) + "_THREADS", int(m.group(2)), m.group(3) or ""
        new_val = wanted[key]
        seen.add(key)
        if new_val == current:
            out.append(line)
            continue
        indent = line[: len(line) - len(line.lstrip())]
        rebuilt = f"{indent}{key}={new_val}{('  ' + comment.rstrip()) if comment else ''}"
        out.append(rebuilt)
        changed = True
    for key, val in wanted.items():
        if key not in seen:
            out.append(f"{key}={val}")
            changed = True
    if not changed:
        return False
    new_text = "\n".join(out) + ("\n" if trailing_nl or out else "")
    target.write_text(new_text, encoding="utf-8")
    return True



def _parse_conf(text: str) -> dict:
    """Read shell-style ``KEY=value`` assignments without running a shell.

    Only the subset the conf file actually uses is honoured: optionally quoted
    scalars, ``$HOME`` and ``~``. Anything else is left as written, which is
    the safe direction — a value this does not understand reaches llama-server
    verbatim instead of being silently rewritten.
    """
    values: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ASSIGN.match(line)
        if not match:
            continue
        key, rhs = match.group(1), match.group(2).strip()
        if rhs[:1] in ('"', "'"):
            quote = rhs[0]
            end = rhs.find(quote, 1)
            rhs = rhs[1:end] if end > 0 else rhs[1:]
        else:
            rhs = rhs.split("#", 1)[0].strip()
        values[key] = os.path.expanduser(os.path.expandvars(rhs))
    return values


class StackConf:
    """Typed view over stack.conf, with the same fallbacks the stack needs.

    The fallbacks are not cosmetic: a conf file written before a key existed
    must still start a server, and the safe value for the two KV-streaming
    keys is the single-sequence one, because the alternative does not run.
    """

    def __init__(self, values: dict):
        self._v = values

    def str(self, key: str, default: str = "") -> str:
        value = self._v.get(key)
        return default if value in (None, "") else value

    def int(self, key: str, default: int) -> int:
        try:
            return int(self.str(key, str(default)))
        except ValueError:
            return default

    def flag(self, key: str, default: bool) -> bool:
        return self.str(key, "1" if default else "0") == "1"

    def path(self, key: str, default: str = "") -> str:
        value = self.str(key, default)
        return os.path.expanduser(os.path.expandvars(value)) if value else ""

    # -- derived ------------------------------------------------------------
    @property
    def llama_dir(self) -> Path:
        return Path(self.path(
            "LLAMA_DIR",
            str(Path.home() / "projects/llama.cpp-adaptive-kv-streaming"),
        ))

    @property
    def server(self) -> Path:
        return self.llama_dir / "build/bin/llama-server"

    @property
    def golden_agent_dir(self) -> Path:
        return Path(self.path("GOLDEN_AGENT_DIR", str(Path.home() / "projects/golden-agent-cpp")))

    @property
    def mmproj(self) -> str:
        """An explicit MMPROJ always wins; otherwise take the projector that
        ships in the model's own HF repo.

        Resolving it here (not at start time) is what makes doctor, setup and
        start agree on which file "the projector" is.

        MMPROJ is documented as "an absolute path to override with a file
        outside the cache" -- but it sits right next to MAIN_MMPROJ_FILE
        (a bare filename resolved from the HF cache), and setting MMPROJ to
        that same bare filename is the obvious thing to try if you don't
        know the two have different rules (observed 2026-09-12). Anything in
        MMPROJ that isn't already a usable path but has no directory
        component gets one retry through the HF-cache lookup before giving
        up -- silent for the common typo, and still returns the literal
        MMPROJ value on failure so stack_report's "MMPROJ set but not found"
        warning names the actual value the user set, not something resolved
        out from under it.
        """
        explicit = self.path("MMPROJ")
        if explicit:
            if os.path.isfile(explicit):
                return explicit
            if not os.path.dirname(explicit):
                resolved = model_path(self.str("MAIN_REPO"), explicit)
                if resolved:
                    return resolved
            return explicit
        named = self.str("MAIN_MMPROJ_FILE")
        return model_path(self.str("MAIN_REPO"), named) if named else ""

    def host_port(self, name: str) -> tuple:
        prefix = name.upper()
        default_port = {"main": 8080, "aux": 8081, "vis": 8082}[name]
        return self.str(f"{prefix}_HOST", "127.0.0.1"), self.int(f"{prefix}_PORT", default_port)

    def enabled(self, name: str) -> bool:
        if name == "aux":
            return self.flag("AUX_ENABLED", True)
        if name == "vis":
            return self.flag("VIS_ENABLED", False)
        return True


def write_default_conf() -> Path:
    target = conf_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(DEFAULT_CONF, encoding="utf-8")
    return target


def load_conf(create: bool = True) -> StackConf:
    """Load stack.conf, writing the annotated default when it is missing.

    ``create=False`` is for the read-only paths: a plain ``daedalus doctor``
    should be able to report on the stack without leaving a conf file behind
    on a machine that never runs one.
    """
    target = conf_path()
    if not target.exists():
        if not create:
            return StackConf(_parse_conf(DEFAULT_CONF))
        write_default_conf()
    if create:
        run_dir().mkdir(parents=True, exist_ok=True)
        log_dir().mkdir(parents=True, exist_ok=True)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        text = DEFAULT_CONF
    return StackConf(_parse_conf(text))


def stack_in_use(conf: StackConf = None) -> bool:
    """Has this machine ever actually set the local stack up?

    A user running entirely on remote providers should not have a page of
    CUDA-toolchain findings in their doctor report, so the detailed section
    is only rendered once there is something to report on.
    """
    conf = conf or load_conf(create=False)
    if conf_path().exists() or conf.llama_dir.is_dir():
        return True
    return any(alive(pid_of(name)) for name in SERVERS)


# --------------------------------------------------------------- models -----

def model_path(repo: str, filename: str) -> str:
    """Resolve a GGUF inside the HuggingFace cache, or return ''.

    Snapshot entries are symlinks into ``blobs/``, so any search that insists
    on real files misses every one of them — hence the followed walk.
    """
    if not filename:
        return ""
    # A plain path is not every GGUF's home. The winning DFlash2 drafter was
    # built locally and lives in ~/models, outside any HF cache -- before this,
    # such a file was unreachable from the config and the launch silently fell
    # back to whatever repo-hosted draft was named instead.
    if filename.startswith(("/", "~", "./")):
        expanded = Path(filename).expanduser()
        return str(expanded) if expanded.is_file() else ""
    if not repo:
        return ""
    root = Path.home() / ".cache/huggingface/hub" / f"models--{repo.replace('/', '--')}"
    if not root.is_dir():
        return ""
    try:
        for dirpath, _dirnames, filenames in os.walk(root, followlinks=True):
            if filename in filenames:
                return str(Path(dirpath) / filename)
    except OSError:
        return ""
    return ""


def gguf_str(path: str, want: str):
    """Read one metadata key out of a GGUF header.

    Used to confirm a projector actually belongs to the model before handing
    both to llama-server, which otherwise accepts the mismatch and fails on
    the first image instead. Returns None on any parse trouble: a diagnostic
    must never be the reason the stack refuses to start.
    """
    try:
        with open(path, "rb") as handle:
            if handle.read(4) != b"GGUF":
                return None
            handle.read(4)                                        # version
            handle.read(8)                                        # tensor count
            n_kv = struct.unpack("<Q", handle.read(8))[0]

            def read_str():
                length = struct.unpack("<Q", handle.read(8))[0]
                return handle.read(length).decode("utf-8", "replace")

            def read_val(kind):
                if kind in (0, 1):
                    return struct.unpack("<B" if kind == 0 else "<b", handle.read(1))[0]
                if kind in (2, 3):
                    return struct.unpack("<H" if kind == 2 else "<h", handle.read(2))[0]
                if kind in (4, 5):
                    return struct.unpack("<I" if kind == 4 else "<i", handle.read(4))[0]
                if kind == 6:
                    return struct.unpack("<f", handle.read(4))[0]
                if kind == 7:
                    return struct.unpack("<?", handle.read(1))[0]
                if kind == 8:
                    return read_str()
                if kind == 9:
                    elem = struct.unpack("<I", handle.read(4))[0]
                    count = struct.unpack("<Q", handle.read(8))[0]
                    return [read_val(elem) for _ in range(count)]
                if kind in (10, 11):
                    return struct.unpack("<Q" if kind == 10 else "<q", handle.read(8))[0]
                if kind == 12:
                    return struct.unpack("<d", handle.read(8))[0]
                raise ValueError(kind)

            for _ in range(n_kv):
                key = read_str()
                value = read_val(struct.unpack("<I", handle.read(4))[0])
                if key == want:
                    return value
    except (OSError, struct.error, ValueError, IndexError):
        return None
    return None


def _human_size(path: str) -> str:
    try:
        size = float(os.stat(path).st_size)
    except OSError:
        return "?"
    for unit in ("B", "K", "M", "G", "T"):
        if size < 1024 or unit == "T":
            return f"{size:.0f}{unit}" if unit in ("B", "K") else f"{size:.1f}{unit}"
        size /= 1024
    return "?"


# ------------------------------------------------------------ processes -----

def pid_file(name: str) -> Path:
    return run_dir() / f"{name}.pid"


def log_file(name: str) -> Path:
    return log_dir() / f"{name}.log"


def pid_of(name: str):
    try:
        return int(pid_file(name).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


# Servers this process launched, so they can be reaped instead of left as
# zombies for as long as the CLI runs.
_STARTED: dict = {}


def _reap(name: str) -> None:
    proc = _STARTED.get(name)
    if proc is None:
        return
    try:
        proc.poll()
    except OSError:
        pass


def alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return True
    # A dead child of this process lingers as a zombie until it is reaped, and
    # signal 0 still succeeds on one — so ask /proc what it actually is, or
    # stop_one() would wait out its whole grace period on a corpse.
    return not _proc_state(pid).startswith("Z")


def _proc_state(pid: int) -> str:
    """Linux process state letter, or '' when it cannot be read."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as handle:
            raw = handle.read().decode("utf-8", "replace")
        # comm can contain spaces and parens; everything after the last ')'
        # is the fixed-width part, whose first field is the state.
        return raw[raw.rfind(")") + 1:].split()[0]
    except (OSError, IndexError):
        return ""


def state_of(name: str) -> str:
    """running | paused | stopped."""
    pid = pid_of(name)
    if not alive(pid):
        return "stopped"
    return "paused" if _proc_state(pid).startswith("T") else "running"


def port_up(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=timeout) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError:
        # Answering at all is what this asks; a 4xx still means a server.
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def socket_up(host: str, port: int, timeout: float = 3.0) -> bool:
    """Is anything listening at all — for services that speak no health route."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_one(name: str, argv: list, env: dict | None = None) -> bool:
    state = state_of(name)
    if state != "stopped":
        warn(f"{name} already {state}")
        return True
    log = log_file(name)
    try:
        handle = open(log, "ab")
    except OSError as exc:
        bad(f"cannot write {log}", f"({exc})")
        return False
    try:
        # start_new_session detaches it from this CLI's session, so the server
        # outlives the terminal that started it — and unlike `setsid` from a
        # shell, the pid recorded here is the server's own, not a wrapper's.
        proc = subprocess.Popen(
            argv,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=({**os.environ, **env} if env else None),
        )
    except OSError as exc:
        bad(f"{name} failed to launch", f"({exc})")
        return False
    finally:
        handle.close()
    _STARTED[name] = proc
    pid_file(name).write_text(str(proc.pid), encoding="utf-8")
    dim(f"{name} starting…")
    return True


def wait_ready(name: str, host: str, port: int, seconds: int = 180) -> bool:
    waited = 0
    while waited < seconds:
        if port_up(host, port):
            ok(f"{name} up on {host}:{port}")
            return True
        if not alive(pid_of(name)):
            bad(f"{name} died", f"— daedalus doctor logs {name}")
            return False
        time.sleep(2)
        waited += 2
    bad(f"{name} did not answer within {seconds}s", f"— daedalus doctor logs {name}")
    return False


def stop_one(name: str) -> None:
    pid = pid_of(name)
    if not alive(pid):
        pid_file(name).unlink(missing_ok=True)
        return
    # CONT first: a paused server never sees the TERM that follows, and would
    # be left frozen and unkillable-looking by anything short of -9.
    for sig in (signal.SIGCONT, signal.SIGTERM):
        try:
            os.kill(pid, sig)
        except OSError:
            pass
    for _ in range(20):
        _reap(name)
        if not alive(pid):
            break
        time.sleep(0.5)
    if alive(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    _reap(name)
    _STARTED.pop(name, None)
    pid_file(name).unlink(missing_ok=True)
    ok(f"{name} stopped")


# ------------------------------------------------------------- commands -----

def cmd_status(args=None, conf: StackConf = None) -> int:
    conf = conf or load_conf()
    for name in SERVERS:
        if not conf.enabled(name):
            continue
        host, port = conf.host_port(name)
        state, pid = state_of(name), pid_of(name)
        if state == "running":
            if port_up(host, port):
                ok(f"{name}  {host}:{port}  pid {pid}")
            else:
                warn(f"{name}  pid {pid}", "— process up, port not answering yet")
        elif state == "paused":
            warn(f"{name}  pid {pid}", "— paused")
        elif port_up(host, port):
            # A server this CLI did not start still occupies the port. Saying
            # "stopped" while something answers there is worse than nothing.
            warn(f"{name}  {host}:{port} answering", "— not started by daedalus (no pid file)")
        else:
            dim(f"{name}  stopped")
    if shutil.which("nvidia-smi"):
        try:
            vram = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            if vram:
                note(f"VRAM: {vram}")
        except (OSError, subprocess.SubprocessError):
            pass
    return 0


def stack_report(conf: StackConf = None) -> None:
    """The 'what is present, what is missing' half of the stack diagnostic.

    Split out from cmd_doctor so ``daedalus doctor`` can fold it into the
    single report the operator already reads, rather than making the local
    inference stack a separate thing to remember to check.
    """
    conf = conf or load_conf()

    section("Inference toolchain")
    for tool in ("git", "cmake", "curl"):
        ok(tool) if shutil.which(tool) else bad(tool, "— required")
    if shutil.which("hf"):
        ok("hf (huggingface CLI)")
    else:
        warn("hf missing", "— pip install huggingface_hub[cli]")
    if shutil.which("nvcc"):
        ok("nvcc")
    else:
        warn("nvcc missing", "— the CUDA build needs the toolkit, not just the driver")
    ok("nvidia-smi") if shutil.which("nvidia-smi") else warn("no nvidia-smi", "— CPU only")

    section("Inference sources")
    if (conf.llama_dir / ".git").is_dir():
        ok(f"llama.cpp at {conf.llama_dir}")
    else:
        bad("llama.cpp missing", "— run: daedalus doctor setup")
    if os.access(conf.server, os.X_OK):
        ok("llama-server built")
    else:
        bad("llama-server not built", "— run: daedalus doctor setup")

    section("Local models")
    main = model_path(conf.str("MAIN_REPO"), conf.str("MAIN_FILE"))
    if main:
        ok(f"main: {os.path.basename(main)}", f"({_human_size(main)})")
    else:
        bad("main model missing", "— run: daedalus doctor setup")
    if conf.enabled("aux"):
        aux = model_path(conf.str("AUX_REPO"), conf.str("AUX_FILE"))
        if aux:
            ok(f"aux:  {os.path.basename(aux)}", f"({_human_size(aux)})")
        else:
            bad("aux model missing", "— run: daedalus doctor setup")

    draft_repo = conf.str("MAIN_DRAFT_REPO")
    draft_file = conf.str("MAIN_DRAFT_FILE")
    if draft_repo or draft_file:
        draft = model_path(draft_repo, draft_file) if draft_file else ""
        if draft:
            ok(f"draft (DFlash2): {os.path.basename(draft)}", f"({_human_size(draft)})")
        else:
            bad("DFlash2 draft model configured but missing", "— run: daedalus doctor setup")
    else:
        warn("no DFlash2 draft model configured",
             "— running MTP + ngram-mod instead (set MAIN_DRAFT_REPO/MAIN_DRAFT_FILE)")

    projector = conf.mmproj
    vision_on = conf.flag("MAIN_VISION", False)
    if not projector:
        warn("no vision projector", "— image input will 500 ('provide the mmproj')")
        note("run: daedalus doctor setup")
    elif not os.path.isfile(projector):
        warn("MMPROJ set but not found", f"({projector})")
    elif not vision_on:
        dim(f"vision: off (MAIN_VISION=0) — {os.path.basename(projector)} present, not loaded")
    else:
        # Pair check. A projector from another model loads and then produces
        # garbage or a dim mismatch at the first image, which is a miserable
        # thing to debug from a 500. projection_dim must match the text
        # model's embedding width.
        pdim = gguf_str(projector, "clip.vision.projection_dim")
        pname = gguf_str(projector, "general.name")
        if pdim:
            ok(f"mmproj: {os.path.basename(projector)}", f"— {pname or '?'}, projection_dim={pdim}")
        else:
            ok(f"mmproj: {os.path.basename(projector)}")

    section("Memory backend")
    url = os.environ.get("MM_WONDERLAND_URL", "http://127.0.0.1:8765")
    stripped = re.sub(r"^https?://", "", url)
    mm_host = re.split(r"[:/]", stripped)[0] or "127.0.0.1"
    port_match = re.search(r"^[^:/]+:(\d+)", stripped)
    mm_port = int(port_match.group(1)) if port_match else 8765
    # The pod speaks MCP, not a plain health route, so probe the socket rather
    # than guessing a path — a GET on / hangs waiting for a session.
    if socket_up(mm_host, mm_port):
        ok(f"mazemaker listening on {mm_host}:{mm_port}")
    else:
        bad(f"mazemaker NOT reachable at {url}")
        note("Without it this harness is an amnesiac: it stops carrying its own")
        note("history by design. See https://mazemaker.online")

    section("Inference servers")
    cmd_status(conf=conf)


def cmd_doctor(args=None, conf: StackConf = None) -> int:
    """``daedalus doctor stack`` — the stack half on its own."""
    stack_report(conf or load_conf())
    print()
    return 0


def cmd_setup(args=None) -> int:
    conf = load_conf()

    # --- thread budget: derive *_THREADS from PHYSICAL cores, not logical ---
    physical = _physical_core_count()
    logical = max(1, os.cpu_count() or physical)
    proposed_main, proposed_aux, proposed_vis = _propose_threads(physical)
    current_main = int(conf.str("MAIN_THREADS", "0") or 0)
    current_aux = int(conf.str("AUX_THREADS", "0") or 0)
    current_vis = int(conf.str("VIS_THREADS", "0") or 0)
    current_total = current_main + current_aux + current_vis
    desired_total = proposed_main + proposed_aux + proposed_vis
    section("thread budget (pure physical cores)")
    print(f"  hardware       : {physical} physical core(s), {logical} logical CPU(s)")
    print(f"  current conf   : MAIN={current_main} AUX={current_aux} VIS={current_vis}"
          f"  -> {current_total} thread slot(s)")
    print(f"  proposed       : MAIN={proposed_main} AUX={proposed_aux} VIS={proposed_vis}"
          f"  -> {desired_total} thread slot(s) (sum <= {physical})")
    if (current_main, current_aux, current_vis) != (proposed_main, proposed_aux, proposed_vis):
        if _patch_threads_in_conf(conf_path(), proposed_main, proposed_aux, proposed_vis):
            conf = load_conf()  # refresh so the rest of setup uses the new values
            ok("stack.conf updated to match physical cores")
        else:
            warn("could not rewrite stack.conf — edit it by hand")
    else:
        ok("stack.conf already on physical-core budget")
    print()

    section("llama.cpp (adaptive KV streaming)")
    if not (conf.llama_dir / ".git").is_dir():
        conf.llama_dir.parent.mkdir(parents=True, exist_ok=True)
        clone = subprocess.run([
            "git", "clone", "--branch", conf.str("LLAMA_BRANCH", "feature/adaptive-kv-stream"),
            conf.str("LLAMA_REPO"), str(conf.llama_dir),
        ])
        if clone.returncode != 0:
            bad("clone failed")
            return 1
    else:
        ok("already cloned")

    if not os.access(conf.server, os.X_OK):
        print("  building (this takes a while)…")
        configure = subprocess.run([
            "cmake", "-S", str(conf.llama_dir), "-B", str(conf.llama_dir / "build"),
            "-DGGML_CUDA=ON", "-DGGML_CUDA_FA_ALL_QUANTS=ON", "-DCMAKE_BUILD_TYPE=Release",
        ])
        build = subprocess.run([
            "cmake", "--build", str(conf.llama_dir / "build"),
            "--config", "Release", "--target", "llama-server", "-j",
        ]) if configure.returncode == 0 else configure
        if build.returncode != 0:
            bad("build failed")
            return 1
    ok("llama-server ready")

    section("Models")
    if not shutil.which("hf"):
        bad("hf CLI missing", "— pip install huggingface_hub[cli]")
        return 1

    def fetch(repo: str, filename: str, label: str) -> bool:
        if model_path(repo, filename):
            ok(f"{label} present")
            return True
        print(f"  fetching {label} ({filename})…")
        return subprocess.run(["hf", "download", repo, filename]).returncode == 0

    if not fetch(conf.str("MAIN_REPO"), conf.str("MAIN_FILE"), "main"):
        return 1
    # The projector is a separate download from the same repo. Without this
    # step the stack comes up looking healthy and only fails on the first image.
    projector_file = conf.str("MAIN_MMPROJ_FILE")
    if projector_file and not fetch(conf.str("MAIN_REPO"), projector_file, "mmproj"):
        warn("mmproj download failed", "— vision stays off")
    draft_repo, draft_file = conf.str("MAIN_DRAFT_REPO"), conf.str("MAIN_DRAFT_FILE")
    if draft_repo and draft_file and not draft_file.startswith(("/", "~", "./")) \
            and not fetch(draft_repo, draft_file, "DFlash2 draft"):
        warn("DFlash2 draft download failed", "— falls back to MTP + ngram-mod")
    if conf.enabled("aux") and not fetch(conf.str("AUX_REPO"), conf.str("AUX_FILE"), "aux"):
        return 1
    if conf.enabled("vis"):
        vis_repo = conf.str("VIS_REPO")
        if vis_repo:
            fetch(vis_repo, conf.str("VIS_FILE"), "vision model")
            fetch(vis_repo, conf.str("VIS_MMPROJ_FILE"), "vision mmproj")
        else:
            warn("VIS_ENABLED=1 but VIS_REPO is empty", f"— set it in {conf_path()}")

    print()
    ok("setup complete", "— daedalus doctor start")
    return 0


def _main_argv(conf: StackConf, model: str) -> list:
    kv_pool = conf.str("MAIN_KV_POOL")
    slots = conf.int("MAIN_SLOTS", 1)
    # Block KV streaming needs a single KV *stream*, not literally one
    # sequence (llama.cpp-adaptive-kv-streaming commit 002b6bce1, 2026-09-11):
    # a unified KV buffer collapses any slot count to one stream, so -np N
    # --kv-unified is fine and was verified running two real parallel slots
    # on this fork. Old builds without that patch will refuse to start with
    # "block KV streaming requires exactly one sequence (-np 1)" -- if that
    # happens, `daedalus doctor setup` needs to rebuild the fork.
    needs_unified = bool(kv_pool) and slots != 1

    argv = [
        str(conf.server), "--model", model,
        "--host", conf.str("MAIN_HOST", "127.0.0.1"), "--port", str(conf.int("MAIN_PORT", 8080)),
        "--ctx-size", str(conf.int("MAIN_CTX", 131072)),
    ]
    # An empty pool means "no block KV streaming"; passing the flag with an
    # empty value would hand llama-server an argument it cannot parse.
    if kv_pool:
        argv += ["--kv-stream-stage-mib", kv_pool]
    argv += [
        # 2026-09-12: this was hardcoded to q4_0/q4_0 -- the same "drifted
        # from the actual benchmark" bug as the spec-decode and vision
        # defaults above. ~/projects/specbench/campaign/GOAT.sh (the winning
        # config) uses q8_0/q4_0: K-cache quantization is more sensitive to
        # attention accuracy than V, so q4_0 on K was a silent quality
        # regression, not a VRAM decision anyone made on purpose.
        "-ctk", conf.str("MAIN_CTK", "q8_0"), "-ctv", conf.str("MAIN_CTV", "q4_0"), "-fa", "on",
        "-ngl", str(conf.int("MAIN_NGL", 99)), "-t", str(conf.int("MAIN_THREADS", 8)),
        "-np", str(slots),
        "-b", "512", "-ub", "512",
        "--temp", "1.0", "--top-k", "20", "--min-p", "0.00", "--top-p", "0.95",
        "--presence-penalty", "0.0", "--repeat-penalty", "1.0",
        "--reasoning", "on", "--reasoning-preserve", "--reasoning-format", "deepseek",
        "--reasoning-budget", str(conf.int("MAIN_REASONING_BUDGET", 12000)),
        "--jinja", "--cont-batching",
        # llama-server's prompt cache lives in ordinary host RAM and defaults
        # to 8192 MiB. Unlike the block-KV host buffer it is swappable, so on
        # a box that is already tight it does not fail -- it pages, and every
        # cache lookup becomes a disk fault. That is what a long session
        # feels like when throughput decays over hours rather than falling
        # over. MAIN_CACHE_RAM caps it; 0 disables the cache entirely, -1 is
        # llama.cpp's "no limit".
        "--cache-ram", str(conf.int("MAIN_CACHE_RAM", 2048)),
        # Exposes /metrics (Prometheus text) -- session tok/s, KV cache-hit
        # counters, and the DFlash2/spec-decode draft-acceptance counters
        # (spec_decode_num_{draft,accepted}_tokens_total) used nowhere else:
        # /slots has per-turn cache usage but not draft-acceptance at all.
        # Near-zero overhead (counter bumps only), off by default upstream.
        "--metrics",
    ]
    # Keep MAIN_CTX as one shared buffer instead of MAIN_CTX/slots each.
    # Automatic whenever KV streaming is on with more than one slot -- that
    # combination is a dead server without it (see needs_unified above) -- or
    # when explicitly requested for the plain multi-slot case.
    if needs_unified or conf.flag("MAIN_KV_UNIFIED", False):
        argv.append("-kvu")
        # --cache-idle-slots is on by default and, under -kvu, saves an idle
        # slot's prompt to the prompt cache and then calls slot.prompt_clear()
        # on it. With two slots that means every task launched on one slot
        # wipes the other's cached prefix, so both slots spend their lives
        # re-prefilling the same history and appear to be fighting over the
        # same work. Only harmful in the unified case, hence the placement.
        argv.append("--no-cache-idle-slots")

    # Speculative decoding: DFlash2 (a real second model, benchmarked in
    # ~/projects/specbench -- GOAT.sh is the winning config, n-max 4 / n-min 1)
    # whenever a draft model is configured and present, falling back to the
    # target model's own MTP head + ngram matching (no extra VRAM, no extra
    # file) when it isn't. 2026-09-12: this had been hardcoded to the MTP
    # fallback unconditionally -- DFlash2 was fully tuned in specbench but
    # never actually wired into the real launch path, so every daedalus
    # session ran the untuned scheme while a validated ~536MB draft model sat
    # unused on disk.
    draft_repo = conf.str("MAIN_DRAFT_REPO")
    draft_file = conf.str("MAIN_DRAFT_FILE")
    draft = model_path(draft_repo, draft_file) if draft_file else ""
    if draft:
        argv += [
            "--model-draft", draft,
            # -ngld defaults to auto (-1), which lets the memory fitter decide
            # how much of the drafter to offload. It is ~1.1GB; offload it all
            # -- a drafter running partly on CPU costs more than it saves.
            "-ngld", str(conf.int("MAIN_NGL", 99)),
            "--spec-type", "draft-dflash",
            "--spec-draft-n-max", str(conf.int("MAIN_DRAFT_N_MAX", 4)),
            "--spec-draft-n-min", str(conf.int("MAIN_DRAFT_N_MIN", 1)),
        ]
        dim(f"speculative: DFlash2 ({os.path.basename(draft)})")
    else:
        argv += [
            "--spec-type", "draft-mtp,ngram-mod", "--spec-draft-n-max", "2",
            "--spec-ngram-mod-n-match", "24", "--spec-ngram-mod-n-min", "24",
            "--spec-ngram-mod-n-max", "32",
        ]
        if draft_repo or draft_file:
            warn("DFlash2 draft model missing", "— run: daedalus doctor setup")
        dim("speculative: MTP + ngram-mod (no draft model configured)")

    # Vision is opt-in (MAIN_VISION, default off), not just "load it whenever
    # the projector happens to be present": on a 16GB card already carrying a
    # 27B + a DFlash2 draft model + 2 slots, the ~890MB mmproj tower is real
    # VRAM competing with everything else, for a capability most turns never
    # use. `daedalus doctor setup` still fetches it so it's one flag away.
    projector = conf.mmproj
    if conf.flag("MAIN_VISION", False):
        if projector and os.path.isfile(projector):
            # --no-mmproj-offload keeps the ~890 MB tower in host RAM. On a
            # 16 GB card already holding a 27B at -ngl 99 that is the
            # difference between vision working and the weights not fitting.
            argv += ["-mm", projector, "--no-mmproj-offload",
                     "--image-min-tokens", "1024", "--image-max-tokens", "2048"]
            dim(f"vision: {os.path.basename(projector)}")
        else:
            warn("MAIN_VISION=1 but no projector", "— vision_analyze will 500")
            note("fetch it with: daedalus doctor setup")
    elif projector and os.path.isfile(projector):
        dim("vision: off (MAIN_VISION=0) — projector present, set MAIN_VISION=1 to use it")
    else:
        note("vision: off — no projector fetched either (daedalus doctor setup to get one)")
    return argv


def cmd_start(args=None) -> int:
    conf = load_conf()
    main = model_path(conf.str("MAIN_REPO"), conf.str("MAIN_FILE"))
    if not os.access(conf.server, os.X_OK):
        bad("llama-server not built", "— run: daedalus doctor setup")
        return 1
    if not main:
        bad("main model missing", "— run: daedalus doctor setup")
        return 1

    section("Starting")
    # Block KV streaming keeps most of the cache in pinned host memory and
    # pages it in; unified memory is what lets an allocation that overshoots
    # VRAM spill to the host instead of failing the launch outright. Without
    # it, MAIN_KV_POOL is a hard ceiling and overshooting it is an OOM at
    # startup rather than a slowdown. The hand-written launch this stack
    # mirrors has always set it; the stack did not, so the two behaved
    # differently under exactly the conditions that matter.
    main_env = {"GGML_CUDA_ENABLE_UNIFIED_MEMORY": "1"}
    if not start_one("main", _main_argv(conf, main), env=main_env):
        return 1

    # The main model must be READY before the helper starts. Both loading at
    # once means two processes fighting for RAM while the big one is pinning
    # its KV cache: the machine swaps, and anything else on it (a memory pod
    # running consolidation, for one) stalls behind the page-outs.
    main_host, main_port = conf.host_port("main")
    if not wait_ready("main", main_host, main_port, 300):
        return 1

    if conf.enabled("aux"):
        aux = model_path(conf.str("AUX_REPO"), conf.str("AUX_FILE"))
        aux_host, aux_port = conf.host_port("aux")
        if aux_port == main_port:
            # AUX_PORT == MAIN_PORT means aux is meant to share the main
            # process's second slot (MAIN_SLOTS=2 --kv-unified), not run as
            # its own process -- a separate process here would either refuse
            # to bind the port main already holds, or bind it in a race and
            # leave one of the two half-started. auxiliary_client.py routes
            # to id_slot=0 on the main endpoint for exactly this case -- slot
            # 0 is the sidekick and slot 1 is the main conversation, because
            # llama-server fills its batch in slot-index order and the lower
            # index gets priority (see MAIN_SLOTS in stack.conf); there is
            # nothing left for this branch to launch.
            note(f"aux shares main's port ({main_port}) — served by slot 0 "
                 f"of the main process, not launched separately")
        elif aux:
            # --reasoning off is load-bearing: with thinking on, a 1.7B spends
            # its whole output budget reasoning and returns empty content.
            start_one("aux", [
                str(conf.server), "--model", aux,
                "--host", aux_host, "--port", str(aux_port),
                "--ctx-size", str(conf.int("AUX_CTX", 12096)),
                "-ngl", "0", "-t", str(conf.int("AUX_THREADS", 6)), "-np", "2",
                "-b", "512", "-ub", "512", "--cont-batching", "--jinja",
                "--temp", "0.3", "--top-p", "0.9", "--reasoning", "off",
            ])
            wait_ready("aux", aux_host, aux_port, 180)
        else:
            warn("aux model missing", "— skipping")

    if conf.enabled("vis"):
        vis = model_path(conf.str("VIS_REPO"), conf.str("VIS_FILE"))
        vis_mm = model_path(conf.str("VIS_REPO"), conf.str("VIS_MMPROJ_FILE"))
        if not vis or not vis_mm:
            warn("VIS_ENABLED=1 but model/projector missing", "— run: daedalus doctor setup")
        else:
            vis_host, vis_port = conf.host_port("vis")
            # -ngl 0 on purpose: it costs no VRAM beside the main model, and
            # being a separate process it answers WHILE the main turn is
            # generating, which is the entire reason this endpoint exists.
            start_one("vis", [
                str(conf.server), "--model", vis, "-mm", vis_mm,
                "--host", vis_host, "--port", str(vis_port),
                "--ctx-size", str(conf.int("VIS_CTX", 16384)),
                "-ngl", "0", "-t", str(conf.int("VIS_THREADS", 4)), "-np", "2",
                "-b", "512", "-ub", "512", "--cont-batching", "--jinja",
                "--reasoning", "off",
            ])
            wait_ready("vis", vis_host, vis_port, 300)
            note(f"point auxiliary.vision.base_url at http://{vis_host}:{vis_port}/v1")
    return 0


def cmd_stop(args=None) -> int:
    section("Stopping")
    # Reverse of start: the dependents go first, the main model last.
    for name in ("vis", "aux", "main"):
        stop_one(name)
    return 0


def cmd_restart(args=None) -> int:
    cmd_stop(args)
    return cmd_start(args)


def _signal_all(sig, verb: str) -> int:
    section(verb.capitalize())
    touched = False
    for name in SERVERS:
        pid = pid_of(name)
        if alive(pid):
            try:
                os.kill(pid, sig)
                ok(f"{name} {verb}")
                touched = True
            except OSError as exc:
                bad(f"{name} could not be {verb}", f"({exc})")
    if not touched:
        warn("nothing running")
    return 0


def cmd_pause(args=None) -> int:
    result = _signal_all(signal.SIGSTOP, "paused")
    note("weights stay loaded; resume with: daedalus doctor resume")
    return result


def cmd_resume(args=None) -> int:
    return _signal_all(signal.SIGCONT, "resumed")


def cmd_logs(args=None) -> int:
    name = getattr(args, "server", None) or "main"
    lines = getattr(args, "lines", 200)
    follow = not getattr(args, "no_follow", False)
    target = log_file(name)
    if not target.exists():
        bad(f"no log for {name}", f"({target})")
        return 1
    argv = ["tail", "-n", str(lines)] + (["-f"] if follow else []) + [str(target)]
    try:
        return subprocess.run(argv).returncode
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        bad("cannot tail the log", f"({exc})")
        return 1


def cmd_conf(args=None) -> int:
    """Show where the knobs live, and create the file if it is missing."""
    target = conf_path()
    existed = target.exists()
    conf = load_conf()
    section("Stack configuration")
    ok(str(target)) if existed else ok(str(target), "(created with defaults)")
    note(f"llama.cpp   {conf.llama_dir}")
    for name in SERVERS:
        if not conf.enabled(name):
            continue
        host, port = conf.host_port(name)
        repo = conf.str(f"{name.upper()}_REPO") or "—"
        note(f"{name:<11} {repo} → {host}:{port}")
    note(f"logs        {log_dir()}")
    print()
    return 0



# ------------------------------------------------------------- watchdog ------

def read_metrics(host: str, port: int, timeout: float = 3.0) -> dict:
    """Scrape llama-server's Prometheus endpoint into a plain dict.

    Needs --metrics on the server (``start`` passes it). Returns {} on any
    trouble: a watchdog that mistakes its own scrape failure for a slow
    server would restart a perfectly healthy one.
    """
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/metrics", timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except Exception:
        return {}
    out = {}
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition(" ")
        if name.startswith("llamacpp:") and "{" not in name:
            try:
                out[name[len("llamacpp:"):]] = float(value)
            except ValueError:
                continue
    return out


def sample_decode_rate(prev: dict, cur: dict):
    """Generation tokens/s between two /metrics scrapes, or None.

    Deliberately a windowed rate from the counters rather than the
    ``predicted_tokens_seconds`` gauge: that gauge is a lifetime average, so
    after a fast hour it takes a very long slow patch to drag it under any
    threshold worth acting on. None means "no verdict" -- the server produced
    no tokens in this window (it was idle), a counter went backwards (it
    restarted underneath us), or a scrape failed. Idle must never look slow.
    """
    if not prev or not cur:
        return None
    d_tokens = cur.get("tokens_predicted_total", 0.0) - prev.get("tokens_predicted_total", 0.0)
    d_seconds = cur.get("tokens_predicted_seconds_total", 0.0) - prev.get("tokens_predicted_seconds_total", 0.0)
    if d_tokens <= 0 or d_seconds <= 0:
        return None
    return d_tokens / d_seconds


def cmd_watch(args) -> int:
    """Restart the main server when generation throughput collapses.

    Long sessions on this fork degrade rather than fail: throughput drifts
    down and stays down, and the fix is a restart. That is cheap here in a way
    it is not for a conventional harness -- daedalus keeps its transcript in
    mazemaker and sends only a window, so a cold KV cache costs one small
    prefill, not a replay of the whole conversation.

    Restarts only on sustained slowness across consecutive *productive*
    windows, and never twice inside the cooldown, because a restart loop on a
    machine that is merely busy is worse than the slowness it is treating.
    """
    conf = load_conf()
    host, port = conf.host_port("main")
    threshold = float(args.threshold)
    interval = max(5.0, float(args.interval))
    trips_needed = max(1, int(args.trips))
    cooldown = max(0.0, float(args.cooldown))

    section("Throughput watchdog")
    dim(f"{host}:{port} · restart below {threshold:g} tok/s for "
        f"{trips_needed} consecutive {interval:g}s windows · cooldown {cooldown:g}s")

    if not port_up(host, port):
        bad("main server is not up", "— nothing to watch")
        return 1
    if not read_metrics(host, port):
        bad("/metrics returned nothing",
            "— the server needs --metrics (daedalus doctor start passes it)")
        return 1

    prev = read_metrics(host, port)
    trips = 0
    last_restart = 0.0
    try:
        while True:
            time.sleep(interval)
            cur = read_metrics(host, port)
            rate = sample_decode_rate(prev, cur)
            prev = cur or prev
            if rate is None:
                continue                      # idle, restarted, or scrape failed
            if rate >= threshold:
                if trips:
                    dim(f"recovered at {rate:.1f} tok/s")
                trips = 0
                continue
            trips += 1
            warn(f"{rate:.1f} tok/s", f"— below {threshold:g} ({trips}/{trips_needed})")
            if trips < trips_needed:
                continue
            since = time.time() - last_restart
            if last_restart and since < cooldown:
                dim(f"cooldown: {cooldown - since:.0f}s before another restart")
                continue
            bad("sustained slow generation", "— restarting the main server")
            stop_one("main")
            model = model_path(conf.str("MAIN_REPO"), conf.str("MAIN_FILE"))
            if not model:
                bad("main model missing", "— cannot restart")
                return 1
            if not start_one("main", _main_argv(conf, model),
                             env={"GGML_CUDA_ENABLE_UNIFIED_MEMORY": "1"}):
                return 1
            if not wait_ready("main", host, port, 300):
                return 1
            last_restart = time.time()
            trips = 0
            prev = read_metrics(host, port)
    except KeyboardInterrupt:
        print()
        dim("watchdog stopped")
        return 0


# -------------------------------------------------------------- wiring -------

def register_cli(parser: argparse.ArgumentParser) -> None:
    """Wire the stack lifecycle onto the ``daedalus doctor`` parser.

    The bare ``daedalus doctor`` keeps whatever the caller set as its default
    handler — the full report — so adding these is purely additive.
    """
    subs = parser.add_subparsers(dest="doctor_command", metavar="COMMAND")

    def add(name, help_text):
        return subs.add_parser(name, help=help_text)

    add("status", "Show the inference servers: ports, pids, VRAM").set_defaults(func=cmd_status)
    add("stack", "Only the local inference stack section of the report").set_defaults(func=cmd_doctor)
    add("setup", "Clone and build llama.cpp, then fetch the models").set_defaults(func=cmd_setup)
    add("start", "Start the inference servers (helper waits for the main model)").set_defaults(func=cmd_start)
    add("stop", "Stop the inference servers").set_defaults(func=cmd_stop)
    add("restart", "Stop, then start").set_defaults(func=cmd_restart)
    add("pause", "Freeze the servers, keeping the weights loaded").set_defaults(func=cmd_pause)
    add("resume", "Unfreeze paused servers").set_defaults(func=cmd_resume)
    add("conf", "Show the stack.conf path and the values in force").set_defaults(func=cmd_conf)

    p_watch = add("watch", "Restart the main server if generation throughput collapses")
    p_watch.add_argument("--threshold", type=float, default=20.0,
                         help="Generation tok/s below which a window counts as slow (default 20)")
    p_watch.add_argument("--interval", type=float, default=30.0,
                         help="Seconds between /metrics samples (default 30)")
    p_watch.add_argument("--trips", type=int, default=3,
                         help="Consecutive slow windows before restarting (default 3)")
    p_watch.add_argument("--cooldown", type=float, default=300.0,
                         help="Minimum seconds between restarts (default 300)")
    p_watch.set_defaults(func=cmd_watch)

    p_logs = add("logs", "Tail a server log")
    p_logs.add_argument("server", nargs="?", default="main", choices=list(SERVERS),
                        help="Which server's log (default: main)")
    p_logs.add_argument("-n", "--lines", type=int, default=200,
                        help="Lines of history to show first (default 200)")
    p_logs.add_argument("--no-follow", action="store_true",
                        help="Print the tail and exit instead of following")
    p_logs.set_defaults(func=cmd_logs)
