---
name: full-project-rebrand
description: |
  Comprehensively rename a project across code, docs, git remote, audits,
  and operational artifacts — without breaking deployment or losing
  historical context. Trigger when the operator says "complete rebrand",
  "rename project", "rebrand everything", or after a GitHub repo rename
  ("hab die repo umbenannt"). Covers the full scope: git remote update,
  multi-pass sed strategy for code + prose, audit-preservation protocol,
  legitimate-ref exceptions (external libs, migration notes, dev paths),
  and post-rebrand cleanup that doesn't touch production.
  Verified on iris-messenger rename (2026-06-20): 440 substitutions across
  38 files, 12 audit docs archived with banner, 3 commits, production
  UNTOUCHED throughout.
version: 1.0.0
tags: [rebrand, rename, sed, migration, git-remote, audit-preservation, alca-stack]
triggers:
  - "complete rebrand / rebrand everything"
  - "rename the project / rename repo"
  - "hab die repo umbenannt"
  - "migrate brand name"
  - "ALLES umbenennen"
metadata:
  hermes:
    category: software-development
---

# Full Project Rebrand

Rename a project comprehensively. Used after operator does GitHub-side rename
or decides the brand needs to change. The goal is: every reference to the
old name is replaced, but historical artifacts (audits, pre-rename docs)
are preserved with clear context markers.

This is **not** a find-and-replace job. It's a multi-pass sed strategy with
explicit decisions about what to KEEP, what to MOVE to archives, and what
to UPDATE.

## WHEN TO USE

- Operator says "complete rebrand", "rename everything", "ALLES umbenennen"
- After a GitHub repo rename (`hab die repo umbenannt`) — git remote points
  to the new URL, local repo still has old name in files
- Brand name appears in: code, env vars, file paths, docs, audit reports,
  manifests, runtime configs, install scripts, CI configs, UI strings
- The project has been around long enough that old-name references
  accumulated across multiple commits and docs

Verified on **iris-messenger** (rename from jrwl-messenger, 2026-06-20):

| Layer | Files touched | Subs |
|---|---|---|
| Source code (.py) | 14 | ~60 |
| Source code (.yaml, .service, .sh) | 4 | ~10 |
| Docs (.md) | 6 | ~330 |
| UI (ui.html) | 1 | ~10 |
| Audit/historical | 12 | moved to archives/ with banner |
| Configs (.gitignore, .github/) | 3 | 5 |
| **Total** | **40 files** | **~440 substitutions** |

## WORKFLOW (9 steps, in order)

### Step 1: Update git remote FIRST

Before any other rebrand work, point the local repo at the new remote. This
prevents accidental `git push` to the old URL during the rebrand.

```bash
git remote -v                       # confirm current
git remote set-url origin git@github.com:USER/NEW-NAME.git
git remote -v                       # verify
git ls-remote origin HEAD           # confirm reachable, returns SHA
```

The `ls-remote` confirms the new repo exists on GitHub. If it errors, STOP —
the operator may have renamed locally but not on GitHub (or vice versa).

### Step 2: Inventory scope

Find every reference to the old name:

```bash
# All refs in active files (exclude archives/, build/, .git/)
grep -rnE 'OLD_NAME|old-name|OldName|OLD-NAME' \
    --include='*.{py,md,yaml,yml,json,html,sh,toml,txt,cfg,service}' \
    --include='Makefile' --include='Containerfile' --include='Dockerfile' \
    --include='Caddyfile' --include='.gitignore' \
    . 2>/dev/null \
    | grep -v __pycache__ | grep -v gateway.build/ | grep -v archives/
```

Categorize by type:
- Display strings ("JRWL Messenger Gateway v2")
- Env var names (`JRWL_DLM_HOST`)
- File paths (`~/.jrwl-messenger/`, `/home/alca/projects/jrwl-messenger/`)
- Container image tags (`localhost/jackrabbit-gateway:latest`)
- Service names (`jackrabbit-gateway.container`)
- Brand identifiers in HTML/UI (`<h1>🐇 JRWL</h1>`)
- Documentation prose (long-form sentences using the brand name)
- Audit/historical reports (pre-rename snapshots)

