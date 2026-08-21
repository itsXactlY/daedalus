---
name: codebase-due-diligence
version: "1.0"
description: "Codebase-Due-Diligence: tiefgehende Projektanalyse bevor Architektur-Entscheidungen oder Strategie-Vorschläge. Trigger: User bittet um Investigation, Audit, oder Änderungen in einem fremden/unbekannten Projekt."
---

# Codebase Due Diligence

## Trigger

- User bittet um Investigation / Audit / Analyse eines Projekts
- User fragt nach Architektur-Änderungen in einem fremden Projekt
- User erwähnt ein Projekt und erwartet eine fundierte Einschätzung
- IMMER laden wenn ein Projekt zum ersten Mal in einer Session auftaucht

## Warum

Der User hat klargestellt: **Keine Strategie-Vorschläge, keine Architektur-claims, keine "ich bau mal schnell was"-Action bevor das Projekt von Grund auf verstanden wurde.** ("bevor du dich weiter aus dem Fenster lehnst, untersuchst du erstmal... von Grund auf, drüber drunter drunter rauf und runter")

Dieses Skill kodiert den systematischen Audit-Prozess. Im Zweifel lieber zu tief graben als zu flach.

## Prozess

### Phase 1 — Top-Level Scan (5 Minuten)

1. **Directory Tree**: `find . -maxdepth 2 -type d | sort` — verstehe die Grobstruktur
2. **File Counts**: `find . -name "*.py" | wc -l`, `find . -name "*.cpp" | wc -l`, etc. — welche Sprachen dominieren?
3. **Total Size**: `du -sh .`
4. **README**: immer zuerst lesen — aber nie blind vertrauen, gegen Code verifizieren
5. **.gitignore / .gitmodules**: Submodule? Ignorierte Pfade?
6. **LICENSE**: Lizenz-Kompatibilität checken

### Phase 2 — Build System

1. **CMake**: `find . -name "CMakeLists.txt" -maxdepth 4`
2. **Package**: `cat package.json`, `cat setup.py`, `cat Cargo.toml`, `cat go.mod`
3. **Install Scripts**: `find . -name "install*" -o -name "setup*" | head -10`
4. **Build Scripts**: `find . -name "Makefile" -maxdepth 2`, `find . -name "*.sh" -path "*/scripts/*"`
5. **CI/CD**: `.github/workflows/`, `.gitlab-ci.yml`

### Phase 3 — Git History

1. **Branches**: `git branch -a` — wieviele, welche sind aktiv/merged?
2. **Last Commits**: `git log --oneline -10`
3. **Submodule Status**: `git submodule status` — sind Submodule auf dem richtigen Commit?

### Phase 4 — Komponenten-Verständnis

1. **Entry Points**: `find . -name "main.py" -o -name "run_*.py" -o -name "main.cpp" -maxdepth 3`
2. **Key Interfaces**: Lese die wichtigsten 3-5 Dateien (Architektur-Doku, Core Engine, Broker Interface)
3. **Data Flow**: Wie kommen Daten rein? (WS/REST/File) → Wie werden sie verarbeitet? → Wo landen sie?
4. **Abhängigkeiten**: `cat requirements.txt`, `cat go.sum`, check vendor/ oder node_modules/

### Phase 5 — Test-Suite

1. **Test Structure**: `find . -path "*/test*" -type f | head -20`
2. **Test Runner**: pytest? jest? go test? cmake --build --target test?
3. **Test Results**: Wenn möglich kurz ausführen: `python -m pytest --collect-only` oder equivalent

### Phase 6 — Architecture Map

Nach dem Scan: **Architektur in 3-5 Sätzen zusammenfassen** und dem User präsentieren. Erst DANN Vorschläge oder Strategien diskutieren.

```
Projekt: <name>
Sprachen: <Python/C++/JS> — <N> Dateien
Grösse: <N> MB/GB
Build: <CMake/Make/Cargo> — <N> Targets
Data Flow: <Eingang> → <Verarbeitung> → <Ausgang>
Exchanges/Connectors: <list>
Limits: <was fehlt/dat fehlt>
```

## Pitfalls

