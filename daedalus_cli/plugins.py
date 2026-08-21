"""
Daedalus Plugin System
====================

Discovers, loads, and manages plugins from three sources:

1. **User plugins**   – ``~/.daedalus/plugins/<name>/``
2. **Project plugins** – ``./.daedalus/plugins/<name>/`` (opt-in via
   ``DAEDALUS_ENABLE_PROJECT_PLUGINS``)
3. **Pip plugins**     – packages that expose the ``daedalus_agent.plugins``
   entry-point group.

Each directory plugin must contain a ``plugin.yaml`` manifest **and** an
``__init__.py`` with a ``register(ctx)`` function.

Lifecycle hooks
---------------
Plugins may register callbacks for any of the hooks in ``VALID_HOOKS``.
The agent core calls ``invoke_hook(name, **kwargs)`` at the appropriate
points.

Tool registration
-----------------
``PluginContext.register_tool()`` delegates to ``tools.registry.register()``
so plugin-defined tools appear alongside the built-in tools.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import logging
import os
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

from daedalus_constants import get_daedalus_home
from utils import env_var_enabled

try:
    import yaml
except ImportError:  # pragma: no cover – yaml is optional at import time
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_HOOKS: Set[str] = {
    "pre_tool_call",
    "post_tool_call",
    "pre_llm_call",
    "post_llm_call",
    "pre_api_request",
    "post_api_request",
    "on_session_start",
    "on_session_end",
    "on_session_finalize",
    "on_session_reset",
    # v0.20.0 additions (registration parity — invocation wired where the
    # agent loop supports it):
    "transform_terminal_output",
    "transform_tool_result",
    "transform_llm_output",
    "pre_verify",
    "api_request_error",
    "subagent_start",
    "subagent_stop",
    "pre_gateway_dispatch",
}

ENTRY_POINTS_GROUP = "daedalus_agent.plugins"

_NS_PARENT = "daedalus_plugins"


def _env_enabled(name: str) -> bool:
    """Return True when an env var is set to a truthy opt-in value."""
    return env_var_enabled(name)


def _get_disabled_plugins() -> set:
    """Read the disabled plugins list from config.yaml."""
    try:
        from daedalus_cli.config import load_config
        config = load_config()
        disabled = config.get("plugins", {}).get("disabled", [])
        return set(disabled) if isinstance(disabled, list) else set()
    except Exception:
        return set()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PluginManifest:
    """Parsed representation of a plugin.yaml manifest."""

    name: str
    key: str = ""           # dedup/load key (category-namespaced, e.g. "image_gen/openai")
    version: str = ""
    description: str = ""
    author: str = ""
    requires_env: List[Union[str, Dict[str, Any]]] = field(default_factory=list)
    provides_tools: List[str] = field(default_factory=list)
    provides_hooks: List[str] = field(default_factory=list)
    source: str = ""        # "user", "project", or "entrypoint"
    path: Optional[str] = None


@dataclass
class LoadedPlugin:
    """Runtime state for a single loaded plugin."""

    manifest: PluginManifest
    module: Optional[types.ModuleType] = None
    tools_registered: List[str] = field(default_factory=list)
    hooks_registered: List[str] = field(default_factory=list)
    enabled: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# PluginContext  – handed to each plugin's ``register()`` function
# ---------------------------------------------------------------------------

class PluginContext:
    """Facade given to plugins so they can register tools and hooks."""

    def __init__(self, manifest: PluginManifest, manager: "PluginManager"):
        self.manifest = manifest
        self._manager = manager

    # -- tool registration --------------------------------------------------

    def register_tool(
        self,
        name: str,
        toolset: str,
        schema: dict,
        handler: Callable,
        check_fn: Callable | None = None,
        requires_env: list | None = None,
        is_async: bool = False,
        description: str = "",
        emoji: str = "",
    ) -> None:
        """Register a tool in the global registry **and** track it as plugin-provided."""
        from tools.registry import registry

        registry.register(
            name=name,
            toolset=toolset,
            schema=schema,
            handler=handler,
            check_fn=check_fn,
            requires_env=requires_env,
            is_async=is_async,
            description=description,
            emoji=emoji,
        )
        self._manager._plugin_tool_names.add(name)
        logger.debug("Plugin %s registered tool: %s", self.manifest.name, name)

    # -- message injection --------------------------------------------------

    def inject_message(self, content: str, role: str = "user") -> bool:
        """Inject a message into the active conversation.

        If the agent is idle (waiting for user input), this starts a new turn.
        If the agent is running, this interrupts and injects the message.

        This enables plugins (e.g. remote control viewers, messaging bridges)
        to send messages into the conversation from external sources.

        Returns True if the message was queued successfully.
        """
        cli = self._manager._cli_ref
        if cli is None:
            logger.warning("inject_message: no CLI reference (not available in gateway mode)")
            return False

        msg = content if role == "user" else f"[{role}] {content}"

        if getattr(cli, "_agent_running", False):
            # Agent is mid-turn — interrupt with the message
            cli._interrupt_queue.put(msg)
        else:
            # Agent is idle — queue as next input
            cli._pending_input.put(msg)
        return True

    # -- CLI command registration --------------------------------------------

    def register_cli_command(
        self,
        name: str,
        help: str,
        setup_fn: Callable,
        handler_fn: Callable | None = None,
        description: str = "",
    ) -> None:
        """Register a CLI subcommand (e.g. ``daedalus honcho ...``).

        The *setup_fn* receives an argparse subparser and should add any
        arguments/sub-subparsers.  If *handler_fn* is provided it is set
        as the default dispatch function via ``set_defaults(func=...)``.
        """
        self._manager._cli_commands[name] = {
            "name": name,
            "help": help,
            "description": description,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
            "plugin": self.manifest.name,
        }
        logger.debug("Plugin %s registered CLI command: %s", self.manifest.name, name)

    # -- hook registration --------------------------------------------------

    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a lifecycle hook callback.

        Unknown hook names produce a warning but are still stored so
        forward-compatible plugins don't break.
        """
        if hook_name not in VALID_HOOKS:
            logger.warning(
                "Plugin '%s' registered unknown hook '%s' "
                "(valid: %s)",
                self.manifest.name,
                hook_name,
                ", ".join(sorted(VALID_HOOKS)),
            )
        self._manager._hooks.setdefault(hook_name, []).append(callback)
        logger.debug("Plugin %s registered hook: %s", self.manifest.name, hook_name)

    # -- provider registration (v0.20.0 parity — "ONE way" registration) -----
    # These mirror upstream daedalus v0.20.0 (NousResearch, tag v2026.8.3):
    # a plugin contributes a backend by calling ctx.register_*_provider(instance),
    # which type-checks against the provider ABC in agent/ and registers into the
    # matching agent/*_registry. The dispatcher (tools/web_tools.py etc.) consults
    # the registry, so config (web.search_backend, browser.cloud_provider, ...)
    # selects the active provider by name. Port 2026-08-09.

    def register_web_search_provider(self, provider) -> None:
        """Register a web search/extract backend (WebSearchProvider)."""
        from agent.web_search_provider import WebSearchProvider
        from agent.web_search_registry import register_provider as _reg

        if not isinstance(provider, WebSearchProvider):
            logger.warning(
                "Plugin '%s' tried to register a web provider that does not "
                "inherit from WebSearchProvider. Ignoring.", self.manifest.name)
            return
        _reg(provider)
        logger.info("Plugin '%s' registered web provider: %s",
                    self.manifest.name, provider.name)

    def register_browser_provider(self, provider) -> None:
        """Register a cloud browser backend (BrowserProvider)."""
        from agent.browser_provider import BrowserProvider
        from agent.browser_registry import register_provider as _reg

        if not isinstance(provider, BrowserProvider):
            logger.warning(
                "Plugin '%s' tried to register a browser provider that does not "
                "inherit from BrowserProvider. Ignoring.", self.manifest.name)
            return
        _reg(provider)
        logger.info("Plugin '%s' registered browser provider: %s",
                    self.manifest.name, provider.name)

    def register_image_gen_provider(self, provider) -> None:
        """Register an image generation backend (ImageGenProvider)."""
        from agent.image_gen_provider import ImageGenProvider
        from agent.image_gen_registry import register_provider

        if not isinstance(provider, ImageGenProvider):
            logger.warning(
                "Plugin '%s' tried to register an image_gen provider that does "
                "not inherit from ImageGenProvider. Ignoring.", self.manifest.name)
            return
        register_provider(provider)
        logger.info("Plugin '%s' registered image_gen provider: %s",
                    self.manifest.name, provider.name)

    def register_video_gen_provider(self, provider) -> None:
        """Register a video generation backend (VideoGenProvider)."""
        from agent.video_gen_provider import VideoGenProvider
        from agent.video_gen_registry import register_provider as _reg

        if not isinstance(provider, VideoGenProvider):
            logger.warning(
                "Plugin '%s' tried to register a video_gen provider that does "
                "not inherit from VideoGenProvider. Ignoring.", self.manifest.name)
            return
        _reg(provider)
        logger.info("Plugin '%s' registered video_gen provider: %s",
                    self.manifest.name, provider.name)

    def register_transcription_provider(self, provider) -> None:
        """Register a transcription backend (TranscriptionProvider)."""
        from agent.transcription_provider import TranscriptionProvider
        from agent.transcription_registry import register_provider as _reg

        if not isinstance(provider, TranscriptionProvider):
            logger.warning(
                "Plugin '%s' tried to register a transcription provider that does "
                "not inherit from TranscriptionProvider. Ignoring.", self.manifest.name)
            return
        _reg(provider)
        logger.info("Plugin '%s' registered transcription provider: %s",
                    self.manifest.name, provider.name)

    def register_tts_provider(self, provider) -> None:
        """Register a text-to-speech backend (TTSProvider)."""
        from agent.tts_provider import TTSProvider
        from agent.tts_registry import register_provider as _reg

        if not isinstance(provider, TTSProvider):
            logger.warning(
                "Plugin '%s' tried to register a tts provider that does not "
                "inherit from TTSProvider. Ignoring.", self.manifest.name)
            return
        _reg(provider)
        logger.info("Plugin '%s' registered tts provider: %s",
                    self.manifest.name, provider.name)

    # -- slash command / dashboard / platform / slack registration ------------
    # v0.20.0 parity — see register_command, register_dashboard_auth_provider,
    # register_platform, register_slack_action_handler in upstream plugins.py.

    def register_command(self, name: str, handler: Callable, description: str = "",
                         args_hint: str = "") -> None:
        """Register an in-session slash command (e.g. ``/cmd``) for CLI + gateway.

        Handler signature: ``fn(raw_args: str) -> str | None`` (may be async).
        Unlike ``register_cli_command`` (which creates ``daedalus <subcommand>``
        terminal commands), this registers slash commands invoked during a
        conversation. Names conflicting with built-in commands are rejected.
        """
        clean = name.lower().strip().lstrip("/").replace(" ", "-")
        if not clean:
            logger.warning(
                "Plugin '%s' tried to register a command with an empty name.",
                self.manifest.name)
            return
        try:
            from daedalus_cli.commands import resolve_command
            if resolve_command(clean) is not None:
                logger.warning(
                    "Plugin '%s' tried to register command '/%s' which conflicts "
                    "with a built-in command. Skipping.",
                    self.manifest.name, clean)
                return
        except Exception:
            pass  # If commands module isn't available, skip the check
        self._manager._plugin_commands[clean] = {
            "handler": handler,
            "description": description or "Plugin command",
            "plugin": self.manifest.name,
            "args_hint": (args_hint or "").strip(),
        }
        logger.debug("Plugin %s registered command: /%s", self.manifest.name, clean)

    def register_dashboard_auth_provider(self, provider) -> None:
        """Register a dashboard authentication provider (DashboardAuthProvider)."""
        from daedalus_cli.dashboard_auth import (
            DashboardAuthProvider, register_provider,
        )
        if not isinstance(provider, DashboardAuthProvider):
            logger.warning(
                "Plugin '%s' tried to register a dashboard-auth provider that does "
                "not inherit from DashboardAuthProvider. Ignoring.", self.manifest.name)
            return
        try:
            register_provider(provider)
        except (TypeError, ValueError) as e:
            logger.warning(
                "Plugin '%s' failed to register dashboard-auth provider %r: %s",
                self.manifest.name, getattr(provider, "name", "?"), e)
            return
        logger.info("Plugin '%s' registered dashboard-auth provider: %s (%s)",
                    self.manifest.name, provider.name, provider.display_name)

    def register_platform(self, name: str, label: str, adapter_factory: Callable,
                          check_fn: Callable, validate_config: Callable | None = None,
                          required_env: list | None = None, install_hint: str = "",
                          **entry_kwargs: Any) -> None:
        """Register a gateway platform adapter (PlatformEntry)."""
        from gateway.platform_registry import platform_registry, PlatformEntry

        entry_kwargs.setdefault("plugin_name", self.manifest.name)
        entry = PlatformEntry(
            name=name, label=label, adapter_factory=adapter_factory,
            check_fn=check_fn, validate_config=validate_config,
            required_env=required_env or [], install_hint=install_hint,
            source="plugin", **entry_kwargs)
        platform_registry.register(entry)
        self._manager._plugin_platform_names.add(name)
        logger.debug("Plugin %s registered platform: %s", self.manifest.name, name)

    def register_slack_action_handler(self, action_id: Any, callback: Callable) -> None:
        """Register a Slack Block Kit action handler from a plugin.

        Callback follows the slack_bolt convention: ``async def handler(ack, body, action)``.
        """
        if not callable(callback):
            raise ValueError(
                f"Plugin '{self.manifest.name}' tried to register a Slack action "
                f"handler with a non-callable callback.")
        if action_id is None or (isinstance(action_id, str) and not action_id.strip()):
            raise ValueError(
                f"Plugin '{self.manifest.name}' tried to register a Slack action "
                f"handler with an empty action_id.")
        self._manager._slack_action_handlers.append(
            (action_id, callback, self.manifest.name))
        logger.debug("Plugin %s registered Slack action handler: %s",
                     self.manifest.name, action_id)


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------

