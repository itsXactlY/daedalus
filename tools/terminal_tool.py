#!/usr/bin/env python3
"""
Terminal Tool Module

A terminal tool that executes commands in local, Modal, SSH, Singularity, and Daytona environments.
Supports local execution, containerized backends, and Modal cloud sandboxes, including managed gateway mode.

Environment Selection (via TERMINAL_ENV environment variable):
- "local": Execute directly on the host machine (default, fastest)
- "modal": Execute in Modal cloud sandboxes (direct Modal or managed gateway)

Features:
- Multiple execution backends (local, modal, singularity, daytona, ssh)
- Background task support
- VM/container lifecycle management
- Automatic cleanup after inactivity

Cloud sandbox note:
- Persistent filesystems preserve working state across sandbox recreation
- Persistent filesystems do NOT guarantee the same live sandbox or long-running processes survive cleanup, idle reaping, or Daedalus exit

Usage:
    from terminal_tool import terminal_tool

    # Execute a simple command
    result = terminal_tool("ls -la")

    # Execute in background
    result = terminal_tool("python server.py", background=True)
"""

import importlib.util
import json
import logging
import os
import platform
import re
import time
import threading
import atexit
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Tuple

logger = logging.getLogger(__name__)


from tools.interrupt import is_interrupted, _interrupt_event  # noqa: F401 — re-exported


def ensure_minisweagent_on_path(_repo_root: Path | None = None) -> None:
    """Backward-compatible no-op after minisweagent_path.py removal."""
    return



from tools.environments.singularity import _get_scratch_dir
from tools.tool_backend_helpers import (
    coerce_modal_mode,
    has_direct_modal_credentials,
    managed_nous_tools_enabled,
    resolve_modal_backend_state,
)


DISK_USAGE_WARNING_THRESHOLD_GB = float(os.getenv("TERMINAL_DISK_WARNING_GB", "500"))


def _check_disk_usage_warning():
    """Check if total disk usage exceeds warning threshold."""
    try:
        scratch_dir = _get_scratch_dir()

        total_bytes = 0
        import glob
        for path in glob.glob(str(scratch_dir / "daedalus-*")):
            for f in Path(path).rglob('*'):
                if f.is_file():
                    try:
                        total_bytes += f.stat().st_size
                    except OSError as e:
                        logger.debug("Could not stat file %s: %s", f, e)
        
        total_gb = total_bytes / (1024 ** 3)
        
        if total_gb > DISK_USAGE_WARNING_THRESHOLD_GB:
            logger.warning("Disk usage (%.1fGB) exceeds threshold (%.0fGB). Consider running cleanup_all_environments().",
                           total_gb, DISK_USAGE_WARNING_THRESHOLD_GB)
            return True
        
        return False
    except Exception as e:
        logger.debug("Disk usage warning check failed: %s", e, exc_info=True)
        return False


_cached_sudo_password: str = ""

_sudo_password_callback = None
_approval_callback = None


def set_sudo_password_callback(cb):
    """Register a callback for sudo password prompts (used by CLI)."""
    global _sudo_password_callback
    _sudo_password_callback = cb


def set_approval_callback(cb):
    """Register a callback for dangerous command approval prompts (used by CLI)."""
    global _approval_callback
    _approval_callback = cb


from tools.approval import (
    check_dangerous_command as _check_dangerous_command_impl,
    check_all_command_guards as _check_all_guards_impl,
)


def _check_all_guards(command: str, env_type: str) -> dict:
    """Delegate to consolidated guard (tirith + dangerous cmd) with CLI callback."""
    return _check_all_guards_impl(command, env_type,
                                  approval_callback=_approval_callback)


_WORKDIR_SAFE_RE = re.compile(r'^[A-Za-z0-9/_\-.~ +@=,]+$')


def _validate_workdir(workdir: str) -> str | None:
    """Reject workdir values that don't look like a filesystem path.

    Uses an allowlist of safe characters rather than a deny-list, so novel
    shell metacharacters can't slip through.

    Returns None if safe, or an error message string if dangerous.
    """
    if not workdir:
        return None
    if not _WORKDIR_SAFE_RE.match(workdir):
        for ch in workdir:
            if not _WORKDIR_SAFE_RE.match(ch):
                return (
                    f"Blocked: workdir contains disallowed character {repr(ch)}. "
                    "Use a simple filesystem path without shell metacharacters."
                )
        return "Blocked: workdir contains disallowed characters."
    return None


def _handle_sudo_failure(output: str, env_type: str) -> str:
    """
    Check for sudo failure and add helpful message for messaging contexts.
    
    Returns enhanced output if sudo failed in messaging context, else original.
    """
    is_gateway = os.getenv("DAEDALUS_GATEWAY_SESSION")
    
    if not is_gateway:
        return output
    
    sudo_failures = [
        "sudo: a password is required",
        "sudo: no tty present",
        "sudo: a terminal is required",
    ]
    
    for failure in sudo_failures:
        if failure in output:
            from daedalus_constants import display_daedalus_home as _dhh
            return output + f"\n\n💡 Tip: To enable sudo over messaging, add SUDO_PASSWORD to {_dhh()}/.env on the agent machine."
    
    return output


