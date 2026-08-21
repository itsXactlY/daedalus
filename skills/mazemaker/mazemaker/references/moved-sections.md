# mazemaker — Detailed Sections

Sections moved out of SKILL.md to keep the core playbook lean. Load with
`skill_view(file_path='references/moved-sections.md')`.

---

## 3. Pod Maintenance (formerly `mazemaker-pod-maintenance`)

### Overview
The Mazemaker pod runs as a Podman pod (`mazemaker`) containing: MCP server (port 8000 internal, 8765 external), Embedding worker (BGE-M3 ~3GB VRAM), License client, Wonderland (federation/peer proxy), PGVector (optional).

**Pro-Tier Architecture Rule**: When pod is Pro-tier with postgres/pgvector, ALL components operate on postgres. No SQLite fallback, no `--db` override, no split-brain.

### Dream Engine Modes
**Mode A: External Daemon** (current) — Separate container runs `dream_worker.py` in tight loop. MCP has `MM_DREAM_DISABLED=1`. No `--cycle-interval` — back-to-back cycles (~22-35s). **CRITICAL FIX (2026-06-02)**: Remove `--db /data/memory.db` from Exec line on Pro-tier pods. Dream worker follows `db.toml` and operates entirely on postgres → zero FK violations.

**Mode B: Inpod Daemon** — MCP starts DreamEngine background thread. Controlled via `MM_DREAM_DISABLED`. **DO NOT USE for production** — blocks async event loop during heavy operations.

**Mode C: One-Shot Cron** (recommended) — Cron job runs `dream_worker.py --once` as separate container every 4 hours. Frees all VRAM on exit. Setup: `~/.hermes/scripts/dream-worker-once.sh`, cron `dream-worker-once` (no_agent=true, `0 */4 * * *`).

### MCP Server Config
**Config**: `~/.config/containers/systemd/mazemaker-mcp.container`

Key env vars: `MM_DREAM_DISABLED=1`, `EMBED_CLIENT_ONLY=1`, `EMBED_BACKEND=`, `EMBED_SOCKET=/root/.mazemaker/sockets/embed.sock`, `MM_RETRIEVAL_MODE=hybrid`, `MAZEMAKER_SYNTHESIS_ENABLED=1`, `MAZEMAKER_SYNTHESIS_WINDOW_S=86400`.

After changes: `systemctl --user daemon-reload && systemctl --user restart mazemaker-mcp.service`.

**Startup behavior**: MCP always loads GpuRecallEngine at init (15s-5min freeze). Event loop blocked during load — normal and unavoidable.

### Embedding Worker Crash Troubleshooting
**Pattern A**: `RuntimeError: Expected one of cpu, cuda... device string: auto` → Change `device = "auto"` to `device = "cuda"` in `embedding.toml` OR fix in `backends.py` to resolve "auto" → `None`.

**Pattern B**: `ModuleNotFoundError: No module named 'license_loader'` → PYTHONPATH must include `/app/shared`: `Environment=PYTHONPATH=/app/shared:/app`.

**Pattern C**: Image tag resolved to `:latest` instead of `:gpu` → Repo defaults to latest; installer patches to `:gpu` on GPU machines. Verify after copying.

### Wonderland Missing Postgres Secret
Symptom: `WARNING wonderland.db postgres password is empty` every ~1s.
Fix: Add `Secret=mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD` to wonderland container file. Apply to ALL THREE locations (live, repo, remote machines).

### Pgvector FK Violations (Dream Worker)
**Root cause**: Dream worker read memories from SQLite but wrote connections to postgres. Memory ID ranges diverged (SQLite max ~360k, postgres max ~530k) → ~5,300 connections lost per cycle to FK violations.
**FIX (2026-06-02)**: Remove `--db /data/memory.db` from dream worker Exec line. Now operates entirely on postgres via `db.toml`. Zero FK violations since fix.
**Safety net**: BEFORE INSERT trigger with `RETURN NULL` (silent skip) — NOT stub creation (v1 created 789 stubs polluting INCEPTIONS panel).

### MCP Server Down / "not connected" — Diagnostic & Recovery
The `mazemaker` MCP server (Hermes config `mcp_servers.mazemaker` → `http://127.0.0.1:8765/mcp`) exports the 31 `mcp__mazemaker__mazemaker_*` tools. When they're missing, the process behind `:8765` is not serving `/mcp`. Two distinct failure classes — diagnose before acting:

**Class A — transient freeze (real, but NOT the recurring one)**: the mcp container is up but GpuRecallEngine is mid-load (15s–5min startup freeze / VRAM spike). `/mcp` times out briefly. Fix: wait, or restart the Hermes gateway / start `/new`.

**Class B — HARD BLOCK (the recurring "dead again" cause)**: `mazemaker-mcp.service` cannot start because its `ExecStartPre` gate `mazemaker-mcp-preflight` exits 1. The unit sits in `activating (auto-restart)` (restart counter climbs into the hundreds) and the mcp container is NEVER created. Symptom chain: `/health` on :8765 returns 200 (wonderland proxy up) but `POST /mcp` returns `502 "mazemaker-mcp unreachable: All connection attempts failed"` (engine :8000 inside the pod is dead). The warmup service (`mazemaker-mcp-warmup.service`) death-loops logging `stats status=502 — engine not ready yet`.

