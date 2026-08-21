# codebase-due-diligence — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Pitfall: Real code wins over LLM inference (BTQuant, 2026-06-20)

**When the codebase is RIGHT THERE, READ IT instead of inferring patterns from class names, file headers, or naming conventions.** The LLM's default is to pattern-match and invent a plausible architecture — for greenfield code this is fine, but when modifying or extending an existing system, the inferred architecture will silently diverge from the real one and produce code that compiles but doesn't integrate.

Operator signal that triggers this pitfall: **"schau wie X funktioniert, wie aufbauen aus Y, NUTZ MAZEMAKER"** (look at how X works, build on Y, USE MAZEMAKER). When the user has to remind you to look at the actual code, you have already failed once.

**Concrete failure mode (BTQuant strategy generation, 2026-06-20):**
- I was generating 601 strategy files using an ARCHITECTURE I INVENTED:
  - Used `self.buy()` / `self.sell()` directly instead of BTQ's `self.create_order(action='BUY'|'SELL')` helper
  - Used raw backtrader instead of BTQ's `backtrader_` fork with `transparencypatch`
  - Made up my own conditions / position-tracking instead of using BTQ's `buy_or_short_condition` / `dca_or_short_condition` / `sell_or_cover_condition` overridable pattern
- The "real" BTQ architecture was a 1401-line `BaseStrategy` at `/home/alca/projects/.btq/lib/python3.13/site-packages/backtrader_/strategies/base.py` plus 22 reference strategies in `/home/alca/projects/PubBTQuant/dependencies/backtrader/strategies/`. I never opened either.
- Result: a class that compiled, instantiated, registered with cerebro, but produced no trades — `class_name` in the file didn't match the file basename, so the backtester's `getattr(module, strategy.class_name)` returned None, fell back to `BaseStrategy` itself (which IS-A `bt.Strategy` but had no indicators → `next()` had no signals).

**The correct workflow (memorize this):**
1. **`mazemaker_recall`** the topic — operator expects this, period.
2. **Read the canonical source** — for BTQuant it's the BaseStrategy in `site-packages/backtrader_/strategies/base.py` plus 2-3 representative `*_Simple.py` files in `dependencies/backtrader/strategies/`. Don't read all 22 — pick the canonical/simplest 2-3.
3. **Read the existing in-repo code** that already integrates with that source — for BTQuant that's `autonomous_agency/strategy_factory.py` and `autonomous_agency/backtester.py` to see how they consume strategy classes.
4. **Only then** write your integration. Your code must follow the canonical BaseStrategy pattern, not your pattern-matched inference.

**The diagnostic check** before claiming a pattern is "correct": does the strategy class `class X(BaseStrategy)` actually appear in a registered `sys.modules` entry with the same name as `X.__name__`? Does `getattr(module, X.__name__)` resolve to the class? Does `next()` actually emit orders? Run a backtest on at least 3 strategies and confirm `trades > 0` for all of them.

**Anti-patterns:**
- ❌ Reading a README and assuming the architecture matches it (READMEs lie)
- ❌ Reading ONE strategy file and assuming the rest follow the same pattern (always read 2-3)
- ❌ Inferring architecture from class names like `Adaptive_Momentum` → "momentum strategy with EMA"
- ❌ Using `self.buy()` / `self.sell()` directly when the framework provides a wrapper
- ❌ Skipping `mazemaker_recall` because "I already know what to do"

**The user-side cost of this failure mode:** ~3 hours of regenerating 601 files through 6 schema versions, plus furious "gottloses Stück Scheiẞe" signal. The fix took 5 minutes once I read the actual code.

## Pitfall: License inference from README prose, not from the file (iris-messenger, 2026-06-20)

**The LICENSE file is the source of truth. README prose about the license is decoration.**

A README may say "MIT — see `LICENSE` (if present) or default MIT terms" or "AGPL-3.0 + PolyForm-NC dual license" or any number of aspirational/wishful claims. None of that matters unless there's an actual `LICENSE`, `LICENSE.md`, or `LICENSE.txt` file with the right header (copyright year + holder + license body or clear pointer to SPDX identifier).

