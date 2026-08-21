---
name: podman-quadlet-ops
description: "Audit Podman Quadlet stacks: OOM, drop-ins, reboot cascades."
trigger: "user asks to audit/analyze a Quadlet deployment, investigates an OOM-killed container (status=137), stop timeouts, units not coming up after reboot, or env/config contradictions between units and toml/env files. Covers stacks like the mazemaker-v2 memory pod."
tags: [podman, quadlet, systemd-user, containers, oom, deployment-audit, rootless]
---

# Podman Quadlet Ops (rootless, systemd --user)

Read-only audit + troubleshooting methodology for Quadlet stacks. Developed on the mazemaker-v2 stack (see `references/mazemaker-v2-stack-deployment.md` for that concrete snapshot).

## Workflow (read-only audit)

1. **Inventory both sides**: repo templates (e.g. `backend/client/quadlet/`) AND installed `~/.config/containers/systemd/` — including `*.d/` drop-ins AND `*.disabled-*` files (renamed = deliberately OFF, a common way to park a drop-in). Build a table: Unit | Type | After/Wants/Requires/BindsTo | GPU (AddDevice=nvidia.com/gpu) | Volumes | Env highlights.
2. **Repo vs installed comparison**: installers `cp` signed units over local edits on every update; drop-ins exist precisely to survive that. Same file size ≈ same content; `stat` mtimes reveal recent manual edits.
3. **Effective values, not comments**: unit comments drift from reality (measured: "MemorySwapMax=0" comment vs `systemctl --user show` → `infinity`; budget sums in comments stale by weeks). Truth:
   - `systemctl --user show <unit> -p MemoryMax -p MemoryHigh -p MemorySwapMax -p FragmentPath`
   - `FragmentPath=/run/user/1000/systemd/generator/...` = quadlet-generated unit.
   - `systemctl --user cat <unit>` shows merged main + drop-ins — verify a fix (e.g. ExecStartPost) actually reached the generated unit.
4. **Unit state**: `systemctl --user list-units --all | grep ...`, `list-timers --all`, `is-enabled` vs `active`. Timers/paths can be `enabled` but `inactive` (stopped after a `daemon-reload` or manual stop) — `is-enabled` alone lies about whether they fire.
5. **Env sanity**: merge EnvironmentFile + toml + runtime.env + drop-in Environment lines; note that compute.toml/db.toml/db.env are license-client-written (DO NOT edit by hand); flag contradictions (e.g. EMBED_BACKEND=http vs socket path configured but unused).
6. **Reboot reasoning**: map the cascade — which targets are `enabled` (boot autostart), which are `static` (CLI-only), what pulls what via Wants/Requires, and which path-units/timers can *reactivate* a stopped pod (see pitfalls).

## OOM forensics (status=137)

status=137 = SIGKILL. Sources, in order of likelihood given evidence:
1. **Container cgroup limit** (`--memory=` via PodmanArgs) — kill happens AT the limit.
2. **Unit MemoryMax** (parent cgroup under `--cgroups=split`) — same, at the limit.
3. **Kernel OOM killer (host level)** — kills BELOW any per-unit limit when the SUM oversubscribes physical RAM. Check `dmesg -T | grep -i oom` and `journalctl -k` — both may be restricted/empty; then rely on the arithmetic.
4. **podman stop-timeout SIGKILL** (stop path, not crash) — journal shows StopTimeout-related messages.
5. Manual `kill -9`.

Decision pattern:
- Journal line `Consumed ... N memory peak` gives memory.peak. **Peak < all limits → NOT a cgroup/unit-limit kill → kernel OOM on the host.**
- Sum ALL MemoryHigh + MemoryMax across the pod vs physical RAM. Per-unit limits are individually defensible; the SUM is the defect. Missing MemoryHigh = first pressure signal is a kill instead of reclaim.
- `OOMScoreAdjust=500` (or higher) marks the sacrificial unit — the kernel picks it first under host pressure.
- MemoryHigh throttles/reclaims, it does NOT kill.
- Look for **two independent memory spikes with nothing sequencing them** (e.g. a restart hook re-arming a 12G tensor while the worker arms its own 13G) — the fix is sequencing, not budget numbers.

## Quadlet semantics that bite

- **Drop-in PodmanArgs REPLACES the main file's PodmanArgs entirely** — a drop-in overriding `--memory` must restate the full set incl. `--pod=`.
- **`Pod=mazemaker.pod` = pod MEMBER** + automatic `WantedBy=pod.service` (every pod start pulls the container). **`PodmanArgs=--pod=<name>`** joins the pod network at runtime WITHOUT member wiring — use when a container must start only via its own target (e.g. BindsTo a dream target), not with the pod.
- **`Pull=never` drop-in** for localhost-built images: without it, a missing image triggers a registry pull attempt → TLS/cert error → exit 125 crash loop.
- **Stop budget nesting**: app graceful timeout < podman `StopTimeout` ([Container], default 10s!) < systemd `TimeoutStopSec` ([Service]). If equal or inverted, podman SIGKILLs first. Verify with `podman inspect --format '{{.Config.StopTimeout}}'`.
- **Unit MemoryMax is the PARENT cgroup** of the container; a smaller unit limit silently caps the podman limit.
- **`BindsTo=` vs `PartOf=`**: PartOf only propagates stops FROM the target; BindsTo also prevents `Restart=on-failure` from reviving a unit while the target is down (orphaned-worker bug class).
- **engine_sha-style build fingerprints** hash the WORKING TREE including untracked/uncommitted files → builds are only reproducible from an identical tree; an uncommitted source file ships in images but breaks preflight digest matching on a fresh checkout.

