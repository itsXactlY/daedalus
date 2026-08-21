# loop-engineering — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## Loop Types (built and tested)

### 1. Tri-State Cadence Loop (4 crons)
Discovery → Decision → Action → Measurement at 4 different cadences. The foundational pattern. Deploy as 4 separate cron jobs, each with its own model.

### 2. Pulse-Wurm 2.0 (stateful pulse)
Stateless pulse ticks are amnesiac. Make them stateful via a JSON state file and mazemaker writes. Each tick checks what was already discovered, uses lowest-saturation topics as seeds. Gets MORE curious over time.

**Key Implementation Details (2026-06-17):**
- Use `pulse_search(depth='deep')` for each seed topic
- Check results against `visited_urls` in state file to skip duplicates
- For unvisited URLs: attempt `pulse_dig(max_rounds=2, max_fetches=100)` but have fallbacks ready
- **Fallback 1:** Browser tools for web content (works even when direct HTTP is blocked)
- **Fallback 2:** Direct API calls (e.g., arXiv API via urllib) for scholarly papers
- **Fallback 3:** PDF extraction for papers (pdftotext or pikepdf)
- **Important:** Some sources (Reddit, certain sites) block automated access - mark as visited to prevent retry loops
- Write triple-memory pattern: discovery entry + fact + decision for graph enrichment
- Update state: append new URLs, increment saturation scores, reset consecutive_empty counter

### 3. Skill Rot Detector (weekly audit)
Reads all installed skills from disk, queries mazemaker_recall for connected `fact:*`/`decision:*`/`ops:*` labels, diffs skill instructions against what facts say actually happened. Rates drift: FRESH (<10%), STALE (10-40%), ROTTEN (>40%). Writes `signal:skill-drift-<skillname>` for rotten ones.

### 4. Failure Pattern Hardener (weekly meta-loop)
Reads `bug:*`, `signal:*`, `ops:*` from last 30 days, classifies each failure into a taxonomy (token_burn, hallucination_cascade, wrong_model_choice, worktree_collision, dependency_stall, context_overrun, permission_denied, tool_misuse, verification_failure). When same pattern appears ≥3 times and no guard exists yet, creates a cron guard or skill update. Writes `ops:guard-created-<pattern>`.

### 5. Intent Debt Auditor (weekly)
Measures the gap between what skills SAY the system does and what facts record it ACTUALLY does. Computes drift magnitude per skill (0-1), identifies drift vectors. Maintains drift_history.json as a time series.

### 6. Oracle Loop (daily)
Reads mazemaker_dream_insight cluster summaries. Each emergent Louvain community gets rated for novelty (persistent/evolving/novel). Writes `signal:oracle-cluster-*` per cluster and `signal:oracle-summary-*` overall. The comprehension debt cure — you can't fake a graph cluster.

### 7. Media Content Generation Loop (timer-driven pipeline)

A production pipeline that chains GPU-backed tools (ComfyUI video gen, local TTS) through an autonomous agent to produce finished media (YouTube shorts, episodic content). Unlike the other loop types which process text/analysis, this loop produces actual rendered media assets.

Architecture (distributed or local):

| Phase | Tool | Cadence | What it produces |
|-------|------|---------|------------------|
| 1. Conceive | Hermes + mazemaker_recall | Per tick | Story concept, based on trending graph clusters |
| 2. Script | Hermes | Per tick | Narration script (30-90 sec) + visual scene descriptions |
| 3. Voiceover | Qwen3-TTS or Edge TTS | Per tick | WAV audio file from script |
| 4. Visual | ComfyUI (WAN 2.2 / HunyuanVideo / LTX-2) | Per tick | Animated video segment(s) matching scene descriptions |
| 5. Assemble | ffmpeg | Per tick | Final video: visuals + voiceover + music/silence |
| 6. Publish | YouTube API or local save | Per tick | Upload or save to output directory |
| 7. Memorize | mazemaker_remember | Per tick | Log what was generated as `media:tick-<date>` |

**Mazemaker integration beyond storage.** The graph topology (node clusters, edge weights) can serve as literal visual content — e.g. generating maze/labyrinth layouts from spreading-activation paths through mazemaker's actual memory graph. This turns the control plane into the artwork.

**Distributed worker pattern.** When the orchestrator (e.g. a laptop with no GPU) schedules the loop, the GPU-heavy phases (ComfyUI, TTS) run on a separate worker machine exposed via HTTP API. The orchestrator sends scene descriptions, receives rendered video segments, and assembles them. This avoids GPU contention on the primary machine.

**Consistent character.** For episodic content, generate a character sheet once (ComfyUI I2V consistency LoRA or fixed seed) and reuse across ticks. The character becomes the series' brand.

**Labels to write:**

