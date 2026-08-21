# Rebrand Commit Message Template

A full project rebrand is typically 3 commits, not 1. Each commit has a
specific scope and atomicity.

## Commit 1: The rename commit (code + env vars + build/container)

This is the BIG commit. It changes everything that's load-bearing for the
project to actually function under the new name.

```markdown
feat: NEW-NAME — [architectural changes happening at the same time]

BREAKING CHANGE: full rebrand from OLD-NAME to NEW-NAME + [other change].

WHY NEW-NAME:
  * [Reason 1 — e.g., distinguishes from existing X-themed services]
  * [Reason 2 — e.g., single-word family fit (Pulse, Mazemaker, Hermes, Atra)]
  * [Reason 3 — e.g., Greek mythology fit (rainbow bearer between realms)]
  * [Reason 4 — e.g., domain + package availability]

[OTHER ARCHITECTURAL CHANGES — e.g., "Nuitka --onefile migration"]:
  * [What changed]
  * [Why]
  * [Verification result]

CONTAINER / BUILD PITFALLS (document in Containerfile comments):
  * [Pitfall 1 — e.g., patchelf 0.18.0 is BUGGY per Nuitka — use 0.17.2]
  * [Pitfall 2 — e.g., glibc search path on Arch is /usr/lib only]
  * [Pitfall 3 — e.g., Unicode banner needs LC_ALL=C.UTF-8]

FILES:
  * Renamed: X → Y (count files)
  * Source code: ENV vars OLD → NEW, paths /old/ → /new/, HKDF info
    strings (BREAKING PROTOCOL CHANGE for federation)
  * dlm_identity: 'old' → 'new'
  * Banner / docstrings / HTML / argparse: New Brand
  * runtime.env: sample committed (NEW_LOG_LEVEL, NEW_DOMAIN, ...)
  * manifest.json: 'New Brand' + [new icon if applicable]
  * .gitignore: build artifacts, lib/ (host glibc copies)

DEFERRED (not blocking, follow-up):
  * [Deferred item 1 — e.g., README/MANUAL brand references (low priority)]
  * [Deferred item 2 — e.g., license-client sidecar]

VERIFIED:
  * Binary runs standalone: ./NEW-NAME.bin (host) shows banner
  * Container runs: REST + WS ports up, identity endpoint returns
    'authentication required' (correct auth gate)
  * Image: XX MB total
  * Zero .py in container layers

Stats: ~XXX substitutions across YY files; ZZ deletions; NN git ops.
```

## Commit 2 (optional): TL;DR / install guide

Only if you wrote a fresh-install guide. This is for fresh-system installs.

```markdown
docs: INSTALL.md — single-page TL;DR for fresh-system install

Production-ready quick-install guide covering:
  1. Host deps (pacman/apt: package list)
  2. [Special binary dep — e.g., patchelf version]
  3. Clone + make build + podman build
  4. bash install.sh (handles venv, binary, image, quadlets, runtime.env)
  5. Verify (curl /api/status, /api/identity)
  6. Firewall (TCP/80 + 443, install.sh doesn't touch iptables)
  7. Update + uninstall paths
  8. Common pitfalls (all N from this session)
  9. File map (host ↔ container paths)
  10. What this is NOT yet (P2 license, P3 mobile, federation breakage)
```

## Commit 3: Bulk rebrand (display strings + docs + audit moves)

This is the cleanup pass — catches everything the rename commit missed.

```markdown
feat: complete NEW-NAME rebrand — code + docs + audits

FULL REBRAND from OLD-NAME to NEW-NAME across:

Source code:
  * [file1, file2, file3]: docstrings + display strings
  * [file4]: HKDF info literals (was missed in initial rebrand)
  * [file5]: header comments
  * [test_files]: 'OLD' → 'NEW' (display strings)
  * [ui.html]: chat export header + browser title + h1 + badge
  * [scripts/]: docs
  * [.github/workflows/ci.yml]: header comment

Documentation:
  * README.md: complete rewrite for NEW-NAME brand (N+ lines, narrative,
    🌈 banner, full env vars table, [other sections])
  * MANUAL.md: master index updated
  * docs/MANUAL_FOUNDATION.md: vocabulary + worked examples
  * docs/MANUAL_USER.md: N substitutions (EN+DE prose)
  * docs/MANUAL_ADMIN.md: N substitutions (full quadlet install guide
    rewritten — quadlet names, paths, env vars, service names)
  * docs/MANUAL_TROUBLESHOOTING.md: N substitutions
  * INSTALL.md: clone URL fixed (was still OLD-NAME.git)

Historical / audits:
  * N audit/historical docs moved to archives/ with banner explaining
    pre-rename context (AUDIT_*, etc.)
  * Banner: 'ARCHIVED — pre-rename snapshot, see git log <rename-sha>'

Build / infra:
  * install.sh: REPO_URL → NEW-NAME.git
  * .gitignore: removed legacy .OLD-NAME/ entry
  * *.service: [decision on local-dir path — kept or updated]

REMAINING LEGITIMATE REFS (not bugs):
  * [path/file]: [reason]
  * [README.md §N]: [reason — migration note]

Stats: ~XXX substitutions across YY files; ZZ deletions; NN git ops.
```

## Why 3 commits instead of 1

1. **Atomicity** — Each commit is self-consistent. If someone clones the
   repo at commit N, they get a working state.
2. **Reviewability** — A reviewer can read 3 focused commits more easily
   than 1 monolith.
3. **Rollback** — If something breaks, you can revert one commit without
   losing the others.
4. **Searchability** — `git log NEW-NAME..HEAD` shows exactly what changed
   between rename and docs update.

## Subject line conventions

- `feat: NEW-NAME — <architectural change>` for the rename commit
- `docs: INSTALL.md — <what it is>` for the install guide
- `feat: complete NEW-NAME rebrand — code + docs + audits` for the bulk

NOT:
- `rebrand` (too vague)
- `rename everything` (also vague)
- `[WIP]` (not WIP — these are atomic)
- `Update brand` (which brand? what scope?)

## Body length

- Subject: 60-80 chars
- Body: as long as needed, but use bullets
- Stats line at end: "Stats: N substitutions across M files; K deletions"
  helps the reviewer gauge scope without reading the diff
