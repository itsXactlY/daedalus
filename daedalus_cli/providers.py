"""
Single source of truth for provider identity in Daedalus Agent.

Two data sources, merged at runtime:

1. **models.dev catalog** — 109+ providers with base URLs, env vars, display
   names, and full model metadata (context, cost, capabilities).  This is
   the primary database.

2. **Daedalus overlays** — transport type, auth patterns, aggregator flags,
   and additional env vars that models.dev doesn't track.  Small dict,
   maintained here.

3. **User config** (``providers:`` section in config.yaml) — user-defined
   endpoints and overrides.  Merged on top of everything else.

Other modules import from this file.  No parallel registries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)



@dataclass(frozen=True)
class DaedalusOverlay:
    """Daedalus-specific provider metadata layered on top of models.dev."""

    transport: str = "openai_chat"
    is_aggregator: bool = False
    auth_type: str = "api_key"
    extra_env_vars: Tuple[str, ...] = ()
    base_url_override: str = ""
    base_url_env_var: str = ""


DAEDALUS_OVERLAYS: Dict[str, DaedalusOverlay] = {
    "openrouter": DaedalusOverlay(
        transport="openai_chat",
        is_aggregator=True,
        extra_env_vars=("OPENAI_API_KEY",),
        base_url_env_var="OPENROUTER_BASE_URL",
    ),
    "nous": DaedalusOverlay(
        transport="openai_chat",
        auth_type="oauth_device_code",
        base_url_override="https://inference-api.nousresearch.com/v1",
    ),
    "openai-codex": DaedalusOverlay(
        transport="codex_responses",
        auth_type="oauth_external",
        base_url_override="https://chatgpt.com/backend-api/codex",
    ),
    "qwen-oauth": DaedalusOverlay(
        transport="openai_chat",
        auth_type="oauth_external",
        base_url_override="https://portal.qwen.ai/v1",
        base_url_env_var="DAEDALUS_QWEN_BASE_URL",
    ),
    "copilot-acp": DaedalusOverlay(
        transport="codex_responses",
        auth_type="external_process",
        base_url_override="acp://copilot",
        base_url_env_var="COPILOT_ACP_BASE_URL",
    ),
    "github-copilot": DaedalusOverlay(
        transport="openai_chat",
        extra_env_vars=("COPILOT_GITHUB_TOKEN", "GH_TOKEN"),
    ),
    "anthropic": DaedalusOverlay(
        transport="anthropic_messages",
        extra_env_vars=("ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"),
    ),
    "zai": DaedalusOverlay(
        transport="openai_chat",
        extra_env_vars=("GLM_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY"),
        base_url_env_var="GLM_BASE_URL",
    ),
    "kimi-for-coding": DaedalusOverlay(
        transport="openai_chat",
        base_url_env_var="KIMI_BASE_URL",
    ),
    "minimax": DaedalusOverlay(
        transport="openai_chat",
        base_url_env_var="MINIMAX_BASE_URL",
    ),
    "minimax-cn": DaedalusOverlay(
        transport="openai_chat",
        base_url_env_var="MINIMAX_CN_BASE_URL",
    ),
    "deepseek": DaedalusOverlay(
        transport="openai_chat",
        base_url_env_var="DEEPSEEK_BASE_URL",
    ),
    "alibaba": DaedalusOverlay(
        transport="openai_chat",
        base_url_env_var="DASHSCOPE_BASE_URL",
    ),
    "vercel": DaedalusOverlay(
        transport="openai_chat",
        is_aggregator=True,
    ),
    "opencode": DaedalusOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="OPENCODE_ZEN_BASE_URL",
    ),
    "opencode-go": DaedalusOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="OPENCODE_GO_BASE_URL",
    ),
    "kilo": DaedalusOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="KILOCODE_BASE_URL",
    ),
    "huggingface": DaedalusOverlay(
        transport="openai_chat",
        is_aggregator=True,
        base_url_env_var="HF_BASE_URL",
    ),
}



@dataclass
class ProviderDef:
    """Complete provider definition — merged from all sources."""

    id: str
    name: str
    transport: str
    api_key_env_vars: Tuple[str, ...]
    base_url: str = ""
    base_url_env_var: str = ""
    is_aggregator: bool = False
    auth_type: str = "api_key"
    doc: str = ""
    source: str = ""

    @property
    def is_user_defined(self) -> bool:
        return self.source == "user-config"



ALIASES: Dict[str, str] = {
    "openai": "openrouter",

    "glm": "zai",
    "z-ai": "zai",
    "z.ai": "zai",
    "zhipu": "zai",

    "kimi": "kimi-for-coding",
    "kimi-coding": "kimi-for-coding",
    "moonshot": "kimi-for-coding",

    "minimax-china": "minimax-cn",
    "minimax_cn": "minimax-cn",

    "claude": "anthropic",
    "claude-code": "anthropic",

    "copilot": "github-copilot",
    "github": "github-copilot",
    "github-copilot-acp": "copilot-acp",

    "ai-gateway": "vercel",
    "aigateway": "vercel",
    "vercel-ai-gateway": "vercel",

    "opencode-zen": "opencode",
    "zen": "opencode",

    "go": "opencode-go",
    "opencode-go-sub": "opencode-go",

    "kilocode": "kilo",
    "kilo-code": "kilo",
    "kilo-gateway": "kilo",

    "deep-seek": "deepseek",

    "dashscope": "alibaba",
    "aliyun": "alibaba",
    "qwen": "alibaba",
    "alibaba-cloud": "alibaba",

    "hf": "huggingface",
    "hugging-face": "huggingface",
    "huggingface-hub": "huggingface",

    "lmstudio": "lmstudio",
    "lm-studio": "lmstudio",
    "lm_studio": "lmstudio",
    "ollama": "ollama-cloud",
    "vllm": "local",
    "llamacpp": "local",
    "llama.cpp": "local",
    "llama-cpp": "local",
}



_LABEL_OVERRIDES: Dict[str, str] = {
    "nous": "Nous Portal",
    "openai-codex": "OpenAI Codex",
    "copilot-acp": "GitHub Copilot ACP",
    "local": "Local endpoint",
}



TRANSPORT_TO_API_MODE: Dict[str, str] = {
    "openai_chat": "chat_completions",
    "anthropic_messages": "anthropic_messages",
    "codex_responses": "codex_responses",
}



def normalize_provider(name: str) -> str:
    """Resolve aliases and normalise casing to a canonical provider id.

    Returns the canonical id string.  Does *not* validate that the id
    corresponds to a known provider.
    """
    key = name.strip().lower()
    return ALIASES.get(key, key)


def get_overlay(provider_id: str) -> Optional[DaedalusOverlay]:
    """Get Daedalus overlay for a provider, if one exists."""
    canonical = normalize_provider(provider_id)
    return DAEDALUS_OVERLAYS.get(canonical)


def get_provider(name: str) -> Optional[ProviderDef]:
    """Look up a provider by id or alias, merging all data sources.

    Resolution order:
      1. Daedalus overlays (for providers not in models.dev: nous, openai-codex, etc.)
      2. models.dev catalog + Daedalus overlay
      3. User-defined providers from config (TODO: Phase 4)

    Returns a fully-resolved ProviderDef or None.
    """
    canonical = normalize_provider(name)

    try:
        from agent.models_dev import get_provider_info as _mdev_provider
        mdev_info = _mdev_provider(canonical)
    except Exception:
        mdev_info = None

    overlay = DAEDALUS_OVERLAYS.get(canonical)

    if mdev_info is not None:
        transport = overlay.transport if overlay else "openai_chat"
        is_agg = overlay.is_aggregator if overlay else False
        auth = overlay.auth_type if overlay else "api_key"
        base_url_env = overlay.base_url_env_var if overlay else ""
        base_url_override = overlay.base_url_override if overlay else ""

        env_vars = list(mdev_info.env)
        if overlay and overlay.extra_env_vars:
            for ev in overlay.extra_env_vars:
                if ev not in env_vars:
                    env_vars.append(ev)

        return ProviderDef(
            id=canonical,
            name=mdev_info.name,
            transport=transport,
            api_key_env_vars=tuple(env_vars),
            base_url=base_url_override or mdev_info.api,
            base_url_env_var=base_url_env,
            is_aggregator=is_agg,
            auth_type=auth,
            doc=mdev_info.doc,
            source="models.dev",
        )

    if overlay is not None:
        return ProviderDef(
            id=canonical,
            name=_LABEL_OVERRIDES.get(canonical, canonical),
            transport=overlay.transport,
            api_key_env_vars=overlay.extra_env_vars,
            base_url=overlay.base_url_override,
            base_url_env_var=overlay.base_url_env_var,
            is_aggregator=overlay.is_aggregator,
            auth_type=overlay.auth_type,
            source="daedalus",
        )

    return None


def get_label(provider_id: str) -> str:
    """Get a human-readable display name for a provider."""
    canonical = normalize_provider(provider_id)

    if canonical in _LABEL_OVERRIDES:
        return _LABEL_OVERRIDES[canonical]

    pdef = get_provider(canonical)
    if pdef:
        return pdef.name

    return canonical


LABELS: Dict[str, str] = {
    "openrouter": "OpenRouter",
    "nous": "Nous Portal",
    "openai-codex": "OpenAI Codex",
    "copilot-acp": "GitHub Copilot ACP",
    "github-copilot": "GitHub Copilot",
    "anthropic": "Anthropic",
    "zai": "Z.AI / GLM",
    "kimi-for-coding": "Kimi / Moonshot",
    "minimax": "MiniMax",
    "minimax-cn": "MiniMax (China)",
    "deepseek": "DeepSeek",
    "alibaba": "Alibaba Cloud (DashScope)",
    "vercel": "Vercel AI Gateway",
    "opencode": "OpenCode Zen",
    "opencode-go": "OpenCode Go",
    "kilo": "Kilo Gateway",
    "huggingface": "Hugging Face",
    "local": "Local endpoint",
    "custom": "Custom endpoint",
    "ai-gateway": "Vercel AI Gateway",
    "kilocode": "Kilo Gateway",
    "copilot": "GitHub Copilot",
    "kimi-coding": "Kimi / Moonshot",
    "opencode-zen": "OpenCode Zen",
}


def is_aggregator(provider: str) -> bool:
    """Return True when the provider is a multi-model aggregator."""
    pdef = get_provider(provider)
    return pdef.is_aggregator if pdef else False


def determine_api_mode(provider: str, base_url: str = "") -> str:
    """Determine the API mode (wire protocol) for a provider/endpoint.

    Resolution order:
      1. Known provider → transport → TRANSPORT_TO_API_MODE.
      2. URL heuristics for unknown / custom providers.
      3. Default: 'chat_completions'.
    """
    pdef = get_provider(provider)
    if pdef is not None:
        return TRANSPORT_TO_API_MODE.get(pdef.transport, "chat_completions")

    if base_url:
        url_lower = base_url.rstrip("/").lower()
        if url_lower.endswith("/anthropic") or "api.anthropic.com" in url_lower:
            return "anthropic_messages"
        if "api.openai.com" in url_lower:
            return "codex_responses"

    return "chat_completions"



def resolve_user_provider(name: str, user_config: Dict[str, Any]) -> Optional[ProviderDef]:
    """Resolve a provider from the user's config.yaml ``providers:`` section.

    Args:
        name: Provider name as given by the user.
        user_config: The ``providers:`` dict from config.yaml.

    Returns:
        ProviderDef if found, else None.
    """
    if not user_config or not isinstance(user_config, dict):
        return None

    entry = user_config.get(name)
    if not isinstance(entry, dict):
        return None

    display_name = entry.get("name", "") or name
    api_url = entry.get("api", "") or entry.get("url", "") or entry.get("base_url", "") or ""
    key_env = entry.get("key_env", "") or ""
    transport = entry.get("transport", "openai_chat") or "openai_chat"

    env_vars: List[str] = []
    if key_env:
        env_vars.append(key_env)

    return ProviderDef(
        id=name,
        name=display_name,
        transport=transport,
        api_key_env_vars=tuple(env_vars),
        base_url=api_url,
        is_aggregator=False,
        auth_type="api_key",
        source="user-config",
    )


def resolve_provider_full(
    name: str,
    user_providers: Optional[Dict[str, Any]] = None,
) -> Optional[ProviderDef]:
    """Full resolution chain: built-in → models.dev → user config.

    This is the main entry point for --provider flag resolution.

    Args:
        name: Provider name or alias.
        user_providers: The ``providers:`` dict from config.yaml (optional).

    Returns:
        ProviderDef if found, else None.
    """
    canonical = normalize_provider(name)

    pdef = get_provider(canonical)
    if pdef is not None:
        return pdef

    if user_providers:
        user_pdef = resolve_user_provider(canonical, user_providers)
        if user_pdef is not None:
            return user_pdef
        user_pdef = resolve_user_provider(name.strip().lower(), user_providers)
        if user_pdef is not None:
            return user_pdef

    try:
        from agent.models_dev import get_provider_info as _mdev_provider
        mdev_info = _mdev_provider(canonical)
        if mdev_info is not None:
            return ProviderDef(
                id=canonical,
                name=mdev_info.name,
                transport="openai_chat",
                api_key_env_vars=mdev_info.env,
                base_url=mdev_info.api,
                source="models.dev",
            )
    except Exception:
        pass

    return None