def _prompt_for_sudo_password(timeout_seconds: int = 45) -> str:
    """
    Prompt user for sudo password with timeout.
    
    Returns the password if entered, or empty string if:
    - User presses Enter without input (skip)
    - Timeout expires (45s default)
    - Any error occurs
    
    Only works in interactive mode (DAEDALUS_INTERACTIVE=1).
    If a _sudo_password_callback is registered (by the CLI), delegates to it
    so the prompt integrates with prompt_toolkit's UI.  Otherwise reads
    directly from /dev/tty with echo disabled.
    """
    import sys
    import time as time_module
    
    if _sudo_password_callback is not None:
        try:
            return _sudo_password_callback() or ""
        except Exception:
            return ""

    result = {"password": None, "done": False}
    
    def read_password_thread():
        """Read password with echo disabled. Uses msvcrt on Windows, /dev/tty on Unix."""
        tty_fd = None
        old_attrs = None
        try:
            if platform.system() == "Windows":
                import msvcrt
                chars = []
                while True:
                    c = msvcrt.getwch()
                    if c in ("\r", "\n"):
                        break
                    if c == "\x03":
                        raise KeyboardInterrupt
                    chars.append(c)
                result["password"] = "".join(chars)
            else:
                import termios
                tty_fd = os.open("/dev/tty", os.O_RDONLY)
                old_attrs = termios.tcgetattr(tty_fd)
                new_attrs = termios.tcgetattr(tty_fd)
                new_attrs[3] = new_attrs[3] & ~termios.ECHO
                termios.tcsetattr(tty_fd, termios.TCSAFLUSH, new_attrs)
                chars = []
                while True:
                    b = os.read(tty_fd, 1)
                    if not b or b in (b"\n", b"\r"):
                        break
                    chars.append(b)
                result["password"] = b"".join(chars).decode("utf-8", errors="replace")
        except (EOFError, KeyboardInterrupt, OSError):
            result["password"] = ""
        except Exception:
            result["password"] = ""
        finally:
            if tty_fd is not None and old_attrs is not None:
                try:
                    import termios as _termios
                    _termios.tcsetattr(tty_fd, _termios.TCSAFLUSH, old_attrs)
                except Exception as e:
                    logger.debug("Failed to restore terminal attributes: %s", e)
            if tty_fd is not None:
                try:
                    os.close(tty_fd)
                except Exception as e:
                    logger.debug("Failed to close tty fd: %s", e)
            result["done"] = True
    
    try:
        os.environ["DAEDALUS_SPINNER_PAUSE"] = "1"
        time_module.sleep(0.2)
        
        print()
        print("┌" + "─" * 58 + "┐")
        print("│  🔐 SUDO PASSWORD REQUIRED" + " " * 30 + "│")
        print("├" + "─" * 58 + "┤")
        print("│  Enter password below (input is hidden), or:            │")
        print("│    • Press Enter to skip (command fails gracefully)     │")
        print(f"│    • Wait {timeout_seconds}s to auto-skip" + " " * 27 + "│")
        print("└" + "─" * 58 + "┘")
        print()
        print("  Password (hidden): ", end="", flush=True)
        
        password_thread = threading.Thread(target=read_password_thread, daemon=True)
        password_thread.start()
        password_thread.join(timeout=timeout_seconds)
        
        if result["done"]:
            password = result["password"] or ""
            print()
            if password:
                print("  ✓ Password received (cached for this session)")
            else:
                print("  ⏭ Skipped - continuing without sudo")
            print()
            sys.stdout.flush()
            return password
        else:
            print("\n  ⏱ Timeout - continuing without sudo")
            print("    (Press Enter to dismiss)")
            print()
            sys.stdout.flush()
            return ""
            
    except (EOFError, KeyboardInterrupt):
        print()
        print("  ⏭ Cancelled - continuing without sudo")
        print()
        sys.stdout.flush()
        return ""
    except Exception as e:
        print(f"\n  [sudo prompt error: {e}] - continuing without sudo\n")
        sys.stdout.flush()
        return ""
    finally:
        if "DAEDALUS_SPINNER_PAUSE" in os.environ:
            del os.environ["DAEDALUS_SPINNER_PAUSE"]


def _transform_sudo_command(command: str) -> tuple[str, str | None]:
    """
    Transform sudo commands to use -S flag if SUDO_PASSWORD is available.

    This is a shared helper used by all execution environments to provide
    consistent sudo handling across local, SSH, and container environments.

    Returns:
        (transformed_command, sudo_stdin) where:
        - transformed_command has every bare ``sudo`` replaced with
          ``sudo -S -p ''`` so sudo reads its password from stdin.
        - sudo_stdin is the password string with a trailing newline that the
          caller must prepend to the process's stdin stream.  sudo -S reads
          exactly one line (the password) and passes the rest of stdin to the
          child command, so prepending is safe even when the caller also has
          its own stdin_data to pipe.
        - If no password is available, sudo_stdin is None and the command is
          returned unchanged so it fails gracefully with
          "sudo: a password is required".

    Callers that drive a subprocess directly (local, ssh, singularity)
    should prepend sudo_stdin to their stdin_data and pass the merged bytes to
    Popen's stdin pipe.

    Callers that cannot pipe subprocess stdin (modal, daytona) must embed the
    password in the command string themselves; see their execute() methods for
    how they handle the non-None sudo_stdin case.

    If SUDO_PASSWORD is not set and in interactive mode (DAEDALUS_INTERACTIVE=1):
      Prompts user for password with 45s timeout, caches for session.

    If SUDO_PASSWORD is not set and NOT interactive:
      Command runs as-is (fails gracefully with "sudo: a password is required").
    """
    global _cached_sudo_password
    import re

    if not re.search(r'\bsudo\b', command):
        return command, None

    sudo_password = os.getenv("SUDO_PASSWORD", "") or _cached_sudo_password

    if not sudo_password:
        if os.getenv("DAEDALUS_INTERACTIVE"):
            sudo_password = _prompt_for_sudo_password(timeout_seconds=45)
            if sudo_password:
                _cached_sudo_password = sudo_password

    if not sudo_password:
        return command, None

    def replace_sudo(match):
        return "sudo -S -p ''"

    transformed = re.sub(r'\bsudo\b', replace_sudo, command)
    return transformed, sudo_password + "\n"


from tools.environments.local import LocalEnvironment as _LocalEnvironment
from tools.environments.singularity import SingularityEnvironment as _SingularityEnvironment
from tools.environments.ssh import SSHEnvironment as _SSHEnvironment
from tools.environments.modal import ModalEnvironment as _ModalEnvironment
from tools.environments.managed_modal import ManagedModalEnvironment as _ManagedModalEnvironment
from tools.managed_tool_gateway import is_managed_tool_gateway_ready


TERMINAL_TOOL_DESCRIPTION = """Execute shell commands on a Linux environment. Filesystem usually persists between calls.

Prefer the file tools (read_file, search_files, patch, write_file) for file ops. Reserve terminal for builds, git, processes, scripts, network, package managers — anything needing a shell.

Foreground (default): returns when done; timeout is a max wait, not a delay.
Background (background=true): returns session_id for long-lived processes (servers, watchers) or long tasks with notify_on_complete=true (auto-notify on completion). process(action="poll") checks, process(action="wait") blocks.
workdir: per-command cwd. pty=true: interactive CLIs. vim/nano need pty=true — they hang otherwise.

Cloud sandboxes may be recreated between turns — files persist, background processes may not. Not durable hosting.
"""

_active_environments: Dict[str, Any] = {}
_last_activity: Dict[str, float] = {}
_env_lock = threading.Lock()
_creation_locks: Dict[str, threading.Lock] = {}
_creation_locks_lock = threading.Lock()
_cleanup_thread = None
_cleanup_running = False

_task_env_overrides: Dict[str, Dict[str, Any]] = {}