## Image reproducibility & staleness-gate audit

Verified 2026-08-07 on the mazemaker stack (full map with file:line + commits: `references/build-chain-reproducibility-audit.md`). Chain to audit: Repo → build context → image LABEL → ExecStartPre gate → unit `Image=`.

1. **Read the fingerprint helper BEFORE trusting the label.** Typical shape: `find . -type f` with exclusion patterns and NO git filter → untracked files inside the source tree change the hash (latent poison: label drifts without any rebuild → gate later blocks spuriously, fail-CLOSED direction).
2. **Gate semantics are fail-open BY DESIGN** (mazemaker `mazemaker-mcp-preflight`, commit c8e02b2): blocks ONLY on a determinate mismatch (expected≠actual≠unknown); missing label, `unknown` label, or absent helper/source → warn + PASS ("pre-stamp image — skipping staleness check (fail-open)"). Intent: never brick a pod on ambiguity. A "dead" preflight is usually this design — read the code before declaring it broken. Gates typically exist on the mcp unit only, not on workers.
3. **Build context vs source**: build scripts rsync the whole tree into the context (e.g. `client/pod/<svc>/core/`) with pattern excludes only — no git filter, so uncommitted files DO ride into the context (verified junk: untracked `cpp/benchmarks/audit/*.md` in the mazemaker context) even when they never reach the final image. Diff context listing vs `git ls-files` to quantify.
4. **Label match test**: `podman image inspect <img> --format '{{index .Config.Labels "<key>"}}'` must equal `bash <sha-helper> <src-tree>`. Compare against the TIER-CORRECT tree — Pro vs free trees hash differently; comparing a Pro image to the free tree gives a false mismatch (and vice versa).
5. **Content verification**: `podman run --rm --entrypoint sh <img> -c 'ls /app'` — a compiled-only image shows `.so` only, zero `.py` (Containerfile lockdown is often fail-closed), and no junk (.md/logs/benchmarks). Cross-check the compile driver's skip list to know which source files are intentionally absent.
6. **Repo ↔ production drift checks** (the "divergence" claims): `git status` in ALL repos (uncommitted quadlet edits are the classic live≠HEAD drift — installers copy signed units, local edits live in the worktree), installer-recorded tag (`~/.mazemaker/installed.image_tag`) vs `<repo>/VERSION` (builder/installer tag skew), `diff ~/.config/containers/systemd/*.container <repo>/client/quadlet/*`, and `release/digests.json` vs registry tags.
7. **Byte-reproducibility ceiling**: floating `FROM` tags without `@sha256:` digest pins mean byte-identical rebuilds are NOT guaranteed even with pinned toolchain versions (e.g. Nuitka==2.5.4, requirements==-pinned).
8. **The one fix** for tree-based fingerprints: hash/extract via `git ls-files` / `git archive` so the fingerprint is a pure function of committed HEAD; digest-pin base images second.

## Pitfalls

- **Stale UNIX sockets in shared volumes** survive pod shutdown (e.g. `embed.sock`). If the server doesn't unlink before bind → EADDRINUSE on next start.
- **ExecStartPost `try-restart` on a RUNNING unit is a full restart**, not a no-op — fine as a one-shot nudge, but a crash-looping consumer re-restarts the dependency in a cycle, each restart re-arming its memory spike.
- **Path-units doing `systemctl restart` on inactive units START them** → watchers (db-watch, compute-watch, image-refresh) reactivate a deliberately stopped pod. Guard with a STOPPED flag file if the app has one.
- **oneshot failures rotate out of the journal fast** — capture `journalctl --user -u <unit>` details immediately, before they're gone.
- **Timers with `Requires=`/`After=` can pull up the whole pod** for a nightly pass (check what the service actually Requires vs Wants — a missing Wants on a runtime dependency makes the pass fail loudly).

## Verification

- After any analysis: `systemctl --user show <unit> -p ...` for every claimed limit; `systemctl --user cat` to confirm fixes are live; `podman inspect` for StopTimeout; compare `systemctl --user list-timers` NEXT/LAST with expectations.

## References

- `references/mazemaker-v2-stack-deployment.md` — concrete 2026-08-07 snapshot of the mazemaker-v2 stack: unit inventory, limit arithmetic, OOM timeline, env contradictions, fix suggestions. NOTE: the separate skill `mazemaker-autonomous-loop` covers the OLD stickman-video pipeline, not this deployment.
- `references/build-chain-reproducibility-audit.md` — verified 2026-08-07 map of the Repo→Image→Label→Unit→Pod chain: engine_sha semantics (fail-open preflight, untracked-file poisoning), rsync-without-git-filter evidence, dead sync.sh vs active plugin path, install.sh `:gpu` retag fix, drift inventory, reproducibility verdict 7/10 + one fix.