**Concrete failure mode (iris-messenger, 2026-06-20):**
- Operator: "the MIT license was hallucinated, gets dropped"
- I had previously stated "iris-messenger is MIT-licensed" in turn outputs and even a rebrand-cleanup report, citing the README's "MIT — see `LICENSE` (if present)" line as evidence.
- Reality: there was no `LICENSE` file in `~/projects/jrwl-messenger/`. The README text was a placeholder/aspirational line the author left in during early development. The phrase "or default MIT terms" only applies if there's an explicit MIT license grant with copyright year + holder, which there wasn't.
- User caught this when planning the iris-android rebrand (which needed to mirror Mazemaker's dual-license model) and told me to drop the fake MIT and use the actual model.
- Cost: a hallucinated license claim persisted across multiple turns, would have caused license laundering in any public release.

**Verification recipe (mandatory before stating any project's license):**
```bash
# 1. List actual license files
ls -la LICENSE LICENSE.md LICENSE.txt LICENSING 2>/dev/null
find . -maxdepth 2 -name 'LICENSE*' -o -name 'LICENCE*' 2>/dev/null

# 2. If found, read the header
head -5 LICENSE

# 3. If multiple, read all of them (e.g. dual-license: LICENSE + LICENSE-AGPL-3.0.txt + LICENSE-POLYFORM-NC-1.0.0.md)
#    and the LICENSE summary if it points at siblings

# 4. If NOT found, the state is: "no license granted; default copyright applies (all rights reserved in most jurisdictions)"
#    Do NOT infer from README prose. Do NOT pick a default. State explicitly: "no LICENSE file; no license grant verified"
```

**Never say "this project is X-licensed" based on:**
- ❌ README prose (`"MIT — see LICENSE (if present)"` is not a license grant)
- ❌ A single LICENSE file with no copyright header
- ❌ A comment in source code (`# License: MIT`)
- ❌ An outdated link to a license text

**If the user asks "what license is this project under?"** and there is no LICENSE file, the honest answer is: "no LICENSE file present; no license grant verified; the README's claim of X is unverified." If the user wants to assign a license, that's a separate action (add LICENSE files + update README).

**For the alca-stack specifically:** the canonical model is the Mazemaker dual-license pattern (AGPL-3.0 + PolyForm-NC). New projects that want to match the stack should add:
- `LICENSE-AGPL-3.0.txt` (copy from any existing alca project)
- `LICENSE-POLYFORM-NC-1.0.0.md` (copy)
- `LICENSE` (summary file pointing at the two)
- `NOTICE` (attributions for vendored dependencies)
- README update replacing any placeholder license prose with the explicit dual-license pointer.

**Cross-reference:** when doing a `full-project-rebrand`, Phase 1 Step 6 of the audit ("LICENSE: Lizenz-Kompatibilität checken") should now also include the verification recipe above — a license is only verified if the FILE exists, not if the README says so.

## After the audit: turning findings into a fix campaign

The audit typically produces 20-50+ findings. Turning this into a fix campaign requires triage, systematic execution, and re-audit. This is a class of work that often follows the initial investigation.

**Triage (main session, not subagent):**
- Categorize: CRITICAL / HIGH / MEDIUM / LOW
- Group by file: which fixes are adjacent in the same file? Batch these.
- Group by type: security / threading / crypto / deployment / testing
- Identify blockers: fixes that enable other fixes (e.g. add session token infra first, then apply auth to all endpoints; add a config type validator before relying on config values)
- Estimate: which fixes are 1-2 hours vs which are days?

**Fix execution (mix of subagents and main session):**
- **Subagents:** focused single-section edits, test writing, single-file documentation, code review of specific files
- **Main session:** multi-section monolith file edits (3000+ LOC), orchestration of cross-cutting changes, anything that needs to "know the story so far"
- For each fix, the brief should include: file:line, current code (quoted), proposed change, how to verify (test name, grep pattern, or commit message)
- See `subagent-driven-development` for the success matrix and timeout pitfalls

**Parallel fix-crew mechanics (observer pattern, 2026-08-07, mazemaker-mobile):**
When the audit produced 2 CRITICAL + 15 HIGH and the operator said "spin up your agency, bring it to production", the fix campaign ran as parallel implementation crews — DIFFERENT mechanics from the audit crew:
- **Disjoint file ownership per worker.** Split fixes into waves where each subagent owns ONLY files no other wave-1 agent touches. Enumerate exact paths in each brief. Wave 1 = 3 agents (jackbox installer, preferences/auth, websocket) on completely separate files; wave 2 = viewmodel, repository/cache/models, gateway-crypto. Never let two agents in the same wave edit the same file — that's a merge-conflict factory.
- **Workers implement only; the OBSERVER commits.** Every brief said "NICHT committen, nicht bauen" (don't commit, don't build). The supervisor/observer owns the git commit + gradle verify between waves. This prevents parallel agents from racing on `git add`/commit and keeps a single clean diff to review per wave.
- **Wave-gate before the next dispatch.** Verify wave N's diff (read the changed files, run `node --check`/gradle syntax) AND commit BEFORE dispatching wave N+1. Do not dispatch all waves up front — later waves depend on earlier ones being in place and reviewable.
- **Observer does the heavy context work, workers get tight briefs.** The observer pre-reads every file the workers will touch (so the brief can carry exact line numbers + current code snippets). Workers get a self-contained task, not "read the whole project". Pre-read also lets the observer catch scope-overlap before dispatch.
- **Explicitly scope work IN the brief** (e.g. "only fix A, B, C — do NOT add the signature system, that's another task") — otherwise a capable worker gold-plates and touches the shared contract, breaking other waves.
- **Release-gate after the fix campaign (2026-08-07): verify the SHIP path, not just the code.** Before building the "production-ready" APK from the fixed checkout, check (a) **versionCode monotonicity**: `grep -E 'versionCode|versionName' <module>/app/build.gradle(.kts)` vs the RELEASED artifact's badging (`aapt2 dump badging` on the shipped APK). A checkout behind the released version (found: checkout 1.3.1/versionCode 6, shipped payload 1.4.0/versionCode 7) builds a DOWNGRADE that Android refuses to install over the existing app. Bump versionCode first. (b) **Build scripts may pin an OLD branch**: `build-box.sh` had `REF[mazemaker]="release/android-1.4.0"` — so the fixed checkout would never actually be what ships; the installer keeps bundling the stale payload. Grep the bundle script for pinned refs (`git worktree add ... <ref>` / `REF[name]=`) and repoint them at the fixed branch. A fix campaign is not production-ready until the build/publish path provably consumes the fixed code.
- **Merging the release branch into live is usually conflict-free — but verify YOUR fixes survived (2026-08-07).** `git merge --no-commit --no-ff <release-branch>` merged 1.4.0 (versionCode 7 + on-device-pod features) into the fixed live checkout with ZERO conflicts even though both sides had modified the same files (PreferencesManager, MazemakerViewModel). Auto-merge does not mean semantic merge: after the merge, (a) grep for your own fix markers to prove they survived (`grep -c 'hermesChatGen' MazemakerViewModel.kt`, `grep -c 'gatewaySecret' PreferencesManager.kt`), (b) verify the release features actually arrived (`git ls-tree`/`test -f` on the new files), (c) re-run the full test suite — merged code can regress the 27/27 baseline silently, (d) THEN commit the merge with a version-bump commit. Never trust an auto-merge result without the marker-grep + test re-run.

Full wave recipe incl. Android/Gradle verification level (`ANDROID_HOME` not exported in bare shell, read test XML results not the BUILD line, aapt2 artifact proof), release-version-drift, and tag-before-delete branch cleanup: `references/fix-campaign-crew-2026-08-07.md`.

**Re-audit (verify, don't trust):**
- Re-dispatch focused subagents on the FIXED sections, not the whole codebase
- Look for: regressions (did the fix break something else?), new findings (what was hiding behind the old bug?), dormant fixes (the code-correct fix isn't wired into the live path)
- E2E tests catch integration bugs that unit tests miss — see the "E2E test value" pitfall below
- Commit-by-commit verification: a fix is only "done" when it survives a fresh subagent's audit of the changed file

**Final phase: ship and remember:**
- Update the project's docs (POST_FIX_STATE.md or equivalent) with the final state
- Save findings to mazemaker as `decision:` and `fact:` entries for future sessions
- Don't trust "fixed" until the live code path is verified end-to-end

## Post-audit phase: aligning docs & build scripts with reality (docs-fix wave)

After the code fixes, the docs usually still describe the fantasy architecture the audit was called against. Fixing them is its own wave with hard rules (learned 2026-08-07 on mazemaker-mobile):

1. **Read every target file fully first** — before rewriting any section.
2. **Verify each claim against the code, THEN write**: real file tree from `find <srcroot> -name '*.kt' | sort` (build the doc tree from that output, verbatim), real dependencies from the build file, real endpoints from `grep` of the API interfaces, real branch/version from `git`. If a doc names a file that does not exist (McpService.kt, AppModule.kt, Typography.kt…), it is fantasy — delete the reference, never "repair" it into existence.
3. **The file beats the task brief.** When a delegated brief's parenthetical contradicts the actual build file (brief said "CameraX 1.3.4", build.gradle pins 1.4.2 with a comment explaining 1.3.4 is banned for 16 KB-page alignment), write the truth and flag the discrepancy in the report. The brief's own overriding instruction is usually "use the real dependencies from build.gradle".
4. **No new promises.** Checklists get updated with what IS true now: mark items done where the code satisfies them, re-count tests (`grep -rc '@Test'`), fix stale "next steps" (shipped features move out). Never add aspirational items.
5. **Stay in scope.** Only touch the named files; out-of-scope artifacts (e.g. a stale root package.json describing an Expo app that no longer exists) get flagged in the report, not fixed.

### Verifying bash script edits without running them

For edits to shell scripts (build scripts, installers), the honest harness is shell-level, not `npm test`:

1. `bash -n <script>` — syntax gate.
2. **Execute the real setup lines, stop before side effects**: `bash -c 'set -u; source <(sed -n "1,9p" script.sh); <asserts on resolved vars>'` — cut the extraction at the first side-effecting command (e.g. `adb wait-for-device`). This proves the actual file content resolves correct paths.
3. **Eval the real table block to test dispatch logic**: `eval "$(sed -n '/^declare -A REPO REF MODULE/,/^NEEDS\[iris\]/p' script.sh)"`. TRAP: under `set -u` this fails if the variables the block references (set earlier in the real script, e.g. `JRWL_REPO=`, `MZM_REPO=`) are not defined first — set them exactly as the real script does, in order.
4. **Synthetic tests for version-selection logic**: build a ladder dir (`34.0.0 35.0.0 35.0.1 36.0.0-rc1`) to prove `ls | sort -V | tail -1` picks the highest, and an empty dir to prove the guard (`[[ -n "$X" ]] || exit 1`) fires.
5. **sed capture trap when extracting version fields**: `s/.*versionCode \([0-9]*\).*/\1/p` ALSO matches comment lines that merely contain the word ("Monotonic versionCode so it") with a zero-digit capture, so `head -1` returns empty. Anchor it: `s/^[[:space:]]*versionCode \([0-9]*\).*/\1/p`. Rule: always anchor regexes when pulling version fields from build files.
6. **Stale-scaffold trap**: a root `package.json` (Expo/React-Native) can describe an app that no longer exists (replaced by native Kotlin). `npm run test` then fails (`jest: command not found`). Before trusting npm as a harness: `find . -name '*.test.js' -o -name '__tests__'`, `ls node_modules`, check for the scaffold's `app/` dir. If all absent, the scaffold is vestigial — verify at the shell level and report the scaffold as a cleanup finding; do NOT install the toolchain to satisfy it.

Session detail (mazemaker-mobile, 2026-08-07 — the 5 files, verified current state, fantasy-file list, verification commands): `references/docs-build-alignment-2026-08-07.md`.

## Post-audit phase: lint pass & dependency freeze (Android, 2026-08-07)

"Lint-Fehler, vollständig übernehmen" = run the lint pass as a closing gate of the fix campaign (after code fixes, before release build). Triage discipline:

1. **Run `./gradlew :app:lintDebug` and count by severity + issue-id.** Parse the XML (`lint-results-debug.xml`) for `(severity, id)` counts, not the HTML. Typical profile: 0 Errors, ~25 Warnings, 2 Informations — of which the majority is `GradleDependency` noise ("newer version available"), NOT real issues. Fix the real code issues; do NOT chase dependency noise.
2. **Real-issue fixes that recur:**
   - `OldTargetApi`: raise compileSdk+targetSdk TOGETHER (targetSdk must never exceed compileSdk). Then document the freeze — Lint will flag 36 as "latest"; a comment explaining "35 is deliberate, every pinned dep is tested against 35, bump with the Kotlin/Compose upgrade" is the fix, not an upgrade.
   - `ObsoleteSdkInt`: `mipmap-anydpi-v26` is obsolete when minSdk==26 → move to `mipmap-anydpi` (git mv).
   - `DataExtractionRules`: `android:dataExtractionRules` needs `tools:targetApi="31"` AND `android:fullBackupContent` (the API-26–30 gap) when minSdk < 31.
   - `AutoboxingStateCreation`: `mutableStateOf(0L/0f)` → `mutableLongStateOf`/`mutableFloatStateOf`.
3. **Deliberate trust decisions get `@SuppressLint` + a reason comment, NOT logic changes.** The lint warning is often correct in general but wrong for a TOFU/pinning design: empty `checkServerTrusted`/`checkClientTrusted` in a TOFU cert-fetch path is the POINT (the real trust anchor is the sha256(SPKI)==fp check after), and a composite System-OR-ISRG trust manager delegates to real stores (Lint can't see the delegation). Suppress with the why.
4. **Dependency freeze is a decision, not a missed upgrade.** Compose/Kotlin/AGP are a tuned set (Compose 1.7.6 ⇄ Kotlin 1.9.24 ⇄ AGP 8.4.2); Lint offering 1.11.4/2.11.0 does NOT mean upgrade — a major bump breaks the set. Upgrade only pure patch releases (appcompat 1.7.0→1.7.1). Record the freeze decision in memory/report so it doesn't get re-litigated.

**Pitfall: Gradle `--rerun-tasks` + a res-move = FALSE compile failure (bit twice, 2026-08-07).** After moving `res/mipmap-anydpi-v26` → `mipmap-anydpi` (or any build-visible renames), a subsequent `./gradlew --rerun-tasks` fails with `Failed to create MD5 hash for file: .../kotlin-classes/...class (Datei oder Verzeichnis nicht gefunden)` and `Cannot access output property 'destinationDirectory'`. That is STALE DAEMON/INCREMENTAL STATE, NOT a code error — the resource error that started it (AAPT `resource mipmap/ic_launcher not found`) is also stale-state, not the rename being wrong. Recovery: `./gradlew --stop` then `./gradlew clean` then the NORMAL build (no `--rerun-tasks`). Do not "fix" the code while Gradle is in this state; verify with a clean build first.

## Pitfall: server-pushed message types missing from client handler

(observed 2026-06-19 on jrwl-messenger)

**Twinned failure mode to "wires-not-wired"**: the server side pushes a message type X to the client (over WS, SSE, push notifications, etc.), the client handler has no `case 'X':` branch for it, and the message is silently dropped. No error, no log, no UI feedback — the data simply disappears.

Concrete example from jrwl-messenger Phase 8.1:
- The server (`gateway.py:_push_message_to_client`) had logic for THREE message shapes: double-ratchet, sender-key, and legacy base64. It correctly distinguished them and sent them as `type: 'message'`, `type: 'group_message'`, etc.
- The client `ui.html` `handleWSMessage()` switch had cases for `message`, `typing`, `auth_code`, `paired`, `sent`, `receipt`, `error` — but NOT for `group_message`.
- Group messages over WS were silently dropped on the client for the entire lifetime of Phase 7.5 (which had wired up the SERVER side of sender-key). The bug had been "live in production" for a week; nobody noticed because the HTTP poll fallback (`/api/messages/{id}`) DOES server-decrypt sender-key envelopes, so the bug only manifested for online users reading via WS.
- The client-side sender-key decryption (Phase 8.1) fixed it — but only because the audit asked "where do group messages go when they arrive over WS?" and the answer was "into the void."

**Recipe to catch this on audit:**
1. **List every `ws.send(...)` or `broadcast_to(...)` on the server.** Extract the `type` field.
2. **List every `case 'X':` in the client's `onmessage` / `handleWSMessage`.**
3. **Diff.** Any server-side type without a client-side case = silent data loss.
4. **For each pair, verify the client's handler actually USES the payload.** A case that just `console.log`s and returns is the same as no case for production purposes.
5. **Run an end-to-end test that exercises the WS path, not just HTTP.** The HTTP path may have a fallback (decrypt server-side, push plaintext) that masks the WS handler bug.

**Generalises beyond WS**: any push channel (SSE, webhook delivery, push notifications, MQTT topics, AMQP routing keys, gRPC server streams) has the same failure mode. The "audit checklist" is identical: enumerate producer message types, enumerate consumer handlers, diff.

**The fix is usually one line** (`case 'group_message': handleIncomingGroupMessage(data); break;`), but only IF you know to look for it. Without the diff, you'll never know it's missing because nothing errors — messages just go to /dev/null.

## Pitfall: audit checks that generalize across project types (mazemaker-mobile, 2026-08-07)

Second application of the parallel-readonly-audit methodology, this time on an
Android/mobile monorepo (Kotlin + installer APK + iOS SPM + TS) instead of a
Python backend. Four checks paid off that were NOT in the original checklist —
add them to any audit:

1. **Storage-encryption consistency**: inventory WHERE each secret lives
   (EncryptedSharedPreferences vs DataStore vs plain SharedPreferences/JSON)
   and diff against the project's own "encrypted at rest" claims. Canonical
   find (mazemaker-mobile): the pod token was in EncryptedSharedPreferences
   (AuthManager) while the GATEWAY token — the secret for the encrypted
   gateway channel — sat in plaintext DataStore (PreferencesManager). Same
   class of secret in two storage mechanisms = finding, even if one is
   encrypted. Cheap grep: `grep -rn "stringPreferencesKey\|GATEWAY_TOKEN"` +
   compare with `EncryptedSharedPreferences`.

2. **Interceptor-swallowed retry = dead retry path**: an OkHttp/middleware
   interceptor that catches IOException and returns HTTP-200 stubs makes the
   repository's IOException-retry branch unreachable (retry logic only fires
   on `code == 500`; the stub's `retryable:true` is never evaluated). Trace
   whether an upstream layer already converted the exception into a
   success-coded response before trusting retry code — the retry path may be
   dead while looking correct.

3. **Worktree/branch topology as an INTEGRATION finding**: `git worktree
   list` + `git merge-base --is-ancestor <tip> <branch>` reveals divergent
   parallel work lines, unmerged release branches, and version drift between
   what a build script bundles and what the checked-out code actually is
   (found: release 1.4.0/versionCode 7 was NOT an ancestor of the live
   checkout at versionCode 6, while the installer bundled 1.4.0). Run this
   BEFORE trusting any "current state" claim about a repo.

4. **Dormant crypto/bad-code severity mitigation**: grep for importers before
   assigning CRITICAL to broken crypto or networking code. Code that nothing
   imports is a bomb, not a live vulnerability — downgrade severity, flag it
   as dead code that must never be wired without a rewrite (found: fake X3DH
   in TS `jrwl_crypto.ts` and iOS `X3DH.swift` with non-persistent keys — both
   unreferenced).

Full mobile-application detail (stream mapping for mobile, 8 verified checks,
process notes): `references/mobile-app-audit-2026-08-07.md`.
