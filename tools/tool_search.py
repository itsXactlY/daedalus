from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tools.registry import tool_error

logger = logging.getLogger("tools.tool_search")


TOOL_SEARCH_NAME = "tool_search"
TOOL_DESCRIBE_NAME = "tool_describe"
TOOL_CALL_NAME = "tool_call"

BRIDGE_TOOL_NAMES = frozenset({TOOL_SEARCH_NAME, TOOL_DESCRIBE_NAME, TOOL_CALL_NAME})

CHARS_PER_TOKEN = 4.0


@dataclass(frozen=True)
class ToolSearchConfig:
    enabled: str
    threshold_pct: float
    search_default_limit: int
    max_search_limit: int
    always_load: Tuple[str, ...] = ()

    @classmethod
    def from_raw(cls, raw: Any) -> "ToolSearchConfig":
        if raw is True:
            return cls(enabled="auto", threshold_pct=5.0,
                       search_default_limit=5, max_search_limit=20)
        if raw is False:
            return cls(enabled="off", threshold_pct=5.0,
                       search_default_limit=5, max_search_limit=20)
        if not isinstance(raw, dict):
            return cls(enabled="auto", threshold_pct=5.0,
                       search_default_limit=5, max_search_limit=20)

        enabled_raw = str(raw.get("enabled", "auto")).strip().lower()
        if enabled_raw in ("true", "1", "yes"):
            enabled = "on"
        elif enabled_raw in ("false", "0", "no"):
            enabled = "off"
        elif enabled_raw in ("auto", "on", "off"):
            enabled = enabled_raw
        else:
            enabled = "auto"

        threshold_pct = _safe_float(raw.get("threshold_pct"), 5.0)
        threshold_pct = max(0.0, min(100.0, threshold_pct))

        max_search_limit = max(1, min(50, _safe_int(raw.get("max_search_limit"), 20)))
        search_default_limit = max(1, min(max_search_limit,
                                          _safe_int(raw.get("search_default_limit"), 5)))

        raw_always = raw.get("always_load")
        if isinstance(raw_always, str):
            raw_always = [raw_always]
        always_load = tuple(
            n.strip() for n in raw_always
            if isinstance(n, str) and n.strip()
        ) if isinstance(raw_always, (list, tuple)) else ()

        return cls(
            enabled=enabled,
            threshold_pct=threshold_pct,
            search_default_limit=search_default_limit,
            max_search_limit=max_search_limit,
            always_load=always_load,
        )


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _safe_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def load_config() -> ToolSearchConfig:
    try:
        from daedalus_cli.config import load_config as _load
        cfg = _load() or {}
        tools_cfg = cfg.get("tools") if isinstance(cfg.get("tools"), dict) else {}
        if not isinstance(tools_cfg, dict):
            tools_cfg = {}
        return ToolSearchConfig.from_raw(tools_cfg.get("tool_search"))
    except Exception as e:
        logger.debug("Failed to load tool-search config: %s", e)
        return ToolSearchConfig.from_raw(None)


def _core_tool_names() -> frozenset[str]:
    try:
        from toolsets import _DAEDALUS_CORE_TOOLS
        return frozenset(_DAEDALUS_CORE_TOOLS)
    except Exception:
        return frozenset()


def is_deferrable_tool_name(
    name: str, config: Optional[ToolSearchConfig] = None
) -> bool:
    if name in BRIDGE_TOOL_NAMES:
        return False
    if name in _core_tool_names():
        return False
    if config is not None and name in config.always_load:
        return False
    try:
        from tools.registry import registry
        return registry.get_toolset_for_tool(name) is not None
    except Exception:
        return False