def register_task_env_overrides(task_id: str, overrides: Dict[str, Any]):
    """
    Register environment overrides for a specific task/rollout.

    Called by Atropos environments before the agent loop to configure
    per-task sandbox settings (e.g., a custom image for the Modal backend).

    Supported override keys:
        - modal_image: str -- Path to Dockerfile or Docker Hub image name
        - cwd: str -- Working directory inside the sandbox

    Args:
        task_id: The rollout's unique task identifier
        overrides: Dict of config keys to override
    """
    for _key in _IMAGE_OVERRIDE_KEYS:
        if _key in overrides:
            _check_image_provenance(_key, overrides[_key])

    _task_env_overrides[task_id] = overrides


def clear_task_env_overrides(task_id: str):
    """
    Clear environment overrides for a task after rollout completes.

    Called during cleanup to avoid stale entries accumulating.
    """
    _task_env_overrides.pop(task_id, None)


_DEFAULT_TRUSTED_IMAGE_REGISTRIES = (
    "docker.io",
    "ghcr.io",
    "gcr.io",
    "quay.io",
    "registry.k8s.io",
    "public.ecr.aws",
    "mcr.microsoft.com",
)

_IMAGE_SCHEMES = ("docker://", "oci://", "docker-archive://", "docker-daemon://")

_warned_images: Set[Tuple[str, str]] = set()


def _trusted_image_registries() -> Tuple[str, ...]:
    """Trusted registry hosts: the defaults plus any operator additions."""
    extra = os.getenv("DAEDALUS_TERMINAL_TRUSTED_REGISTRIES", "")
    added = tuple(h.strip().lower() for h in extra.split(",") if h.strip())
    return _DEFAULT_TRUSTED_IMAGE_REGISTRIES + added


def _image_registry_host(image: str) -> Optional[str]:
    """Return the registry host an image reference resolves to.

    Applies Docker's own rule: the first path segment is a registry host only
    if it contains a ``.`` or ``:`` or is exactly ``localhost``; otherwise the
    reference is an implicit Docker Hub name (``nikolaik/python-nodejs:...``,
    ``python:3.11``). Returns ``None`` for references we deliberately don't
    classify — local Dockerfile paths, which Modal accepts in place of an
    image name.
    """
    ref = (image or "").strip()
    for scheme in _IMAGE_SCHEMES:
        if ref.startswith(scheme):
            ref = ref[len(scheme):]
            break
    if not ref:
        return None
    if ref.startswith(("/", "./", "../", "~")) or os.path.basename(ref) == "Dockerfile":
        return None
    head = ref.split("/", 1)[0]
    if "/" in ref and ("." in head or ":" in head or head == "localhost"):
        return head.lower()
    return "docker.io"


def image_is_trusted(image: str) -> bool:
    """Is *image* served by a recognized registry? Unclassifiable refs pass."""
    host = _image_registry_host(image)
    if host is None:
        return True
    return host in _trusted_image_registries()


def _check_image_provenance(field: str, image: Any) -> None:
    """Log a warning when *image* comes from an unrecognized registry."""
    if not isinstance(image, str) or not image.strip():
        return
    if image_is_trusted(image):
        return
    key = (field, image)
    if key in _warned_images:
        return
    _warned_images.add(key)
    logger.warning(
        "Sandbox %s=%r resolves to registry %r, which is not in the trusted "
        "set (%s). The sandbox will pull and execute this image. Add the host "
        "to DAEDALUS_TERMINAL_TRUSTED_REGISTRIES to silence this warning.",
        field, image, _image_registry_host(image),
        ", ".join(_trusted_image_registries()),
    )


_IMAGE_OVERRIDE_KEYS = (
    "modal_image", "singularity_image", "daytona_image",
)


def _parse_env_var(name: str, default: str, converter=int, type_label: str = "integer"):
    """Parse an environment variable with *converter*, raising a clear error on bad values.

    Without this wrapper, a single malformed env var (e.g. TERMINAL_TIMEOUT=5m)
    causes an unhandled ValueError that kills every terminal command.
    """
    raw = os.getenv(name, default)
    try:
        return converter(raw)
    except (ValueError, json.JSONDecodeError):
        raise ValueError(
            f"Invalid value for {name}: {raw!r} (expected {type_label}). "
            f"Check ~/.daedalus/.env or environment variables."
        )


def _get_env_config() -> Dict[str, Any]:
    """Get terminal environment configuration from environment variables."""
    default_image = "nikolaik/python-nodejs:python3.11-nodejs20"
    env_type = os.getenv("TERMINAL_ENV", "local")

    if env_type == "local":
        default_cwd = os.getcwd()
    elif env_type == "ssh":
        default_cwd = "~"
    else:
        default_cwd = "/root"

    cwd = os.getenv("TERMINAL_CWD", default_cwd)
    host_prefixes = ("/Users/", "/home/", "C:\\", "C:/")
    if env_type in ("modal", "singularity", "daytona") and cwd:
        is_host_path = any(cwd.startswith(p) for p in host_prefixes)
        is_relative = not os.path.isabs(cwd)
        if (is_host_path or is_relative) and cwd != default_cwd:
            logger.info("Ignoring TERMINAL_CWD=%r for %s backend "
                        "(host/relative path won't work in sandbox). Using %r instead.",
                        cwd, env_type, default_cwd)
            cwd = default_cwd

    for _env_var, _field in (
        ("TERMINAL_SINGULARITY_IMAGE", "singularity_image"),
        ("TERMINAL_MODAL_IMAGE", "modal_image"),
        ("TERMINAL_DAYTONA_IMAGE", "daytona_image"),
    ):
        _check_image_provenance(_field, os.getenv(_env_var, ""))

    return {
        "env_type": env_type,
        "modal_mode": coerce_modal_mode(os.getenv("TERMINAL_MODAL_MODE", "auto")),
        "singularity_image": os.getenv("TERMINAL_SINGULARITY_IMAGE", f"docker://{default_image}"),
        "modal_image": os.getenv("TERMINAL_MODAL_IMAGE", default_image),
        "daytona_image": os.getenv("TERMINAL_DAYTONA_IMAGE", default_image),
        "cwd": cwd,
        "timeout": _parse_env_var("TERMINAL_TIMEOUT", "180"),
        "lifetime_seconds": _parse_env_var("TERMINAL_LIFETIME_SECONDS", "300"),
        "ssh_host": os.getenv("TERMINAL_SSH_HOST", ""),
        "ssh_user": os.getenv("TERMINAL_SSH_USER", ""),
        "ssh_port": _parse_env_var("TERMINAL_SSH_PORT", "22"),
        "ssh_key": os.getenv("TERMINAL_SSH_KEY", ""),
        "ssh_persistent": os.getenv(
            "TERMINAL_SSH_PERSISTENT",
            os.getenv("TERMINAL_PERSISTENT_SHELL", "true"),
        ).lower() in ("true", "1", "yes"),
        "local_persistent": os.getenv("TERMINAL_LOCAL_PERSISTENT", "false").lower() in ("true", "1", "yes"),
        "container_cpu": _parse_env_var("TERMINAL_CONTAINER_CPU", "1", float, "number"),
        "container_memory": _parse_env_var("TERMINAL_CONTAINER_MEMORY", "5120"),
        "container_disk": _parse_env_var("TERMINAL_CONTAINER_DISK", "51200"),
        "container_persistent": os.getenv("TERMINAL_CONTAINER_PERSISTENT", "true").lower() in ("true", "1", "yes"),
    }