### Step 3: Decide what to KEEP (legitimate exceptions)

Before any sed pass, mark these as **do-not-touch**:

| Category | Example | Why keep |
|---|---|---|
| External libraries | `jackrabbitdlm/jackrabbitdlm:latest`, `JackrabbitDLM` | Not the project brand — third-party dependency |
| Dev paths matching local dir | `/home/alca/projects/jrwl-messenger/` in `*.service` | Operator may have local dir named differently than GitHub repo |
| Migration notes in README/INSTALL | "This project was renamed from X to Y" | Future readers need the history |
| `(unchanged from X — ...)` annotations | "(unchanged from JRWL — protocol surface is identical)" | Cross-reference context |
| `archives/` content | Old audit reports | Historical accuracy |

Document these BEFORE sedding so you don't accidentally rewrite them.

### Step 4: Move audit/historical to archives/ WITH BANNER

Don't rewrite old audits. MOVE them with a clear banner explaining the
rename context. Future readers need to know these are pre-rename snapshots,
not current.

```bash
mkdir -p archives

# Pattern: any AUDIT_*, CODE_QUALITY_*, COVERAGE_*, THREADING_*, etc.
for f in AUDIT_*.md CODE_QUALITY_*.md COVERAGE_REPORT.md \
         THREADING_*.md ERROR_HANDLING_*.md \
         POST_FIX_STATE.md REVIEWER_REPORT.md SECURITY_AUDIT.md; do
    [ -f "$f" ] || continue
    # Add banner at top (idempotent — check first)
    if ! head -1 "$f" | grep -q 'ARCHIVED'; then
        cat > /tmp/banner.md <<'EOF'
# ⚠️ ARCHIVED AUDIT — pre-rename

> **This document is preserved as historical record.**
> It was written against the **OLD-NAME** codebase (pre-RENAME-DATE).
> The project was renamed to **NEW-NAME** on RENAME-DATE along with a
> migration to [whatever else changed at rename time].
> Source code referenced in this audit may use the old name in paths and
> string literals. The technical findings are still valid for the NEW-NAME
> codebase that superseded it.
>
> See: `git log RENAME-COMMIT` for the rename commit.

---

EOF
        cat /tmp/banner.md "$f" > /tmp/tempfile && mv /tmp/tempfile "$f"
    fi
    mv "$f" archives/
done
```

Git will detect these as RENAMES (not delete + add) if the content is similar,
preserving history.

### Step 5: Multi-pass sed (4 passes, most specific → broadest)

**Never try to do this in one pass.** Long prose files (manuals with 1000+
lines, bilingual docs) need progressive refinement.

```python
# Pass 1: Specific long phrases (most → least specific)
subs_pass1 = [
    ('OLD_NAME Messenger gateway', 'NEW_NAME Messenger gateway'),
    ('OLD_NAME Messenger Gateway', 'NEW_NAME Messenger Gateway'),
    ('OLD_NAME Messenger — Configuration', 'NEW_NAME Messenger — Configuration'),
    ('OLD_NAME Messenger — Signal-Grade Cryptography Layer', '...'),
    # ... etc
]

# Pass 2: Common patterns (paths, container names, etc.)
subs_pass2 = [
    ('old-name-gateway', 'new-name-gateway'),     # container names
    ('old-name-pod', 'new-name-pod'),
    ('~/.old-name/', '~/.new-name/'),
    ('%h/.old-name/', '%h/.new-name/'),
    # ... etc
]

# Pass 3: Catch-all prefixes (but exclude external libs!)
subs_pass3 = [
    ('old-name-', 'new-name-'),     # catch-all for remaining hyphens
]

# Pass 4: Word-boundary bare brand names
import re
subs_pass4 = [
    (r'\bOLD_NAME\b', 'NEW_NAME'),  # \bJRWL\b → \bIris\b
    (r'\bOldName\b', 'NewName'),
]
```

**Critical:** Always exclude `external-lib-name` from any catch-all sed.
Use specific subs BEFORE the catch-all to avoid accidental rewrites.

