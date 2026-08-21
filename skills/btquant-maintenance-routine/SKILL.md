---
name: btquant-maintenance-routine
description: Reusable approach for maintaining BTQuant trading infrastructure projects with dependency, linting, type checking, and test validation
category: devops
---

# BTQuant Maintenance Routine

## Overview
Reusable approach for maintaining BTQuant (trading infrastructure) projects with dependency checking, linting, type checking, and test execution. Handles common issues with externally managed environments and complex project structures.

## Trigger Conditions
- Scheduled maintenance of BTQuant/PubBTQuant projects
- Pre-deployment checks
- Post-update verification
- Regular system health monitoring for trading infrastructure
- User asks to build a "Quantower-like" visual feature for the trading terminal
- User reports "nothing renders", "no candles", "blank UI", "disgusting dogshit visuals"

## Prerequisites
- Access to ~/projects/PubBTQuant/
- Existing virtual environment at venv/
- Basic understanding of BTQuant project structure
- write_file and memory tool access

## Procedure

### 1. Environment Setup
```bash
cd ~/projects/PubBTQuant/
source venv/bin/activate  # Use existing venv to avoid externally-managed-environment errors
```

### 2. Dependency Verification
```bash
# Check current package state and count
pip list --format=json | wc -l  # Get package count

# Output package list for documentation
pip list --format=json > pip-list.json  # Save for reporting

# Verify requirements are met (installs to venv, not system)
pip install -r requirements-dev.txt  # Safe to run even if already installed
```

### 3. Linting Analysis (flake8 or ruff)
```bash
# Primary: flake8 with BTQuant exclusions
flake8 . --count \
  --exclude=.git,__pycache__,venv,.benchmarks,.btq_cache,.mypy_cache,.ruff_cache,.pytest_cache,.claude \
  --max-line-length=120 \
  --statistics

# Fallback: ruff (often pre-installed when flake8 missing)
ruff check hotspine/ --output-format=concise
# Output: Shows file:line:col error codes (F401 unused imports, E402 import order issues)
```

### Linting Tool Availability Notes
**flake8 not installed**: If `python3 -m flake8` fails with "No module named flake8", fall back to `ruff check` which is commonly available in Hermes venvs. Both tools catch the same core issues (unused imports, line length, import order) with equivalent actionability.

### 4. Type Checking (mypy)
```bash
# Handle duplicate module issues by excluding problematic directories
# NOTE: mypy --exclude uses regex with | separator, NOT comma-separated
mypy . --exclude='\.git|__pycache__|venv|\.benchmarks|\.btq_cache|\.mypy_cache|\.ruff_cache|\.pytest_cache|\.claude|dependencies' --ignore-missing-imports

# Alternative: Check specific modules (still useful when root-level syntax errors block full pass)
mypy hotspine/ --ignore-missing-imports --exclude='\.git|__pycache__|venv|\.benchmarks|\.btq_cache|\.mypy_cache|\.ruff_cache|\.pytest_cache|\.claude|dependencies'
```

### 5. Test Execution
```bash
# Run HotSpine-specific tests
python -m pytest hotspine/ -v

# Run MS SQL hotswap tests
python -m pytest test_ms_sql_hotswap.py -v

# For examples/tests in test/new structure:
cd tests/new/examples  # Or relevant subdirectory
python -m pytest . -v
```

### 6. Results Documentation
Create structured session state report:
```markdown
# BTQuant Trading Infrastructure - Cron Report
**Report Time:** [CURRENT TIMESTAMP]
**Maintenance Type:** Hourly Pulse Monitoring

## Critical Status
- HotSpine SHM `/dev/shm/BTQ`: ACTIVE|MISSING
- MCP Adapter port 8910: LISTENING|OFFLINE
- market_data_collector: RUNNING|STOPPED

# If BOTH SHM and collector are MISSING/STOPPED:
#   All pulse signals referencing these components are NON-ACTIONABLE
#   Report as "🔴 CRITICAL: ALL TRADING SYSTEMS OFFLINE"

## Pulse Signals
| Signal | Source | Score | Actionable? | Notes |
|--------|--------|-------|-------------|-------|
| [List top signals with actionability assessment] |
```

### 7. Pulse Signal Actionability Check (REQUIRED)
After pulse_search returns candidates:
```
IF signal references BTQ component (watchlist_panel, HotSpine, detectors)
AND component is offline (SHM missing OR process not running)
THEN mark signal as NON-ACTIONABLE with ⚠️ status
DO NOT report monitoring-level signals as trading opportunities
```

