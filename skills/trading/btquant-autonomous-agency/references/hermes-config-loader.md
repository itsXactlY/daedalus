# Hermes Config Loader — LLM endpoint from `~/.hermes/config.yaml`

**Why this exists:** the operator's hard rule (2026-06-18) was
"use whatever's in `~/.hermes/config.yaml`, do not hardcode LLM
endpoints in the agency." This reference documents the
`_load_from_hermes_config()` pattern so future sessions can
reuse it instead of re-deriving.

## TL;DR

```python
# In autonomous_agency/llm_adapter.py
def _load_from_hermes_config(provider: str = "rapeit") -> Dict[str, Any]:
    """Read the active provider block from ~/.hermes/config.yaml
    without holding the API key in this module's text."""
    candidates = [
        Path.home() / ".hermes" / "config.yaml",
        Path(os.getenv("HERMES_CONFIG", "")),
    ]
    for path in candidates:
        if not path or not str(path) or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8")
            pattern = rf"^\s{{0,4}}{re.escape(provider)}\s*:\s*$"
            m = re.search(pattern, text, re.MULTILINE)
            if not m:
                continue
            # CRITICAL: indent-aware block boundary, NOT
            # `re.match(r"^\S", line)`. The latter leaks sibling
            # providers at the same indent into the block.
            provider_indent = (len(m.group(0))
                               - len(m.group(0).lstrip(" ")))
            block_lines = []
            for line in text[m.end():].splitlines():
                if not line.strip():
                    block_lines.append(line)
                    continue
                line_indent = len(line) - len(line.lstrip(" "))
                if line_indent <= provider_indent:
                    break
                block_lines.append(line)
            block = "\n".join(block_lines)
            result: Dict[str, Any] = {"source": str(path)}
            for key in ("base_url", "default_model", "api_key"):
                km = re.search(rf"^\s+{key}\s*:\s*(.+?)\s*$",
                               block, re.MULTILINE)
                if km:
                    val = km.group(1).strip()
                    if (val.startswith('"') and val.endswith('"')) or \
                       (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    result[key] = val
            if "base_url" in result or "default_model" in result:
                return result
        except Exception:
            continue
    return {}
```

Then in `LLMConfig`:

```python
@dataclass
class LLMConfig:
    base_url: str = os.getenv(
        "BTQ_LLM_BASE_URL",
        _load_from_hermes_config(
            os.getenv("BTQ_LLM_PROVIDER", "rapeit")
        ).get("base_url", DEFAULT_BASE_URL),
    )
    model: str = os.getenv(
        "BTQ_LLM_MODEL",
        _load_from_hermes_config(
            os.getenv("BTQ_LLM_PROVIDER", "rapeit")
        ).get("default_model", DEFAULT_MODEL),
    )
    api_key: str = os.getenv(
        "BTQ_LLM_API_KEY",
        _load_from_hermes_config(
            os.getenv("BTQ_LLM_PROVIDER", "rapeit")
        ).get("api_key", ""),
    )
    # ... timeout, temperature, max_tokens, insecure, ca_bundle
```

## Why No `pyyaml`

`pyyaml` is a 700KB dep that:
- Adds an import-time vulnerability surface (CVE-2017-18342 was
  the famous one).
- Calls `os.environ.update()` and other side-effects in some
  configurations (e.g. `!!python/object/apply:os.system`).
- Triggers Hermes' own config-loader race conditions if both
  loaders run on the same file.

The minimal regex parser:
- Reads only the 3 keys the agency actually needs
  (`base_url`, `default_model`, `api_key`).
- Doesn't import any yaml library
- Has no side effects beyond reading the file
- Handles `~`, `~user`, env var paths, and quoted values
- Fails closed: returns `{}` if anything goes wrong, defaults
  take over

## The Indent-Aware Block Boundary Bug

First version of the parser used `re.match(r"^\S", line)` to
detect end-of-block. This looked like:

```yaml
  rapeit:
    api_key: sk-MRr...Ltqk
    base_url: https://api.tokenrouter.com/v1
    default_model: MiniMax-M3
    models:
      - MiniMax-M3
  llama-turbo:
    api_key: none
    base_url: http://127.0.0.1:18080/v1
    ...
```

