# Legitimate Refs Cheatsheet

When doing a full rebrand, these references SHOULD NOT be rewritten. Either
they refer to external libraries, they document the rename history itself, or
they reflect local filesystem paths that the operator hasn't renamed.

## External libraries — KEEP unchanged

These are third-party dependencies that happen to share namespace with the
old project name. Renaming them breaks the dependency.

| Old project | External lib to KEEP |
|---|---|
| jrwl-messenger → iris-messenger | `jackrabbitdlm`, `JackrabbitDLM`, `docker.io/jackrabbitdlm/...` |
| any-old → any-new | check: docker images, pip packages, npm packages, lib names |

How to identify them in the wild:
- `docker.io/<lib-name>/<lib-name>:tag` — Docker Hub official library images
- `pip install <lib-name>` — Python package
- `npm install <lib-name>` — JS package
- `<lib-name>.so` or `<lib-name>.dylib` — system library

## Migration notes — KEEP unchanged (intentionally)

These document the rename history for future readers. Removing them creates
"why was this renamed?" questions with no answer.

```markdown
# Examples of KEEP-as-is migration notes:

# In README.md "## What is X?" section:
X was previously named "Y" (Z). The rebrand happened 2026-06-20 along
with the migration to W.

# In INSTALL.md "## What this is NOT yet" section:
**Source-level federation with pre-X nodes:** BREAKING — HKDF info
strings (`y-x3dh-v1` → `x-x3dh-v1`) and dlm_identity (`y` → `x`)
renamed. Old clients cannot federate with new ones. This is
intentional for the rebrand.

# In INSTALL.md "## Update" section:
cd ~/<src-dir>
git pull
bash install.sh
# Clone URL points to new repo: git@github.com:USER/NEW-NAME.git

# In source code, banner for protocol changelog:
# HKDF info strings renamed 2026-06-20 (jrwl-* → iris-*). Old nodes
# cannot federate until they upgrade.
```

## Dev paths in `*.service` files — KEEP unchanged if local dir matches

The `iris-messenger.service` (or equivalent) has:
```
WorkingDirectory=/home/alca/projects/jrwl-messenger
ExecStart=/home/alca/projects/jrwl-messenger/iris-messenger.bin --port 9091
```

These reference the LOCAL filesystem path, which is set up by the operator.
If they renamed the local dir to `iris-messenger` too, update these. If not,
LEAVE them — the path must match the actual directory.

**How to check:** Does `/home/alca/projects/<old-name>` exist? If yes, the
operator hasn't renamed the local dir; leave the service paths alone. If no,
they've renamed it; update the paths.

## Cross-reference annotations — KEEP unchanged

These help future readers understand context:

```markdown
# "(unchanged from X — protocol surface is identical, only the brand name changed)"
# "(unchanged — WebSocket is on port Y, same message types as X)"
```

They're not branding the project; they're explaining "this section is
verbatim from before; only the brand name differs."

## Cryptographic identifiers — UPDATE (but document as BREAKING)

These are protocol-level identifiers and renaming them BREAKS federation
with existing clients/servers. Update them, but note the break clearly in
the commit message + README "Known limitations" section.

| What | Example | Why it's breaking |
|---|---|---|
| HKDF info strings | `jrwl-x3dh-v1` → `iris-x3dh-v1` | Old clients compute different keys |
| dlm_identity | `jrwl-messenger` → `iris-messenger` | Federation routing changes |
| Gateway-ID | `jrwl-messenger-gw-1` → `iris-messenger-gw-1` | Peer discovery |
| Sub-protocol names | `jrwl-handshake-v1` → `iris-handshake-v1` | Wire format breaks |

**Always document these in:**
1. The rebrand commit message (under BREAKING CHANGES)
2. README "What this is NOT yet" section
3. INSTALL.md migration notes
4. Code comments near the changed strings

## Migration tags in source code — KEEP unchanged

Sometimes source code has labels like:

```python
# Iris was previously "jrwl-messenger" (2026-06-20 rename). The HKDF
# info strings above were renamed; old federated nodes need to upgrade.
HKDF_INFO_X3DH = b"iris-x3dh-v1"  # was b"jrwl-x3dh-v1"
```

The "was b'jrwl-x3dh-v1'" annotation is intentional documentation. KEEP.

## Specific keep-vs-rewrite decision table

| Reference type | Action | Rationale |
|---|---|---|
| External lib (jackrabbitdlm, etc.) | KEEP | Third-party dep |
| Migration note in README/INSTALL | KEEP | Documents history |
| HKDF info string | UPDATE | Protocol identifier |
| Container name (iris-gateway) | UPDATE | Project brand |
| Data dir (~/iris/) | UPDATE | Project brand |
| Service name (iris-messenger.service) | UPDATE | Project brand |
| Display string ("Iris Messenger Gateway") | UPDATE | Project brand |
| Dev path in `*.service` file | CONDITIONAL | Matches local dir |
| ASCII art / banner with old brand | UPDATE | Project brand |
| Cross-reference annotation | KEEP | Context for reader |
| Comment referencing old URL for clarity | KEEP | Sometimes necessary |

## Audit decisions (where to put old-name references)

When the rename leaves old-name references in audit reports or historical
docs, you have three choices:

1. **Move to archives/ with banner** (recommended) — preserves history,
   clearly marks as pre-rename
2. **Rewrite** — keeps current-state consistency but loses history
3. **Delete** — only if the doc is genuinely obsolete

For audits specifically: ALWAYS choose #1. Audits are time-stamped snapshots;
rewriting them is historical revisionism.

## Quick decision tree

```
Is this reference in an EXTERNAL library?
  YES → KEEP
  NO ↓

Is this reference in archives/ (already moved)?
  YES → KEEP (don't touch archives/)
  NO ↓

Is this a MIGRATION NOTE explaining the rename?
  YES → KEEP
  NO ↓

Is this a CRYPTOGRAPHIC IDENTIFIER (HKDF, dlm_id, etc.)?
  YES → UPDATE + document as BREAKING CHANGE
  NO ↓

Is this a CROSS-REFERENCE ANNOTATION ("unchanged from X")?
  YES → KEEP
  NO ↓

Is this a DEV PATH in a `*.service` file matching the local dir?
  YES → CONDITIONAL (check if local dir was renamed)
  NO → UPDATE (sed)
```