def classify_tools(
    tool_defs: List[Dict[str, Any]], config: Optional[ToolSearchConfig] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    visible: List[Dict[str, Any]] = []
    deferrable: List[Dict[str, Any]] = []
    for td in tool_defs:
        fn = td.get("function") or {}
        name = fn.get("name", "")
        if name in BRIDGE_TOOL_NAMES:
            continue
        if is_deferrable_tool_name(name, config):
            deferrable.append(td)
        else:
            visible.append(td)
    return visible, deferrable


def estimate_tokens_from_schemas(tool_defs: Iterable[Dict[str, Any]]) -> int:
    total_chars = 0
    for td in tool_defs:
        try:
            total_chars += len(json.dumps(td, ensure_ascii=False, separators=(",", ":")))
        except (TypeError, ValueError):
            total_chars += len(str(td))
    return int(math.ceil(total_chars / CHARS_PER_TOKEN))


def should_activate(
    config: ToolSearchConfig,
    deferrable_tokens: int,
    context_length: Optional[int],
) -> bool:
    if config.enabled == "off":
        return False
    if deferrable_tokens <= 0:
        return False
    return True


@dataclass
class CatalogEntry:
    name: str
    description: str
    schema: Dict[str, Any]
    source: str
    source_name: str

    _tokens: List[str] = field(default_factory=list)


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _entry_search_text(td: Dict[str, Any]) -> str:
    fn = td.get("function") or {}
    name = fn.get("name", "")
    desc = fn.get("description", "") or ""
    params = ((fn.get("parameters") or {}).get("properties") or {})
    param_names = " ".join(params.keys())
    name_words = name.replace("_", " ").replace(".", " ").replace("-", " ").replace(":", " ")
    return f"{name_words} {desc} {param_names}"


def _classify_source(name: str) -> Tuple[str, str]:
    try:
        from tools.registry import registry
        toolset = registry.get_toolset_for_tool(name)
        if not toolset:
            return ("other", "")
        if toolset.startswith("mcp-"):
            return ("mcp", toolset)
        return ("plugin", toolset)
    except Exception:
        return ("other", "")


def build_catalog(tool_defs: List[Dict[str, Any]]) -> List[CatalogEntry]:
    catalog: List[CatalogEntry] = []
    for td in tool_defs:
        fn = td.get("function") or {}
        name = fn.get("name", "")
        if not name:
            continue
        desc = fn.get("description", "") or ""
        source, source_name = _classify_source(name)
        entry = CatalogEntry(
            name=name,
            description=desc,
            schema=td,
            source=source,
            source_name=source_name,
            _tokens=_tokenize(_entry_search_text(td)),
        )
        catalog.append(entry)
    return catalog


def _bm25_score(query_tokens: List[str], doc_tokens: List[str],
                doc_lengths: List[int], avg_dl: float,
                doc_freq: Dict[str, int], n_docs: int,
                k1: float = 1.5, b: float = 0.75) -> float:
    if not doc_tokens:
        return 0.0
    score = 0.0
    dl = len(doc_tokens)
    doc_tf: Dict[str, int] = {}
    for t in doc_tokens:
        doc_tf[t] = doc_tf.get(t, 0) + 1
    for q in query_tokens:
        df = doc_freq.get(q, 0)
        if df == 0:
            continue
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        tf = doc_tf.get(q, 0)
        if tf == 0:
            continue
        norm = tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1.0)))
        score += idf * norm
    return score


def _name_affinity(query: str, query_tokens: List[str], name: str) -> float:
    ql = query.strip().lower()
    nl = name.lower()
    if ql == nl:
        return 3.0
    if ql and ql in nl:
        return 2.0
    name_tokens = set(_tokenize(name))
    if not query_tokens:
        return 0.0
    if set(query_tokens) <= name_tokens:
        return 1.0
    return len(set(query_tokens) & name_tokens) / len(set(query_tokens))


def search_catalog(catalog: List[CatalogEntry], query: str, limit: int = 5) -> List[CatalogEntry]:
    if not catalog or limit <= 0:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    doc_lengths = [len(e._tokens) for e in catalog]
    avg_dl = sum(doc_lengths) / max(len(doc_lengths), 1)
    doc_freq: Dict[str, int] = {}
    for e in catalog:
        for t in set(e._tokens):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    n_docs = len(catalog)

    scored: List[Tuple[float, float, str, CatalogEntry]] = []
    for entry in catalog:
        affinity = _name_affinity(query, query_tokens, entry.name)
        relevance = _bm25_score(query_tokens, entry._tokens, doc_lengths, avg_dl,
                                doc_freq, n_docs)
        if affinity or relevance > 0:
            scored.append((affinity, relevance, entry.name, entry))

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [e for _, _, _, e in scored[:limit]]


def rank_documents(documents: List[Tuple[str, str]], query: str,
                   limit: int = 20) -> List[Tuple[str, float]]:
    """Rank (name, text) pairs by the same BM25 + name-affinity used for tools."""
    if not documents or limit <= 0:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    token_docs = [_tokenize(f"{n.replace('-', ' ').replace('_', ' ')} {t}")
                  for n, t in documents]
    doc_lengths = [len(d) for d in token_docs]
    avg_dl = sum(doc_lengths) / max(len(doc_lengths), 1)
    doc_freq: Dict[str, int] = {}
    for d in token_docs:
        for t in set(d):
            doc_freq[t] = doc_freq.get(t, 0) + 1
    n_docs = len(token_docs)

    scored: List[Tuple[float, float, str]] = []
    for (name, _text), tokens in zip(documents, token_docs):
        affinity = _name_affinity(query, query_tokens, name)
        relevance = _bm25_score(query_tokens, tokens, doc_lengths, avg_dl,
                                doc_freq, n_docs)
        if affinity or relevance > 0:
            scored.append((affinity, relevance, name))

    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [(name, affinity + relevance) for affinity, relevance, name in scored[:limit]]