**Diagnose (Class B)**:
1. `systemctl --user status mazemaker-mcp.service` → `activating (auto-restart)` + `ExecStartPre=...mazemaker-mcp-preflight (code=exited, status=1/FAILURE)`.
2. `journalctl --user -u mazemaker-mcp.service -n 20` → `ERROR: engine source changed since image build (image=<old> expected=<current>)`.
3. Proxy-vs-engine split: `curl -fsS http://127.0.0.1:8765/health` (200) vs `curl -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"p","version":"1"}}}'` (502).
4. Compare baked image label to live source fingerprint:
   - `podman image inspect localhost/mazemaker-v2-mcp:latest --format '{{index .Config.Labels "org.mazemaker.engine_sha"}}'`
   - `bash /home/alca/.mazemaker/bin/engine-sha.sh /home/alca/projects/mazemaker-pro/python`  ← Pro tree (tier=pro)
   They differ → that IS the gate failure. Root cause: image built from an older Pro commit than current source.

**Fix (Class B)** — rebuild the image from current Pro source so its `engine_sha` label matches what the preflight computes, then restart:
```bash
cd /home/alca/projects/mazemaker-v2-stack/backend
bash bin/build-all-locked.sh --only=mcp          # builds from ~/projects/mazemaker-pro/python (MAZEMAKER_PRO_ENGINE_SRC); bakes engine_sha = current Pro fingerprint into the image label. NO --push → no registry needed. Nuitka + C++ libmazemaker.so compile: 10–25 min.
# CRITICAL TAG-GAP: the build tags registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc6[-gpu] — NOT the localhost/mazemaker-v2-mcp:latest|:gpu the quadlets run. No auto-retag without --push+install. Retag manually:
podman tag registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc6      localhost/mazemaker-v2-mcp:latest
podman tag registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc6-gpu localhost/mazemaker-v2-mcp:gpu
systemctl --user restart mazemaker-mcp.service   # preflight now passes → container starts, :8000 up, :8765 proxy 200
# verify 200:
curl -fsS -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"p","version":"1"}}}'
```
After the server is back, the 31 tools are STILL not registered in a Hermes session that started while mcp was down. Re-register by restarting the gateway (drops the current session — expected): `systemctl --user restart hermes-gateway.service`. See `references/mcp-down-diagnosis.md` for the full command recipe and preflight internals.

**CRITICAL PITFALLS**
- **Pro vs Free source trap**: when tier=pro (db.toml + license = postgres), the preflight hashes the PRIVATE Pro engine tree `~/projects/mazemaker-pro/python`, NOT the public free tree `~/projects/mazemaker/python`. The free tree hashes to a *different* sha (e.g. `adc881ca…` vs the Pro `c4343504a460…`). A naive rebuild from the free tree would STILL fail the gate. `build-all-locked.sh --only=mcp` resolves `MAZEMAKER_PRO_ENGINE_SRC` → Pro tree automatically — never hand-point the build at the free repo.
- **Dream-worker is NOT the MCP server**: `mazemaker-dream-worker.service` (image `:gpu`) joins the pod network and shares the pod's published `:8765` surface, but does NOT serve `/mcp` — wonderland proxy does, forwarding to the mcp container's `:8000`. Don't mistake the dream-worker answering `/health` 200 on `:8765` for a working server; `/mcp` 502 means the mcp container itself is down.
- **Rebuilding `:gpu` does not disrupt the running dream-worker**: `build-all-locked.sh --only=mcp` rebuilds BOTH `:latest` (mcp.service) and `:gpu` (dream-worker) tags. The running dream-worker keeps the old `:gpu` image by ID until it is itself restarted, so the rebuild is safe w.r.t. the live worker.
- **Gateway restart is the LAST step**: it kills the current agent session. Do the image build + `mazemaker-mcp.service` restart + `/mcp` 200 verification FIRST, then `systemctl --user restart hermes-gateway.service`.
- **The restart loop is benign**: `RestartPreventExitStatus=1` is in the quadlet but ExecStartPre failure still triggers `Restart=on-failure`, so the counter climbs — it's failing closed (not 500-looping). The real fix is the rebuild, not stopping the loop.
- **THE TAG-GAP IS THE REAL RECURRING BLOCKER (2026-07-20)**: `build-all-locked.sh` tags `registry.mazemaker.dev/mazemaker-mcp:1.0.0-rc6[-gpu]`, but the quadlets run `localhost/mazemaker-v2-mcp:latest`/`:gpu`. Skipping the manual `podman tag` leaves the STALE localhost image (old `engine_sha`) running, so the preflight STILL fails even after a successful build. Always retag to the localhost names after every `--only=mcp` build. Verify: `podman image inspect localhost/mazemaker-v2-mcp:latest --format '{{index .Config.Labels "org.mazemaker.engine_sha"}}'` must equal `bash /home/alca/.mazemaker/bin/engine-sha.sh /home/alca/projects/mazemaker-pro/python`.
- **Restart storm ≠ swap/thrash cause**: the preflight exits at `ExecStartPre` BEFORE the container (and its GpuRecallEngine tensor) ever loads, so the loop consumes negligible RAM. If the box is swapping, it's chronic capacity — `mazemaker-dream-worker.service` (~7 GB) + the mcp GpuRecallEngine (~4 GB) on a 31 GB host — NOT the restart loop. Don't attribute swap pressure to the mcp death; the death actually REDUCES load.