def _get_modal_backend_state(modal_mode: object | None) -> Dict[str, Any]:
    """Resolve direct vs managed Modal backend selection."""
    return resolve_modal_backend_state(
        modal_mode,
        has_direct=has_direct_modal_credentials(),
        managed_ready=is_managed_tool_gateway_ready("modal"),
    )


def _create_environment(env_type: str, image: str, cwd: str, timeout: int,
                        ssh_config: dict = None, container_config: dict = None,
                        local_config: dict = None,
                        task_id: str = "default",
                        host_cwd: str = None):
    """
    Create an execution environment for sandboxed command execution.

    Args:
        env_type: One of "local", "singularity", "modal", "daytona", "ssh"
        image: Singularity/Modal/Daytona image name (ignored for local/ssh)
        cwd: Working directory
        timeout: Default command timeout
        ssh_config: SSH connection config (for env_type="ssh")
        container_config: Resource config for container backends (cpu, memory, disk, persistent)
        task_id: Task identifier for environment reuse and snapshot keying
        host_cwd: Optional host-side working directory (falls back to *cwd*).

    Returns:
        Environment instance with execute() method
    """
    cc = container_config or {}
    cpu = cc.get("container_cpu", 1)
    memory = cc.get("container_memory", 5120)
    disk = cc.get("container_disk", 51200)
    persistent = cc.get("container_persistent", True)

    if env_type == "local":
        lc = local_config or {}
        return _LocalEnvironment(cwd=host_cwd or cwd, timeout=timeout,
                                 persistent=lc.get("persistent", False))

    elif env_type == "singularity":
        return _SingularityEnvironment(
            image=image, cwd=cwd, timeout=timeout,
            cpu=cpu, memory=memory, disk=disk,
            persistent_filesystem=persistent, task_id=task_id,
        )
    
    elif env_type == "modal":
        sandbox_kwargs = {}
        if cpu > 0:
            sandbox_kwargs["cpu"] = cpu
        if memory > 0:
            sandbox_kwargs["memory"] = memory
        if disk > 0:
            try:
                import inspect, modal
                if "ephemeral_disk" in inspect.signature(modal.Sandbox.create).parameters:
                    sandbox_kwargs["ephemeral_disk"] = disk
            except Exception:
                pass

        modal_state = _get_modal_backend_state(cc.get("modal_mode"))

        if modal_state["selected_backend"] == "managed":
            return _ManagedModalEnvironment(
                image=image, cwd=cwd, timeout=timeout,
                modal_sandbox_kwargs=sandbox_kwargs,
                persistent_filesystem=persistent, task_id=task_id,
            )

        if modal_state["selected_backend"] != "direct":
            if modal_state["managed_mode_blocked"]:
                raise ValueError(
                    "Modal backend is configured for managed mode, but "
                    "DAEDALUS_ENABLE_NOUS_MANAGED_TOOLS is not enabled and no direct "
                    "Modal credentials/config were found. Enable the feature flag or "
                    "choose TERMINAL_MODAL_MODE=direct/auto."
                )
            if modal_state["mode"] == "managed":
                raise ValueError(
                    "Modal backend is configured for managed mode, but the managed tool gateway is unavailable."
                )
            if modal_state["mode"] == "direct":
                raise ValueError(
                    "Modal backend is configured for direct mode, but no direct Modal credentials/config were found."
                )
            message = "Modal backend selected but no direct Modal credentials/config was found."
            if managed_nous_tools_enabled():
                message = (
                    "Modal backend selected but no direct Modal credentials/config or managed tool gateway was found."
                )
            raise ValueError(message)

        return _ModalEnvironment(
            image=image, cwd=cwd, timeout=timeout,
            modal_sandbox_kwargs=sandbox_kwargs,
            persistent_filesystem=persistent, task_id=task_id,
        )
    
    elif env_type == "daytona":
        from tools.environments.daytona import DaytonaEnvironment as _DaytonaEnvironment
        return _DaytonaEnvironment(
            image=image, cwd=cwd, timeout=timeout,
            cpu=int(cpu), memory=memory, disk=disk,
            persistent_filesystem=persistent, task_id=task_id,
        )

    elif env_type == "ssh":
        if not ssh_config or not ssh_config.get("host") or not ssh_config.get("user"):
            raise ValueError("SSH environment requires ssh_host and ssh_user to be configured")
        return _SSHEnvironment(
            host=ssh_config["host"],
            user=ssh_config["user"],
            port=ssh_config.get("port", 22),
            key_path=ssh_config.get("key", ""),
            cwd=cwd,
            timeout=timeout,
            persistent=ssh_config.get("persistent", False),
        )

    else:
        raise ValueError(f"Unknown environment type: {env_type}. Use 'local', 'singularity', 'modal', 'daytona', or 'ssh'")


def _cleanup_inactive_envs(lifetime_seconds: int = 300):
    """Clean up environments that have been inactive for longer than lifetime_seconds."""
    current_time = time.time()

    try:
        from tools.process_registry import process_registry
        for task_id in list(_last_activity.keys()):
            if process_registry.has_active_processes(task_id):
                _last_activity[task_id] = current_time
    except ImportError:
        pass

    envs_to_stop = []

    with _env_lock:
        for task_id, last_time in list(_last_activity.items()):
            if current_time - last_time > lifetime_seconds:
                env = _active_environments.pop(task_id, None)
                _last_activity.pop(task_id, None)
                if env is not None:
                    envs_to_stop.append((task_id, env))

        with _creation_locks_lock:
            for task_id, _ in envs_to_stop:
                _creation_locks.pop(task_id, None)

    for task_id, env in envs_to_stop:
        try:
            from tools.file_tools import clear_file_ops_cache
            clear_file_ops_cache(task_id)
        except ImportError:
            pass

        try:
            if hasattr(env, 'cleanup'):
                env.cleanup()
            elif hasattr(env, 'stop'):
                env.stop()
            elif hasattr(env, 'terminate'):
                env.terminate()

            logger.info("Cleaned up inactive environment for task: %s", task_id)

        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                logger.info("Environment for task %s already cleaned up", task_id)
            else:
                logger.warning("Error cleaning up environment for task %s: %s", task_id, e)