After each pass, verify with grep:
```bash
grep -rnE 'OLD_NAME|old-name' --include='*.md' . | grep -v archives/ | head -10
```

When grep returns clean (only legitimate-ref lines), move to the next pass.

### Step 5.5: Deep-command-snippet pass (systemd, paths, search patterns)

The four multi-pass seds above catch most prose and surface-level references.
They **miss** the brand name in places where the prose context hides it:
shell command snippets, in-container paths, systemd unit names, backup
filename prefixes, and `grep`-pattern arguments. These show up in
long-form technical docs (MANUAL.md, MANUAL_ADMIN.md, MANUAL_TROUBLESHOOTING.md,
README.md) inside ```bash ... ``` code blocks.

**The pattern is:** the prose and surface grep are clean, but a 4-line
command in a code block still says the old name because the brand appears
in a context the multi-pass sed didn't match (e.g. embedded in a path or
unit-name suffix).

**Categories to grep for specifically after Step 5:**

```bash
# 1. Systemd unit-name suffixes (the .container unit has a -container suffix;
#    but the systemd USER unit has different naming — verify what name shows up
#    in `systemctl --user list-unit-files`)
grep -rnE 'old-name-(gateway|proxy|dlm|server|pod|service|client)\b' \
    --include='*.md' --include='*.sh' --include='*.service' . 2>/dev/null \
    | grep -v archives/ | head

# 2. In-container data paths (Containerfile VOLUME / bind-mount targets
#    differ from the host ~/.app-name/ convention)
grep -rnE '/(root|var|opt)/\.?old-name|/(root|var|opt)/old-name' \
    --include='*.md' . 2>/dev/null | grep -v archives/ | head

# 3. Backup filename prefixes (the install script's tar command uses
#    a date-stamped prefix; easy to miss)
grep -rnE 'var/backups/old-name|/backup/old-name|old-name-(YYYY|backup|backup-)' \
    --include='*.md' . 2>/dev/null | grep -v archives/ | head

# 4. Search/filter pattern arguments (the docs may have a
#    `journalctl -u old-name-pod` or `grep -r old-name` that the
#    prose-level sed missed)
grep -rnE '\b(grep|rg|ag|ack)\s+["'\'']?old-name["'\'']?|\bjournalctl.*old-name\b' \
    --include='*.md' . 2>/dev/null | grep -v archives/ | head

# 5. Sibling git/clone paths (e.g. /home/USER/old-name/ in install instructions
#    — the README's "git clone .../old-name.git" was caught, but a separate
#    "cd /home/USER/old-name" in INSTALL.md might have been missed)
grep -rnE '~?/[\w/]*old-name/' \
    --include='*.md' . 2>/dev/null | grep -v archives/ | head
```

**Verified on iris-messenger (2026-06-20):** the four multi-pass seds caught
~440 substitutions in 38 files. Step 5.5 caught an additional **89 stale
references across 2 files** in these exact categories:
- `iris-gateway-pod` → `iris-gateway` (16 hits in TROUBLESHOOTING systemd commands)
- `iris-proxy-pod` → `iris-proxy` (14 hits)
- `iris-dlm-pod` → `iris-dlm` (6 hits)
- `~/.iris-messenger/{identities,sender_keys,ratchet_sessions,backups}/` paths (22 hits)
- `~/.local/share/iris-messenger/backups/` (2 hits)
- `$HOME/.jackrabbit/{data,dlm}` and `.jackrabbit/caddy/data` (12 hits)
- `/var/backups/jrwl-` (4 hits)
- `grep jackrabbit` (4 hits in list-timers commands)
- `/root/.iris-messenger` (4 hits in hardening docs, actual Containerfile VOLUME is `/var/lib/iris`)

**Why this works:** the multi-pass sed in Step 5 was prose-level (`OLD_NAME` in
running text). The deep-command-snippet grep is **structural** — it looks for
the old name in the syntactic slots where a brand name appears in commands
(unit name, file path, backup prefix, search argument). These are
mutually-exclusive sets: Step 5 misses the slots, Step 5.5 misses the prose.