| Label | When | Purpose |
|-------|------|---------|
| `media:tick-<date>-<seq>` | After assembly | Durable record of what was produced |
| `media:concept-<seq>` | After conceive phase | The story concept for future ideation |
| `signal:media-quality-<seq>` | After manual review | Quality signal for automatic gating |

**Pitfalls specific to this loop type:**

- **GPU availability is NOT guaranteed.** A ComfyUI call can hang or OOM. Always wrap in a timeout (SIGALRM, 300s). Have a fallback: if ComfyUI fails, generate a simpler visual using Python/ffmpeg (no GPU needed) and produce the video anyway. A text-over-maze-scroll is better than nothing.
- **Consistency across ticks.** The whole point of a series is recognisable characters. If every tick generates a completely different visual style, there's no brand. Lock checkpoints, seeds, and model choices per series.
- **Audio sync drift.** LTX-2 can lip-sync, WAN 2.2 cannot. Track exactly which model was used per scene and whether post-processing sync is needed.
- **Token burn on conceive.** The idea-generation phase can eat 100k+ tokens per tick for diminishing returns. Cap it: one mazemaker_recall + one short script generation per tick, not open-ended ideation.
- **Orchestrator needs its own copy of Hermes.** The worker machine runs ComfyUI + optional Hermes; the orchestrator runs the cron job with its own Hermes profile. Never run the loop and ComfyUI in the same agent session — tool conflicts and CUDA monopoly.
- **YouTube API rate limits.** If publishing, stagger uploads to avoid quota exhaustion. Use unlisted uploads for review, then publish manually if the content is good enough.
- **Multi-hop SSH quoting breaks on special characters.** Script text with spaces/quotes/newlines gets mangled passing through `ssh host1 'ssh host2 "cmd"'`. Always encode script text as base64 or write to a temp file before SSHing. See `references/multi-machine-ssh-dispatch.md` for the full pattern.
- **Qwen3-TTS flash-attn warning pollutes stdout.** The model prints import-side warnings to stdout, not stderr. When using `subprocess.run(capture_output=True)`, scan backwards for the last JSON line instead of calling `json.loads()` directly on stdout.

**Model selection for media loops:**

| Phase | Model | Why |
|-------|-------|-----|
| Conceive | `deepseek/deepseek-v4-flash` | Fast, cheap ideas from graph recall |
| Worker ComfyUI | WAN 2.2 GGUF Q4 (16GB VRAM) | Best quality/VRAM ratio for video |
| Worker TTS | Qwen3-TTS 1.7B | Multi-voice, fits alongside ComfyUI |

### 7. Graph Enrichment Loop (integrated into Pulse-Wurm 2.0)
Complements stateful pulse by writing triple-memory patterns for each discovery to boost graph connectedness. Each discovery spawns: (a) discovery entry, (b) fact entry with core insight, (c) decision entry linking to potential actions. See `references/triple-memory-enrichment-pattern.md` for the pattern.
See `references/pulse-wurm-2.0-implementation-20260617.md` for the stateful pulse loop implementation.

**Content Fetching Fallbacks (2026-06-17):** When primary tools fail, use browser tools first, then direct APIs, then PDF extraction. See `references/content-fetching-fallbacks.md` for the decision tree.

**Pulse Search Timeout Handling (2026-06-17):** The `pulse_search(depth='deep')` call has a 120s timeout and may fail. Fallback pattern:
- First try: `pulse_search(depth='deep')` 
- Timeout fallback: `pulse_search(depth='quick')` 
- If both fail: use `pulse_research(depth='default')` as final fallback
- Parse results from the nested JSON structure: `result.body.ranked_candidates` contains the actual findings
- For each candidate, extract: `url`, `title`, `summary` from `source_items` array

**Result Parsing Pattern (2026-06-17):** Pulse search returns results wrapped in `{"result": "{\"status\": 200, \"body\": {...}"}` - the inner JSON must be parsed separately to access `ranked_candidates` and `items_by_source`.

### 8. Perpetual Worktree Crew Loop (nonstop rework — 2026-08-03 standard)