class PluginManager:
    """Central manager that discovers, loads, and invokes plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, LoadedPlugin] = {}
        self._hooks: Dict[str, List[Callable]] = {}
        self._plugin_tool_names: Set[str] = set()
        self._cli_commands: Dict[str, dict] = {}       # `daedalus <subcommand>` (register_cli_command)
        self._plugin_commands: Dict[str, dict] = {}    # in-session `/slash` commands (register_command, v0.20.0)
        self._slack_action_handlers: List[tuple] = []  # (action_id, callback, plugin_name)
        self._plugin_platform_names: Set[str] = set()
        self._discovered: bool = False
        self._cli_ref = None  # Set by CLI after plugin discovery

    # -----------------------------------------------------------------------
    # Public
    # -----------------------------------------------------------------------

    def discover_and_load(self) -> None:
        """Scan all plugin sources and load each plugin found."""
        if self._discovered:
            return
        self._discovered = True

        manifests: List[PluginManifest] = []

        # 1. User/bundled plugins (~/.daedalus/plugins/) — recursive (flat +
        #    category layouts, v0.20.0). Categories with their own discovery
        #    systems are skipped at the top level; platforms/ is scanned one
        #    level deeper for its adapters.
        user_dir = get_daedalus_home() / "plugins"
        skip_top = {"memory", "context_engine", "platforms", "model-providers", "cron_providers"}
        manifests.extend(self._scan_directory(user_dir, source="user", skip_names=skip_top))
        manifests.extend(self._scan_directory(user_dir / "platforms", source="user"))

        # 2. Project plugins (./.daedalus/plugins/)
        if _env_enabled("DAEDALUS_ENABLE_PROJECT_PLUGINS"):
            project_dir = Path.cwd() / ".daedalus" / "plugins"
            manifests.extend(self._scan_directory(project_dir, source="project"))

        # 3. Pip / entry-point plugins
        manifests.extend(self._scan_entry_points())

        # Load each manifest (skip user-disabled plugins)
        disabled = _get_disabled_plugins()
        for manifest in manifests:
            if manifest.name in disabled:
                loaded = LoadedPlugin(manifest=manifest, enabled=False)
                loaded.error = "disabled via config"
                self._plugins[manifest.name] = loaded
                logger.debug("Skipping disabled plugin '%s'", manifest.name)
                continue
            self._load_plugin(manifest)

        if manifests:
            logger.info(
                "Plugin discovery complete: %d found, %d enabled",
                len(self._plugins),
                sum(1 for p in self._plugins.values() if p.enabled),
            )

    # -----------------------------------------------------------------------
    # Directory scanning
    # -----------------------------------------------------------------------

    def _scan_directory(self, path: Path, source: str,
                        skip_names: Optional[Set[str]] = None) -> List[PluginManifest]:
        """Read ``plugin.yaml`` manifests from subdirectories of *path*.

        Supports two layouts, mixed freely (v0.20.0 parity):
        * **Flat** — ``<root>/<plugin-name>/plugin.yaml``.
        * **Category** — ``<root>/<category>/<plugin-name>/plugin.yaml``,
          where the category dir itself has no ``plugin.yaml``. Depth capped
          at two segments.
        """
        return self._scan_directory_level(
            path, source, skip_names=skip_names, prefix="", depth=0
        )

    def _scan_directory_level(
        self,
        path: Path,
        source: str,
        *,
        skip_names: Optional[Set[str]],
        prefix: str,
        depth: int,
    ) -> List[PluginManifest]:
        """Recursive implementation of :meth:`_scan_directory`."""
        manifests: List[PluginManifest] = []
        if not path.is_dir():
            return manifests
        for child in sorted(path.iterdir()):
            if not child.is_dir():
                continue
            if depth == 0 and skip_names and child.name in skip_names:
                continue
            manifest_file = child / "plugin.yaml"
            if not manifest_file.exists():
                manifest_file = child / "plugin.yml"
            if manifest_file.exists():
                manifest = self._parse_manifest(manifest_file, child, source, prefix)
                if manifest is not None:
                    manifests.append(manifest)
                continue
            # No manifest at this level: within the depth cap, treat as a
            # category namespace and recurse one level in.
            if depth >= 1:
                logger.debug("Skipping %s (no plugin.yaml, depth cap reached)", child)
                continue
            sub_prefix = f"{prefix}/{child.name}" if prefix else child.name
            manifests.extend(
                self._scan_directory_level(
                    child, source, skip_names=None, prefix=sub_prefix, depth=depth + 1
                )
            )
        return manifests

    def _parse_manifest(
        self,
        manifest_file: Path,
        plugin_dir: Path,
        source: str,
        prefix: str,
    ) -> Optional[PluginManifest]:
        """Parse a single ``plugin.yaml`` into a :class:`PluginManifest`."""
        try:
            if yaml is None:
                logger.warning("PyYAML not installed – cannot load %s", manifest_file)
                return None
            data = yaml.safe_load(manifest_file.read_text()) or {}
            name = data.get("name", plugin_dir.name)
            key = f"{prefix}/{plugin_dir.name}" if prefix else name
            return PluginManifest(
                name=name,
                key=key,
                version=str(data.get("version", "")),
                description=data.get("description", ""),
                author=data.get("author", ""),
                requires_env=data.get("requires_env", []),
                provides_tools=data.get("provides_tools", []),
                provides_hooks=data.get("provides_hooks", []),
                source=source,
                path=str(plugin_dir),
            )
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", manifest_file, exc)
            return None

    # -----------------------------------------------------------------------
    # Entry-point scanning
    # -----------------------------------------------------------------------

    def _scan_entry_points(self) -> List[PluginManifest]:
        """Check ``importlib.metadata`` for pip-installed plugins."""
        manifests: List[PluginManifest] = []
        try:
            eps = importlib.metadata.entry_points()
            # Python 3.12+ returns a SelectableGroups; earlier returns dict
            if hasattr(eps, "select"):
                group_eps = eps.select(group=ENTRY_POINTS_GROUP)
            elif isinstance(eps, dict):
                group_eps = eps.get(ENTRY_POINTS_GROUP, [])
            else:
                group_eps = [ep for ep in eps if ep.group == ENTRY_POINTS_GROUP]

            for ep in group_eps:
                manifest = PluginManifest(
                    name=ep.name,
                    source="entrypoint",
                    path=ep.value,
                )
                manifests.append(manifest)
        except Exception as exc:
            logger.debug("Entry-point scan failed: %s", exc)

        return manifests

    # -----------------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------------

    def _load_plugin(self, manifest: PluginManifest) -> None:
        """Import a plugin module and call its ``register(ctx)`` function."""
        loaded = LoadedPlugin(manifest=manifest)

        try:
            if manifest.source in ("user", "project"):
                module = self._load_directory_module(manifest)
            else:
                module = self._load_entrypoint_module(manifest)

            loaded.module = module

            # Call register()
            register_fn = getattr(module, "register", None)
            if register_fn is None:
                loaded.error = "no register() function"
                logger.warning("Plugin '%s' has no register() function", manifest.name)
            else:
                ctx = PluginContext(manifest, self)
                register_fn(ctx)
                loaded.tools_registered = [
                    t for t in self._plugin_tool_names
                    if t not in {
                        n
                        for name, p in self._plugins.items()
                        for n in p.tools_registered
                    }
                ]
                loaded.hooks_registered = list(
                    {
                        h
                        for h, cbs in self._hooks.items()
                        if cbs  # non-empty
                    }
                    - {
                        h
                        for name, p in self._plugins.items()
                        for h in p.hooks_registered
                    }
                )
                loaded.enabled = True

        except Exception as exc:
            loaded.error = str(exc)
            logger.warning("Failed to load plugin '%s': %s", manifest.name, exc)

        self._plugins[manifest.name] = loaded

    def _load_directory_module(self, manifest: PluginManifest) -> types.ModuleType:
        """Import a directory-based plugin as ``daedalus_plugins.<name>``."""
        plugin_dir = Path(manifest.path)  # type: ignore[arg-type]
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            raise FileNotFoundError(f"No __init__.py in {plugin_dir}")

        # Ensure the namespace parent package exists
        if _NS_PARENT not in sys.modules:
            ns_pkg = types.ModuleType(_NS_PARENT)
            ns_pkg.__path__ = []  # type: ignore[attr-defined]
            ns_pkg.__package__ = _NS_PARENT
            sys.modules[_NS_PARENT] = ns_pkg

        key = manifest.key or manifest.name
        slug = key.replace("/", "__").replace("-", "_")
        module_name = f"{_NS_PARENT}.{slug}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            init_file,
            submodule_search_locations=[str(plugin_dir)],
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {init_file}")

        module = importlib.util.module_from_spec(spec)
        module.__package__ = module_name
        module.__path__ = [str(plugin_dir)]  # type: ignore[attr-defined]
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _load_entrypoint_module(self, manifest: PluginManifest) -> types.ModuleType:
        """Load a pip-installed plugin via its entry-point reference."""
        eps = importlib.metadata.entry_points()
        if hasattr(eps, "select"):
            group_eps = eps.select(group=ENTRY_POINTS_GROUP)
        elif isinstance(eps, dict):
            group_eps = eps.get(ENTRY_POINTS_GROUP, [])
        else:
            group_eps = [ep for ep in eps if ep.group == ENTRY_POINTS_GROUP]

        for ep in group_eps:
            if ep.name == manifest.name:
                return ep.load()

        raise ImportError(
            f"Entry point '{manifest.name}' not found in group '{ENTRY_POINTS_GROUP}'"
        )

    # -----------------------------------------------------------------------
    # Hook invocation
    # -----------------------------------------------------------------------

    def invoke_hook(self, hook_name: str, **kwargs: Any) -> List[Any]:
        """Call all registered callbacks for *hook_name*.

        Each callback is wrapped in its own try/except so a misbehaving
        plugin cannot break the core agent loop.

        Returns a list of non-``None`` return values from callbacks.

        For ``pre_llm_call``, callbacks may return a dict describing
        context to inject into the current turn's user message::

            {"context": "recalled text..."}
            "recalled text..."          # plain string, equivalent

        Context is ALWAYS injected into the user message, never the
        system prompt.  This preserves the prompt cache prefix — the
        system prompt stays identical across turns so cached tokens
        are reused.  All injected context is ephemeral — never
        persisted to session DB.
        """
        callbacks = self._hooks.get(hook_name, [])
        results: List[Any] = []
        for cb in callbacks:
            try:
                ret = cb(**kwargs)
                if ret is not None:
                    results.append(ret)
            except Exception as exc:
                logger.warning(
                    "Hook '%s' callback %s raised: %s",
                    hook_name,
                    getattr(cb, "__name__", repr(cb)),
                    exc,
                )
        return results

    # -----------------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------------

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Return a list of info dicts for all discovered plugins."""
        result: List[Dict[str, Any]] = []
        for name, loaded in sorted(self._plugins.items()):
            result.append(
                {
                    "name": name,
                    "version": loaded.manifest.version,
                    "description": loaded.manifest.description,
                    "source": loaded.manifest.source,
                    "enabled": loaded.enabled,
                    "tools": len(loaded.tools_registered),
                    "hooks": len(loaded.hooks_registered),
                    "error": loaded.error,
                }
            )
        return result