def _source_label(source_name: str) -> str:
    label = source_name or "other"
    if label.startswith("mcp-"):
        label = label[4:]
    return label


def bridge_tool_schemas(deferred_count: int) -> List[Dict[str, Any]]:
    desc_search = (
        f"Search the {deferred_count} tools that are not loaded in this context. "
        "Returns matching names with their descriptions; follow with "
        f"`{TOOL_DESCRIBE_NAME}` for a tool's parameter schema, then "
        f"`{TOOL_CALL_NAME}` to invoke it. All {deferred_count} are connected "
        "and callable — never report a capability as missing until a search "
        "for it returned no match. Tools already listed in this context are "
        "loaded and must be called directly, not searched."
    )
    desc_describe = (
        f"Load the full JSON schema for one tool returned by `{TOOL_SEARCH_NAME}`. "
        f"Required before `{TOOL_CALL_NAME}` if the tool's parameters are unknown."
    )
    desc_call = (
        "Invoke a deferred tool by name with the given arguments. Argument shape "
        f"matches the tool's schema (see `{TOOL_DESCRIBE_NAME}`). Policy, hooks, "
        "and approvals run exactly as for any directly-listed tool."
    )

    return [
        {
            "type": "function",
            "function": {
                "name": TOOL_SEARCH_NAME,
                "description": desc_search,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Keywords describing the capability you need (e.g. 'create github issue').",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return. Default 5.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_DESCRIBE_NAME,
                "description": desc_describe,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Exact tool name (as returned by tool_search).",
                        },
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": TOOL_CALL_NAME,
                "description": desc_call,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Exact tool name to invoke.",
                        },
                        "arguments": {
                            "type": "object",
                            "description": "Arguments for the tool, matching its schema.",
                        },
                    },
                    "required": ["name", "arguments"],
                },
            },
        },
    ]


@dataclass
class AssemblyResult:
    tool_defs: List[Dict[str, Any]]
    activated: bool
    deferred_count: int = 0
    deferred_tokens: int = 0
    threshold_tokens: int = 0


def assemble_tool_defs(
    tool_defs: List[Dict[str, Any]],
    *,
    context_length: Optional[int] = None,
    config: Optional[ToolSearchConfig] = None,
) -> AssemblyResult:
    if config is None:
        config = load_config()

    incoming = [td for td in tool_defs
                if (td.get("function") or {}).get("name") not in BRIDGE_TOOL_NAMES]

    visible, deferrable = classify_tools(incoming, config)
    if not deferrable:
        return AssemblyResult(tool_defs=incoming, activated=False)

    deferrable_tokens = estimate_tokens_from_schemas(deferrable)
    if not should_activate(config, deferrable_tokens, context_length):
        return AssemblyResult(
            tool_defs=incoming,
            activated=False,
            deferred_count=len(deferrable),
            deferred_tokens=deferrable_tokens,
            threshold_tokens=int((context_length or 0) * (config.threshold_pct / 100.0)),
        )

    result = visible + bridge_tool_schemas(len(deferrable))

    logger.info(
        "tool_search activated: %d visible tools kept, %d deferred (~%d tokens)",
        len(visible), len(deferrable), deferrable_tokens,
    )

    return AssemblyResult(
        tool_defs=result,
        activated=True,
        deferred_count=len(deferrable),
        deferred_tokens=deferrable_tokens,
        threshold_tokens=int((context_length or 0) * (config.threshold_pct / 100.0)),
    )


def is_bridge_tool(name: str) -> bool:
    return name in BRIDGE_TOOL_NAMES


def _format_search_hit(entry: CatalogEntry) -> Dict[str, Any]:
    return {
        "name": entry.name,
        "source": entry.source,
        "source_name": entry.source_name,
        "description": (entry.description or "")[:400],
    }


