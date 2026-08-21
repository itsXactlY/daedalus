---
name: pulse-add-hard-reach-source
description: Add a hard-reach source (browser automation, CAPTCHA) to PULSE — X/Twitter pattern
tags: [pulse, camoufox, browser-automation, scraping]
last_updated: 2026-04-28
---

# PULSE Hard-Reach Source Integration

## When to Use

When adding a new source to PULSE that requires browser automation, CAPTCHA solving, or non-standard API access (e.g. X/Twitter, Instagram, LinkedIn, paywalled sites).

## The Pattern

### 1. Create the source module

Location: `/home/alca/projects/pulse/scripts/lib/<name>.py`

Required elements:
```python
from __future__ import annotations
import logging
from typing import List, Dict, Any

# Graceful dependency check (don't crash if library unavailable)
try:
    from camoufox.sync_api import Camoufox
    _HAS_CAMOUFOX = True
except ImportError:
    _HAS_CAMOUFOX = False

from . import log as _log
from .relevance import token_overlap_relevance  # NOTE: spelled 'relevance', NOT 'relvance'

def _source_log(msg: str):
    _log.source_log("SourceName", msg)

DEPTH_CONFIG = {"quick": 1, "default": 3, "deep": 5}

def search(topic: str, from_date: str = "", to_date: str = "", depth: str = "default") -> List[Dict[str, Any]]:
    if not _HAS_CAMOUFOX:
        return _fallback_method(topic)  # Always have a fallback
    # ... Camoufox logic
```

### 2. Register in pipeline.py

Two patches required:

**Import patch** — add to the `from . import (...)` block:
```python
from . import (
    ...
    twitter_browser as _twitter_browser,
)
```

**SOURCE_MAP patch** — add to `SOURCE_MAP` dict:
```python
    "source_name": _twitter_browser,
```

### 3. Register in query_router.py

Three patches required:

**TYPE_SOURCES** — add `"source_name"` to these lists:
- `breaking_news` (high priority for Twitter)
- `sentiment_pulse` (high priority)
- `technical_comparison`
- `recommendation`
- `academic_deep`

**NOTE:** The file may have DUPLICATE blocks if multiple patches went wrong. Verify with:
```python
from lib.query_router import TYPE_SOURCES
for k, v in TYPE_SOURCES.items():
    print(f"{k}: twitter={'twitter' in v}")
```

**PROBE_SOURCES** — add to `_PROBE_SOURCES`:
```python
_PROBE_SOURCES = {
    "quick": [..., "source_name"],
    "default": [..., "source_name"],
    "deep": [..., "source_name"],
}
```

### Step 4: Fix pipeline blocking check (CRITICAL)

`available_sources()` in `config.py` acts as an allowlist. If your source is NOT in the available list, PULSE raises "No sources available" even when the user explicitly requested it.

Fix in `pipeline.py` around line 247 — replace:
```python
if requested_sources:
    available = [s for s in available if s in requested_sources]
if not available:
    raise RuntimeError("No sources available. Check your API keys.")
```

With:
```python
if requested_sources:
    # User explicitly requested sources — use those even if not in available list
    to_use = [s for s in requested_sources if s in SOURCE_MAP]
    if not to_use:
        raise RuntimeError(f"None of the requested sources are valid: {requested_sources}")
else:
    to_use = available
    if not to_use:
        raise RuntimeError("No sources available. Check your API keys.")
```

### Step 5: Verify all checks

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from lib.query_router import TYPE_SOURCES, _PROBE_SOURCES
from lib.pipeline import SOURCE_MAP

checks = {
    'SOURCE_MAP': 'source_name' in SOURCE_MAP,
    'breaking_news': 'source_name' in TYPE_SOURCES.get('breaking_news', []),
    'sentiment_pulse': 'source_name' in TYPE_SOURCES.get('sentiment_pulse', []),
    'technical_comparison': 'source_name' in TYPE_SOURCES.get('technical_comparison', []),
    'recommendation': 'source_name' in TYPE_SOURCES.get('recommendation', []),
    'academic_deep': 'source_name' in TYPE_SOURCES.get('academic_deep', []),
    'quick_probe': 'source_name' in _PROBE_SOURCES.get('quick', []),
    'default_probe': 'source_name' in _PROBE_SOURCES.get('default', []),
    'deep_probe': 'source_name' in _PROBE_SOURCES.get('deep', []),
}
for k, v in checks.items():
    print(f'  [{\"PASS\" if v else \"FAIL\"}] {k}')
"
```

### 5. Camoufox usage pattern (from Haus-Suche)

```python
from camoufox.sync_api import Camoufox

with Camoufox(headless=True, humanize=0.5) as browser:
    page = browser.new_page()
    page.goto(url, timeout=30000)
    time.sleep(2)
    # Accept cookies if present
    try:
        btn = page.locator('button:has-text("Alle akzeptieren"), button:has-text("Accept all")')
        if btn.first.is_visible(timeout=3000):
            btn.first.click()
            time.sleep(1)
    except:
        pass
    # DOM extraction via JS
    data = page.evaluate("""() => {
        const items = [];
        document.querySelectorAll('selector').forEach(el => {
            items.push({ title: el.querySelector('h3').innerText });
        });
        return items;
    }""")
```

**NOTE:** Camoufox lives in the container overlay FS at `~/.local/share/containers/storage/overlay/...`, NOT in pip. It's available in the hermes-agent environment but not in the PULSE venv. Use `_HAS_CAMOUFOX` flag.

### 6. X/Twitter specific notes

- Twitter blocks most headless browsers without Camoufox-level spoofing
- syndication.twitter.com only works for known profile handles, NOT topic search
- Date filtering requires login (not available publicly)
- Build tweet URLs from `https://x.com/{handle}/status/{id}`
- DOM selectors: `article[data-testid="tweet"]`, `[data-testid="tweetText"]`, `[data-testid="User-Name"]`
- Cloudflare/CAPTCHA detection: look for `#challenge-form`, `.cf-error`, `checking your browser`

### Files Modified

- `.../pulse/scripts/lib/twitter_browser.py` (NEW — 390 lines, Camoufox-based Twitter source)
- `.../pulse/scripts/lib/pipeline.py` (+1 import, +1 SOURCE_MAP entry, +blocking-bug fix)
- `.../pulse/scripts/lib/query_router.py` (+twitter in 5 TYPE_SOURCES lists + 3 _PROBE_SOURCES lists)

## Common Pitfalls

1. **Import typo**: `from .relvance` → CORRECT: `from .relevance`
2. **Duplicate blocks**: Patching same string twice creates duplicate lists. Verify with grep.
3. **Camoufox not in pip**: Lives in container overlay. Use try/except import with `_HAS_CAMOUFOX` flag.
4. **Thread safety**: Use `threading.Lock()` + dict to cache one browser per thread.

## Verification

```bash
cd /home/alca/projects/pulse && python3 scripts/pulse.py --diagnose 2>&1 | grep -i source
```