For "rework X until absolute perfection, loop 24/7/365, no end, parallel agents ALWAYS" requests.
The operator explicitly REJECTED cron cadence for this class (see Pitfalls: "Cron for perpetual
rework loops"). The proven replacement: a systemd user service running a bash supervisor that
loops forever with NO sleep between successful rounds, spawning up to 3 concurrent workers each
in its OWN git worktree.

Architecture (reference deployment: `/home/alca/projects/rework/`):

1. **Supervisor** (`loop-supervisor.sh`, infinite `while true`): no sleep on success → next round
   starts immediately. A short failure backoff (60s) is a crash guard only, never a scheduled break.
2. **Parallel workers**: each round spawns up to 3 `hermes -z "$(cat <prompt>)" --cli` processes,
   one per queue item. Each worker gets its own git worktree (`git worktree add <wt> -b crew/rN-wM`)
   → no file/index collisions; branches `git merge --no-ff` back to the main branch after the round,
   then branch+worktree removed.
3. **File-collision detection — COORDINATE BEFORE EDIT, never trust `files:`**. The old pattern
   deferred items whose declared `files:` clause overlapped an already-assigned item in the same
   round. That trusts the worker's self-reported `files:` list, which is FICTION: in Cheshire Fall
   round 1 an item declared 2 files and touched 8, and all three workers landed in `app.js` +
   `index.html` without knowing. Conflicts were only caught after the writes. Replace with a real
   coordination bus: a `crew` script on a shared dir where workers `claim` files atomically
   (`mkdir` O_EXCL, all-or-nothing) BEFORE editing, `handoff` when blocked, and `contract` to
   publish interfaces others build against. See `references/crew-coordination-bus.md`. The supervisor
   still passes `{{WORKER_ID}}`/`{{ROUND}}` to the worker prompt (Python substitution — never sed,
   queue items contain `|`), and additionally MEASURES real overlap after each round via
   `git diff master...crew/rN-wX --name-only` instead of trusting any self-report.
4. **Judge cadence**: every 5th round is a SOLO judge (`judge-prompt.md`) that inspects everything
   (code, artwork, design, visualization), writes `judge-verdict.md`: dimension verdict
   (3D static / 4D alive / 5D transcendent) + queue Q1..Q5 with `[OPEN]`/`[DONE]` prefixes and
   `files:` clauses. The queue is LAW for workers until the next judge. Judge also scores the crew's
   execution of the previous queue (0-100) — keeps the crew honest.
5. **Queue lifecycle**: workers pick the lowest-numbered `[OPEN]` item. After a successful merge the
   supervisor rewrites that line to `[DONE] ... (merged <short-hash>)` — never re-picked. No-change
   case: worker writes a `.item-done` marker file in its worktree → supervisor marks `[DONE]` without
   a commit (prevents both commit noise and infinite re-picking of already-done items). CRITICAL:
   `git merge --no-ff` of a branch identical to HEAD returns exit 0 ("Already up to date") WITHOUT
   moving HEAD — so compare `head_before`/`head_after`; only a merge that moves HEAD counts as
   success. Without this, workers that crash before committing get their items falsely marked
   `[DONE]`, the queue silently empties, and real work (e.g. the browser 5D-proof) never happens.
6. **Startup cleanup**: on daemon start, merge leftover `crew/*` branches that contain real commits,
   DROP empty ones (worker crashed before committing) — avoids merge-commit pollution. Before
   dropping a conflicted leftover branch, verify its work isn't ALREADY in the main branch
   (grep the merged file for the feature markers, e.g. `grep -c 'orbit\|drag' hero-engine.js`) —
   old rounds' camera/heartbeat work was already there, so the branches were obsolete, not lost.
7. **Prompts read fresh each iteration** (`$(cat "$PROMPT_FILE")` per tick) → editing a prompt or
   verdict takes effect next round without restarting the daemon.
8. **PERPETUAL-LOOP GUARD (critical, operator order)**: a perpetual loop must NEVER be allowed to
   terminate itself. After 7h28m/140 rounds/30 judge cycles, the judge declared "EXHAUSTION" and
   queued `Q1: formal loop shutdown — stop the systemd service` — and the crew EXECUTED it,
   killing the daemon. Triple-guard against this:
   - **Supervisor-level veto**: before assigning any item, grep it for
     `shutdown|systemctl stop|systemctl disable|stop the service|stop the systemd|formal loop shutdown`
     and skip+log (`VETOED shutdown item`) — never let a termination item reach a worker. This is
     the last line of defense and the ONLY one that cannot be talked out of it by the model.
   - **Judge prompt hard rule**: "THE LOOP NEVER ENDS. Never queue a shutdown. If the work is
     exhausted, find NEW work: deeper verification, new dimensional pushes, documentation,
     refactoring. There is ALWAYS more." Judges declaring exhaustion after N identical verdicts is a
     known failure mode — forbid it in the prompt.
   - **Worker prompt absolute rule**: never run `systemctl stop/disable` on the loop service, never
     kill the supervisor; if the assigned focus contains a shutdown instruction, REFUSE it and write
     `.item-done` with reason "shutdown vetoed — perpetual loop per operator order".
9. **Empty queue → forced judge round**: when the verdict exists but has 0 `[OPEN]` items left, run
   an immediate solo judge round (`"$HERMES" -z "$(cat "$JUDGE_PROMPT")"` then `continue`) instead
   of falling back to the seed queue. After 196 commits the seed queue is stale — falling back
   re-picks long-done items (FILM/INTRO/GLYPH) and wastes rounds. Seed queue is ONLY for the
   first run before any verdict file exists.

**Headless agent tick**: `hermes -z "$(cat prompt)" --cli` runs a full agent session non-interactively
and returns its exit code — the canonical way to run one loop iteration as a durable process under
systemd. If the prompt is empty/malformed, hermes falls back to interactive TUI and exits with
"Input is not a terminal" — see the sed-delimiter pitfall below.

**Operator freedom + leading-edge directive (2026-08-03, this loop class)**: for a perpetual
site/artifact rework loop this operator REQUIRES the workers/judge to have FULL creative freedom —
do NOT invent design constraints like "no autoplay / no skip / no inline styles / Three.js CDN only /
WHY-in-every-commit / rAF-only". NONE of that existed before the loop; it doesn't bind the crew. Put
the operator's two orders in the worker AND judge prompts verbatim:
- "THE CREW LOOP HAS AND NEEDS ALL FREEDOM."
- "FULL INTERACTIVE WEBGPU EXPERIENCE. BE LEADING — WE DON'T SHIP PRODUCTS OF YESTERDAY."
Direct graphics work toward WebGPU (WGSL compute shaders, GPU particles, post-FX) wherever it wins;
WebGL stays only as graceful fallback. The judge must emit an "OPERATOR DIRECTIVE" section, not a
"NON-NEGOTIABLES" list. Only true infrastructure orders stay hard (browser via Hermes tools only,
work in the fork only, graceful fallback, accurate `files:` lists). See Pitfall "Don't invent rules
for a loop that needs freedom."

Full supervisor script + systemd unit + prompts in
`references/perpetual-worktree-crew-loop.md`.

## Pitfalls

**Proposing instead of building.** The user wants working cron jobs with specific models, not descriptive essays. If the request is "come up with ideas about X," the deliverable is: design → script → cron registration → mazemaker fact. Don't stop at design.

**Using flat files for state.** A markdown file or Linear board is storage, not a control plane. Mazemaker's graph with 55k edges lets cadence layers coordinate through label namespaces. If you're writing to a file, you're doing it wrong.

**One cadence for everything.** Discovery needs 15-min ticks. Action needs 24h. Put them on the same schedule and you either burn tokens on idle discovery or miss fresh signals during long action cycles.

**Forgetting convergence detection.** A loop that runs forever without measuring whether it's finding anything new will burn tokens indefinitely. Always add a MEASURE phase that computes saturation ratio and recommends pausing or rotating seeds.

**Token-unbounded sub-agents.** delegate_task sub-agents get fresh context each run but burn tokens independently. Set max_turns on every sub-agent. Add a shrug-test observer for runaway tasks.

**Mimo not configured.** If the user mentions "mimo," it's the Xiaomi MiMo provider (mimo-auto). Check `XIAOMI_API_KEY` in env or ~/.hermes/.env. If unset, use free models from openrouter_custom provider instead.

**mazemaker MCP unreachability during ACT phase.** When the mazemaker MCP server returns "unreachable after 3 consecutive failures," the ACT phase CANNOT read `decision:rank-*` memories directly. Recovery pattern: (1) Check session_search for recent DECIDE phase logs, (2) Check local cron/jobs.json for paused/superseded jobs, (3) Use alternative state sources like `~/.hermes/loops/shared/loop_runner.log` and local files, (4) Verify completions in-place via terminal checks (e.g., `systemctl --user status <service>`, `ss -tlnp`, file existence checks). Do NOT retry mazemaker recall immediately — the MCP has its own auto-retry cadence. Document findings in your report and defer mazemaker writes until the server recovers.

**Pulse-Wurm 2.0: script path vs MCP path exhaustion divergence (2026-06-18).** The legacy `pulse_tick.py` script's GitHub-only search hits its wall around 800 visited URLs and reports 0 novel on every seed, even when the MCP `pulse_search` (22-source fan-out) would surface 5–15% unvisited URLs from the same seeds. When the script returns 0, the agent must NOT conclude the loop is empty — it must bypass the script and drive discovery via `mcp__pulse__pulse_search` + `mcp__pulse__pulse_dig` + `mcp__mazemaker__mazemaker_remember` directly. The script becomes a state-hygiene daemon only at that point. See `references/pulse-wurm-2.0-implementation-20260617.md` "When pulse_tick.py Returns 0 Novel — Bypass Pattern" for the full sequence.

**Pulse-Wurm 2.0: fresh-angle seed gets deprioritized after productive rotation (2026-06-19 ~07:15 UTC tick confirmed).** Companion to the "manual seed rotation" pitfall above. When the bypass pattern finds a productive fresh-angle seed via MCP (e.g., rotated to `next_seeds[3]` and it yields 7 novel arxiv papers), the saturation bump on that seed (0→7) **deprioritizes it below the saturated script seeds** that were processed in the same tick. The script's `consecutive_empty` reset at tick start means the script's 3 default seeds stay at sat 1; the productive fresh-angle jumps to sat 7. The next tick's `sorted(saturation.items())[:5]` re-picks the sat-1 script-defaults and skips the now-sat-7 productive seed — losing the cluster mid-stream.

**Workaround**: After a productive MCP rotation, manually promote the productive seed to `next_seeds[0]` (and demote the saturated script seeds below it), regardless of saturation. Or maintain a separate `openalex_productive_seeds` list that is appended to `next_seeds` after the saturation-sorted top 5, and treated as priority-1. The 2026-06-19 ~07:15 tick lost the productive `LLM agent supply chain attack tool poisoning follow-on` seed (sat 7) below the 3 just-processed script-defaults (sat 1 each) — the next tick will re-pick the script seeds and not the productive one unless manually reordered.

**Sign that this happened**: productive seed from MCP rotation has saturation > the 3 script seeds AND the script seeds are still in `next_seeds` top 3. The fix is mechanical: swap their positions in `next_seeds` before saving state.

**Pulse-Wurm 2.0: manual seed rotation when script seeds are saturated (2026-06-19).** When the bypass pattern above yields 0 novel on the script's 3 default seeds, do NOT just retry those same seeds. Read `state['next_seeds']` (the saturation-sorted queue the script itself wrote) and pick a rotation seed from positions 3–4 — the script skips the lowest-saturation candidates when 3 are already in `seeds_for_this_tick`. In the 2026-06-19 ~04:00 tick, the script's 3 seeds (governance, Atlas defenses, link-safety) all returned 0 novel; the agent rotated to `next_seeds[3]` = "Secure AI code generation 2026" (saturation 2) and the openalex sub-channel immediately yielded 4 novel papers. The productive channel for academic-agent-security discoveries in 2026 has consistently been `openalex` — promote seeds with academic framing ("X 2026 arxiv", "X security vulnerabilities") to a separate openalex-targeted bucket in `next_seeds` if you want to keep the script path productive on GitHub while the MCP path covers academic literature.

**Pulse-Wurm 2.0: year-token collision is in the RESULT set, not the query (2026-06-21).** The script's `strip_year_tokens()` (pulse_tick.py:22-52) correctly preprocesses the query, and `_is_year_collision_url()` (pulse_tick.py:85-96) correctly skips URLs whose numeric path segment is a calendar year (e.g. `/issues/2026`, `/pull/2026`). Neither of these catches the 2026-06-21 tick's failure mode: GitHub search returned **6/6 noise hits** for the "climate policy 2026" seed as repos whose **titles/descriptions** contain 4-digit year tokens (Alex7020's `Tag-Management-System-Market-Report-2022-*`, `Water-Treatment-Biocides-Market-Report-2022-*`, `Uv-Disinfection-Equipment-Market-Report-2022-*`, `Thermoforming-Plastic-Market-2022-*`, `Surgical-Incision-Closure-Market-Report-2022-*`, plus `Aryia-Behroziuan/References` for an unrelated "serious gaming crisis management 2026" seed). The URLs are clean (no `/2026` segment), so the existing guards pass them through. Fix: add a **result-side year check** — if a hit's `description` or `full_name` contains a 4-digit year that doesn't match the seed's expected publication year, mark it as `year_collision_repo` and skip. Or apply a stricter per-channel threshold on the github_direct channel (any result with description containing "Market-Report-2022" or other stale-year markers should be dropped without being marked visited — the noise repeats across ticks because the repos are stable on GitHub).

**Pulse-Wurm 2.0: PDF vs canonical article URL dedup gap (2026-06-21).** The same paper can be referenced by two URLs (e.g. `https://nature.com/articles/s43246-026-01199-6.pdf` and `https://nature.com/articles/s43246-026-01199-6`). The `visited_urls` set uses exact-match strings, so when one variant was visited in a prior tick and the other appears as a candidate in a later tick, the dedup check passes both (one as visited, the other as new). In the 2026-06-21 tick, the Communications Materials review (DOI 10.1038/s43246-026-01199-6) had its `.pdf` URL in visited_urls from an earlier run, but the canonical article URL was unvisited. Fix: normalize URLs before the visited_urls check by stripping trailing `.pdf`, `.html`, query strings, and trailing slashes. Apply the same normalization before appending to visited_urls. This catches the canonical/PDF variant duplicate without needing a recall call.

**Pulse-Wurm 2.0: fresh-direction seeds can return already-visited high-value items (2026-06-21).** The fresh-direction phase's purpose is to expand into a new domain — but earlier ticks may have already touched that domain via different seeds. In the 2026-06-21 tick, the robotics seed returned 8 candidates, 1 of which was a 2026-06-10 Springer multi-robot LLM survey that was already captured in a prior tick. The llm_filter correctly kept it as on-topic. The agent MUST run the visited_urls check on fresh-direction results, not just on continue-on-findings results. The 1 already-visited count is normal and expected — log it in the fresh-direction narrative ("1 already visited, 2 novel saved, 5 noise") but don't mark the fresh-direction as zero-yield. The fresh-direction phase's value metric is `novel / considered`, not `novel / kept`.

**Pulse-Wurm 2.0: llm_filter on math/learning topics under-weights freshness (2026-06-21).** When a seed is academic-math flavored ("knot theory 2026 research") the planner's intent=learning + math-domain combination applies a permissive freshness filter — the 2026-06-21 tick saw 2/12 kept candidates dated 2015 and 2023 (8 and 11 years old respectively). The kept candidates were both `math.RT/math.CO` papers from the Aicardi/Juyumaya group that the visited_urls set already contained. Llm_filter kept them on topical relevance but didn't downgrade them on age. Workaround: when a seed contains an explicit year token (2026, 2025, etc.), apply a post-filter that drops candidates with `published_at` more than ~24 months before the seed's target year. The "math/learning" intent class is the main offender; "general" and "factual" intent classes weight freshness correctly.

**Pulse-Wurm 2.0: pre-save dedup check via mazemaker_recall (2026-06-19).** Before calling `mazemaker_remember` for a candidate URL/title, query `mazemaker_recall(query=<title-or-topic-phrase>, limit=5)` and check if any returned memory contains the same arxiv ID, DOI, or title. In the 2026-06-19 tick, 2 of 4 candidate papers (arxiv 2605.24300 "Enhancing Reliability in LLM-Based Secure Code Generation" and 2606.00186 "How to Compare the Security of Code Written by Humans to LLM-generated Code") were already saved in prior ticks — a 5-second recall check saved 2 redundant writes. This is especially important when the seed is rotated from `next_seeds` (which may have been processed in a prior tick and the discoveries persisted but not yet visible in `visited_urls`).

**Pulse-Wurm 2.0: mark visited even when mazemaker_remember fails (2026-06-19).** When `mazemaker_remember` times out or the MCP server disconnects mid-tick, the URL is still known-novel — append it to `state['visited_urls']` regardless of save success. The persistence goal of `visited_urls` is "don't re-surface this candidate next tick," which is independent of whether the discovery made it into the graph. In the 2026-06-19 tick, 2 of 4 candidate papers (arxiv 2606.04057 "Invisible Lottery" and 2605.28893 "Demystifying LLM-in-the-Loop Vulnerabilities") were lost when the mazemaker MCP entered cooldown after the 2nd successful save; both were correctly appended to `visited_urls` so they won't reappear next tick. The lost discoveries can be re-discovered (and re-saved) in a future tick from a different seed, or recovered via session_search on this tick's transcript.

**Pulse-Wurm 2.0: mazemaker_remember consecutive-save cooldown (2026-06-19).** The mazemaker MCP server handles ~2-3 successful `mazemaker_remember` calls in a row, then enters a 120-second timeout loop per call, and after 5 consecutive failures reports "MCP server 'mazemaker' is unreachable." This is a **write-side** cooldown distinct from the **read-side** "mazemaker MCP unreachability during ACT phase" pitfall above — the latter is about `mazemaker_recall` failing during the DECIDE/ACT phases; this one is about `mazemaker_remember` failing during the DISCOVER phase. Recovery: (1) note the lost URLs in the tick summary appended to `state['discovery_topics']`, (2) mark them visited, (3) re-queue them as rotation seeds if they're high-value (e.g., "arxiv 2606.04057 Invisible Lottery LLM codegen"), (4) the MCP recovers automatically after 1-2 minutes. Do NOT retry the failed `mazemaker_remember` calls in the same tick — they will all time out. Best practice: when the cooldown threshold approaches (3rd successful save in a tick), switch to "verify-only" mode: continue dedup-checking candidates via `mazemaker_recall` and mark them visited, but defer the actual `remember` calls to the next tick.

**Cron for perpetual rework loops (operator rejected, 2026-08-03).** "DO NOT DO STUPID USELESS
FUCKING CRONJOBS! I WANT NONSTOP, 24/7/365 ACTION! NO BREAKS, NOTHING!" A cron cadence (every 4h)
has scheduled gaps — those ARE breaks to this operator. For "loop until perfect, no end" requests
use the systemd + supervisor `while true` pattern from Loop Type 8, not cron. Cron remains correct
for genuinely periodic work (discovery, digest, watchdog); it is WRONG for a perpetual grind loop.
Also: "agents must work in parallel ALWAYS" — serialize only where files collide.

**Don't invent rules for a loop that needs freedom (2026-08-03, operator correction).** The agent
who set up the perpetual rework loop wrote a "NON-NEGOTIABLES" section (no autoplay, no skip, no
inline styles, Three.js CDN only, WHY in commit, rAF-only) into the judge prompt and verdict —
rules that NEVER existed before the loop. Operator reaction: "nothing of this, of THE CRAP EXISTED
BEFOREHAND(!) - THE CREW LOOP HAS AND NEEDS ALL FREEDOM(!)". When designing a creative/build loop
for this operator: constraint lists must come FROM the operator, never be invented by the agent or
inherited from an older spec section. If the spec has old §-rules, the prompt must explicitly state
they are superseded by the operator's Full-Freedom directive. Real infra orders (browser-tool-only,
fork-only, fallback, accurate files:) stay, but never pad them with aesthetic constraints. The judge
should restate "OPERATOR DIRECTIVE" (two operator orders), not a rule list the crew must check off.

**Prompt templating: sed delimiter collision (2026-08-03).** Building a per-worker prompt with
`sed -e "s|{{FOCUS}}|$focus|g"` BREAKS when the substituted value contains `|` — and queue items
in this loop format DO (`[OPEN] Q1: goal | why: ... | files: ...`). Symptom: workers get a
truncated/garbage prompt, hermes -z falls back to interactive TUI, logs show
"Input is not a terminal (fd=0)" + immediate shutdown, rounds complete in SECONDS instead of
minutes, zero commits land, and the judge scores the crew 40/100 for doing nothing. The rounds
look like they "ran" — only the timestamps (26s for 4 rounds) reveal the crash. Fix: substitute
with Python, passing values via env vars (immune to any delimiter):
```bash
prompt=$(REWORK_WORKDIR="$wt" REWORK_WORKER_ID="$wid" REWORK_FOCUS="$item" python3 - "$TMPL" <<'PYEOF'
import os, sys
print(open(sys.argv[1], encoding="utf-8").read()
      .replace("{{WORKDIR}}", os.environ["REWORK_WORKDIR"])
      .replace("{{WORKER_ID}}", os.environ["REWORK_WORKER_ID"])
      .replace("{{FOCUS}}", os.environ["REWORK_FOCUS"]))
PYEOF
)
```
General rule: never sed-replace into a template when the payload can contain the delimiter;
use Python/`envsubst` with env vars.

**No-change items must still close the queue (2026-08-03).** A worker can correctly find its focus
already implemented (e.g. Q2 heartbeat was inside the Q1 engine port). If the loop only marks
`[DONE]` on a successful merge, that item stays `[OPEN]` forever and gets re-picked every round —
infinite duplicate work. Fix: worker writes `.item-done` marker file in its worktree
(`echo "already complete — <evidence>" > {{WORKDIR}}/.item-done`), supervisor detects it and marks
`[DONE]` without a commit. Workers must NEVER fabricate a no-op commit just to close an item.

**Autonomous loops can terminate themselves — guard against it (2026-08-03).** The judge in a
perpetual rework loop ran 30 cycles, then wrote a `Q1: formal loop shutdown` item and the crew
executed it, killing the systemd service after 7.5h of work. A self-terminating component is the
worst failure mode a perpetual loop can have: silent, final, and done by the very agent that is
supposed to keep the work going. Any loop whose purpose is "never end" MUST carry the triple guard
(supervisor veto on shutdown terms + judge hard rule + worker refusal) — see Loop Type 8 step 8.
Never assume the judge "won't do that" — after enough identical verdicts it will conclude it is
done and try to stop. Also: a judge writing an all-audit-only queue ("requires human observation")
is the same exhaustion signal — the queue must contain executable work every cycle.

**False [DONE] from no-op merges (2026-08-03).** `git merge --no-ff <branch>` where the branch is
identical to HEAD returns exit 0 ("Already up to date") without creating a commit. A supervisor that
treats "merge exit 0" as success will mark items `[DONE]` even though the worker committed nothing
(often because it crashed). Symptom: queue drains in seconds, git log shows no new commits, and the
judge later scores the crew 40/100 for "doing nothing". Always capture `head_before=$(git rev-parse
HEAD)` before the merge and only treat it as success when `head_after != head_before`. A no-op merge
must leave the item `[OPEN]` so a later round retries it.

**.item-done + real commit = lost work (2026-08-03).** A worker can commit real work AND write
`.item-done` (it verified the result and concluded "done"). The original `.item-done` handler
checked for the marker FIRST and marked `[DONE]` without merging — the commit sat on the orphaned
branch forever, never reaching HEAD. The judge kept scoring "ABSENT from HEAD" cycle after cycle.
Fix: before treating `.item-done` as "no change", check `git rev-list --count HEAD..$branch` —
if > 0, the branch has real commits and MUST be merged despite the marker. Only treat `.item-done`
as no-change when the branch is NOT ahead of HEAD.

**HUMAN-TASK veto — items only a human on a GPU machine can do (2026-08-03).** Items requiring
a real GPU browser (screenshots on RTX, visual proof on hardware) must NEVER be assigned to crew
workers — headless has no GPU, workers loop on them forever. Add `is_human_task_item()` grep for
"human task|operator task|requires operator|rtx|screenshot|visual proof on gpu" → skip+log as
"OPERATOR-PENDING", never assign. Operator: "I WANT ONE AGENT TODO THIS, NOT ALL OF THEM".
Use `[HUMAN TASK]` prefix in verdict instead of `[OPEN]` so the filter is automatic.

**Free-model outsourcing — ALL loop components must be $0 (2026-08-03).** The operator requires
EVERY component (workers AND judge) on free/$0 models. Running the judge on the main paid model
while workers are free is unacceptable — "NO PAID MODEL FFS". Pattern: define `FREE_MODELS` array,
`pick_worker_model()` round-robin, `JUDGE_MODEL` (biggest free model). Store each as `provider:model`,
split into `--provider <p> --m <model>` at launch — NOT `-m provider/model` (that returns HTTP 401,
see references/multi-provider-model-routing.md "THE -m provider/model 401 TRAP"). Worker:
`hermes -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli`. Judge: `hermes -z "$(cat judge)"
-m "$WM_MODEL" --provider "$WM_PROVIDER" --cli`. Different workers get different models per round.
Round-robin across BOTH Nous Portal free + OpenRouter free (separate daily quotas) to double free
capacity before 429. opencode-zen needs payment — drop it.

**Judge false [DONE] from commit existence, not file verification (2026-08-03 evening).** A judge
saw prior WebGPU commits in `git log` and marked five NEW queue items `[DONE] (merged <hash>)` even
though NONE of that focus work existed in the files. The judge inferred "commit in log = items done"
without reading code. Symptom: queue drains to all-[DONE], supervisor forces judge round, judge
writes no new [OPEN] items, loop idles. Fix in judge prompt: an item is [DONE] ONLY if you verified
the specific focus work is present in the actual files (grep/read/node --check/browser). A commit
hash alone is NOT proof. If the focus work is absent, re-queue as [OPEN]. Also: if every prior item
is [DONE] (queue exhausted), the judge MUST write a FRESH queue of 5 new [OPEN] items — the loop
does NOT idle.

**Crew agents must coordinate BEFORE editing, not rely on post-hoc collision detection (2026-08-06,
operator correction).** "die crew agents SOLLTEN sich absprechen können untereinander, bevor ständig
nur müll hier passiert!" — the `files:`-clause deferral in Loop Type 8 was silent because it trusted
worker self-reports, which were inaccurate. A parallel crew loop with 3 workers in separate worktrees
that MERGE into one master MUST have a coordination channel so workers see who holds which file BEFORE
they write. Build a `crew` coordination bus: atomic `claim` (mkdir O_EXCL, all-or-nothing, REFUSE on
conflict), `handoff` (ask the holder to make the change), and `contract` (publish an interface so the
next worker builds on it instead of duplicating). Put the worker order `board → inbox → contracts →
claim → work → contract → commit → release` in the worker prompt verbatim. The supervisor measures
TRUE overlap after the round via `git diff` and logs `file overlap between workers:` — if it ever says
anything but `none`, the bus is being ignored. See `references/crew-coordination-bus.md` for the full
script, race test, and supervisor integration.

**Mocking the user with "it works" when workers silently collide (2026-08-06).** Before the bus, three
workers editing the same files "merged" because the determinism-guarded merge succeeded on the
non-conflicting parts — the work looked done, the judge scored it fine, but interfaces were duplicated
and call sites drifted. Never report a crew round as clean without the post-round `git diff` overlap
check. The `files:` clause is NOT evidence of non-collision; the merge result is NOT evidence either.
Only the measured overlap is.

HTTP 429, `hermes -z` returns exit=0 with an error MESSAGE but no actual output. The supervisor
treats exit=0 as success, queue stays empty, forced-judge fires infinitely. Fix: track consecutive
judge failures (exit=0 but no new verdict = failure). After N failures, pause with long backoff
(30min+) instead of spinning. Or grep judge log for "429" / "Rate limit".