# ---------------------------------------------------------------------------
# Module-level singleton & convenience functions
# ---------------------------------------------------------------------------

_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Return (and lazily create) the global PluginManager singleton."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def discover_plugins() -> None:
    """Discover and load all plugins (idempotent)."""
    get_plugin_manager().discover_and_load()


def _ensure_plugins_discovered() -> PluginManager:
    """Return the global manager after ensuring plugin discovery has run."""
    manager = get_plugin_manager()
    manager.discover_and_load()
    return manager


def get_plugin_commands() -> Dict[str, dict]:
    """Return the full plugin commands dict (name → {handler, description, plugin}).

    Triggers idempotent plugin discovery so callers can use plugin commands
    before any explicit discover_plugins() call.
    """
    return _ensure_plugins_discovered()._plugin_commands


def invoke_hook(hook_name: str, **kwargs: Any) -> List[Any]:
    """Invoke a lifecycle hook on all loaded plugins.

    Returns a list of non-``None`` return values from plugin callbacks.
    """
    return get_plugin_manager().invoke_hook(hook_name, **kwargs)


def get_plugin_tool_names() -> Set[str]:
    """Return the set of tool names registered by plugins."""
    return get_plugin_manager()._plugin_tool_names


def get_plugin_cli_commands() -> Dict[str, dict]:
    """Return CLI commands registered by general plugins.

    Returns a dict of ``{name: {help, setup_fn, handler_fn, ...}}``
    suitable for wiring into argparse subparsers.
    """
    return dict(get_plugin_manager()._cli_commands)