- ❌ **Nicht vom README blenden lassen**. READMEs lügen, sind veraltet oder voller Wunschdenken. Immer gegen echten Code prüfen.
- ❌ **Keine Strategie- oder Architektur-Vorschläge vor Phase 6**. Der User hat null Toleranz für Annahmen über Code der nicht gelesen wurde.
- ❌ **Nicht nur die Top-Level-Dateien lesen**. "Drüber drunter drunter rauf und runter" heisst: Entry Points, Core Engine, Broker/Store, Tests, Build System, Data Flow — alles.
- ❌ **Submodule nicht ignorieren**. Viele Projekte haben kritische Logik in Submodulen (ccapi, render engine, etc.)
## Pitfall: "Wires-not-wired" — code-correct fix that isn't on the live path

A class that imports cleanly, has correct code, but is never called by the live handler provides FALSE reassurance. The fix audit can pass while the production traffic still hits the broken path. This is a real failure mode — concrete example: an E2E messenger where `ratchet_encrypt` was imported at the top of `gateway.py` but the live `/api/message/send` handler used a legacy `encrypt_message` function. The audit found the ratchet to be code-correct, the team committed the fix, the live path still used the legacy path. The actual fix had to be a separate commit that wired the ratchet into the live handler. **Rule: when an audit fix is "X is broken in Y.py", verify that Y.py is actually called by the live code path. `grep -n` for the function/method. Trace one request through. If the broken code is in an imported-but-never-called module, the fix is dormant.**


<!-- moved to references/moved-sections.md: ## Pitfall: Real code wins over LLM inference (BTQuant, 2026-06-20) -->


<!-- moved to references/moved-sections.md: ## Pitfall: License inference from README prose, not from the file (iris-messenger, 2026-06-20) -->


<!-- moved to references/moved-sections.md: ## After the audit: turning findings into a fix campaign -->


<!-- moved to references/moved-sections.md: ## Post-audit phase: aligning docs & build scripts with reality (docs-fix wave) -->


<!-- moved to references/moved-sections.md: ## Post-audit phase: lint pass & dependency freeze (Android, 2026-08-07) -->

## Pitfall: E2E test value vs unit test confidence

(observed 2026-06-19 on jrwl-messenger)

**E2E tests catch integration bugs that unit tests miss.** A class that compiles, passes its unit tests, but is never called by the live handler provides FALSE reassurance.

Concrete example from jrwl-messenger (2026-06-19):
- The codebase had unit tests for `verify_signed_prekey` in `test_crypto_exhaustive.py` (passed)
- The `verify_signed_prekey` function was code-correct
- BUT: the `/api/x3dh/exchange` HTTP handler in `gateway.py` called `verify_signed_prekey()` (line 3205) without ever importing it
- The handler returned 400 "SPK signature invalid" for every X3DH exchange request
- This bug had been in production for MONTHS (the import was missing since the last import list refactor)
- Unit tests passed because they tested the function in isolation; the live handler never reached the function because the import failed at module load
- An E2E test that drove a real HTTP request through the full X3DH handshake caught it in seconds

**Rule:** if a fix touches the LIVE CODE PATH (HTTP handler, WS handler, real-time message flow, anything user-facing), an E2E test is required. Unit tests are not sufficient for live-path changes. The cost of writing the E2E test is always less than the cost of a production bug that passed unit tests.

**When unit tests ARE sufficient:** for internal helpers, data structures, utility functions, anything that doesn't directly affect the live code path. If the change can't be reached by an external request, unit tests are fine.


<!-- moved to references/moved-sections.md: ## Pitfall: server-pushed message types missing from client handler -->

## Pitfall: "wires-not-wired" verification recipe

When a security/audit finding says "function X is broken" or "library Y is misused":

1. **`grep -rn "X\|Y"`** in the live entry point (main script, request handler) — is X or Y called at all?
2. **Trace one user request through the live code path.** Pick the most common action (e.g. "send a message"). Follow every line from the entry point to the response. Note every cryptographic operation, every storage call, every network call.
3. **If the broken/misused function is in an import but never in a call site**: the audit finding is real but the fix is dormant. The fix needs TWO commits — one for the code itself (which may already be correct), one for the live path that should call it.
4. **If the broken function is in a parallel implementation that's used in production while the audited implementation sits unused**: there are TWO architectures running. The audit needs to flag both.