### 7.5. Live System End-to-End Verification (REQUIRED — added 2026-06-18 after the HEADER_SIZE silent-corruption incident)
Compile-clean and SHM-present are NECESSARY but NOT SUFFICIENT. The HEADER_SIZE 80 vs 4096 bug compiled cleanly, the producer started, the consumer connected — and silently read denormal noise prices. Only an end-to-end smoke test catches layout drift.

After every maintenance cycle that touches SHM / producer / consumer code:

1. **Producer FD health:** `lsof /dev/shm/btquant` → must show producer PID with live FD. If "No such file or directory" but `ps` shows producer running → zombie FD state (see pipe-break pitfall above), kill + restart.
2. **Consumer actually reads data:** run BTQuantTerminal briefly, check log for "Orderbook Full Sync from 0 to N" where N > 100, plus trade count > 0.
3. **Sanity check the data:** spot-check recent trade prices AND orderbook symbol_ids. They should be in normal float range (e.g. BTC $80k-$90k) AND symbol_ids in range 1-20 (matching `/dev/shm/btquant_symbols.json`). Prices like 2.12e-314 (denormal) or symbol_ids like 2965605936 (garbage) = SHM layout drift.
4. **Pulse signal actionability:** only mark signals referencing live BTQ components as actionable AFTER this verification passes.
5. **Check for parallel-agent commits (added 2026-06-18).** BTQuant repos are routinely worked by multiple agents in parallel (kanban workers, cron jobs, openhands sessions). Before starting work, run `git log --since="10 min ago" --format="%h %an <%ae> %s"` and verify only YOUR agent's commits landed since your last check. If a different author committed in your window (e.g. `openhands@all-hands.dev`, kanban-bot, tpad-brain), STOP and `git show <sha>` to see what they changed — it may interact with your work. Observed case: openhands agent committed `5d5a4e0a` (HEADER_SIZE 80→4096 fix + watchlist config) between an assistant's Phase 3.3/4.2 commits and the assistant's next commit — same files were already touched by the other agent. Caught by `git log` between `git add` and `git commit`.

If step 3 fails: jump to SHM Layout Drift pitfall above. Verify all 8 constants in `references/btquant-shm-layout.md` match between Python and C++. Restart producer + consumer after fix.

### 8. Memory Management
Proactively manage agent memory before saving significant updates:
- Check current memory usage
- Remove oldest/redundant entries if nearing limit
- Add maintenance summary as new memory entry

## Common Issues & Solutions

### Externally Managed Environment
**Problem:** `error: externally-managed-environment` when using system pip
**Solution:** Always use project virtual environment (`source venv/bin/activate`)

### Duplicate Module Detection (mypy)
**Problem:** `Duplicate module named "setup"`
**Solution:** Exclude conflicting directories:
```
--exclude=dependencies,dependencies/MsSQL
```

### Test Collection Errors
**Problem:** Import errors in test configuration
**Solution:** Run tests from specific directories rather than project root when dealing with complex import structures

### HotSpine sys.exit() Crash (all test files)
**Problem:** ALL hotspine test files contain `sys.exit()` at module level — not just test_hotspine_basic.py
**Affected files (verified 2026-03-31):** test_hotspine_basic.py:89, test_hotspine_reader.py:22, test_hotspine_comprehensive.py, test_hotspine_core.py, test_hotspine_integration.py, test_hotspine_simple.py, test_hotspine_system.py, test_hotspine_sql_architecture.py
**Workaround:** `python -m pytest hotspine/ --ignore=hotspine/test_hotspine_basic.py` still crashes on other files. Use `test_ms_sql_hotswap.py` (9/9 passing) as the only currently runnable test suite.
**Fix:** Wrap all `sys.exit()` calls in `if __name__ == "__main__":` guards

### SHM Layout Drift Between Python Producer and C++ Consumer (SILENT data corruption)
**Problem:** `mock_data_producer.py` (Python) was writing trades at SHM offset 80 (`HEADER_SIZE = 80`), but `HotSpineDataBridge` (C++) reads at offset 4096 (`HOTSPINE_HEADER_SIZE = 4096`, cache-line aligned). The first ~4016 bytes of "trades" were mmap noise — price=2.12e-314 denormal, size=0. **Consumer didn't crash, didn't error — just showed empty/garbage data.** Only an end-to-end smoke test (build + run + observe actual trade flow) caught it.