### Full Clean Restart of the Entire Stack
When the user reports the stack is "not normal" / escalating / "kill it all and clean-restart", do a FULL podman kill + clean start rather than patching the single failing unit. Verified procedure (2026-07-20):

**Unit inventory** (all `mazemaker-*` under `~/.config/systemd/user/`; core containers are quadlet-generated from `~/.config/containers/systemd/*.container` + `mazemaker.pod`):
`mazemaker-pod`, `mazemaker-pgvector`, `mazemaker-mcp`, `mazemaker-license-client`, `mazemaker-embedding-worker`, `mazemaker-wonderland`, `mazemaker-dream-worker`, `mazemaker-hermes-bridge`, `mazemaker-apk-gateway`, `mazemaker-apk-gateway-mdns` (plus auxiliary watch/upgrade oneshots that are not normally running).

**STOP** — a single batch `systemctl --user stop <all>` FAILS with `Job ... canceled` because `mazemaker-mcp.service` `Requires=mazemaker-pod.service` (Pod=) creates a transaction conflict. Either stop one-by-one leaves→pod, or use the mask+kill path:
```bash
UNITS="mazemaker-apk-gateway-mdns.service mazemaker-apk-gateway.service mazemaker-hermes-bridge.service mazemaker-dream-worker.service mazemaker-embedding-worker.service mazemaker-wonderland.service mazemaker-license-client.service mazemaker-mcp.service mazemaker-pgvector.service mazemaker-pod.service"
systemctl --user mask $UNITS        # prevents Restart=always respawn during kill
systemctl --user stop $UNITS
podman pod rm -f mazemaker          # force-kill all containers (SIGKILL); does NOT touch pgvector bind-mount data
systemctl --user unmask $UNITS      # restore so they can start again
systemctl --user daemon-reload      # REGENERATES quadlet .service files (mask deleted them; .container/.pod sources survive; .service.d/ drop-ins survive)
```
**PITFALL — mask deletes quadlet .service files**: `systemctl mask` replaces each unit file with a `/dev/null` symlink (deleting the original). For quadlet units this is recoverable via `daemon-reload` (regenerated from `.container`/`.pod` sources) — BUT for any hand-written real `.service` file it would be lost (mask errors "already exists" and skips). Always run `daemon-reload` after unmask so the regenerated units are live before starting.

**START** — order matters; pgvector must be ready (postgres accepts connections) BEFORE mcp, and mcp MUST be started LAST because its drop-in restarts `hermes-gateway.service` (drops the current session):
```bash
systemctl --user start mazemaker-pod.service mazemaker-pgvector.service \
  mazemaker-license-client.service mazemaker-embedding-worker.service \
  mazemaker-wonderland.service mazemaker-dream-worker.service \
  mazemaker-hermes-bridge.service mazemaker-apk-gateway.service mazemaker-apk-gateway-mdns.service
# wait for pgvector crash-recovery (WAL redo ~60s after the SIGKILL) to finish:
podman logs systemd-mazemaker-pgvector 2>&1 | tail -5 | grep -q "ready to accept connections" || sleep 30
systemctl --user start mazemaker-mcp.service   # LAST: triggers gateway restart (session drop) + warmup
```
- **pgvector crash recovery is NORMAL** after `podman pod rm -f` (postgres was SIGKILLed). It replays WAL ("redo in progress") then logs "database system is ready to accept connections". Data is intact — wait, don't panic.
- **mcp warmup wedge**: after start, `mazemaker-mcp-warmup.service` is `activating` while GpuRecallEngine loads its tensor (1–3 min). `/mcp` blocks during this; clears itself. `/health` on :8765 returns 200 immediately.
- **Verify**: `curl -fsS http://127.0.0.1:8765/health` → `{"status":"ok",...}`; gateway `MainPID` changes after mcp start = 31 tools re-registered in the new session.

Full command recipe in `references/clean-restart-procedure.md`.

### Android/Mobile Hermes Bridge Connectivity
When the Android APK says it is not connected to the bridge, treat it as a separate runtime path from the MCP server:

