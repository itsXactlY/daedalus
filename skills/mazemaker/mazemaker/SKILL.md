---
name: mazemaker
description: "Full-stack Mazemaker operations: backend deployment, production backend operations, pod maintenance, viral trailer production, and Three.js visualizations iteration."
category: mazemaker
---

# Mazemaker Full-Stack Operations

## 0. Tool Availability & Installation

**Purpose**: Ensure the required Mazemaker CLI tools (`mazemaker_recall`, `mazemaker_remember`, `mcp__mazemaker__mazemaker_recall`) are available in the Hermes Agent environment before attempting discovery or decision phases.

### Installation Checklist
1. **Verify Podman installation** – required for running the Mazemaker pod:
   ```bash
   podman --version
   ```
   Minimum version 4.9.0.
2. **Clone the Mazemaker repository** (if not already present):
   ```bash
   git clone https://github.com/NousResearch/mazemaker.git ~/mazemaker
   ```
3. **Build and install the CLI tools** – run the provided installer script which sets up a virtual environment and adds the binaries to `$HOME/.local/bin`:
   ```bash
   cd ~/mazemaker
   ./install.sh --user
   ```
   This script:
   - Creates a Python virtual environment with `uv`.
   - Installs the `mazemaker` package in editable mode.
   - Symlinks `mazemaker_recall`, `mazemaker_remember`, and the MCP wrapper `mcp__mazemaker__mazemaker_recall` into `$HOME/.local/bin`.