**Second variant (2026-06-18):** Python writes orderbooks at stride 6464 (with 40 bytes of 64-byte-alignment pad), but C++ `HotOrderbookSnapshot` without `alignas(64)` had `sizeof = 6424`. C++ ring-buffer stride was 6424 — after the first OB the consumer read misaligned slots and got garbage `symbol_id`s (e.g. 2965605936 instead of 1-20). Trade data was fine because `HotTrade`'s natural sizeof(40) already matched.

**Root cause:** Two files independently defining the SHM layout. The Python producer was written before the C++ cache-line-alignment optimization and never updated. Unit tests in each file passed individually because the offsets are correct within each file. The OB stride case is subtler because `sizeof` differs by exactly the pad size (40 bytes) — Python's `alignas(64)` comment was the only documentation of the intent.

**Fixes:**
- commit `5d5a4e0a`: `HEADER_SIZE = 4096` in `mock_data_producer.py`. Smoke test confirmed zero "Invalid trade data" warnings.
- commit `6e0cf798`: Add `struct alignas(64) HotOrderbookSnapshot { ... };` in `include/hotspine_data_bridge.hpp`. OrderbookPanel now shows real symbols (BTCUSDT ID=1), `ActiveSyms=20`.

**Defensive rule for the future:** SHM layout constants MUST be defined ONCE and SHARED between producer and consumer. For Python+C++ systems: either generate the Python constants from the C++ header at build time, OR pin them in a shared `btquant_shm_layout.py` module that both sides reference. Never let drift accumulate.

**Symptom → cause mapping:** See `references/btquant-shm-layout.md` for the full table. Highlights:
- denormal prices → HEADER_SIZE mismatch
- `UNKNOWN (ID=<huge int>)` in OrderbookPanel, `ActiveSyms` growing unbounded → `alignas(64)` missing on OB struct
- Trade count = 0 but consumer connects → SHM file missing or zombie FD (see pipe-break pitfall)