- Pod/MCP endpoint is usually `:8765`; mobile Hermes bridge sidecar is usually `:8769`.
- Android `127.0.0.1` means the phone itself, not the host. The intended direct LAN shape is pod host `192.168.0.2:8765` and bridge `192.168.0.2:8769`.
- A phone timeout against `http://<pod-ip>:8769/sessions` means service/network failure first, not APK parsing.
- Verify with `ss -ltnp '( sport = :8769 )'`: `0.0.0.0:8769` or `[::]:8769` is good; `127.0.0.1:8769` is localhost-only and unreachable from the phone.
- If the bridge binds localhost only, use a systemd user drop-in to clear `MAZEMAKER_HERMES_BRIDGE_BIN` and run the source bridge directly:
  ```ini
  [Service]
  Environment=MAZEMAKER_HERMES_BRIDGE_BIN=
  ExecStart=
  ExecStart=/usr/bin/python3 %h/projects/mazemaker-architect/bridge/mazemaker-hermes-bridge.py
  ```
  Then run `systemctl --user daemon-reload` and `systemctl --user enable --now restart mazemaker-hermes-bridge.service`.
- If `ss` is correct but the phone still times out, check firewall, router isolation, guest WiFi, or phone subnet before changing APK code.
- If the phone browser reaches the bridge but the APK does not, force-stop the app, check host settings, and remember that release APK cannot update over debug without uninstall-first due to signature mismatch.

For the full client-side decision table and command recipe, load `android-mobile-architecture` and read `references/mazemaker-hermes-bridge-troubleshooting.md`.

### Dream Garden Dispatch (Cron)
Cron job `dream-garden-insights` posts to #dream-garden when insight growth exceeds +1000 threshold. Uses `dream_disp.py` script which reads/writes `dream_disp_state.json` for last-reported insights tracking. See `references/dream-garden-state-file.md` for verified state file pattern.

**Critical Pitfall**: Two dispatch scripts exist with divergent logic:
- `~/.hermes/scripts/dream_disp.py` (pre-run) - fetches live stats, uses `last_total` field
- `~/.hermes/palace/scripts/dream_garden_update.py` - has hardcoded values, uses `last_total_insights` field

**Fix**: Always fetch live stats via MCP tools. Never hardcode insight counts. See `references/dream-garden-patterns.md` for correct patterns and the 2026-06-15 fix.

### GPU Configuration Verification
PyTorch is CPU-only build (2.6.0+cpu) → `torch.cuda.is_available()` returns False. Embedding uses HttpEmbeddingBackend. No GPU processes in containers. VRAM budget calculations are conservative.

### VRAM Budget (RTX 4060 Ti, 16GB)
| Component | VRAM |
|---|---|
| Embedding worker (BGE-M3) | ~3.0 GB |
| GpuRecallEngine | ~5.5 GB |
| Dream_worker --once (extra) | +~8.5 GB (temporary) |
| Xorg + desktop | ~0.5-1 GB |
| ComfyUI (if running) | ~5 GB (kill when not in use) |
| **Total usable** | **~14.5 GB** (leaves ~1.5-2 GB headroom) |

### License Fingerprint Binding
**Root cause**: Compiled `fingerprint_proof.so` looks for cached fingerprint at `/var/lib/mazemaker/fingerprint` (hardcoded). Container only mounted at `/root/.local/share/mazemaker/`. Fallback computes fingerprint from pod-internal virtual MAC → wrong hash.
**Fix**: Add second volume mount `Volume=%h/.local/share/mazemaker:/var/lib/mazemaker:ro,z` to license-client container. Apply to ALL THREE locations.

**Re-registration required**: Existing JWT has old `sub` bound to wrong fingerprint. Run `curl -fsSL https://api.mazemaker.dev/install.sh | bash -s -- --reconfigure`.

---

## 5. Visuals Iteration / Three.js (formerly `mazemaker-visuals-iteration`)

### When to Load
- Running the MAZE CREW LOOP cron job (maze-crew-bio/dream/trailer)
- Improving mazemaker-architect visualizations
- Autonomous iterative improvement over related visual files
- Trailer/launch content work — **load this AND check launch framing first**
- "Never seen before" demonstrations of autonomous dream engine

### The Three Files
Located in `~/projects/mazemaker-architect/public/`:
| File | Purpose | Key Visual Elements |
|------|---------|-------------------|
| `maze-crew-bio.html` | Biological organism — thought regions as living tissue | Instanced mesh nodes, tissue hulls, traveling pulses, heartbeat, fog-of-war, 3000-point starfield |
| `maze-crew-dream.html` | Dream engine — NREM/REM/Insight phase cycling | Dream particles, brain shell, ripple shader, bridge-discovery pulses, phase progression, REM chaos, traveling activation pulses, arrival flash bursts, RGB chromatic split, community halos |
| `maze-crew-trailer.html` | 20s cinematic auto-looping trailer | CatmullRom camera spline, 900-node synthetic maze, black fade-out loop, no HUD, RGB chromatic split overlay, camera speed curve |

### Rotation System
Fixed: **bio → dream → trailer → bio → …**
Determine next: read `public/maze-crew-ITERATION-LOG.md` `## Next Up`, cross-check mtime + git status. Prefer log as canonical.