**Pitfall: skipping Step 5.5 because Step 5 grep returned "clean"** is
common. Step 5 verifies prose-level cleanliness. Step 5.5 verifies
command-level cleanliness. They check different things. **Both must pass.**

**After Step 5.5, do a final** `grep -rnE 'OLD_NAME|old-name|OldName'` with
no exclusions. Every remaining hit should be in `archives/` (historical
preservation), in a legitimate-ref list (external libs, migration notes),
or be a comment explaining "we used to call it X".

### Step 6: Surgical fixes (the leftovers)

After 4 sed passes, typically 5-10 lines remain that need manual fixes.
Common categories:

```bash
# Legitimate migration notes — leave
# (intentional — explains rename history to future readers)

# Actual bugs that sed missed — fix
# e.g., clone URL in INSTALL.md pointing to old GitHub URL:
sed -i 's|OLD-NAME.git|NEW-NAME.git|g' INSTALL.md

# Bare brand names in table cells — sed missed because of context
# e.g., "An end user who installed OLD_NAME on their device" in MANUAL.md
```

### Step 7: Commit sequence (3 commits, in order)

Rebrand is not one big commit. Split it for reviewability and atomicity:

```bash
git add -A
git commit -m "feat: NEW-NAME — [architectural changes, e.g. Nuitka --onefile migration]"
# → SHA1 (this is the "rename commit" referenced in archives/ banners)

git add -A
git commit -m "docs: INSTALL.md — TL;DR for fresh-system install"
# → SHA2 (only if you wrote a fresh-install guide)

git add -A
git commit -m "feat: complete NEW-NAME rebrand — code + docs + audits"
# → SHA3 (the bulk rebrand)
```

Order matters:
- Commit 1: code changes that depend on the new name (build, container, env vars)
- Commit 2: new install guide (TL;DR for fresh system)
- Commit 3: bulk rebrand (display strings, docs, audit moves)

This lets `git log SHA1..HEAD` show exactly what changed between the rename
and the docs update.

### Step 8: Cleanup without touching production

For "abfahrt" / final cleanup:

```bash
# 1. Git status: clean
git status --short   # should be empty

# 2. No test containers
podman ps -a | grep NEW-NAME   # should be empty

# 3. No project images
podman images | grep NEW-NAME  # should be empty

# 4. /tmp: remove build venvs, temp dirs from this session
ls /tmp/ | grep -i NEW-NAME   # identify
rm -rf /tmp/NEW-NAME-build-venv /tmp/onefile_* ...

# 5. Production UNTOUCHED
podman ps | grep -E 'mazemaker|pulse|atlas'  # should still be running
# DO NOT restart/stop/rebuild production services

# 6. Disk reclaim confirmation
df -h /tmp /home
```

The operator's strong preference: **"lass laufen"** = let production run.
NEVER touch `pulse`, `mazemaker`, `atlas`, `wonderland`, or other long-running
production containers during cleanup.

### Step 9: Verify + report

```bash
# Final check — only legitimate refs should remain
grep -rnE 'OLD_NAME|old-name|OldName' \
    --include='*.{py,md,yaml,yml,json,html,sh,toml,txt,cfg,service}' \
    --include='Makefile' --include='Containerfile' \
    . 2>/dev/null \
    | grep -v __pycache__ | grep -v gateway.build/ | grep -v archives/ \
    | grep -v 'external-lib-name'
```

Should return only:
- Dev paths in `*.service` files (legitimate — matches local dir name)
- Migration notes in README.md / INSTALL.md (legitimate — explains history)

## PITFALLS

### Pitfall #1: Doing one big sed pass

Trying to replace all `OLD_NAME` variants in one regex fails. Long prose
manuals have:
- Mixed case (`OLD_NAME`, `OldName`, `old-name`)
- Compound forms (`OLD_NAME Messenger Gateway`, `OLD_NAME-Messenger-Pod`)
- Context-specific (`OLD_NAME.down`, `OLD_NAME is`, `OLD_NAME has`)
- Hyphenated paths (`~/.old-name/`, `/home/old-name/`)