The false-reassurance failure mode:
- Audit says "X is broken"
- Fix: make X correct
- Commit X
- Run tests, tests pass (because tests test X, not the live path that doesn't use X)
- Ship
- Production still has the broken behavior because the live path uses Y, not X

The verification: **grep for the call site, not just for the function definition.**

## Pitfall: status-first Flow + `.first()` = the work never runs (Kotlin)

`Flow.first()` returns after the FIRST emission and cancels collection. An install/update flow that emits a status (`Installing`) BEFORE doing the real work (download → verify → commit) is a trap: a background worker calling `flow.first()` "succeeds" instantly and silently cancels the actual work. Symptom: worker always returns success, nothing ever happens, no error anywhere. The code comment may even claim the flow is being "drained" — verify the terminal operator actually collects to completion (`.collect { }`) or refactor to a suspend function that runs to completion. This is the coroutine-flavored variant of wires-not-wired.

## Pitfall: audit the SHIPPED artifact, not just the source

Source-level review misses permission/packaging facts that only exist after the build. For Android, ground truth is the built artifact: `aapt2 dump badging <published.apk> | grep -E 'package:|uses-permission'` (aapt2 from the newest build-tools) and the packaged merged manifest under `build/intermediates/packaged_manifests/<variant>/.../AndroidManifest.xml`. Canonical failure (mazemaker-mobile The Box, 2026-08-07): an auto-updater APK shipped with NO `android.permission.INTERNET` — every network call threw, was caught, and the feature was silently dead in every build including the published 1.0.5; `git log --all -p -- <AndroidManifest.xml>` proved the permission never existed. Source review + artifact verification together are the only reliable pair. Note the trap that `ACCESS_NETWORK_STATE` (added by libraries like WorkManager) is NOT `INTERNET` — it only queries status, it does not open sockets.

Full Android installer/auto-updater audit checklist + The Box findings: `references/android-installer-updater-audit.md`.

## Reference: BTQuant Deep Dive (2026-05-25)

Ein exemplarischer Deep Dive findet sich unter `trading/btquant-full-stack` — das Ergebnis der Anwendung dieses Prozesses auf ein 7.1GB / 40K-File C++/Python HFT-Framework.

## Pitfall: "STOP GUESSING" — the operator's zero-tolerance signal (2026-08-01)

When the operator gives you a project directory and asks for an idea/concept/rebuild ("come up with a full idea for our X website", "what would you build", "make it visual"), producing generic abstract marketing-vision prose is a FAILURE, not a first draft. The operator's exact signal when I did this: **"stop this fucking brainraped shit here, ffs. STOP GUESSING, FOR WHAT DID I GAVE U ALL THE INFOS?"** — followed by the correction: **"use mazemaker, recall everything about the trailer, marketing, everything what matters the deeper u walk the maze. then lets make a plan... step by step. slow and steady."**

This applies not just to code, but to ANY creative/strategy deliverable for an existing project. The directory IS the input. The sequence that fixes it:

1. **`mazemaker_recall` first, walk it deep** — recall, then recall_multi, then think() on the strongest hit. For a website, ask about the design-language commit, the original build prompt ("GOATED prompt"), prior trailer/video work, and any paused autonomous-loop cron on the target.
2. **Inspect the ACTUAL files** — asset directory inventory, live `:root` design tokens, real copy in `index.html`, `git status` + branches. Speak only to what exists on disk.
3. **Only then propose** — and ground EVERY proposed visual in copy already on the page, not invented value props.
4. **Fork before building** — for a marketing site, `main` is often production. Create a real git branch, stash the dirty tree, leave prod untouched.
5. **Phase-gate + step-by-step** — run ONE phase, surface a decision point, wait. "Slow and steady" is an explicit operator instruction for this class; barrel-through is rejected.

The "messaging spine" technique (which won approval): derive N beats, each mapped to existing page copy, every visual must serve one beat. That's what turns "add images/videos" into "each visual teaches one verified claim."

Full worked example (mazemaker.online visual rebuild: six beats, fork command, design-language constraints, asset audit): the `mazemaker` umbrella's `references/website-content-rebuild-2026-08-01.md` documents it. This pitfall is the meta-lesson that governs the whole class.

## Pitfall: Forking inside a LIVE git worktree = editing production on disk (2026-08-01)

**The most severe failure mode of "fork before building":** `git checkout -b <branch>` executed **inside** the operator's live worktree does NOT isolate your work. It switches that worktree's checked-out branch, so the files on disk in the live directory immediately become your branch's state. You edit `website/index.html`, add `assets/foo.js` — and every byte lands in the production tree the operator is looking at.

The operator's exact reaction when I did this on their new-site worktree (`.../.claude/worktrees/design-import`, branch `design/site-rebuild`): **"USE UR OWN BROKEN DIPSHIT FORK FFS", "U ALREADY MADE A FORK, OF THE OLD WEBSITE, THEN TOOK THE NEW ONE, THAN EDITED ON LIVE!"** A separate branch is NOT isolation. The working tree you edit is the live one regardless of branch.

**The rule:** when the target project is checked out in a **git worktree** (path contains `.claude/worktrees/...` or you see multiple entries in `git worktree list`), the ONLY safe way to fork is a **separate worktree at its own path**:

```bash
# WRONG — edits files on disk in the LIVE worktree directory
cd /path/to/live-worktree && git checkout -b my-fork && edit files...

# RIGHT — a separate worktree, based on the live branch tip, at its OWN path
git worktree add /path/to/my-fork -b my-fork design/site-rebuild
cd /path/to/my-fork && edit files...
```

**Before any edit, ask two questions:**
1. `git worktree list` — is the target inside a worktree (not the main checkout)?
2. What is `git -C <target> branch --show-current` — is it the live branch?

If the target is a worktree on the live branch, your fork MUST be a new worktree, never a `git checkout -b` inside it.

**Recovery if you already edited inside the live worktree:**
1. Commit the work to your fork branch (`git add -A && git commit`) so nothing is lost.
2. `git checkout <live-branch>` inside the worktree to restore the live files.
3. Verify pristine: `git status --short` is empty, `git status -sb` shows the live branch, and `git merge-base --is-ancestor <fork-branch> <live-branch>` returns NON-zero (fork is not an ancestor of live).
4. If you can't safely restore in-place, ask the operator where they want the fork to live rather than guessing a path — guessing is how you hit this again.

## Pitfall: sub-agent severity claims are SELF-REPORTS — verify before reporting (2026-08-07, mazemaker-pro)

Third application of the parallel-readonly-audit methodology (mazemaker-pro engine, 3 streams, 90 findings). The single most important lesson: **a parallel audit crew's CRITICAL/HIGH findings must be verified against the source before they reach the operator as fact.**

Real case: the crew reported 3 CRITICALs — FTS5 MATCH injection (memory_client.py:1088/1139), Postgres tsquery injection (postgres_store.py:1796/1837), NUL-byte truncation (cpp_bridge vs mazemaker.py). All three were REFUTED in minutes of direct reading:
- Both "injection" sanitizers ran a token-extraction regex (`[A-Za-z0-9_][A-Za-z0-9_/\-]{1,}`) that filtered every metacharacter BEFORE the sink; every token was wrapped in quotes, and inside FTS5 phrases / tsquery lexemes all operators are literal. Sub-agents had read the sink, not the guard. (Note: `-` is an operator in FTS5 but NOT in tsquery — the workers assumed the opposite for both.)
- The NUL-byte checks sat exactly at the only c_char_p boundary (cpp_bridge); the active SQLite path stores NUL intact.

**Verification protocol (add to any crew audit):**
1. For every CRITICAL and the top 2-3 HIGHs: read the cited file:line ±30 yourself, plus one `search_files` grep for the guard (sanitizer, validator, pre-filter) that runs before the cited sink.
2. Downgrade culture: worker CRITICAL → verified LOW is a WIN. Record both the worker claim and the verified severity in the report so the discrepancy is visible.
3. Verify the top fix candidate as well — confirm the exact line before recommending the change.
4. Do NOT re-verify all 90 findings — 4-6 targeted windows + grep is enough; the rest stays as "unverified worker claim".

Also this session: **an audit is READ-ONLY until the operator orders otherwise.** "Nur Code-Audit" = no test-suite execution, no builds, no restarts. Starting the upside-down test suite as "empirical basis" during an audit was corrected by the operator ("nein. nur code audit."). Empirical verification is a separate, explicitly ordered step.

## Pitfall: delegation config pins ALL sub-agents globally — free-model roulette by default (2026-08-07)

`delegation:` in `~/.hermes/config.yaml` (model + provider) pins EVERY `delegate_task` sub-agent — children do NOT inherit the parent model while delegation.model is set. A leftover pin like `model: nvidia/nemotron-3-ultra-550b-a55b:free / provider: openrouter_free` (with duplicated base_url+api_key) silently routes all workers to a free model.

Symptoms of free-model workers:
- status=completed with an EMPTY summary ("Let me compile the report" and nothing else)
- 600s timeout with zero output (child_timeout_seconds)
- Re-dispatch on the same config reproduces the same failure

Check before any crew dispatch: `grep -A6 '^delegation:' ~/.hermes/config.yaml`. Operator preference (explicit, 2026-08-07): NO free-model roulette — delegation pinned to `deepseek-v4-flash`/`deepseek`; switching to free models only with explicit approval for approved cheap-mass jobs. When a worker comes back empty, re-dispatch AFTER fixing the config, never on the same pin.

Full session detail (3-stream mazemaker-pro audit, the 3 refuted CRITICALs with code quotes, OOM/RAM-bloat diagnosis methodology — systemd-oomd vs kernel-OOM, steady-state vs leak, get_all() materialization math, bisect checkpoint recipe — and benchmark-model-history reconstruction): `references/parallel-readonly-audit-mazemaker-2026-08-07.md`.


<!-- moved to references/moved-sections.md: ## Pitfall: audit checks that generalize across project types (mazemaker-mobile, 2026-08-07) -->

## Pitfall: "service is UP but not DISCOVERABLE" — LAN client silently falls back to a relay/wrong endpoint (2026-08-07, mazemaker-mobile + Pixel 7 Pro)

A gateway/server process being `active (running)` on the right port does NOT mean a
discovery-dependent client can reach it over the LAN. Separate the two facts:

- **The target is up**: `ss -tlnp | grep :8443` shows the python gateway listening.
- **The DISCOVERY is up**: the mDNS/DNS-SD advertisement that lets the phone find it.

Canonical failure: a phone app that normally pairs over LAN (QR code carries only
`{v, token, fp}` — no host by design; the app does mDNS discovery to find the gateway)
started hitting `api.mazemaker.dev` (the out-of-network relay, Route C) and 404'd
everywhere. Diagnosis chain:
1. App logcat showed the app DID run mDNS discovery (`_mazemaker-gw._tcp`, 6 s timeout)
   but **no `onServiceFound`** → it concluded "no gateway on LAN" → fell back to the
   relay URL baked as Route C.
2. The gateway process was up (ports 8443/38374) but `avahi-browse -rt _mazemaker-gw._tcp`
   returned nothing → the **advertisement service** (`mazemaker-apk-gateway-mdns.service`)
   was `inactive (dead)` + `disabled`, never started (empty journal).
3. Fix = `systemctl --user start` + `enable` the mdns unit; re-run
   `avahi-browse -rt` until the service appears with its TXT `a=<routable-LAN-IP>`
   (the TXT record carrying the LAN IPv4 is what sidesteps mDNS handing the phone a
   virbr0/link-local address).

Generalise: **before debugging a "wrong endpoint / routed over NAT instead of LAN"
symptom, verify BOTH the serving process AND its discovery/advertisement service are
running.** A firewall or a disabled systemd advertisement unit produces the same
symptom as a down gateway, and is silent — the client just picks whatever fallback
path it has. Also confirm the fallback (relay) endpoint the app defaults to actually
serves the path the app requests (a public API domain returning `only serves /api/*`
404s is the tell that the fallback URL is the wrong one).

Full runtime diagnosis (logcat reads, avahi verification, provision-apk.sh payload
shape, relay endpoint mismatch): `references/lan-discovery-fallback-debug-2026-08-07.md`.