### Guiding Principles (NOT optional)
- **Visualize COGNITION, not structure** — nodes as tissue/organic clusters, not graph vertices
- **Biological/cosmic aesthetic** — breathing, pulsing, growing; maze as character with mood
- **Dream phases = brain sleeping/dreaming/awakening** — NREM slow/dim, REM chaotic/bright, INSIGHT crystallized clarity
- **Thought propagation** — activation VISIBLY travels: (a) Traveling spheres along arcs (bio), (b) Network wavefront via edges (dream). Pick mechanism per file.
- **Infinite feel** — distant fog-of-war structures, slow-rotating starfields, nebula particles
- **Screen-recordable** — 7-second clip quality, no flickering, no pop-in, smooth transitions

### Making a Change
**One Change Per Run** from priority list:
- Add try/catch error handling around animate loop
- Fix missing `setSize()` on renderer (pixelation bug)
- Add phase progress bar
- Improve thought propagation visuals (see `references/pulse-arrival-flash.md`, `references/trail-ribbon.md`, `references/billboard-trail-rings.md`)
- Add distant fog-of-war structures for infinite feel
- Add heartbeat indicator
- Fix camera path discontinuities
- Add RGB shift on phase transitions
- Add camera-proximity gain — derive one `[0..1]` factor from camera-to-scene-center distance, apply to multiple heartbeat-driven layers (see `references/camera-proximity-gain-pattern.md`)
- Add phase-color vignette bloom (see `references/phase-color-transition-bloom.md`)
- Connect existing scene elements to activation (see `references/brain-shell-pulse.md`)
- Add community halos on INSIGHT (see `references/community-halos.md`)
- Add camera speed curves (see `references/camera-speed-curve.md`)
- Bring sibling files to parity

### Critical Technical Pitfalls

**Patch-Ordering TDZ Hazard (Insertion)**: When inserting code across multiple `patch()` calls, `const`/`let`/`var` declarations are hoisted within scope but NOT across patches. Place declaration FIRST, then code that uses it. Re-read patched region after ALL patches.

**Declaration-Deletion TDZ Hazard (Removal)**: Removing a seemingly redundant declaration can orphan uses 50-80 lines later. After removal, grep for ALL remaining uses in same scope — every use must still have declaration above it.

**Per-Frame THREE.Object3D/Color Allocation (GC Pressure)**: Every `new THREE.Object3D()`, `new THREE.Color()`, `new THREE.Vector3()` in animate loop = 60 allocations/sec. Hoist to module scope + reuse with `.set()`.

**Trail Buffers: Pre-Allocated Circular Buffers (NOT Dynamic Arrays)**: `trail: []` + `push/shift/splice` = massive GC. Use `Float32Array` circular buffer with `trailBuf`, `trailLen`, `trailWrite`.

**Dead Computed Values**: Value computed every frame but never applied (e.g., `targetVig` computed but never assigned to element.style). For every `const target*` or `const desired*`, ask: "where does this value go?"

**Lazy Material Property Capture**: Use `??` (nullish coalescing), NOT `||`:
```js
c.material.opacity = (c.userData._baseOp ?? (c.userData._baseOp = c.material.opacity)) * distantPulse * 0.8;
```

**CSS Filter Effects on Canvas**: Apply CSS `filter` to `<canvas>` for cinematic post-processing (chromatic shift, desaturation, vignette) without Three.js post-processing pipeline.

**Module-Scoped Getter/Setter Syntax**: ES module = strict mode. Getters/setters must be SEPARATE properties with comma:
```js
const obj = { get x() { return x; }, set x(v) { x = v; } };  // correct
```

**Three.js API Pitfalls**:
- `setInstanceMatrix()` does NOT exist → use `setMatrixAt(index, matrix)`
- `mesh.attributes` does NOT exist → always use `mesh.geometry.attributes`
- `getMatrixAt()` / `getColorAt()` do NOT exist on `InstancedMesh` (r163) → recompute from source data

### Autonomous Dream Engine Visualization
For revolutionary "never seen before" visualizations showcasing autonomous dream engine:
- Three-phase cycle: NREM (memory replay), REM (bridge discovery), INSIGHT (pattern recognition)
- Real-time neural network with 150+ autonomous nodes
- Dynamic connection formation, community clustering, live statistics
- Key message: "Databases store data. Operating systems create behavior. MAZEMAKER IS THE SECOND ONE."

### Sibling-File Parity Pattern
When feature X exists in one file and adding to another:
1. Read source file's implementation
2. Adapt to target file's structure
3. Document in iteration log