def get_plugin_toolsets() -> List[tuple]:
    """Return plugin toolsets as ``(key, label, description)`` tuples.

    Used by the ``daedalus tools`` TUI so plugin-provided toolsets appear
    alongside the built-in ones and can be toggled on/off per platform.
    """
    manager = get_plugin_manager()
    if not manager._plugin_tool_names:
        return []

    try:
        from tools.registry import registry
    except Exception:
        return []

    # Group plugin tool names by their toolset
    toolset_tools: Dict[str, List[str]] = {}
    toolset_plugin: Dict[str, LoadedPlugin] = {}
    for tool_name in manager._plugin_tool_names:
        entry = registry._tools.get(tool_name)
        if not entry:
            continue
        ts = entry.toolset
        toolset_tools.setdefault(ts, []).append(entry.name)

    # Map toolsets back to the plugin that registered them
    for _name, loaded in manager._plugins.items():
        for tool_name in loaded.tools_registered:
            entry = registry._tools.get(tool_name)
            if entry and entry.toolset in toolset_tools:
                toolset_plugin.setdefault(entry.toolset, loaded)

    result = []
    for ts_key in sorted(toolset_tools):
        plugin = toolset_plugin.get(ts_key)
        label = f"🔌 {ts_key.replace('_', ' ').title()}"
        if plugin and plugin.manifest.description:
            desc = plugin.manifest.description
        else:
            desc = ", ".join(sorted(toolset_tools[ts_key]))
        result.append((ts_key, label, desc))

    return result
