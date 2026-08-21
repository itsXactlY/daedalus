"""Mazemaker tools for semantic memory storage and retrieval.

Registers four tools for the mazemaker memory system:

  mazemaker_remember  — Store a memory (with conflict detection)
  mazemaker_recall    — Search memories by semantic similarity  
  mazemaker_think     — Spreading activation from a memory
  mazemaker_graph     — View knowledge graph statistics

The mazemaker memory provider is loaded via the plugin system and
accessed through the MemoryManager.
"""

import json
import logging
from typing import Dict, Any

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

# ── Module-level state ──

_mazemaker_provider = None  # initialized MazemakerProvider instance


def _provider_initialized(provider) -> bool:
    """Return True when a provider has a live backend instance.

    Recognises both the in-process ``mazemaker`` provider (``_memory``) and
    the MCP-routed ``mcp`` provider (``_client``).  Either backend handle
    being non-None means the provider has finished its ``initialize()``.
    """
    if provider is None:
        return False
    if getattr(provider, "_memory", None) is not None:
        return True
    if getattr(provider, "_client", None) is not None:
        return True
    return False


def _resolve_active_provider_name() -> str:
    """Read ``memory.provider`` from config.yaml. Defaults to ``"mazemaker"``."""
    try:
        from daedalus_cli.config import load_config
        cfg = load_config() or {}
        name = (cfg.get("memory") or {}).get("provider")
        if name in ("mazemaker", "mcp"):
            return name
    except Exception:
        pass
    return "mazemaker"


def _load_mazemaker_provider():
    """Load the active mazemaker-tools provider without assuming MemoryManager exists.

    Normal agent sessions initialize the provider through MemoryManager and call
    set_mazemaker_provider(). Direct registry/API tool calls do not have that path,
    so they must lazily load the provider here.

    Honours ``memory.provider`` in config.yaml — if the user flipped to
    ``mcp`` we route through the MCP socket instead of in-process Mazemaker.
    Falls back to ``mazemaker`` if the configured provider is unavailable so
    the four tool handlers stay green during transient daemon outages.
    """
    from plugins.memory import load_memory_provider
    name = _resolve_active_provider_name()
    provider = load_memory_provider(name)
    if provider and provider.is_available():
        return provider
    if name != "mazemaker":
        # Fall back to the in-process provider so the four mazemaker_* tools
        # still work even when the MCP daemon is down.
        provider = load_memory_provider("mazemaker")
        if provider and provider.is_available():
            return provider
    return None


def _ensure_mazemaker_provider(session_id: str = ""):
    """Return an initialized mazemaker provider, or None.

    The old check_fn path stored an uninitialized provider. Handlers then called
    provider.handle_tool_call(), which crashed as `'NoneType' object has no
    attribute 'recall'` because provider._memory was still None. Direct tool
    execution must be self-contained.
    """
    global _mazemaker_provider

    provider = _mazemaker_provider
    if provider is None or not provider.is_available():
        provider = _load_mazemaker_provider()
        _mazemaker_provider = provider

    if provider is None:
        return None

    if not _provider_initialized(provider):
        try:
            provider.initialize(session_id or "mazemaker-tool-session")
        except TypeError:
            provider.initialize(session_id=session_id or "mazemaker-tool-session")
        if not _provider_initialized(provider):
            return None

    return provider


def set_mazemaker_provider(provider) -> None:
    """Set the mazemaker memory provider instance.
    
    Called by the MemoryManager when mazemaker provider is loaded.
    """
    global _mazemaker_provider
    _mazemaker_provider = provider


def clear_mazemaker_provider() -> None:
    """Clear the mazemaker provider reference."""
    global _mazemaker_provider
    _mazemaker_provider = None


def _check_mazemaker_available() -> bool:
    """Check if mazemaker memory is importable.

    Keep this side-effect-light: get_tool_definitions() calls check_fn during
    schema filtering. Initialization happens in the handlers or MemoryManager.
    """
    try:
        if _mazemaker_provider is not None:
            return _mazemaker_provider.is_available()
        return _load_mazemaker_provider() is not None
    except Exception:
        return False


# ── Tool schemas ──

_MAZEMAKER_REMEMBER_SCHEMA = {
    "name": "mazemaker_remember",
    "description": (
        "Store a memory in the mazemaker memory system. "
        "Memories are embedded and auto-connected to similar memories. "
        "Use this for facts, user preferences, decisions, and important context. "
        "Automatically detects and updates conflicting memories."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The memory content to store.",
            },
            "label": {
                "type": "string",
                "description": "Short label for the memory (optional, auto-generated from content if omitted).",
            },
        },
        "required": ["content"],
    },
}