def _cleanup_thread_worker():
    """Background thread worker that periodically cleans up inactive environments."""
    while _cleanup_running:
        try:
            config = _get_env_config()
            _cleanup_inactive_envs(config["lifetime_seconds"])
        except Exception as e:
            logger.warning("Error in cleanup thread: %s", e, exc_info=True)

        for _ in range(60):
            if not _cleanup_running:
                break
            time.sleep(1)


def _start_cleanup_thread():
    """Start the background cleanup thread if not already running."""
    global _cleanup_thread, _cleanup_running

    with _env_lock:
        if _cleanup_thread is None or not _cleanup_thread.is_alive():
            _cleanup_running = True
            _cleanup_thread = threading.Thread(target=_cleanup_thread_worker, daemon=True)
            _cleanup_thread.start()


def _stop_cleanup_thread():
    """Stop the background cleanup thread."""
    global _cleanup_running
    _cleanup_running = False
    if _cleanup_thread is not None:
        try:
            _cleanup_thread.join(timeout=5)
        except (SystemExit, KeyboardInterrupt):
            pass


def get_active_env(task_id: str):
    """Return the active BaseEnvironment for *task_id*, or None."""
    with _env_lock:
        return _active_environments.get(task_id)


def get_active_environments_info() -> Dict[str, Any]:
    """Get information about currently active environments."""
    info = {
        "count": len(_active_environments),
        "task_ids": list(_active_environments.keys()),
        "workdirs": {},
    }
    
    total_size = 0
    for task_id in _active_environments:
        scratch_dir = _get_scratch_dir()
        pattern = f"daedalus-*{task_id[:8]}*"
        import glob
        for path in glob.glob(str(scratch_dir / pattern)):
            try:
                size = sum(f.stat().st_size for f in Path(path).rglob('*') if f.is_file())
                total_size += size
            except OSError as e:
                logger.debug("Could not stat path %s: %s", path, e)
    
    info["total_disk_usage_mb"] = round(total_size / (1024 * 1024), 2)
    return info


def cleanup_all_environments():
    """Clean up ALL active environments. Use with caution."""
    task_ids = list(_active_environments.keys())
    cleaned = 0
    
    for task_id in task_ids:
        try:
            cleanup_vm(task_id)
            cleaned += 1
        except Exception as e:
            logger.error("Error cleaning %s: %s", task_id, e, exc_info=True)
    
    scratch_dir = _get_scratch_dir()
    import glob
    for path in glob.glob(str(scratch_dir / "daedalus-*")):
        try:
            shutil.rmtree(path, ignore_errors=True)
            logger.info("Removed orphaned: %s", path)
        except OSError as e:
            logger.debug("Failed to remove orphaned path %s: %s", path, e)
    
    if cleaned > 0:
        logger.info("Cleaned %d environments", cleaned)
    return cleaned


def cleanup_vm(task_id: str):
    """Manually clean up a specific environment by task_id."""
    env = None
    with _env_lock:
        env = _active_environments.pop(task_id, None)
        _last_activity.pop(task_id, None)

    with _creation_locks_lock:
        _creation_locks.pop(task_id, None)

    try:
        from tools.file_tools import clear_file_ops_cache
        clear_file_ops_cache(task_id)
    except ImportError:
        pass

    if env is None:
        return

    try:
        if hasattr(env, 'cleanup'):
            env.cleanup()
        elif hasattr(env, 'stop'):
            env.stop()
        elif hasattr(env, 'terminate'):
            env.terminate()

        logger.info("Manually cleaned up environment for task: %s", task_id)

    except Exception as e:
        error_str = str(e)
        if "404" in error_str or "not found" in error_str.lower():
            logger.info("Environment for task %s already cleaned up", task_id)
        else:
            logger.warning("Error cleaning up environment for task %s: %s", task_id, e)


def _atexit_cleanup():
    """Stop cleanup thread and shut down all remaining sandboxes on exit."""
    _stop_cleanup_thread()
    if _active_environments:
        count = len(_active_environments)
        logger.info("Shutting down %d remaining sandbox(es)...", count)
        cleanup_all_environments()

atexit.register(_atexit_cleanup)



def _interpret_exit_code(command: str, exit_code: int) -> str | None:
    """Return a human-readable note when a non-zero exit code is non-erroneous.

    Returns None when the exit code is 0 or genuinely signals an error.
    The note is appended to the tool result so the model doesn't waste
    turns investigating expected exit codes.
    """
    if exit_code == 0:
        return None

    segments = re.split(r'\s*(?:\|\||&&|[|;])\s*', command)
    last_segment = (segments[-1] if segments else command).strip()

    words = last_segment.split()
    base_cmd = ""
    for w in words:
        if "=" in w and not w.startswith("-"):
            continue
        base_cmd = w.split("/")[-1]
        break

    if not base_cmd:
        return None

    semantics: dict[str, dict[int, str]] = {
        "grep":  {1: "No matches found (not an error)"},
        "egrep": {1: "No matches found (not an error)"},
        "fgrep": {1: "No matches found (not an error)"},
        "rg":    {1: "No matches found (not an error)"},
        "ag":    {1: "No matches found (not an error)"},
        "ack":   {1: "No matches found (not an error)"},
        "diff":  {1: "Files differ (expected, not an error)"},
        "colordiff": {1: "Files differ (expected, not an error)"},
        "find":  {1: "Some directories were inaccessible (partial results may still be valid)"},
        "test":  {1: "Condition evaluated to false (expected, not an error)"},
        "[":     {1: "Condition evaluated to false (expected, not an error)"},
        "curl":  {
            6: "Could not resolve host",
            7: "Failed to connect to host",
            22: "HTTP response code indicated error (e.g. 404, 500)",
            28: "Operation timed out",
        },
        "git":   {1: "Non-zero exit (often normal — e.g. 'git diff' returns 1 when files differ)"},
    }

    cmd_semantics = semantics.get(base_cmd)
    if cmd_semantics and exit_code in cmd_semantics:
        return cmd_semantics[exit_code]

    return None


