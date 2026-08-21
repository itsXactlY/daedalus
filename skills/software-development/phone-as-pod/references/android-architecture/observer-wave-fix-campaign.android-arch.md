# Observer-Mode Wave Execution — post-audit fix campaigns (verified 2026-08-07)

How the mazemaker-mobile production-reife campaign ran: supervisor-in-session
("Aufseher") delegation over an Android/Gradle monorepo, 3 waves, all fixes
from a 2-CRITICAL/15-HIGH audit shipped + released in one session.

## The wave pattern

1. **Split the fix list into disjoint file-spheres, 3 per wave** (config cap
   `delegation.max_concurrent_children=3`). Every agent gets an explicit
   "NUR diese Dateien, KEINE anderen" list. Spheres that worked:
   - Wave 1 (core/kill-features): installer manifest+worker / secret-storage /
     websocket-lifecycle
   - Wave 2 (logic): ViewModel races / repository+retry+cache / gateway+pairing
   - Wave 3 (polish): UI leaks+UX / docs+build-scripts
2. **Agents implement but DO NOT commit.** Hard rule in every brief: "KEIN git
   commit/add — macht der Aufseher." Removes git-race / merge-conflict between
   parallel workers; observer owns one linear history.
3. **Agents DO NOT build either** ("KEIN gradle/Build/Tests"). Parallel gradle
   runs fight over the Kotlin daemon → false `e: Daemon compilation failed:
   null` mid-wave (saw this twice; clean `--rerun-tasks` after the wave passed).
4. **Observer verification between waves:**
   - `git diff --stat` + read the actual diffs (self-reports lie; diff is truth)
   - compile+test yourself, then read the XML result files, don't trust
     "BUILD SUCCESSFUL" alone
   - artifact-level claims need the real tool: aapt2 badging for
     versionCode/permissions, `git check-ignore -v` for .gitignore, `bash -n`
     for shell scripts
   - then `git add` + `git commit` with a wave-summary message listing every
     fix + verification evidence
5. **Branch/release integration is its own wave-step:** merging a release
   branch into the live branch requires a versionCode bump (monotonic over the
   shipped payload) or installed devices refuse the update. The installer box
   itself must bump too (1.0.5→1.0.6) or its own auto-updater
   (`installed < remote.versionCode`) never pulls the fix. Verify the new
   version lands in the artifact (aapt2 badging / BuildConfig.java), not just
   in the .gradle file.
6. **Release + live-publish after all waves:** signed release APK → repo's
   publish script → verify the LIVE endpoint (curl manifest, HEAD APKs HTTP
   200). Never claim a deploy from the local artifact alone.

## Android/Gradle verification harness (no npm)

The generic "run npm test" gate does not exist here. Correct verification:

```bash
export ANDROID_HOME=$HOME/Android/Sdk   # bare shells lack it; build scripts set it
./gradlew :app:compileDebugKotlin       # compile gate
./gradlew :app:testDebugUnitTest        # unit tests
# read the XML, don't trust the summary:
for f in app/build/test-results/testDebugUnitTest/*.xml; do
  grep -o 'tests="[0-9]*" skipped="[0-9]*" failures="[0-9]*" errors="[0-9]*"' "$f"
done
# artifact claims:
~/Android/Sdk/build-tools/36.0.0/aapt2 dump badging app/build/outputs/apk/release/app-release.apk
~/Android/Sdk/build-tools/36.0.0/aapt2 dump permissions app/build/outputs/apk/release/app-release.apk
# config claims:
git check-ignore -v .claude/
bash -n jackbox/build-box.sh
```

## ADB device deploy + smoke test (Pixel 7 Pro verified)

```bash
export PATH=$PATH:~/Android/Sdk/platform-tools
adb devices -l                          # USB: model Pixel_7_Pro
adb install -r <app-release.apk>        # -r = upgrade, keeps data, same-signature required
adb shell dumpsys package <pkg> | grep -E "versionCode|versionName"   # confirm new version
adb shell am start -n <pkg>/.MainActivity
adb shell pidof <pkg>                   # process alive
adb logcat -d -t 200 | grep -iE "FATAL|AndroidRuntime.*<pkg>"        # no crash
```

## Findings that were real this time (vs. the earlier all-refuted audit)

The 2026-08-07 audit of mazemaker-mobile: ALL 5 crew CRITICAL/HIGH claims held
verification (unlike mazemaker-pro 2026-08-07 where 3/3 CRITICALs were
refuted). Top verified: TheBox-APK shipped WITHOUT `android.permission.INTERNET`
since its first commit → the entire auto-update feature was dead on arrival in
every published version (aapt2 dump permissions proved it); UpdateWorker used
`.first()` on a flow that emits `Installing` first → download/verify/commit
never ran. Both were one-line fixes that unlocked the whole release.
