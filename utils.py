"""Shared utility functions for daedalus."""

import argparse
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional, Union
from urllib.parse import urlparse

import yaml


TRUTHY_STRINGS = frozenset({"1", "true", "yes", "on"})


def run_main_with_argparse(
    main_fn: Callable,
    *,
    prog: Optional[str] = None,
    description: Optional[str] = None,
) -> Any:
    """Run *main_fn* with an argparse-derived CLI.

    Replacement for Google Fire's ``fire.Fire(main)``. Fire coerced
    numeric-looking values to int (a session id like ``20260810_105748_798252``
    arrived as the huge int ``20260810105748798252``, overflowing SQLite
    INTEGER on resume), so it is gone. This helper builds an argparse parser
    from the function's signature: every ``--param`` maps to the keyword by
    name (dashes→underscores), with the type inferred from the default value
    (bool defaults → store_true; int/float defaults → typed; str/None → str).
    Values are never auto-coerced beyond the declared type — session ids and
    other opaque strings stay strings.
    """
    parser = argparse.ArgumentParser(
        prog=prog or Path(sys.argv[0]).name,
        description=description or (inspect.getdoc(main_fn) or ""),
    )

    sig = inspect.signature(main_fn)
    for name, param in sig.parameters.items():
        default = param.default
        is_required = default is inspect.Parameter.empty
        dash_name = name.replace("_", "-")

        if is_required:
            parser.add_argument(f"--{dash_name}", required=True)
            continue

        if isinstance(default, bool):
            parser.add_argument(
                f"--{dash_name}",
                action="store_true",
                default=default,
            )
        elif isinstance(default, int):
            parser.add_argument(
                f"--{dash_name}",
                type=int,
                default=default,
            )
        elif isinstance(default, float):
            parser.add_argument(
                f"--{dash_name}",
                type=float,
                default=default,
            )
        else:
            # str (or None default → string positional). Never coerce — this
            # is the whole point vs Fire.
            parser.add_argument(
                f"--{dash_name}",
                type=str,
                default=default,
            )

    args = parser.parse_args()
    kwargs = {name: getattr(args, name) for name in sig.parameters}
    return main_fn(**kwargs)


def is_truthy_value(value: Any, default: bool = False) -> bool:
    """Coerce bool-ish values using the project's shared truthy string set."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in TRUTHY_STRINGS
    return bool(value)


def env_var_enabled(name: str, default: str = "") -> bool:
    """Return True when an environment variable is set to a truthy value."""
    return is_truthy_value(os.getenv(name, default), default=False)


def env_int(key: str, default: int = 0) -> int:
    """Read an environment variable as an integer, with fallback."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (ValueError, TypeError):
        return default


def normalize_proxy_url(proxy_url: str | None) -> str | None:
    """Normalize proxy URLs for httpx/aiohttp compatibility.

    WSL/Clash-style environments often export SOCKS proxies as
    ``socks://127.0.0.1:PORT``. httpx rejects that alias and expects the
    explicit ``socks5://`` scheme instead.
    """
    candidate = str(proxy_url or "").strip()
    if not candidate:
        return None
    if candidate.lower().startswith("socks://"):
        return f"socks5://{candidate[len('socks://'):]}"
    return candidate


def env_float(key: str, default: float = 0.0) -> float:
    """Read an environment variable as a float, with fallback."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (ValueError, TypeError):
        return default


def atomic_json_write(
    path: Union[str, Path],
    data: Any,
    *,
    indent: int = 2,
    **dump_kwargs: Any,
) -> None:
    """Write JSON data to a file atomically.

    Uses temp file + fsync + os.replace to ensure the target file is never
    left in a partially-written state. If the process crashes mid-write,
    the previous version of the file remains intact.

    Args:
        path: Target file path (will be created or overwritten).
        data: JSON-serializable data to write.
        indent: JSON indentation (default 2).
        **dump_kwargs: Additional keyword args forwarded to json.dump(), such
            as default=str for non-native types.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=indent,
                ensure_ascii=False,
                **dump_kwargs,
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Intentionally catch BaseException so temp-file cleanup still runs for
        # KeyboardInterrupt/SystemExit before re-raising the original signal.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def atomic_yaml_write(
    path: Union[str, Path],
    data: Any,
    *,
    default_flow_style: bool = False,
    sort_keys: bool = False,
    extra_content: str | None = None,
) -> None:
    """Write YAML data to a file atomically.

    Uses temp file + fsync + os.replace to ensure the target file is never
    left in a partially-written state.  If the process crashes mid-write,
    the previous version of the file remains intact.

    Args:
        path: Target file path (will be created or overwritten).
        data: YAML-serializable data to write.
        default_flow_style: YAML flow style (default False).
        sort_keys: Whether to sort dict keys (default False).
        extra_content: Optional string to append after the YAML dump
            (e.g. commented-out sections for user reference).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.stem}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=default_flow_style, sort_keys=sort_keys)
            if extra_content:
                f.write(extra_content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # Match atomic_json_write: cleanup must also happen for process-level
        # interruptions before we re-raise them.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def base_url_hostname(base_url: str) -> str:
    """Return the lowercased hostname for a base URL, or ``""`` if absent.

    Use exact-hostname comparisons against known provider hosts
    (``api.openai.com``, ``api.x.ai``, ``api.anthropic.com``) instead of
    substring matches on the raw URL. Substring checks treat attacker- or
    proxy-controlled paths/hosts like ``https://api.openai.com.example/v1``
    or ``https://proxy.test/api.openai.com/v1`` as native endpoints, which
    leads to wrong api_mode / auth routing.
    """
    raw = (base_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    return (parsed.hostname or "").lower().rstrip(".")


def base_url_host_matches(base_url: str, host: str) -> bool:
    """True when *base_url*'s hostname is *host* or a subdomain of it.

    ``agent/message_sanitization.py`` has imported this since the 0.20.0
    wholesale sync, but the function never came across with it -- every call
    raised ImportError. The reasoning-content echo policy is the only caller
    and nothing invokes it today, so the breakage stayed invisible; re-wiring
    that policy without this would have crashed on the first request.

    Matching is on hostname boundaries, never substrings, per
    ``base_url_hostname``: "moonshot.ai" matches "api.moonshot.ai" but
    "api.openai.com" does NOT match the lookalike "api.openai.com.example".
    """
    actual = base_url_hostname(base_url)
    wanted = (host or "").strip().lower().rstrip(".")
    if not actual or not wanted:
        return False
    return actual == wanted or actual.endswith("." + wanted)