Multi-pass sed (specific → broadest) catches all of them without false
positives.

### Pitfall #2: Rewriting audit/historical reports

Audit reports are TIME-STAMPED snapshots. Rewriting them with new brand names
is historical revisionism. The findings are still valid; the context is now
historical. Move them to `archives/` with a banner instead.

### Pitfall #3: Not updating git remote URL first

If you sed the clone URL in INSTALL.md BEFORE updating the remote, you might
accidentally `git push` to the old URL during the rebrand. Always update
remote first, verify with `ls-remote`, then start sedding.

### Pitfall #4: Sibling subagents editing the same files

If you spawn parallel work (e.g. delegated subagents, parallel file edits),
they can clobber each other's changes. Watch for `_warning: ... modified by
sibling subagent` messages from `write_file`. Re-read the file before
re-writing.

### Pitfall #5: Touching production containers during cleanup

`podman rmi` and `podman rm` are dangerous if you're not careful with filters.
Production containers (mazemaker, pulse, atlas, wonderland) MUST stay running.

```bash
# WRONG — kills everything
podman rm -f $(podman ps -aq)
podman rmi -f $(podman images -q)

# RIGHT — filter by project
podman rm $(podman ps -a --filter name=NEW-NAME)
podman rmi localhost/NEW-NAME:latest
```

Always verify the filter list before executing.

### Pitfall #6: Removing legacy `.gitignore` entries

If the project had `.gitignore` entries like `.old-name/` (for legacy data
dirs), REMOVE them only after confirming no user has data in those paths.
For a fresh rebrand with no existing users, removal is safe.

### Pitfall #7: HKDF info string renaming is a PROTOCOL CHANGE

If the project has cryptographic HKDF info strings (e.g. `jrwl-x3dh-v1`),
renaming them to `iris-x3dh-v1` BREAKS FEDERATION with existing nodes.
Document this as a BREAKING CHANGE in the commit message and the README.

Old clients won't be able to federate with new ones until they upgrade.

## STEPS (summary)

1. `git remote set-url origin NEW-URL` + verify with `ls-remote`
2. Inventory all old-name refs (grep) + categorize
3. Mark legitimate-ref exceptions (external libs, migration notes, dev paths)
4. Move audit/historical docs to `archives/` with banner
5. Multi-pass sed: specific phrases → patterns → catch-all prefixes → bare words
6. Surgical fixes for the 5-10 leftovers
7. Commit in 3 stages: code → install guide → bulk rebrand
8. Cleanup WITHOUT touching production containers
9. Verify: only legitimate refs remain
10. Memory: save the rebrand protocol for next time

## RELATED

- `references/multi-pass-sed.md` — full sed patterns with order rationale
- `references/legitimate-refs-cheatsheet.md` — what to KEEP, what to REPLACE
- `templates/git-commit-message.md` — rebrand commit message structure
- `python-binary-distribution` — used when rebrand includes compilation/single-file
  binary changes (the iris-messenger case)
- `durable-process-supervision` — for "lass laufen" / production-safety principles

## VERIFICATION CHECKLIST

- [ ] Git remote points to new URL
- [ ] `git ls-remote origin HEAD` returns valid SHA
- [ ] All active code files use new name (verified by grep)
- [ ] All active docs use new name (verified by grep)
- [ ] Audit/historical docs moved to archives/ with banner
- [ ] External lib names (e.g. `jackrabbitdlm`) untouched
- [ ] Migration notes in README/INSTALL preserved (intentional)
- [ ] Dev paths in `*.service` files preserved if local dir matches
- [ ] Image build succeeds (podman build)
- [ ] Container runs (podman run + curl health)
- [ ] Zero `.py` in container (nukita pattern check)
- [ ] `git status` clean after commit
- [ ] No test containers left over
- [ ] No project images left over
- [ ] Production containers (mazemaker/pulse/etc.) UNTOUCHED
- [ ] Disk space reclaimed (df -h)
- [ ] Final summary in operator's preferred format (German/English)
