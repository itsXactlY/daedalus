# Fix-Campaign Crew: Audit → Production-Readiness (mazemaker-mobile, 2026-08-07)

Overseer-driven wave pattern that took a 2-CRITICAL / 15-HIGH audit to a shipped,
live-verified production release in one session. This is the WRITE side of the
audit loop — pair it with `references/parallel-readonly-audit-2026-08-07.md` (read side).

## Wave orchestration (the core loop)

- Split audit findings into WAVES of ≤3 parallel `delegate_task` agents, each on a
  STRICTLY DISJOINT file sphere (no two agents touch the same file). Group by
  file-family (e.g. jackbox/, PreferencesManager+Auth, PodWebSocket), not by concern.
- Agents are IMPLEMENT-ONLY. Brief must say: "NUR die zugewiesenen Dateien ändern.
  KEIN git commit/add (macht der Aufseher). KEIN gradle/Build/Tests (der Aufseher
  kompiliert nach jeder Welle)." This eliminates git race conditions from parallel work.
- Briefs must carry: exact file paths + line numbers from the audit, the concrete
  before-code, the target behavior, and "Lese die Datei vollständig zuerst."
- Overseer loop per wave: dispatch (background) → on batch completion read `git diff`
  YOURSELF (agent summaries are self-reports and lie) → compile + run tests YOURSELF →
  commit with the project's commit convention → next wave.

## Verification level = the project's real harness (Android/Gradle case)

- When the system/grader asks for `npm run test` and the project is Android/Gradle:
  there is NO package.json — the concrete blocker is "no npm in this repo". The correct
  harness is Gradle + artifact inspection, NOT npm:
  - `./gradlew :app:testDebugUnitTest` — then read the XML results
    (`app/build/test-results/testDebugUnitTest/*.xml`: tests=, failures=, errors=).
    Do NOT trust the "BUILD SUCCESSFUL" line alone.
  - `ANDROID_HOME` is NOT exported in a bare shell (build scripts set it themselves).
    Export `ANDROID_HOME=$HOME/Android/Sdk` before bare gradle runs, or you get
    "SDK location not found" — an environment error, not a code error.
  - APK proof: `aapt2 dump badging app.apk | head -1` (version) and
    `aapt2 dump permissions app.apk` (permission presence).
  - `apksigner verify --print-certs app.apk` proves the release cert.
- Gradle task names that matter: `:app:compileDebugKotlin`, `:app:testDebugUnitTest`,
  `:app:assembleRelease` (signed when keystore.properties exists).

## Release strategy pitfalls (learned the hard way)

- Before shipping, check VERSION DRIFT between the live checkout and the release
  branch: `git show release/<tag>:android/app/build.gradle | grep -E "versionCode|versionName"`.
  The packaged box may bundle a NEWER payload (e.g. 1.4.0/code 7) than the checkout
  (1.3.1/code 6) — a build from the checkout would be a downgrade devices reject.
- Merge the release branch into the live branch to pull its features, THEN bump
  versionCode MONOTONICALLY (8 > 7) so devices with the shipped version accept the update.
- Auto-updater logic `installed < remote.versionCode` means: same versionCode never
  gets pulled. Bump or the fix never reaches existing devices (dead auto-update = the
  exact bug being fixed).
- Verify the SHIPPED artifact, not the source: aapt2 badging/permissions on the
  built APK, plus curl the live manifest/APK after publish (HTTP 200 + new version).

## Branch / worktree cleanup

- Obsolete check: `git rev-list --count <branch>..HEAD` → 0 = fully contained in HEAD.
- Tag before delete: `git tag crew-archive/<branch> <branch>` then `git branch -D`.
- `git worktree remove --force <path>` BEFORE `git branch -D` (the worktree pins the branch).

## Audit → fix verification rule

- After a fix wave, ALWAYS verify worker CRITICAL claims yourself (this session: all
  5 survived; the previous audit's 3 were all refuted — never assume the direction).
- After merging a release branch that touches files the crew already fixed, grep for
  the fix markers (e.g. `gatewaySecret`, `hermesChatGen`) to confirm BOTH sides of the
  merge survived, then compile. Semantic merge conflicts are silent.