_MAZEMAKER_RECALL_SCHEMA = {
    "name": "mazemaker_recall",
    "description": (
        "Search mazemaker memory using semantic similarity. "
        "Returns memories ranked by relevance with connection info. "
        "Use this to recall past conversations, facts, or user preferences."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for.",
            },
            "limit": {
                "type": "integer",
                "description": "Max results to return (default: 5).",
            },
        },
        "required": ["query"],
    },
}

_MAZEMAKER_THINK_SCHEMA = {
    "name": "mazemaker_think",
    "description": (
        "Spreading activation from a memory — explore connected ideas. "
        "Returns memories activated by traversing the knowledge graph from a starting point. "
        "Use to find related context that isn't directly similar."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "integer",
                "description": "Starting memory ID.",
            },
            "depth": {
                "type": "integer",
                "description": "Activation depth (default: 3).",
            },
        },
        "required": ["memory_id"],
    },
}

_MAZEMAKER_GRAPH_SCHEMA = {
    "name": "mazemaker_graph",
    "description": (
        "Get knowledge graph statistics and top connections. "
        "Use to understand the structure of stored memories."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ── Tool handlers ──

def _handle_mazemaker_remember(args: Dict[str, Any], **kwargs) -> str:
    """Handle mazemaker_remember tool call."""
    provider = _ensure_mazemaker_provider(kwargs.get("session_id") or kwargs.get("task_id") or "")
    if not provider:
        return tool_error("Mazemaker memory provider not available")
    
    try:
        return provider.handle_tool_call("mazemaker_remember", args)
    except Exception as e:
        return tool_error(f"mazemaker_remember failed: {e}")


def _handle_mazemaker_recall(args: Dict[str, Any], **kwargs) -> str:
    """Handle mazemaker_recall tool call."""
    provider = _ensure_mazemaker_provider(kwargs.get("session_id") or kwargs.get("task_id") or "")
    if not provider:
        return tool_error("Mazemaker memory provider not available")
    
    try:
        return provider.handle_tool_call("mazemaker_recall", args)
    except Exception as e:
        return tool_error(f"mazemaker_recall failed: {e}")


def _handle_mazemaker_think(args: Dict[str, Any], **kwargs) -> str:
    """Handle mazemaker_think tool call."""
    provider = _ensure_mazemaker_provider(kwargs.get("session_id") or kwargs.get("task_id") or "")
    if not provider:
        return tool_error("Mazemaker memory provider not available")
    
    try:
        return provider.handle_tool_call("mazemaker_think", args)
    except Exception as e:
        return tool_error(f"mazemaker_think failed: {e}")


def _handle_mazemaker_graph(args: Dict[str, Any], **kwargs) -> str:
    """Handle mazemaker_graph tool call."""
    provider = _ensure_mazemaker_provider(kwargs.get("session_id") or kwargs.get("task_id") or "")
    if not provider:
        return tool_error("Mazemaker memory provider not available")
    
    try:
        return provider.handle_tool_call("mazemaker_graph", args)
    except Exception as e:
        return tool_error(f"mazemaker_graph failed: {e}")


# ── Register tools ──

registry.register(
    name="mazemaker_remember",
    toolset="memory",
    schema=_MAZEMAKER_REMEMBER_SCHEMA,
    handler=_handle_mazemaker_remember,
    check_fn=_check_mazemaker_available,
    description="Store a memory in mazemaker memory system with conflict detection",
    emoji="🧠💾🧠",
)

registry.register(
    name="mazemaker_recall",
    toolset="memory",
    schema=_MAZEMAKER_RECALL_SCHEMA,
    handler=_handle_mazemaker_recall,
    check_fn=_check_mazemaker_available,
    description="Search memories by semantic similarity",
    emoji="🧠🔍🧠",
)

registry.register(
    name="mazemaker_think",
    toolset="memory",
    schema=_MAZEMAKER_THINK_SCHEMA,
    handler=_handle_mazemaker_think,
    check_fn=_check_mazemaker_available,
    description="Explore connected ideas via spreading activation",
    emoji="🧠💡🧠",
)

registry.register(
    name="mazemaker_graph",
    toolset="memory",
    schema=_MAZEMAKER_GRAPH_SCHEMA,
    handler=_handle_mazemaker_graph,
    check_fn=_check_mazemaker_available,
    description="View knowledge graph statistics",
    emoji="🧠📊🧠",
)
