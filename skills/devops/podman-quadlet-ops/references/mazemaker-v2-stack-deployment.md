# Mazemaker-v2 Stack Deployment — Snapshot 2026-08-07 (read-only audit)

Host: 31G RAM, RTX 4060 Ti 16G, rootless Podman + Quadlet under systemd --user.
State at audit time: pod deliberately stopped (all units inactive), ollama.service running.

## Pods
- `mazemaker` pod — local memory stack: license-client (8767), pgvector, mcp (8000), embedding-worker (8766), wonderland (8765, published 0.0.0.0 for federation), llm (8768). Images localhost/mazemaker-v2-* (+:gpu variants).
- `mazemaker-v2` pod — SaaS backend: api/nginx/cloudflared, NO memory limits at all.

## Effective limits (systemctl --user show; comments in units were stale)
| Unit | MemoryHigh | MemoryMax | MemorySwapMax |
|---|---|---|---|
| mcp | 12G | 16G | 2G |
| dream-worker | 12G | 16G | infinity (comment claims 0; container gets 0 via PodmanArgs --memory-swap=16g) |
| pgvector | 9G | 10G | infinity |
| llm | 3G | 4G | infinity |
| embedding-worker | 2500M | 3G | infinity |
| wonderland | 1500M | 2G | infinity |
| license-client | 256M | 512M | infinity |
| afe-window (oneshot) | 8G | 12G | infinity |

Sum: 51.5G MemoryMax / 40.3G MemoryHigh on 31G RAM → oversubscribed. The pgvector unit's arithmetic comment (32.5G/27.2G, dream 8G, mcp 5G) is outdated.

## OOM timeline (2026-08-07)
- 10:35 + 11:30 CEST: dream-worker status=137, both ~22min after worker start, shortly after SYNTHESIS+DAE phase. Last kill: memory peak 12.9G < 16G limit → NOT cgroup kill.
- dmesg/journalctl -k empty (restricted) — kernel OOM inferred from arithmetic + OOMScoreAdjust=500 + documented 19G swap pressure.
- DAE (dae_enabled=true in compute.toml, runtime.env MM_DAE_ENABLED=1) is a documented OOM amplifier: 214k-corpus recompute ~194s/cycle, recall channel "intentionally unwired". The MM_DAE_ENABLED=0 drop-in exists but was renamed `dae-off.conf.disabled-20260806` (parked).
- ExecStartPost `try-restart mcp` on every worker start = full mcp restart → 12G mcp arm spike parallel to worker's 13G arm → the "nothing sequencing them" pattern.

## Key mechanisms found
- dream-worker: NOT a pod member (`PodmanArgs=--pod=mazemaker`, no `Pod=` key) + `BindsTo=mazemaker-dream.target` (static, CLI-only) → no boot autostart, no pod-start pull-in.
- ExecStartPost fix (mazemaker-dream-worker.container:261): `-systemctl --user --no-block try-restart mazemaker-mcp.service` — live in generated unit; robust (-, --no-block, try-restart) but a full restart on running mcp; only fires on worker start, so the boot race (mcp has no After=embedding-worker → arms 2504 MiB duplicate tensor) persists until first worker start.
- Drop-ins in `~/.config/containers/systemd/<unit>.container.d/` (memory-16g, colbert, pull-never, embed-timeout) survive the daily signed-unit `cp`; memory-16g drop-in REPLACES PodmanArgs (must restate --pod).
- Stop budget nesting verified: app 10 < podman StopTimeout 30/150 < systemd TimeoutStopSec 45/180.
- engine_sha: build-all-locked.sh fingerprints the WORKING TREE (incl. untracked files); local images at audit time had NO org.mazemaker.engine_sha label (built outside the locked path) → mcp-preflight fails open → staleness protection dead. gpu_recall.py now committed (was uncommitted → non-reproducible builds, preflight mismatch on fresh checkouts).
- Image tag drift: installed mcp unit references `:latest` (installer rewrite to :gpu not applied or reset by update cp); works only while both tags point to the same ID.

## Reboot weak spots
- mazemaker.target enabled (boot autostart) but Wants pulse-pod.service which does NOT exist (sponge ingest silently gone).
- afe-window.timer: enabled but inactive (stopped 12:05); when it fires it pulls pod+llm up via Requires but NOT embedding-worker → nightly pass fails without a running stack.
- db/compute-watch + image-refresh restart commands START stopped units → watchers can reactivate a stopped pod; no STOPPED-flag guard (license-client knows MAZEMAKER_STOPPED_FLAG).
- Stale embed.sock survives pod down (EADDRINUSE risk if server doesn't unlink).
- update-watch/upgrade-watch: enabled but inactive; hermes-compress-guard disabled; selftest failed 05:34 (exit 1, journal already rotated).

## Suggested fixes (not applied)
1. Re-park DAE (rename dae-off drop-in back to .conf).
2. Recompute limit sums; target MemoryHigh total ≤ ~28G.
3. mcp: add After=embedding-worker; afe-window: add Wants=embedding-worker.
4. STOPPED-flag guard in db/compute-watch + image-refresh.
5. Build images only via build-all-locked.sh (restores engine_sha label); commit/ignore untracked engine files.
6. Limits for mazemaker-v2 pod containers; fix mcp unit to :gpu; correct MemorySwapMax comment; investigate selftest failure; start or deliberately disable afe-window.timer.