4. **Add the bin directory to PATH** (add to `~/.bashrc` or appropriate shell rc):
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```
   Reload shell: `source ~/.bashrc`.
5. **Confirm availability**:
   ```bash
   which mazemaker_recall
   mazemaker_recall --help
   ```
   All commands should return a usage message without error.

### Common Failure Modes & Fixes

**Additional Pitfall – Missing CLI tools**:
- If `mazemaker_recall` or `mazemaker_remember` return "command not found", the installation script likely hasn't been run, or `$HOME/.local/bin` is not in your `PATH` for non‑interactive shells. Run:
  ```bash
  cd ~/mazemaker && ./install.sh --user
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
  source ~/.bashrc
  ```
- Verify the binaries are present with `which mazemaker_recall` and ensure the session's `PATH` includes `$HOME/.local/bin`.
- On systems using a different shell (e.g., `zsh`), add the export to the appropriate rc file.
- After installing, re‑run `mazemaker_recall --help` to confirm availability.

See `references/cli-tool-missing.md` for a full troubleshooting checklist.
- **`command not found`** – Ensure step 4 was performed and the current session has the updated PATH.
- **Missing `uv`** – Install via `pip install uv` inside your base Python (or use the system package manager).
- **Podman socket permission errors** – Add your user to the `podman` group and restart the session:
  ```bash
  sudo usermod -aG podman $USER
  newgrp podman
  ```
- **Version mismatch** – The CLI tools are tied to the Mazemaker pod version. After a pod upgrade, rerun `./install.sh --user` to refresh the wrappers.

### Runtime Note for Hermes Loops
The tri‑state cadence loops (`discover_seed.py`, `decide_rank.py`, `act_implement.py`) invoke these tools directly. If any tool is missing, the loop will silently skip the step, leading to empty discovery results. Adding this installation step early in the environment setup prevents that silent failure.

---

This umbrella skill consolidates all Mazemaker operational domains into a single class-level reference. Each section below represents a formerly separate narrow skill, now organized as labeled subsections for discoverability.

---

## 1. Backend Deployment (formerly `mazemaker-backend-deployment`)

### When to Load
- Building or rebuilding Nuitka host binaries (`build-host-binaries.sh`)
- Publishing a new source.tar.gz (`install-backend.sh`)
- Debugging a Quadlet that fails to start (wrong path, missing file, GPU vs CPU mismatch)
- Diagnosing a 500/522 on any mazemaker.dev subdomain
- Installing or updating the mazemaker pod on a machine (desk, tpad, Hetzner)
- Adding Hermes integration (memory provider, MCP, skills)
- **Before ANY action: load the HANDBOOK.md first** (`~/.hermes/projects/mazemaker-v2-stack/backend/docs/HANDBOOK.md`)

### Core Principles
1. **Handbook First — STRICT RULE**: Read the handbook before touching anything. Do NOT guess facts about deployment topology.
2. **Use uv, not pip, for container builds**: Every `pip install` → `uv pip install --system`. Pre-install uv via `pip install uv` in the same RUN layer.
3. **Never Replace a Nuitka Binary by Hand**: Rebuild via `bin/build-host-binaries.sh` with correct deps.
4. **Ship Through the Pipeline**: repo commit → git push → `install-backend.sh` on Hetzner. Never patch files directly on customer machines.

### Build Pipeline (build-host-binaries.sh)
**Location**: `backend/bin/build-host-binaries.sh`

Runs in a `python:3.12-slim` container, installs build deps, compiles each script in `SCRIPTS=()` array with `--onefile` to `dist/host-binaries/`. Also builds `fingerprint` binary (multi-file package).

**Key references**: `references/nuitka-paths.md` (complete .py → .so path mapping), `references/gpu-image-push.md` (full GPU build transcript), `references/nuitka-build-patterns.md` (full Nuitka build reference).

### Common Pitfalls
- **Missing pip dependency**: Add to line 74-75 of builder (PyYAML is REQUIRED despite soft fallback)
- **Fingerprint binary**: Must copy `crypto.py` AND add `cryptography` pip package (fixed 2026-05-31)
- **Nuitka path resolution**: Compiled `.so` files land at `/app/<module>.cpython-311-x86_64-linux-gnu.so`, NOT original relative path
- **GPU vs CPU Quadlet**: `AddDevice=nvidia.com/gpu=all` causes CDI errors on non-NVIDIA machines; install.sh handles stripping

### Publisher (install-backend.sh)
**Location**: `backend/scripts/install-backend.sh`

Syncs architect SPA, bundles host binaries, Hermes plugins/skills, runs PUBLISH GATE, creates source.tar.gz, builds API image.

**PUBLISH GATE exemptions**: `client/hermes-plugins/*` MUST remain as .py source (Hermes plugins need `__init__.py`).

### Deploy Modes
- **Mode A** (standard): Prod has git clone → `git pull && bash scripts/install-backend.sh --refresh`
- **Mode B** (no git clone): Build tarball on desk, SCP to prod, copy installer files, restart via DBUS-aware systemctl

### Customer Install (install.sh)
**Location**: `backend/installer/linux/install.sh`

Handles Hermes integration: agent install/detect, bridge binaries, memory provider plugin, skill, config integration, pod image pull, Quadlet start.

**Auto:Turn Verification Critical**: `MazemakerMemoryProvider.sync_turn()` MUST accept `**kwargs` (Hermes passes `session_id`). Check `agent.log` for `sync_turn failed` errors. Verify entries in pgvector. Restart Hermes after plugin update.

### Quadlet Templates
**Location**: `backend/client/quadlet/`

Key templates: mazemaker-v2.pod, mazemaker-v2-api.container, mazemaker-v2-nginx.container, mazemaker-v2-cloudflared.container, mazemaker-dream-worker.container, mazemaker-hermes-bridge.service.

**Dream Worker**: Runs as systemd user service with timers (03:00 start, 07:00 stop). `MM_DREAM_DISABLED=1` disables inpod AND on-demand calls; user prefers `MM_DREAM_DISABLED=0` to keep active.

**License-Client Fix**: Must add `Volume=%h/.local/share/mazemaker:/var/lib/mazemaker:ro,z` to license-client container for fingerprint binding.

---

## 2. Backend Operations (formerly `mazemaker-backend-operations`)

### When to Load
- Troubleshooting onboarding wizard failures
- Diagnosing license refresh failures (`fingerprint_binding_violated`, expired SMTP)
- Cleaning up stale fingerprints/licenses on production backend
- Restoring from database backups
- Debugging email delivery failures
- Deploying onboarding frontend to Cloudflare Pages

### Core Rules
1. **HANDBOOK FIRST — ABSOLUTE**: `backend/docs/HANDBOOK.md` has exact commands for every operational procedure.
2. **BACKUP FIRST — BEFORE ANY DB DELETE**: Copy database before modifications. Hourly backups at `~/mazemaker-v2-pod/backups/`.
3. **TARGET ONLY THE PROBLEM USER — NEVER WIPE ALL**: Use `DELETE ... WHERE user_id = ?` with specific UID.

### Onboarding Failure Debug Flow
1. Check browser console: `insertBefore` → Rocket Loader conflict; `Cannot find Widget` → Turnstile auto-render conflict; `We can't verify` → API rejection
2. Check backend API directly via podman exec
3. **Rate limit?** Test email-verify API. If "Rate limit exceeded: 3 per 1 hour" → restart `mazemaker-v2-api` (NOT remainder-api)
4. **SMTP broken?** Test SMTP directly. Error 535 = Vivaldi app-password expired
5. **Stale backend data?** Clean only the user's records (see rule 3)
6. **Last resort**: direct license issuance via `issue_license_for_local_install.py`

### Rate Limit Recovery
**ONLY correct command** (from HANDBOOK.md):
```bash
ssh mazemaker-prod 'sudo -u mazemaker -H XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user restart mazemaker-v2-api'
```
Must include both env vars. Service name IS `mazemaker-v2-api`. slowapi uses in-memory storage → restart resets all counters.

### SMTP / Email
Config in `.env` (smtp.vivaldi.net, port 587, user alca@vivaldi.net). Passwords expire periodically. Fix: generate new Vivaldi app-password, update `.env`, restart API.

### Database Operations
Connection via SSH + sqlite3 or Python. Key tables: users, fingerprints, licenses, fingerprint_bans, abuse_events, onboard_sessions.

### Cloudflare Pages Deploy

**DO NOT use `deploy-pages.sh`** — the file has literal `***` sanitization damage
(`$(cat ~/.cf_api)` and the Bearer token were replaced with `***`). Always use
wrangler directly.

```bash
cd ~/projects/mazemaker-v2-stack/frontend
bash scripts/build-pages.sh
wrangler pages deploy dist-online --project-name=mazemaker-online --branch main
```

**Safety rule — deploy only `dist-online`**: The build script rebuilds BOTH
`dist-online/` (from `website/`) AND `dist-dev/` (from `website-dev/`) locally.
This is safe — only the wrangler push matters. **Never deploy `dist-dev` to
`mazemaker-dev` unless explicitly asked.** The `--project-name=mazemaker-online`
flag is the guard rail.

`--branch main` REQUIRED. Wrangler OAuth in system keyring (alcatr4z@gmail.com);
`~/.cf_api` token lacks Pages write permission.

**Footer is a shared partial**: The site footer lives in
`assets/partials/footer.html` and is fetched + injected by `nav.js` on every
page at runtime. One edit updates the entire site (Home, Docs, Blog,
Comparison, Privacy, Terms, all deep-dives). No per-page edits needed.

**Cache busting**: Add `?v=N` to JS URLs in index.html after deploying fixes.

---


<!-- moved to references/moved-sections.md: ## 3. Pod Maintenance (formerly `mazemaker-pod-maintenance`) -->

## 4. Viral Trailer Production (formerly `mazemaker-viral-trailer`)

### When to Use
Creating, extending, or fixing Mazemaker marketing/promo trailers.

**Two pipelines — choose the right one:**
- **Pipeline A (Flux → Cosmos Predict2 → Resolve)**: Professional cinematic. Flux stills → Cosmos Predict2 animates each into 4-8s video → Resolve edit.
- **Pipeline B (Flux → HTML/CSS)**: Self-contained browser deliverable. Flux stills as CSS backgrounds with Ken Burns zoom, kinetic typography, Web Audio soundtrack, rendered to MP4 via Xvfb + Chrome.

**Pipeline C (Re-cut from existing assets)** — see `cinematic-html-trailer` skill's `references/100-iterations-pattern.md`. When the 23-style × 15-page comic + 16 VOs + score are already on disk, the work is curation + pacing. A single 49KB self-contained HTML can deliver 100+ kinetic moments without generating a single new image. Use the 6-act viral architecture (below) as the spine; pull hero plates from `outputs/style_*/`; schedule the existing `voiceover_uprising/vo_*.wav` files via a `VOS` dict. The 209-iteration Director's Cut trailer in `comic/mazemaker-inception-os/v3/trailer/directors-cut/` is a worked example of this pattern.

**NOT for Three.js maze-crew visualizations** (use Section 5).

### Pipeline A: Flux → Cosmos Predict2 → Resolve
**Phase 1: Director's Brief Format — NOT Image Prompts**
Write director's briefs (8 fields in flowing prose): subject, environment, camera, motion, atmosphere, emotional payload, cinematic language. Cosmos Predict2 needs explicit motion descriptions.

**Phase 2: Establish Visual Language (Master Prompt)**
Single paragraph defining visual identity. Every shot inherits from it. Save as `references/visual-language-master-prompt.md`. Test with ONE hero still first.

**Phase 3: Shot Structure**
Same 6-act structure as Pipeline B. Target 24-30 shots for ~45s trailer.

**Phase 4: Generate 24-30 Flux Hero Stills**
Extract concise Flux prompt from each brief. Generate at 1216x688, 30 steps, Euler, Flux Dev fp8. Save descriptive filenames.

**Phase 5: Image-to-Video**
**CRITICAL**: Cosmos Predict2 has NO cloud API — self-hosted only (Docker/pip, requires H100/A100 80GB+ VRAM). RTX 4060 Ti (16GB) insufficient.
Alternatives: WAN 2.2 14B GGUF Q4 (~12GB, ComfyUI), LTX-Video (~12GB), Cloud APIs (Fal/Replicate/Luma).

**Phase 6: Edit in Resolve**
Arrange clips matching 6-act structure. Kinetic typography sync'd to bass hits. **Climax structure**: CLAUDE STORED IT → HERMES FOUND IT → THE MODEL REMEMBERED. Hard cuts only, white flash frames on act boundaries, subliminal cuts on impacts.

### Pipeline B: Flux → HTML/CSS (Self-Contained)
**Viral Architecture (6 Acts)**:
- ACT 0 (0-2s): INSTANT EXECUTION — fullscreen kinetic text, SHAKE, audio BRAAM
- ACT 1 (2-10.5s): EMOTIONAL DAMAGE — 6 PTSD flashbacks @ 1.1-1.7s each
- ACT 2 (10.5-22.5s): THE IMPOSSIBLE MOMENT — cross-agent recall with MATCH CONFIRMED receipt
- ACT 3 (22.5-31.0s): RECEIPTS — 8 benchmark bombs with hit() on each
- ACT 4 (31.0-37.0s): OS REFRAME — "This is not memory. This is an OS for AI agents."
- ACT 5 (37.0-45.5s): RELIGIOUS ENDING + PRICING CARDS — $9/$29 founder rates. HARD CUT.

**Timing Rules**: Flashbacks 1.1-1.7s, receipts 1.0-1.5s with 0.1s gap. OS reframe slow down. Total 42-46s. Zero fat.

**CSS Motion Overlay** (replaces ffmpeg zoompan — too slow):
- Ken Burns zoom via CSS animation (GPU-accelerated)
- Camera shake on impacts
- Glitch burst on hard cuts
- Bloom pulse on reveals
**MOTION > IMAGE QUALITY** — pacing, motion, impacts, sound sync, escalation drive virality.

### Audio Approaches
**Approach A: Web Audio API** (in-browser SFX)
Functions: `tick()`, `hit()`, `sub()`, `pad()`, `swell()`. Use `SOUNDTRACK` array with `[time, fnName, ...args]` + `fired` tracker.

**Approach B: MusicGen soundtrack** (standalone FLAC)
**BEST**: 2-segment continuous generation with single 2.0s crossfade (not 6 acts with 5 crossfades — disjointed).
- Part 1 (24s build-up): "28 Years Later trailer style orchestral..."
- Part 2 (24s climax+resolution): "Full orchestra erupting, powerful brass..."
- musicgen-small FP16 (fits 4GB+ VRAM). Save WAV via scipy, convert with ffmpeg.

### Technical Setup
**Stage**: 1920x1080 scaled to viewport via JS `fit()`.
**CSS Pitfalls**: Never use `transform: translate(-50%,-50%)` on animated elements (animation overwrites). Use flexbox centering. `[data-show].live` rule overwrites transform — use `!important` overrides.

**Rendering to 4K Video**: Xvfb (3840x2160) + google-chrome-stable (NOT Firefox — black frames) + ffmpeg x11grab. Click stage center to trigger playback.

---


<!-- moved to references/moved-sections.md: ## 5. Visuals Iteration / Three.js (formerly `mazemaker-visuals-iteration`) -->

## 6. Comic Generation (Images Only — Voice Has Its Own Skill)

## 7. Discovery Memory Management

The Mazemaker ecosystem includes a lightweight memory store for discovery tick records, accessed via custom MCP tools `mazemaker_recall` and `mazemaker_remember`. These tools enable the tri‑state cadence loop to persist novel findings and avoid duplicate work.

- **`mazemaker_recall`** – Retrieves recent discovery entries matching a query pattern (e.g., `discovery:pulse-tick-*`). Use it with a `limit` (e.g., 20) to fetch the latest ticks and filter out already‑seen topics.
- **`mazemaker_remember`** – Writes a new discovery entry with fields:
  - `label`: unique identifier following `discovery:pulse-tick-YYYYMMDD_HHMMSS-<hash>`
  - `content`: brief topic description, 2‑3 sentence summary, source URL or memory ID, originating seed.
  - `salience`: numeric weight (default 0.3) influencing retrieval ranking.

**Typical workflow in the DISCOVER phase:**
1. Invoke `mazemaker_recall(query='discovery:pulse-tick-*', limit=20)` to get recent ticks.
2. Run `pulse_search` for each seed topic.
3. **Dedup gate**: For each novel candidate not in the recall list, call `mazemaker_recall(query=<core_topic>, limit=5)` to check whether the topic is already covered in memory. If a hit returns with similarity ≥ 0.4, the candidate is a duplicate — skip the save. The recall check fires on the **topic**, not the URL (the URL may be novel but the topic may be extensively documented). Verified 2026-06-18 08:32 pulse-wurm tick: the Opus 4.7 "legendarily bad" candidate (Q=0.202, 869 comments — would have been a strong save) was skipped because `mazemaker_recall("Claude Code Opus 4.7 quality degradation")` returned 361067 (`decision:rank-20260618-important-claude-code-source-leak`) at sim 0.55 plus multiple auto:claude entries at 0.56-0.58. Without this gate, the tick would have produced a redundant 4th discovery.
4. For each candidate that passes the dedup gate, call `mazemaker_remember` with the appropriate payload.
5. If all seeds yield no novel results, remain silent – the DECIDE phase will interpret the lack of new ticks as a signal to pause.

**Triple-memory shape (per pulse-wurm 2.0 reference):** Each discovery triggers 3 linked memories (discovery + fact + decision) for graph enrichment. The exact shape is **driven by the discovery count**, not a fixed 5+5+1. See `pulse-wurm-everything` skill pitfall "Triple-memory shape by discovery count" for the full matrix. Quick reference: 1→3, 2→5, 3→7, 4→9, 5→11, 6+→2N+2.

**Pitfalls & Gotchas**
- Ensure the label is unique; include a short hash of the source URL to avoid collisions.
- **Recall-based dedup before writing (2026-06-18):** The `discovery_topics` list and `visited_urls` set catch URL-level duplicates but NOT topic-level duplicates. Two different URLs can cover the same topic. Before saving any candidate, call `mazemaker_recall` with the core topic phrase and check similarity ≥ 0.4. If a high-similarity hit exists, skip the save. This gate prevents the graph from accumulating redundant memory entries on the same topic. Topic-level recall query: use the noun-phrase that captures the discovery's significance, not the URL. Example: for a URL titled "Opus 4.7 is legendarily bad", query `mazemaker_recall("Claude Code Opus 4.7 quality degradation")` — not the URL or title.
- **MCP server unreachable**: When `pulse_search` or `pulse_dig` MCP tools fail with timeout or connection errors, fall back to GitHub API search:
  ```bash
  curl -s "https://api.github.com/search/repositories?q=<query>&sort=updated" \
    -H "Accept: application/vnd.github.v3+json"
  ```
  Process results in Python, check against visited URLs, and save discoveries to JSON.
  
**Pulse-Wurm 2.0 Tool Availability Reality (2026-06-17)**:
- `mcp__mazemaker__mazemaker_remember` and `mcp__mazemaker__mazemaker_recall` tools may NOT be available in all Hermes environments
- When unavailable, save discoveries to JSON files: `~/.hermes/loops/pulse-wurm2/discoveries_YYYYMMDD.json`
- The `pulse_tick.py` script uses GitHub API directly (not pulse_search/pulse_dig) and is the primary discovery mechanism
- Memory tool may also be unavailable - use JSON file persistence as fallback
- **Rate limiting**: GitHub API has 60 requests/hour for unauthenticated calls. Use authentication via `GITHUB_TOKEN` env var for 5000/hr limit.
- **Duplicate detection**: Always check `visited_urls` from state file before processing new results. Use topic similarity matching to avoid semantic duplicates.
- Remember to set `salience` at 0.3 for discovery entries; higher values bias retrieval undesirably.
- The recall tool returns entries ordered by `timestamp` descending; filter by `generated_at` if you need a specific time window.
- The tools are thin wrappers around the Mazemaker MCP API; network latency may cause occasional timeouts – retry with backoff.

**References**
- `references/mazemaker_discovery_memory.md` – detailed usage examples and API payload schema.

---


<!-- moved to references/moved-sections.md: ## 8. DECIDE Phase (Ranking Discoveries) -->
