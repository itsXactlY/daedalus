# Multi-Pass sed Strategy for Full Project Rebrand

Why multiple passes? Long prose manuals (1000+ lines, bilingual EN+DE) have
many variants of the brand name in different contexts. One regex pass misses
most of them. Multi-pass catches progressively broader patterns without
false positives.

## The 4 passes

### Pass 1: Specific long phrases (most specific first)

**Goal:** Catch compound phrases before they get fragmented by shorter matches.

Order matters: longest, most-specific phrases go FIRST. Otherwise `jrwl-messenger`
gets replaced before `jrwl-messenger pod` (which would leave "iris-messenger pod"
matching, but the order matters for documentation consistency).

```python
subs_pass1 = [
    # Long compound forms (longest first)
    ('OLD-NAME Messenger gateway', 'NEW-NAME Messenger gateway'),
    ('OLD-NAME Messenger Gateway', 'NEW-NAME Messenger Gateway'),
    ('OLD-NAME Messenger ecosystem', 'NEW-NAME Messenger ecosystem'),
    ('OLD-NAME Messenger — Signal-Grade Cryptography Layer', 'NEW-NAME Messenger — Signal-Grade Cryptography Layer'),
    ('OLD-NAME Messenger Gateway Configuration', 'NEW-NAME Messenger Gateway Configuration'),
    ('OLD-NAME Messenger — Configuration', 'NEW-NAME Messenger — Configuration'),
    ('OLD-NAME Messenger — Chat Export', 'NEW-NAME Messenger — Chat Export'),
    ('OLD-NAME Messenger built by', 'NEW-NAME Messenger built by'),
    ('OLD-NAME codebase', 'NEW-NAME codebase'),
    # Section-header patterns
    ('# OLD-NAME Messenger', '# NEW-NAME Messenger'),
    # Doc references (e.g., from MANUAL.md to docs/MANUAL_*.md)
    ('OLD-NAME Manual', 'NEW-NAME Manual'),
]
```

### Pass 2: Common patterns (paths, container names, env vars)

**Goal:** Catch the structured references — env vars, file paths, container
names, systemd unit names.

```python
subs_pass2 = [
    # Container / unit names (with hyphen)
    ('old-name-gateway', 'new-name-gateway'),
    ('old-name-proxy', 'new-name-proxy'),
    ('old-name-pod', 'new-name-pod'),
    ('old-name-dlm-container', 'new-name-dlm-container'),
    # Host paths
    ('~/.old-name/', '~/.new-name/'),
    ('%h/.old-name/', '%h/.new-name/'),
    # Quadlet paths in docs
    ('quadlet/old-name.gateway.container', 'quadlet/new-name-gateway.container'),
    ('quadlet/old-name.proxy.container', 'quadlet/new-name-proxy.container'),
    ('quadlet/old-name.dlm.container', 'quadlet/new-name-dlm.container'),
    ('quadlet/old-name.pod', 'quadlet/new-name.pod'),
    # Env var prefix
    ('OLD_NAME_', 'NEW_NAME_'),
    # systemd service names
    ('old-name.service', 'new-name.service'),
    ('old-name-pod', 'new-name-pod'),
    # HKDF info strings (BREAKING — see skill pitfall #7)
    ("'old-name-x3dh-v1'", "'new-name-x3dh-v1'"),
    ("'old-name-rk-v1'", "'new-name-rk-v1'"),
    # docker-compose volume names
    ('old-name-data', 'new-name-data'),
    # Docker image names (when in dev config)
    ('localhost/old-name', 'localhost/new-name'),
    # Git remote clone URL (only in docs/INSTALL — actual remote set in step 1)
    ('OLD-NAME.git', 'NEW-NAME.git'),
]
```

### Pass 3: Catch-all prefixes (with exclusion list)

**Goal:** Catch anything missed by specific patterns.

**CRITICAL:** Some strings look like the brand but aren't. Always exclude
external libraries BEFORE running catch-all subs.

```python
# Build an exclusion list FIRST (what NOT to touch)
EXCLUDE_PATTERNS = [
    'external-lib-name',   # e.g., jackrabbitdlm, JackrabbitDLM
    'jackrabbit-',         # if the rename is FROM jackrabbit and TO iris
                           # then jackrabbit- needs separate handling
    'External-Lib',        # external dependencies
    'kebab-cased-external', # etc
]

# Only then run catch-all prefixes
subs_pass3 = [
    ('old-name-', 'new-name-'),  # catch-all hyphenated
    ('old_name_', 'new_name_'),  # catch-all underscored
]
```

If the brand name contains the external lib's name (e.g. rename FROM
`jackrabbit-messenger` TO `iris-messenger`), you need surgical handling
for the lib refs:
- Don't blanket-replace `jackrabbit-`
- Replace only in specific contexts (container names, paths)
- Keep `jackrabbitdlm` and `JackrabbitDLM` untouched

### Pass 4: Word-boundary bare brand names (final pass)

**Goal:** Catch bare uses of the brand in regular prose.

```python
import re

subs_pass4 = [
    # Word-boundary bare references
    (r'\bOLD-NAME\b', 'NEW-NAME'),
    (r'\bOldName\b', 'NewName'),
    # Common typos
    (r'\bOLD_NAMES\b', "NEW-NAME's"),
]
```

`\b` matches word boundaries so you don't accidentally rewrite `OLD-NAMED`
or `OLD-NAMER` (if such words exist).

## Verification between passes

After each pass, run the inventory grep to see what's left:

```bash
grep -rnE 'OLD-NAME|old-name|OldName|OLD-NAME' \
    --include='*.{py,md,yaml,yml,json,html,sh,toml,txt,cfg,service}' \
    --include='Makefile' --include='Containerfile' \
    . 2>/dev/null \
    | grep -v __pycache__ | grep -v gateway.build/ | grep -v archives/ \
    | grep -v 'external-lib'
```

**Expected progression:**
- After Pass 1: 60-70% of lines removed
- After Pass 2: 80-90% removed
- After Pass 3: 95%+ removed
- After Pass 4: only legitimate-ref lines remain (5-10)

If after Pass 4 you still have 20+ lines, you missed a pattern. Common misses:
- Title case variants (`OldName` vs `OLD-NAME`)
- Hyphenated compound words you didn't anticipate
- Section header patterns (`## OLD-NAME section`)
- Display strings in scripts with different quote styles

Add one more targeted pass for each pattern you discover.

## Real example (iris-messenger, 2026-06-20)

```text
After grep inventory:    168 lines with old-name refs
After Pass 1 (long forms): 113 substitutions, ~30 lines remain
After Pass 2 (paths/units): 202 substitutions, ~10 lines remain
After Pass 4 (bare words): 94 substitutions, 5 lines remain
After surgical fixes:   9 lines remain (all legitimate)
```

Final: 5 lines that are LEGITIMATE (intentionally kept):
- Migration notes in README/INSTALL (explain rename history)
- Dev path in `*.service` matching local dir name
- `jackrabbitdlm` external lib refs (excluded by filter)