def _available_source_summary(catalog: List[CatalogEntry]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for entry in catalog:
        label = _source_label(entry.source_name)
        counts[label] = counts.get(label, 0) + 1
    return [
        {"name": name, "tool_count": counts[name]}
        for name in sorted(counts)
    ]


def dispatch_tool_search(args: Dict[str, Any],
                         *,
                         current_tool_defs: List[Dict[str, Any]],
                         config: Optional[ToolSearchConfig] = None) -> str:
    if config is None:
        config = load_config()
    query = str(args.get("query") or "").strip()
    if not query:
        return tool_error("query is required")

    raw_limit = args.get("limit")
    if raw_limit is None:
        limit = config.search_default_limit
    else:
        limit = max(1, min(config.max_search_limit, _safe_int(raw_limit, config.search_default_limit)))

    _, deferrable = classify_tools(current_tool_defs, config)
    catalog = build_catalog(deferrable)
    hits = search_catalog(catalog, query, limit=limit)
    result: Dict[str, Any] = {
        "query": query,
        "total_available": len(catalog),
        "matches": [_format_search_hit(h) for h in hits],
    }
    if not hits and catalog:
        result["available_sources"] = _available_source_summary(catalog)
        result["hint"] = (
            "No lexical match was found, but the sources above are connected "
            "and their tools remain available. Retry tool_search with the "
            "service name plus a concrete action or object before concluding "
            "the capability is unavailable."
        )
    return json.dumps(result, ensure_ascii=False)


def dispatch_tool_describe(args: Dict[str, Any],
                           *,
                           current_tool_defs: List[Dict[str, Any]]) -> str:
    name = str(args.get("name") or "").strip()
    if not name:
        return tool_error("name is required")
    _cfg = load_config()
    if not is_deferrable_tool_name(name, _cfg):
        return tool_error(
            f"'{name}' is not a deferrable tool. If you see it in the tools list "
            "already, call it directly; otherwise check the spelling against tool_search."
        )
    _, deferrable = classify_tools(current_tool_defs, _cfg)
    for td in deferrable:
        fn = td.get("function") or {}
        if fn.get("name") == name:
            return json.dumps({
                "name": name,
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters", {}),
            }, ensure_ascii=False)
    return tool_error(
        f"'{name}' is not currently available. Re-run tool_search to refresh."
    )


def scoped_deferrable_names(tool_defs: List[Dict[str, Any]]) -> frozenset[str]:
    names: set[str] = set()
    for td in tool_defs:
        name = (td.get("function") or {}).get("name", "")
        if name and is_deferrable_tool_name(name):
            names.add(name)
    return frozenset(names)


def validate_deferred_call_args(name: str, args: Dict[str, Any]) -> Optional[str]:
    try:
        from tools.registry import registry as _registry
        schema = _registry.get_schema(name)
        if not isinstance(schema, dict):
            return None
        fn = schema.get("function") if schema.get("type") == "function" else schema
        if not isinstance(fn, dict):
            return None
        params = fn.get("parameters")
        if not isinstance(params, dict):
            return None
        required = params.get("required")
        if not isinstance(required, list) or not required:
            return None
        missing = [r for r in required if isinstance(r, str) and r not in args]
        if not missing:
            return None
        return tool_error(
            f"tool_call to '{name}' is missing required argument(s): "
            f"{', '.join(missing)}. The tool was NOT invoked.",
            parameters=params,
            hint=(
                "Retry tool_call with 'arguments' matching the parameters "
                "schema above."
            ),
        )
    except Exception:
        logger.debug("validate_deferred_call_args failed for %s", name, exc_info=True)
        return None


def resolve_underlying_call(args: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
    name = str(args.get("name") or "").strip()
    if not name:
        return None, {}, "tool_call requires a 'name' argument"
    if name in BRIDGE_TOOL_NAMES:
        return None, {}, f"tool_call cannot invoke '{name}' (it is itself a bridge tool)"
    raw_args = args.get("arguments")
    if raw_args is None:
        raw_args = {}
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            return None, {}, f"tool_call 'arguments' is not valid JSON: {e}"
    if not isinstance(raw_args, dict):
        return None, {}, "tool_call 'arguments' must be an object"
    if not is_deferrable_tool_name(name):
        return None, {}, (
            f"'{name}' is not a deferrable tool. If it appears in the model-facing tools "
            "list already, call it directly instead of via tool_call."
        )
    return name, raw_args, None


__all__ = [
    "TOOL_SEARCH_NAME",
    "TOOL_DESCRIBE_NAME",
    "TOOL_CALL_NAME",
    "BRIDGE_TOOL_NAMES",
    "ToolSearchConfig",
    "CatalogEntry",
    "AssemblyResult",
    "load_config",
    "is_deferrable_tool_name",
    "classify_tools",
    "estimate_tokens_from_schemas",
    "should_activate",
    "build_catalog",
    "search_catalog",
    "bridge_tool_schemas",
    "assemble_tool_defs",
    "is_bridge_tool",
    "dispatch_tool_search",
    "dispatch_tool_describe",
    "resolve_underlying_call",
    "scoped_deferrable_names",
    "validate_deferred_call_args",
]