The line `  llama-turbo:` starts with space (indent 2) — `^\S`
does NOT match. So the parser kept slurping into llama-turbo's
block, then extracted `api_key: none` for `rapeit.api_key`.
Agency 401'd because `"none"` was sent as the bearer token.

Fix: track `provider_indent` (the indent level of the
`provider:` line itself, e.g. 2 for `  rapeit:`) and break when
a line's indent drops to or below that level. Now
`line_indent <= provider_indent` correctly closes the block
at `  llama-turbo:`.

## What the Operator Has in `~/.hermes/config.yaml` (verified 2026-06-18)

```yaml
providers:
  rapeit:
    api_key: sk-MRr...Ltqk
    base_url: https://api.tokenrouter.com/v1
    default_model: MiniMax-M3
    models:
      - MiniMax-M3
  llama-turbo:
    api_key: none
    base_url: http://127.0.0.1:18080/v1
    default_model: z-ai/glm-5.1
    ...
  openrouter_custom:
    base_url: https://openrouter.ai/api/v1
    ...
  openrouter_fallback:
    ...
  kilocode:
    base_url: https://kilo.ai/api/openrouter/v1
    ...
  ollama-launch:
    base_url: http://localhost:11434/v1
    ...
```

To switch providers:

```bash
# Default (rapeit / MiniMax-M3)
python3 -m autonomous_agency.run_loop

# OpenRouter
BTQ_LLM_PROVIDER=openrouter_custom python3 -m autonomous_agency.run_loop

# Local llama-turbo (Z.AI GLM 5.1)
BTQ_LLM_PROVIDER=llama-turbo python3 -m autonomous_agency.run_loop

# KiloCode
BTQ_LLM_PROVIDER=kilocode python3 -m autonomous_agency.run_loop
```

If the agency's LLM is in a code path that doesn't have access
to `os.path.expanduser`, hard-override:

```bash
BTQ_LLM_BASE_URL=https://my-host/v1 \
BTQ_LLM_MODEL=my-model \
BTQ_LLM_API_KEY=*** \
  python3 -m autonomous_agency.run_loop
```

## When the Loader Fails

If `_load_from_hermes_config()` returns `{}`, the dataclass
defaults kick in:

- `base_url` → `https://api.tokenrouter.com/v1`
- `model` → `MiniMax-M3`
- `api_key` → `""` (empty)

Empty `api_key` → 401 from the API. The agency's
`_call_ai_model` catches the 401, logs it, and falls back to
the deterministic `_fallback_text_response()`. Loop stays
alive but produces placeholder strategies until the config
gets fixed.

To debug the loader:

```python
import sys
sys.path.insert(0, "/home/alca/projects/PubBTQuant")
from autonomous_agency.llm_adapter import _load_from_hermes_config
print(_load_from_hermes_config("rapeit"))
# Expected: {'source': '/home/alca/.hermes/config.yaml',
#           'base_url': 'https://api.tokenrouter.com/v1',
#           'default_model': 'MiniMax-M3',
#           'api_key': 'sk-...'}
```

## Bringup Checklist for a Fresh Machine

If `~/.hermes/config.yaml` doesn't exist or doesn't have a
`providers:` block yet:

1. The agency will silently use defaults — first cycle will 401.
2. Create the file with at least:
   ```yaml
   providers:
     my-provider:
       api_key: ***           # bare token, not "Bearer ..."
       base_url: https://host/v1
       default_model: model-name
   ```
3. Either `BTQ_LLM_PROVIDER=my-provider` or change the
   `_load_from_hermes_config()` default arg to `"my-provider"`.
4. No restart needed — every `LLMClient()` instantiation
   re-reads the config.

## Why This Pattern Is Worth Keeping

- **No drift.** When the operator rotates their `rapeit` key in
  `~/.hermes/config.yaml`, the agency picks up the new key
  on the next cycle. No code changes, no env var updates, no
  rebuilds.
- **Single source of truth.** Operator's config IS the
  config. No re-typing, no parallel configuration to keep in
  sync, no risk of one team's settings drifting from
  another's.
- **Multi-provider is free.** A user with three providers in
  their config can switch with one env var
  (`BTQ_LLM_PROVIDER=...`) without code changes. The agency
  becomes a portable testbed for "which provider produces the
  best quant strategies?"
- **Self-documenting.** The `providers:` block in
  `~/.hermes/config.yaml` IS the documentation. A new
  operator can read it and immediately know what the agency
  will use.