def terminal_tool(
    command: str,
    background: bool = False,
    timeout: Optional[int] = None,
    task_id: Optional[str] = None,
    force: bool = False,
    workdir: Optional[str] = None,
    check_interval: Optional[int] = None,
    pty: bool = False,
    notify_on_complete: bool = False,
) -> str:
    """
    Execute a command in the configured terminal environment.

    Args:
        command: The command to execute
        background: Whether to run in background (default: False)
        timeout: Command timeout in seconds (default: from config)
        task_id: Unique identifier for environment isolation (optional)
        force: If True, skip dangerous command check (use after user confirms)
        workdir: Working directory for this command (optional, uses session cwd if not set)
        check_interval: Seconds between auto-checks for background processes (gateway only, min 30)
        pty: If True, use pseudo-terminal for interactive CLI tools (local backend only)
        notify_on_complete: If True and background=True, auto-notify the agent when the process exits

    Returns:
        str: JSON string with output, exit_code, and error fields

    Examples:
        # Execute a simple command
        >>> result = terminal_tool(command="ls -la /tmp")

        # Run a background task
        >>> result = terminal_tool(command="python server.py", background=True)

        # With custom timeout
        >>> result = terminal_tool(command="long_task.sh", timeout=300)
        
        # Force run after user confirmation
        # Note: force parameter is internal only, not exposed to model API
    """
    try:
        config = _get_env_config()
        env_type = config["env_type"]

        effective_task_id = task_id or "default"

        overrides = _task_env_overrides.get(effective_task_id, {})
        
        if env_type == "singularity":
            image = overrides.get("singularity_image") or config["singularity_image"]
        elif env_type == "modal":
            image = overrides.get("modal_image") or config["modal_image"]
        elif env_type == "daytona":
            image = overrides.get("daytona_image") or config["daytona_image"]
        else:
            image = ""

        cwd = overrides.get("cwd") or config["cwd"]
        default_timeout = config["timeout"]
        effective_timeout = timeout or default_timeout

        _start_cleanup_thread()

        with _env_lock:
            if effective_task_id in _active_environments:
                _last_activity[effective_task_id] = time.time()
                env = _active_environments[effective_task_id]
                needs_creation = False
            else:
                needs_creation = True

        if needs_creation:
            with _creation_locks_lock:
                if effective_task_id not in _creation_locks:
                    _creation_locks[effective_task_id] = threading.Lock()
                task_lock = _creation_locks[effective_task_id]

            with task_lock:
                with _env_lock:
                    if effective_task_id in _active_environments:
                        _last_activity[effective_task_id] = time.time()
                        env = _active_environments[effective_task_id]
                        needs_creation = False

                if needs_creation:
                    if env_type == "singularity":
                        _check_disk_usage_warning()
                    logger.info("Creating new %s environment for task %s...", env_type, effective_task_id[:8])
                    try:
                        ssh_config = None
                        if env_type == "ssh":
                            ssh_config = {
                                "host": config.get("ssh_host", ""),
                                "user": config.get("ssh_user", ""),
                                "port": config.get("ssh_port", 22),
                                "key": config.get("ssh_key", ""),
                                "persistent": config.get("ssh_persistent", False),
                            }

                        container_config = None
                        if env_type in ("singularity", "modal", "daytona"):
                            container_config = {
                                "container_cpu": config.get("container_cpu", 1),
                                "container_memory": config.get("container_memory", 5120),
                                "container_disk": config.get("container_disk", 51200),
                                "container_persistent": config.get("container_persistent", True),
                                "modal_mode": config.get("modal_mode", "auto"),
                            }

                        local_config = None
                        if env_type == "local":
                            local_config = {
                                "persistent": config.get("local_persistent", False),
                            }

                        new_env = _create_environment(
                            env_type=env_type,
                            image=image,
                            cwd=cwd,
                            timeout=effective_timeout,
                            ssh_config=ssh_config,
                            container_config=container_config,
                            local_config=local_config,
                            task_id=effective_task_id,
                            host_cwd=config.get("host_cwd"),
                        )
                    except ImportError as e:
                        return json.dumps({
                            "output": "",
                            "exit_code": -1,
                            "error": f"Terminal tool disabled: environment creation failed ({e})",
                            "status": "disabled"
                        }, ensure_ascii=False)

                    with _env_lock:
                        _active_environments[effective_task_id] = new_env
                        _last_activity[effective_task_id] = time.time()
                        env = new_env
                    logger.info("%s environment ready for task %s", env_type, effective_task_id[:8])

        approval_note = None
        if not force:
            approval = _check_all_guards(command, env_type)
            if not approval["approved"]:
                if approval.get("status") == "approval_required":
                    return json.dumps({
                        "output": "",
                        "exit_code": -1,
                        "error": approval.get("message", "Waiting for user approval"),
                        "status": "approval_required",
                        "command": approval.get("command", command),
                        "description": approval.get("description", "command flagged"),
                        "pattern_key": approval.get("pattern_key", ""),
                    }, ensure_ascii=False)
                desc = approval.get("description", "command flagged")
                fallback_msg = (
                    f"Command denied: {desc}. "
                    "Use the approval prompt to allow it, or rephrase the command."
                )
                return json.dumps({
                    "output": "",
                    "exit_code": -1,
                    "error": approval.get("message", fallback_msg),
                    "status": "blocked"
                }, ensure_ascii=False)
            if approval.get("user_approved"):
                desc = approval.get("description", "flagged as dangerous")
                approval_note = f"Command required approval ({desc}) and was approved by the user."
            elif approval.get("smart_approved"):
                desc = approval.get("description", "flagged as dangerous")
                approval_note = f"Command was flagged ({desc}) and auto-approved by smart approval."

        if workdir:
            workdir_error = _validate_workdir(workdir)
            if workdir_error:
                logger.warning("Blocked dangerous workdir: %s (command: %s)",
                               workdir[:200], command[:200])
                return json.dumps({
                    "output": "",
                    "exit_code": -1,
                    "error": workdir_error,
                    "status": "blocked"
                }, ensure_ascii=False)

        if background:
            from tools.approval import get_current_session_key
            from tools.process_registry import process_registry

            session_key = get_current_session_key(default="")
            effective_cwd = workdir or cwd
            try:
                if env_type == "local":
                    proc_session = process_registry.spawn_local(
                        command=command,
                        cwd=effective_cwd,
                        task_id=effective_task_id,
                        session_key=session_key,
                        env_vars=env.env if hasattr(env, 'env') else None,
                        use_pty=pty,
                    )
                else:
                    proc_session = process_registry.spawn_via_env(
                        env=env,
                        command=command,
                        cwd=effective_cwd,
                        task_id=effective_task_id,
                        session_key=session_key,
                    )

                result_data = {
                    "output": "Background process started",
                    "session_id": proc_session.id,
                    "pid": proc_session.pid,
                    "exit_code": 0,
                    "error": None,
                }
                if approval_note:
                    result_data["approval"] = approval_note

                max_timeout = effective_timeout
                if timeout and timeout > max_timeout:
                    result_data["timeout_note"] = (
                        f"Requested timeout {timeout}s was clamped to "
                        f"configured limit of {max_timeout}s"
                    )

                if notify_on_complete and background:
                    proc_session.notify_on_complete = True
                    result_data["notify_on_complete"] = True

                    _gw_platform = os.getenv("DAEDALUS_SESSION_PLATFORM", "")
                    if _gw_platform and not check_interval:
                        _gw_chat_id = os.getenv("DAEDALUS_SESSION_CHAT_ID", "")
                        _gw_thread_id = os.getenv("DAEDALUS_SESSION_THREAD_ID", "")
                        proc_session.watcher_platform = _gw_platform
                        proc_session.watcher_chat_id = _gw_chat_id
                        proc_session.watcher_thread_id = _gw_thread_id
                        proc_session.watcher_interval = 5
                        process_registry.pending_watchers.append({
                            "session_id": proc_session.id,
                            "check_interval": 5,
                            "session_key": session_key,
                            "platform": _gw_platform,
                            "chat_id": _gw_chat_id,
                            "thread_id": _gw_thread_id,
                            "notify_on_complete": True,
                        })

                if check_interval and background:
                    effective_interval = max(30, check_interval)
                    if check_interval < 30:
                        result_data["check_interval_note"] = (
                            f"Requested {check_interval}s raised to minimum 30s"
                        )
                    watcher_platform = os.getenv("DAEDALUS_SESSION_PLATFORM", "")
                    watcher_chat_id = os.getenv("DAEDALUS_SESSION_CHAT_ID", "")
                    watcher_thread_id = os.getenv("DAEDALUS_SESSION_THREAD_ID", "")

                    proc_session.watcher_platform = watcher_platform
                    proc_session.watcher_chat_id = watcher_chat_id
                    proc_session.watcher_thread_id = watcher_thread_id
                    proc_session.watcher_interval = effective_interval

                    process_registry.pending_watchers.append({
                        "session_id": proc_session.id,
                        "check_interval": effective_interval,
                        "session_key": session_key,
                        "platform": watcher_platform,
                        "chat_id": watcher_chat_id,
                        "thread_id": watcher_thread_id,
                    })

                return json.dumps(result_data, ensure_ascii=False)
            except Exception as e:
                return json.dumps({
                    "output": "",
                    "exit_code": -1,
                    "error": f"Failed to start background process: {str(e)}"
                }, ensure_ascii=False)
        else:
            max_retries = 3
            retry_count = 0
            result = None
            
            while retry_count <= max_retries:
                try:
                    execute_kwargs = {"timeout": effective_timeout}
                    if workdir:
                        execute_kwargs["cwd"] = workdir
                    result = env.execute(command, **execute_kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if "timeout" in error_str:
                        return json.dumps({
                            "output": "",
                            "exit_code": 124,
                            "error": f"Command timed out after {effective_timeout} seconds"
                        }, ensure_ascii=False)
                    
                    if retry_count < max_retries:
                        retry_count += 1
                        wait_time = 2 ** retry_count
                        logger.warning("Execution error, retrying in %ds (attempt %d/%d) - Command: %s - Error: %s: %s - Task: %s, Backend: %s",
                                       wait_time, retry_count, max_retries, command[:200], type(e).__name__, e, effective_task_id, env_type)
                        time.sleep(wait_time)
                        continue
                    
                    logger.error("Execution failed after %d retries - Command: %s - Error: %s: %s - Task: %s, Backend: %s",
                                 max_retries, command[:200], type(e).__name__, e, effective_task_id, env_type)
                    return json.dumps({
                        "output": "",
                        "exit_code": -1,
                        "error": f"Command execution failed: {type(e).__name__}: {str(e)}"
                    }, ensure_ascii=False)
                
                break
            
            output = result.get("output", "")
            returncode = result.get("returncode", 0)
            
            output = _handle_sudo_failure(output, env_type)
            
            MAX_OUTPUT_CHARS = 50000
            if len(output) > MAX_OUTPUT_CHARS:
                head_chars = int(MAX_OUTPUT_CHARS * 0.4)
                tail_chars = MAX_OUTPUT_CHARS - head_chars
                omitted = len(output) - head_chars - tail_chars
                truncated_notice = (
                    f"\n\n... [OUTPUT TRUNCATED - {omitted} chars omitted "
                    f"out of {len(output)} total] ...\n\n"
                )
                output = output[:head_chars] + truncated_notice + output[-tail_chars:]

            from tools.ansi_strip import strip_ansi
            output = strip_ansi(output)

            from agent.redact import redact_sensitive_text
            output = redact_sensitive_text(output.strip()) if output else ""

            exit_note = _interpret_exit_code(command, returncode)

            result_dict = {
                "output": output,
                "exit_code": returncode,
                "error": None,
            }
            if approval_note:
                result_dict["approval"] = approval_note
            if exit_note:
                result_dict["exit_code_meaning"] = exit_note

            return json.dumps(result_dict, ensure_ascii=False)

    except Exception as e:
        import traceback
        tb_str = traceback.format_exc()
        logger.error("terminal_tool exception:\n%s", tb_str)
        return json.dumps({
            "output": "",
            "exit_code": -1,
            "error": f"Failed to execute command: {str(e)}",
            "traceback": tb_str,
            "status": "error"
        }, ensure_ascii=False)


def check_terminal_requirements() -> bool:
    """Check if all requirements for the terminal tool are met."""
    config = _get_env_config()
    env_type = config["env_type"]

    try:
        if env_type == "local":
            return True

        elif env_type == "singularity":
            executable = shutil.which("apptainer") or shutil.which("singularity")
            if executable:
                result = subprocess.run([executable, "--version"], capture_output=True, timeout=5)
                return result.returncode == 0
            return False

        elif env_type == "ssh":
            if not config.get("ssh_host") or not config.get("ssh_user"):
                logger.error(
                    "SSH backend selected but TERMINAL_SSH_HOST and TERMINAL_SSH_USER "
                    "are not both set. Configure both or switch TERMINAL_ENV to 'local'."
                )
                return False
            return True

        elif env_type == "modal":
            modal_state = _get_modal_backend_state(config.get("modal_mode"))
            if modal_state["selected_backend"] == "managed":
                return True

            if modal_state["selected_backend"] != "direct":
                if modal_state["managed_mode_blocked"]:
                    logger.error(
                        "Modal backend selected with TERMINAL_MODAL_MODE=managed, but "
                        "DAEDALUS_ENABLE_NOUS_MANAGED_TOOLS is not enabled and no direct "
                        "Modal credentials/config were found. Enable the feature flag "
                        "or choose TERMINAL_MODAL_MODE=direct/auto."
                    )
                    return False
                if modal_state["mode"] == "managed":
                    logger.error(
                        "Modal backend selected with TERMINAL_MODAL_MODE=managed, but the managed "
                        "tool gateway is unavailable. Configure the managed gateway or choose "
                        "TERMINAL_MODAL_MODE=direct/auto."
                    )
                    return False
                elif modal_state["mode"] == "direct":
                    if managed_nous_tools_enabled():
                        logger.error(
                            "Modal backend selected with TERMINAL_MODAL_MODE=direct, but no direct "
                            "Modal credentials/config were found. Configure Modal or choose "
                            "TERMINAL_MODAL_MODE=managed/auto."
                        )
                    else:
                        logger.error(
                            "Modal backend selected with TERMINAL_MODAL_MODE=direct, but no direct "
                            "Modal credentials/config were found. Configure Modal or choose "
                            "TERMINAL_MODAL_MODE=auto."
                        )
                    return False
                else:
                    if managed_nous_tools_enabled():
                        logger.error(
                            "Modal backend selected but no direct Modal credentials/config or managed "
                            "tool gateway was found. Configure Modal, set up the managed gateway, "
                            "or choose a different TERMINAL_ENV."
                        )
                    else:
                        logger.error(
                            "Modal backend selected but no direct Modal credentials/config was found. "
                            "Configure Modal or choose a different TERMINAL_ENV."
                        )
                    return False

            if importlib.util.find_spec("modal") is None:
                logger.error("modal is required for direct modal terminal backend: pip install modal")
                return False

            return True

        elif env_type == "daytona":
            from daytona import Daytona  # noqa: F401 — SDK presence check
            return os.getenv("DAYTONA_API_KEY") is not None

        else:
            logger.error(
                "Unknown TERMINAL_ENV '%s'. Use one of: local, singularity, "
                "modal, daytona, ssh.",
                env_type,
            )
            return False
    except Exception as e:
        logger.error("Terminal requirements check failed: %s", e, exc_info=True)
        return False


if __name__ == "__main__":
    print("Terminal Tool Module")
    print("=" * 50)
    
    config = _get_env_config()
    print("\nCurrent Configuration:")
    print(f"  Environment type: {config['env_type']}")
    print(f"  Modal image: {config['modal_image']}")
    print(f"  Working directory: {config['cwd']}")
    print(f"  Default timeout: {config['timeout']}s")
    print(f"  Lifetime: {config['lifetime_seconds']}s")

    if not check_terminal_requirements():
        print("\n❌ Requirements not met. Please check the messages above.")
        exit(1)

    print("\n✅ All requirements met!")
    print("\nAvailable Tool:")
    print("  - terminal_tool: Execute commands in sandboxed environments")

    print("\nUsage Examples:")
    print("  # Execute a command")
    print("  result = terminal_tool(command='ls -la')")
    print("  ")
    print("  # Run a background task")
    print("  result = terminal_tool(command='python server.py', background=True)")

    print("\nEnvironment Variables:")
    default_img = "nikolaik/python-nodejs:python3.11-nodejs20"
    print(f"  TERMINAL_ENV: {os.getenv('TERMINAL_ENV', 'local')} (local/singularity/modal/daytona/ssh)")
    print(f"  TERMINAL_SINGULARITY_IMAGE: {os.getenv('TERMINAL_SINGULARITY_IMAGE', f'docker://{default_img}')}")
    print(f"  TERMINAL_MODAL_IMAGE: {os.getenv('TERMINAL_MODAL_IMAGE', default_img)}")
    print(f"  TERMINAL_DAYTONA_IMAGE: {os.getenv('TERMINAL_DAYTONA_IMAGE', default_img)}")
    print(f"  TERMINAL_CWD: {os.getenv('TERMINAL_CWD', os.getcwd())}")
    from daedalus_constants import display_daedalus_home as _dhh
    print(f"  TERMINAL_SANDBOX_DIR: {os.getenv('TERMINAL_SANDBOX_DIR', f'{_dhh()}/sandboxes')}")
    print(f"  TERMINAL_TIMEOUT: {os.getenv('TERMINAL_TIMEOUT', '60')}")
    print(f"  TERMINAL_LIFETIME_SECONDS: {os.getenv('TERMINAL_LIFETIME_SECONDS', '300')}")


from tools.registry import registry

TERMINAL_SCHEMA = {
    "name": "terminal",
    "description": TERMINAL_TOOL_DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to execute on the VM"
            },
            "background": {
                "type": "boolean",
                "description": "Run in background; returns session_id. For long-lived processes (servers, watchers) or long tasks with notify_on_complete=true.",
                "default": False
            },
            "timeout": {
                "type": "integer",
                "description": "Max wait seconds (default: 180). Returns when command finishes — set high for long tasks.",
                "minimum": 1
            },
            "workdir": {
                "type": "string",
                "description": "Working directory for this command (absolute path). Defaults to the session working directory."
            },
            "check_interval": {
                "type": "integer",
                "description": "Seconds between background-progress checks (gateway only; min 30). When set, progress is reported proactively.",
                "minimum": 30
            },
            "pty": {
                "type": "boolean",
                "description": "Run in a pseudo-terminal for interactive CLIs (Codex, Claude Code, REPL). Local/SSH backends only.",
                "default": False
            },
            "notify_on_complete": {
                "type": "boolean",
                "description": "Notify automatically when a background process finishes — no polling. Use for long tasks (tests, builds, deploys).",
                "default": False
            }
        },
        "required": ["command"]
    }
}


def _handle_terminal(args, **kw):
    return terminal_tool(
        command=args.get("command"),
        background=args.get("background", False),
        timeout=args.get("timeout"),
        task_id=kw.get("task_id"),
        workdir=args.get("workdir"),
        check_interval=args.get("check_interval"),
        pty=args.get("pty", False),
        notify_on_complete=args.get("notify_on_complete", False),
    )


registry.register(
    name="terminal",
    toolset="terminal",
    schema=TERMINAL_SCHEMA,
    handler=_handle_terminal,
    check_fn=check_terminal_requirements,
    emoji="💻",
    max_result_size_chars=100_000,
)