### Iteration Log Management
File: `public/maze-crew-ITERATION-LOG.md`
Update after EVERY change: add row (run#, date, file, description), update `## Next Up` to next file in rotation.

### Git Workflow
```bash
cd ~/projects/mazemaker-architect
git add public/maze-crew-<file>.html public/maze-crew-ITERATION-LOG.md
git commit -m "maze-crew-<file>: <brief description> (run #N)"
```

### Verification Checklist
- [ ] File reads correctly (`wc -l`, no truncated endings)
- [ ] Module syntax check passes: extract `<script type="module">` → `node --check`
- [ ] Variable declarations precede usage (insertion TDZ check)
- [ ] After variable removal: grep remaining uses — every use has declaration above (deletion TDZ check)
- [ ] Iteration log updated + next file
- [ ] Changes committed to git

---

## 8. DECIDE Phase (Ranking Discoveries)

The DECIDE phase runs every 60 minutes via `python3 ~/.hermes/loops/tri-state/decide_rank.py`. Its job: read recent pulse-wurm discoveries, score them by graph connectedness + novelty + recency, and write the top 3 as `decision:rank-YYYYMMDD-<priority>-<n>-<slug>` memories so the ACT phase (06:00Z daily) can implement them.

This section captures the operational lessons from running the DECIDE phase. The skill is the canonical home — these patterns are non-obvious and were learned the hard way.

### The Three Non-Obvious Techniques

**1. Use `mazemaker_browse` with `label_prefix`, NOT `mazemaker_recall` with a glob, to enumerate the discovery pool.**

`mazemaker_recall(query="discovery:pulse-tick-*", limit=50)` is the obvious-looking call but it has TWO failure modes that silently drop fresh discoveries:

- **Glob-vs-label mismatch**: Real labels are `discovery:pulse-wurm-20260621_*`, NOT `discovery:pulse-tick-*`. The recall query matches semantically-related prior decisions, not the actual discovery memories. The 0330 cycle flagged this in its context notes ("Recommend updating the recall query in future DECIDE cycles to use a broader pattern like `discovery:pulse-*` or `discovery:pulse-wurm-*` to avoid missing fresh discoveries") — and the recommendation was not followed. By the 08:15 cycle, the same gap re-occurred.
- **Semantic ranking hides recent items**: `mazemaker_recall` ranks by similarity to the query. A vague query like "pulse-tick" returns the most-cited old decisions, not the freshest discoveries. The DECIDE phase needs CHRONOLOGICAL order, not semantic order.

**Correct pattern**:
```python
mazemaker_browse(label_prefix="discovery:", limit=30)
```
This returns the 30 most-recently-created memories in `created_at DESC` order. The actual label-prefix for the broader pulse-wurm-2.0 family is `discovery:pulse-wurm-*` and `discovery:pulse-*` — using `discovery:` as the prefix captures both. Then filter in Python to the last 24h window by `created_at` (UTC).

**2. The 2-hour skip rule is on the DECISION memory's `created_at`, not the discovery memory's `created_at`.**

The system prompt says: "Skip items already written as `decision:rank-*` in the last 2 hours to avoid duplicates." This means: check the `created_at` of the DECISION memories, not the discovery memories. A discovery from 4h ago is eligible if no decision was written about it in the last 2h.

The 2-hour window is also where the **3-rank-per-cycle limit** bites. If cycle N at 08:00 UTC filled its 3 ranks with the US-China AI competition axis (silent sabotage / Chinese distillation / NK npm), and a CRITICAL Palantir-Maven-Iran finding was created at 07:55 UTC, that finding is INSIDE the 2h window but MISSED by cycle N. The NEXT cycle (08:15 UTC) must pick it up. Always enumerate the full 24h discovery pool via `browse`, not just the recent 2h, and check decision coverage on each.

**3. `created_at` is UTC; the suffix on the label (e.g. `_0609_tick`) is local-time-looking but unreliable for skip math.**

Discovery labels like `discovery:pulse-wurm-20260621_0609_tick` LOOK like the tick happened at 06:09 local time, but the `created_at` field in the memory record is the authoritative UTC timestamp. The DECIDE cron script's `timestamp` field (e.g. `20260621_081557`) is also UTC. Mismatching local-vs-UTC in skip-rule math leads to either (a) re-ranking items already in the skip window or (b) skipping items that should be ranked. Always do skip math on `created_at` UTC vs current UTC.

### The DECIDE Phase Workflow (Verified Pattern, 2026-06-21 08:15Z)

1. **Enumerate the pool**: `mazemaker_browse(label_prefix="discovery:", limit=30)` — get the 30 most recent memories.
2. **Filter to 24h window**: keep items where `created_at` is within the last 24h (UTC). Convert `created_at` epoch → UTC datetime, compare against current UTC.
3. **Filter out already-decided**: for each discovery, check if a `decision:rank-*` memory references it. The decision's `content` field typically includes "Discovery Memory ID: NNN". Parse out the ID and compare. Skip if the decision was created in the last 2h UTC.
4. **Score each candidate** by:
   - **Graph connectedness** (0-1): `mazemaker_recall(query=<core_topic>, limit=10)` → count how many of top 10 are `fact:*` or `decision:*` labels. Divide by 10.
   - **Novelty** (0-1): `1 - max_similarity` to closest existing memory from the same recall. If max_sim is 0.7, novelty is 0.3.
   - **Recency** (0-1): linear decay from 1.0 (just created) to 0.0 (24h+ old). Roughly: `max(0, 1 - age_hours/24)`.
   - **Priority boost**: +0.20 (CRITICAL), +0.10 (IMPORTANT), +0.00 (NICE_TO_KNOW).
5. **Rank by total score** and write the top 3 with `mazemaker_remember`:
   - `label`: `decision:rank-YYYYMMDD-<priority>-<N>-<short-slug>`
   - `content`: 60-300 words with discovery ID, why-it-matters, score breakdown, action type, cluster context.

### Why Each Cycle Has Only 3 Ranks (and Why That Matters)

The DECIDE cron writes 3 decisions per cycle. This is a HARD LIMIT. A 60-minute cadence means the cycle pool refreshes every hour. If a CRITICAL finding is created at minute 0 of cycle N and the cycle's 3 ranks are filled with less-urgent items, the CRITICAL finding waits up to 60 minutes for cycle N+1 to pick it up. The implications:

- **Pick by composite score, not by chronology alone.** A 20-min-old CRITICAL beats a 5-min-old NICE_TO_KNOW.
- **Cluster diversity matters.** Filling all 3 ranks with the same axis (e.g., 3 US-China AI competition findings) misses other axes that are equally fresh. Aim for one CRITICAL + one IMPORTANT + one NICE_TO_KNOW from different clusters.
- **The 3-rank limit is the bottleneck, not the discovery volume.** A 30-item pool with 3 truly novel CRITICAL/IMPORTANT items is fully served by 3 ranks. A 30-item pool with 10 novel items needs 4 cycles to drain.

### Common DECIDE Phase Pitfalls

- **Trusting the recall query's top-50 results**: This is the most common failure mode. The recall API is semantic, not chronological. The 4th-50th results are usually saturated prior decisions, not fresh discoveries. Always verify with `browse` that you've actually seen the 24h window.
- **Counting `decision:rank-*` from same cycle as duplicates**: They are not duplicates if they cover different discoveries. Only skip if the SPECIFIC discovery ID appears in a decision's content within the 2h window.
- **Treating recent-vs-rankable as the same thing**: A 5-min-old discovery might be NICE_TO_KNOW with low score. A 1-hour-old discovery might be CRITICAL with high score. Score trumps age.
- **Missing the 2h gap when 08:00 UTC cycle runs**: The 2h skip window from the 08:00 cycle's 3 decisions extends to 10:00 UTC. The 08:15 cycle (this one) is INSIDE that window for items the 08:00 cycle covered, but OUTSIDE for items the 08:00 cycle did NOT cover (because the 3-rank limit excluded them). The browse-based enumeration handles this correctly; the recall-based approach does not.

### Reading `decide_rank.py` Output

The cron runs `python3 ~/.hermes/loops/tri-state/decide_rank.py` first. Its JSON output is the instruction contract:
```json
{"phase": "decide", "timestamp": "20260621_081557", "cadence": "60min", "type": "decision_request",
 "instructions": "1) mazemaker_recall with query 'discovery:*' limit=50 ...", ...}
```
Note: the script's `instructions` field still suggests the broken `mazemaker_recall` pattern. The workflow above supersedes those instructions — use `browse` instead. The script's role is just to provide a timestamp anchor; the actual discovery enumeration is your call.

### References
- `references/decide-phase-skip-rule-2026-06-21.md` – worked example of skip-rule math with concrete UTC timestamps and decision IDs.
- `references/decide-phase-saturation-2026-06-22.md` – worked example of a fully-saturated cycle (all discoveries already ranked); covers the `[SILENT]` cron-delivery rule, saturation detection, and parsing large persisted recall/browse outputs.
- `references/decision-label-format.md` – label schema and slug-derivation rules.


### When to Load
- Generating multi-style comic variations
- Using riverflow API for image generation
- Do NOT load for voice — use `skill_view(name='comic-voiceover-scripting')` for narration scripts and `skill_view(name='tts-local-generation')` for audio generation

### Voiceover Production
Comic voiceovers are handled by two separate skills:
- **`comic-voiceover-scripting`** — writing narration scripts (tone, structure, dialog format)
- **`tts-local-generation`** — generating audio from scripts (Orpheus 3B, Qwen3-TTS, CUDA isolation)

### Comic Generation Pipeline
**Pattern: Multi-style single story**
- 15 pages telling the same story across 22+ artistic variations
- Each page: ARCHITECT, SYSTEM, DREAM ENGINE, INCEPTIONS characters with ALL text rendered
- Style examples: cyberpunk neon, steampunk brass, Art Deco, biopunk organic, solarpunk futurism, terminal green, etc.
- Use `sourceful/riverflow-v2.5-pro:free` with `reasoning: {effort: "high"}`

**Batch Generation Pattern** (from V3 session):
- Each riverflow call takes 2-3 minutes
- Total: 23 styles × 15 pages = 345 images
- Estimate total time: ~11 hours
- Use named temp files to avoid race conditions:
```python
pf = '/tmp/style_{style}_{page}.json'  # NOT tempfile.mktemp()
rf = '/tmp/out_{style}_{page}.json'
subprocess.run(curl_cmd, capture_output=True, timeout=480)
time.sleep(1)  # CRITICAL: wait for write to complete
with open(rf) as f: data = json.load(f)
```

**23 Artistic Styles** (for V3):
1. cyberpunk_neon
2. steampunk_brass
3. art_deco_luxury
4. biopunk_organic
5. solarpunk_futurism
6. dark_academia
7. terminal_green
8. paper_cutout_flat
9. isometric_low_poly
10. ukiyo_e_woodblock
11. pop_art_comic
12. noir_chiaroscuro
13. glitch_digital
14. pixel_art_retro
15. wireframe_tech
16. crystalline_geometric
17. neural_network_glow
18. architectural_blueprint
19. watercolor_wash
20. ink_brush_traditional
21. diesel_punk_heavy
22. quantum_superposition
23. analog_cybernetics

### Batch Generation Pattern (from V3 session):
- Tempfile race: use named paths (`/tmp/style_{style}_{page}.json`), NOT `tempfile.mktemp()`
- After curl completes, `time.sleep(1)` before reading output file
- API timeout: 420s (`--max-time 420`), subprocess timeout 480s
- Resume logic: skip if output exists and `> 5KB`

---

### V4 Pattern: Sector Usecase Generation (115 images, 1 per usecase)

**When to use**: User asks for breadth across sectors rather than depth in one story. One image per usecase showing Mazemaker tech solving a real-world sector problem.

**Key difference from V3**: V3 = 23 artistic styles × same 15-page story (345 images). V4 = 115 usecases × 1 image each, sector-focused methodology. The story IS the sector problem being solved.

**Usecase data structure** (Python dict per usecase):
```python
dict(id="health-01", sector="HEALTHCARE",
     title="Hospital Data Federation",
     scene="THE ARCHITECT stands between two hospital Podman pods, "
           "patient record data flowing through teal encrypted tunnels...")
```

**19 sector categories** (established in V4): HEALTHCARE, MILITARY, FINANCE, GOVERNMENT, ACADEMIA, CRITICAL INFRASTRUCTURE, ENERGY, SPACE & AEROSPACE, TELECOM, LEGAL, INSURANCE, SUPPLY CHAIN, INTELLIGENCE, CLIMATE, CYBERSECURITY, MANUFACTURING, TECHNOLOGY, QUANTUM, EMERGENCY SERVICES

**Prompt construction** (Riverflow API call):
1. Start with MASTER_STYLE (characters: ARCHITECT, SYSTEM, DREAM ENGINE, INCEPTIONS + Mazemaker tech visuals)
2. Append SECTOR + USECASE title
3. Append SCENE description — shows ARCHITECT doing sector-specific work with Mazemaker tech
4. Every scene references specific Mazemaker technologies: Neural Memory Graph, Rootless Podman Federation, Post-Quantum Encryption, Zero-Knowledge Protocol, PULSE Search, Dream Engine cycles, Recall Prism, Federation Protocol
5. End with format instruction: "21:9 ultrawide 1536x672. Single-panel comic illustration."

**API call** (direct https to OpenRouter):
```python
body = json.dumps({
    "model": "sourceful/riverflow-v2.5-pro:free",
    "reasoning": {"effort": "xhigh"},
    "messages": [{"role": "user", "content": prompt}],
    "max_tokens": 4000
})
```
Images return in `choices[0].message.images[0].image_url.url` as base64 data URLs.

**Resume-capable pattern**: Skip if output exists and >5KB. Each usecase saved to `{sector_dir}/{id}_{title_slug}.webp`.

**Performance**: ~170-200s per image at xhigh reasoning. 115 images ≈ 5.5-6.5h total. Sourceful provider ~94.9% uptime.

**Visual style**: Same MASTER_STYLE from `~/mazemaker-hero.webp` (teal/pink/charcoal, blueprint grid, manga ohmsha). Characters identical to V3.

#### CRITICAL PITFALL: Riverflow free tier rate limiting

`sourceful/riverflow-v2.5-pro:free` has severe rate limiting that can stall bulk generation:

- **Observed symptoms**: After 7 successful images at ~3 min intervals, the API returns `{"error": {"message": "Rate limit exceeded: limit_rpm/sourceful/riverflow-v2.5-pro-20260605/... High demand for sourceful/riverflow-v2.5-pro:free"}}`
- **Root cause**: The free model ID includes a date (`20260605`), suggesting a time-limited free tier. RPM limit is very low (~1-2 RPM) and the free tier is heavily contended.
- **Exponential backoff does NOT help**: Even waiting 5+ minutes between requests, the limit persists for hours. The free tier appears to have a hard daily cap (~5-10 images total).
- **Rate limit recovery timing**: Uncertain — may reset daily. Did not recover within 3+ hours of continuous retry with up to 5min backoff.
- **Alternative approaches when rate limited**:
  - Switch to a different free model (HuggingFace FLUX.1-schnell inference API — requires HF_TOKEN)
  - Use a cheap paid OpenRouter model (Google Gemini Flash Image: ~0.05¢/image)
  - Set up FAL AI free tier (FAL_KEY at fal.ai, free credits on signup)
  - Run locally with SDXL-Turbo or ComfyUI if VRAM permits
- **Detection pattern**: When Riverflow free calls start returning `"Rate limit exceeded"` after a burst of successful images, stop retrying and switch fallback immediately. The backoff loop wastes hours.

For the full sector/usecase listing see `references/v4-comic-usecases.md`.