### Producer Startup with `| head -N` Pipe-Break → Zombie with Deleted FD
**Problem:** Bash pattern `python3 mock_data_producer.py 2>&1 | head -10` is meant to "show first few lines of output then keep running in background". It DOES NOT WORK:
- `head -10` exits after reading 10 lines → pipe breaks → producer's stdout/stderr become broken pipe
- If producer survives (SIGPIPE not fatal in mmap write loop): keeps FD open to the SHM file
- Meanwhile, something deletes the SHM file (another `rm -f` from a restart loop, a watchdog, manual rm, or the producer's own unlink)
- Result: producer writes to a `(deleted)` inode. No consumer can open the file by name. Wasted CPU, no functional data flow.

**Diagnosis (2026-06-18, observed live):**
- `lsof /dev/shm/btquant` → "No such file or directory"
- `ls -la /proc/<producer_pid>/fd/` → shows `lrwx 4 -> /dev/shm/btquant (deleted)`
- `ps -p <pid>` → producer still "running" with full CPU but no useful output

**Fix:**
1. `kill -9 <producer_pid>` the zombie
2. Restart WITHOUT the pipe-to-head. Either:
   - Background with logfile: `nohup python3 mock_data_producer.py > /tmp/btquant-producer.log 2>&1 &`
   - Detach from controlling terminal: `setsid python3 mock_data_producer.py > /tmp/btquant-producer.log 2>&1 < /dev/null &`
   - **Or via Hermes `terminal(background=true, notify_on_complete=false)`** for long-lived producers — Hermes tracks the lifecycle and you can poll via `process(action='poll')`.
3. Verify: `lsof /dev/shm/btquant` should now show the producer PID with a live (non-deleted) FD.

**Rule:** Never pipe a long-running producer through `head`, `tail -f`, `grep -m1`, or any consumer that exits. Use logfile redirection. If you need to see early output, `tee` to a logfile AND let the producer keep writing — `python3 mock_data_producer.py 2>&1 | tee /tmp/btquant-producer.log &`.

### ImGui PushID/PopID Leak → "Nothing Renders, No Errors" (added 2026-06-18)
**Problem:** A panel's render loop pushes TWO `ImGui::PushID()` calls per row but pops only ONE `ImGui::PopID()` at the end of the iteration. Every row leaks 1 ID per frame. After thousands of leaked PushIDs, ImGui's internal ID stack is deeply corrupted — every subsequent widget ID is wrong, so widgets either don't render or render in wrong parents. The application doesn't crash; it just looks like "nothing works".

**Observed case:** `WatchlistPanel` rendered 20 watchlist rows × 60 fps × however long the user runs. PushIDs at line 1227 (column 0 Symbol) and line 2051 (column 10 Action). Only one PopID at line 2131 (end of iteration). Log showed 4283 `[imgui-error] Mismatching PushID/PopID!` messages — these weren't just noise, they were the canary. The user's complaint "nothing of the visuals working correctly, no candles, nothing" was this bug, not the Quantower feature work.

**Diagnosis recipe:**
1. `grep -c "imgui-error" /tmp/btquant_terminal.log` → if > 0, you have ID stack corruption.
2. `grep "imgui-error" /tmp/btquant_terminal.log | grep -oE "In window '[^']+'" | sort -u` → which panel.
3. In that panel's render code, `grep -nE "PushID|PopID"` — count PushIDs vs PopIDs in the same scope (e.g. inside a for loop). They must balance 1:1.
4. Fix: add the missing `PopID()` (or remove the extra `PushID()`) so they match.

**Fix (commit b0171064):** Added the second `PopID()` at the end of the WatchlistPanel per-row loop, matching the PushID at line 2051.

**Rule:** Every `ImGui::PushID` MUST have a matching `ImGui::PopID` on every code path (including early returns, exceptions, conditionals). Use RAII guards (`ImGui::PushID id(id); ... auto _ = ImGui::PopID();`) in C++ if the scope is non-trivial. The ImGui ID stack is a critical global resource — corruption from leaks propagates to EVERY subsequent widget.

### Visual Features Rejected by User → Revert Immediately (FIRST-CLASS user preference, 2026-06-18)
**Problem:** The user asked for "Quantower-style" features (ImGui docking, order flow bars on candles, TPO panel data wiring). The implementation was technically functional — docking flag set, panels draggable, order flow split bars rendered. But the visual result looked like "disgusting dogshit" (user's words). I kept defending the work ("theoretically everything is working") instead of reverting. The user got more frustrated and demanded removal.

**Lesson:**
- When the user says "get rid of it", "remove it", "revert it", "this looks bad" — DO IT IMMEDIATELY. Don't explain why it's working. Don't defend the work. Don't suggest alternatives. Revert and report.
- The user is the architect/observer. They see the visual result. "Working in theory" is not success. "Working AND looking right" is success.
- Visual features for the trading terminal need to match the Quantower aesthetic — clean, professional, well-proportioned. A custom default dock layout, colored split bars inside candles, etc. can easily look amateurish if not carefully designed.
- **Before adding a visual feature**, ask: is this the look the user wants? If unsure, prototype minimally first, get feedback, THEN expand.
- **If the user rejects visual work**, the right response is `git revert` (or `git reset --hard` to before the visual commits + cherry-pick any non-visual commits back). Don't try to "fix" the visuals — the user has already seen them and doesn't want them.

### Long Iterative Development Without `git push` = Data Loss Risk
**Problem:** Branch `0.0.2` accumulated 19 unpushed commits (15 from 100-iteration code review + 3 from a session + 1 from a parallel agent). Working tree was clean but the local repo was 19 commits ahead of `origin/0.0.2`. If the machine died, all that work would be lost — including a critical bug fix (HEADER_SIZE 80→4096).

**Detection:** `git rev-list --left-right --count origin/<branch>...HEAD` shows the gap. Compare to expected delta after your work.

**Rule:** Push after every meaningful work block, NOT at "the end of the project". For BTQuant-style iterative review work, push every 5-10 commits. For active development, push before any operation that risks corrupting local state (rebase, large merge, force push).

**What "push" means here:** `git push origin <branch>` — fast-forward if no remote-side commits, merge commit if there are. NEVER `--force` unless explicitly asked; the user values "ship complete work" over rewrites.

### Parallel Agent Commits Stack On Top Of Your Work
**Problem:** This codebase is routinely worked by multiple agents in parallel — kanban workers, cron jobs, openhands sessions, the assistant itself. The openhands agent committed `5d5a4e0a` (HEADER_SIZE fix) and `b0171064` (PopID fix) on top of the assistant's Quantower work. This caused a nasty `git revert` interaction when the user asked to revert the Quantower commits: `git reset --hard b0171064` left the working tree containing Quantower code because `b0171064` was a later commit that included both the PopID fix AND the (then-reverted) Quantower code from the openhands agent's perspective.

**Mitigation (added to verification step 5 above):** Before any reset/revert, run `git log --since="10 min ago" --format="%h %an <%ae> %s"`. If you see commits from agents other than yourself, check what they did — they may have either helped (bug fixes) or stomped on your work.

**Recovery recipe for "revert visual commits but keep a later parallel-agent bug fix":**
1. `git reset --hard <commit-before-visual-work>` (e.g. `6e0cf798` for the orderbook stride fix, which predates the Quantower commits)
2. `git cherry-pick <parallel-agent-fix-commit>` (e.g. `b0171064` for the PopID fix)
3. Verify the cherry-pick brought only the intended changes: `git show HEAD --stat`
4. Rebuild and smoke-test

### test_hotspine_reader.py Stale Import
**Problem:** `ImportError: cannot import name 'HotSpineRuntime' from 'backtrader.hotspine.reader' (test_hotspine_reader.py:18)`
**Cause:** `HotSpineRuntime` class was removed/renamed — test import is stale
**Fix:** Remove `HotSpineRuntime` from the import line: `from backtrader.hotspine.reader import HotSpineReader, HotTrade`

### test_configuration.py Stale Import
**Problem:** `ImportError: cannot import name 'HotSpineRuntime' from 'backtrader.hotspine.reader'`
**Cause:** `HotSpineRuntime` class was removed/renamed — test import is stale
**Fix:** Update import to current class name or remove test

### pip install -r requirements-dev.txt may succeed but pip list JSON has trailing noise
**Problem:** `pip list --format=json` sometimes appends non-JSON text after the array, causing `JSONDecodeError: Extra data`
**Fix:** Find last `]` in output and slice: `pkgs = json.loads(text[:text.rfind(']')+1])`

### Memory Limits
**Problem:** Exceeding agent memory capacity
**Solution:** Proactively remove older entries before adding new ones, prioritizing recent operational data

## Verification Steps
- [ ] Virtual environment activated successfully
- [ ] Dependency check completed without blocking errors
- [ ] Linting run completed (informational - failures don't halt process)
- [ ] Type checking completed with appropriate exclusions
- [ ] Critical test suites passing (HotSpine, MS SQL hotswap)
- [ ] HotSpine shared memory active at `/dev/shm/BTQ`
- [ ] Market data collector process running (verify live data feed)
- [ ] MCP adapter listening on port 8910
- [ ] Pulse signals checked for actionability
- [ ] Live system end-to-end smoke test passed (trades flow, prices sane, OrderbookPanel shows real symbols, 0 imgui-errors)
- [ ] Parallel-agent commits checked
- [ ] Session state documentation created
- [ ] Memory entry added successfully

## Reporting
- Primary output: Session state markdown file at `~/proactivity/session-state.md`
- Secondary: Agent memory entry for cross-session awareness
- Optional: Discord/webhook notifications if configured

## Time Estimation
- Quick check (deps + basic tests): 5-10 minutes
- Full routine (linting + type + comprehensive tests): 15-25 minutes
- Factors: Test suite size, network speed for downloads, issue resolution time

## Notes
- BTQuant prioritizes existing infrastructure reuse over rebuilding
- Focus on HotSpine integration and MS SQL hotswap as critical paths
- Example files often have linting issues - core framework quality is priority
- Regular maintenance prevents accumulation of technical debt in trading systems
- The trading terminal has accumulated years of feature requests from the user. When adding visual features, match the Quantower aesthetic (clean, professional, well-proportioned) — if in doubt, prototype minimally and ask before expanding. The user is the architect/observer; visual quality matters as much as functional correctness.

## References
- `references/cron-report-template.md` — Hourly pulse monitoring template with actionability thresholds
- `references/btquant-shm-layout.md` — Canonical SHM constants (Python producer ↔ C++ consumer) + symptom→cause table + recovery recipe. Covers HEADER_SIZE (commit 5d5a4e0a), alignas(64) OB stride (commit 6e0cf798), and the WatchlistPanel PushID leak (commit b0171064) — three SHM/rendering layout bugs found in one session, all caused by missing shared-source-of-truth between layers.
