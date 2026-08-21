---
name: durable-process-supervision
category: devops
description: Supervise long-running agent processes (BTQuant agency, ComfyUI, dream-worker, mcp servers, custom daemons) so they survive shell logout, crashes, and reboots on this operator's machine. Systemd user service is the canonical pattern; Daedalus wrapper detection BLOCKS nohup/setsid/disown at the shell level. Triggers when the operator says "lass laufen", a long-running process died with SIGTERM/SIGHUP, or you need to start a daemon that should outlive the agent session.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [devops, systemd, supervision, daemon, process-management, long-running, sigterm, nohup, setsid]
    related_skills: [hermes-s6-container-supervision, btquant-autonomous-agency, cron-job-discord-delivery]
---

# Durable Process Supervision

How to make a long-running agent process survive shell logout, crashes, and reboots on this operator's machine.

## When to use this skill

Load this skill when:
- You just started a long-running process (BTQuant agency, ComfyUI, dream-worker, an MCP server, a custom daemon) and need it to outlive the current terminal session
- A previously-running process died with SIGTERM or SIGHUP and you suspect the launch shell closed
- The operator says "lass laufen" (let it run), "muss weiterlaufen" (must keep running), or any variant indicating the process should be durable
- You need a restart-on-crash guarantee (Restart=on-failure, RestartSec=N)
- You need a process to start automatically on boot

**Do NOT use this skill for:**
- One-shot CLI tasks (use the regular `terminal()` tool)
- Short-lived daemon processes for testing (use `terminal(background=true)` with a session_id)
- Processes that should be killed when the agent session ends
- Container-internal supervision — that's `hermes-s6-container-supervision`

## The Hermes Wrapper Constraint (READ FIRST)

The Hermes `terminal()` tool **detects and blocks shell-level
background wrappers** in the foreground path. The error looks like:

```
Foreground command uses shell-level background wrappers (nohup/disown/setsid/trailing '&').
Use terminal(background=true) so Hermes can track the process…
```

This means you **CANNOT** use `nohup`, `setsid`, `disown`, or
trailing `&` inside a `terminal()` call to daemonize a process
for the long term. `terminal(background=true)` is fine for
short-lived daemon processes (you get a session_id, can poll,
can kill), but the process is still parented to the agent
session — it dies when the session dies (reboot, agent exit,
explicit kill).

**The only durable answer on this operator's machine is a
systemd user service.** `systemctl --user enable --now
<name>.service` detaches the process from any terminal AND
ties it to systemd (which IS the parent). It survives shell
logout, agent exit, and with `Restart=on-failure`, it survives
crashes too. With `[Install] WantedBy=default.target`, it
starts on boot.

If you're tempted to write `nohup python3 foo.py & disown` —
**stop and use a unit file instead**.

## Architecture: Systemd User Services

The operator already has a pattern: `~/.config/systemd/user/`
holds unit files (e.g. `mazemaker-apk-gateway.service`,
`hermes-gateway.service`). New services slot in the same place.

### Anatomy of a good unit file

```ini
[Unit]
Description=Human-readable name
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/absolute/path/to/project
ExecStart=/usr/bin/python3 -m package.module --flags
Restart=on-failure
RestartSec=30
StandardOutput=append:/absolute/path/to/stdout.log
StandardError=append:/absolute/path/to/stderr.log

# Environment variables (secrets via EnvironmentFile= is better,
# but for non-secret config inline works)
Environment=KEY=value

# Hardening — the operator runs everything as `alca` (the user).
# These flags limit the blast radius if the process is compromised.
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
# Whitelist the specific paths the process writes to:
ReadWritePaths=/home/alca/project /home/alca/.config /tmp
MemoryMax=8G

[Install]
WantedBy=default.target
```

### Pitfall: `ProtectSystem=full` breaks logging

`ProtectSystem=full` makes **the entire filesystem read-only**
(only `/dev`, `/proc`, `/sys` are writable). If your process
opens a log file for append on every cycle (which the BTQuant
agency does), it crashes with `OSError: [Errno 30] Read-only
file system` and the service goes into a 13-second crash loop.

**Use `ProtectSystem=strict` + `ReadWritePaths=` whitelist.**
`strict` is the default-deny policy that respects the
whitelist; `full` is "deny everything, no exceptions".

### Pitfall: `Type=simple` requires the process to stay foregrounded

`Type=simple` tells systemd "this process IS the main
service, don't fork". `Type=forking` is for processes that
double-fork into the background. For long-running agent
processes, `simple` is correct — the process runs in the
foreground of its own service slot, and systemd's supervisor
is the parent.

If your process accidentally daemonizes itself (via
`os.fork()` or `subprocess.Popen(detach=True)`), systemd will
think it exited successfully and not restart it. The unit
file's `ExecStart=` line should reference the actual
long-running entry point, not a wrapper that forks.

### Pitfall: `WorkingDirectory=` is mandatory for relative imports

If your module is launched as `python3 -m package.module` and
the package has relative imports, systemd starts the process
in `$HOME` by default. The module's `import` will fail with
`ModuleNotFoundError: No module named 'package'`. Always set
`WorkingDirectory=/absolute/path/to/project` in the unit.

## Quick recipes

### Start a new long-running process durably

1. Write the unit file to `~/.config/systemd/user/<name>.service`
2. `systemctl --user daemon-reload`
3. `systemctl --user enable --now <name>.service`
4. `systemctl --user status <name>.service` — verify
   `Active: active (running)`, parent PID is systemd (943)
5. `journalctl --user -u <name>.service -f` for live logs
6. **Critical:** `ps -o pid,ppid,sid,pgid,cmd -p <PID>` —
   PPid MUST be systemd (943), SID MUST be different from
   your login session. If PPid is your terminal's PID, the
   process is still session-bound and will die at logout.

### Diagnose a dead daemon

```bash
# Did the process die with SIGTERM? Look at the last log lines.
journalctl --user -u <name>.service --since "1 hour ago"

# Is it in a restart loop?
systemctl --user status <name>.service
# Look for: "Main process exited, code=exited, status=1/FAILURE"
# followed by "Scheduled restart job, restart counter is at N"

# Did systemd even start it?
systemctl --user list-units --type=service | grep <name>
```

### Stop a durable process

```bash
systemctl --user stop <name>.service
# Or hard kill if it's ignoring SIGTERM:
systemctl --user kill -s SIGKILL <name>.service

# Disable autostart on boot (without stopping right now):
systemctl --user disable <name>.service
```

### Stop a quadlet/podman stack PERMANENTLY (mask pattern)

`systemctl stop` is NOT enough for services with `Restart=on-failure`.
When a container exits with code 137 (SIGKILL from timeout), systemd sees a
"failure" and the Restart policy queues a START job that CANCELS the running
STOP job — the service comes back up while you're trying to stop it.

**The reliable sequence:**

1. **Stop watchers/timers first** — path-units (`.path`) and timers (`.timer`)
   trigger restarts independently of the service's own Restart policy.
2. **Gracefully stop services** — `systemctl stop` sends SIGTERM, systemd waits
   `TimeoutStopSec` before escalating to SIGKILL. Let current workloads finish.
3. **reset-failed** — clean up 137 residuals so they don't linger.
4. **MASK** — symlink unit to `/dev/null`. A masked unit cannot be started by
   anything: not by dependency, not by trigger, not by timer, not manually.

```bash
# 1. Stop triggers
for unit in myapp-compute-watch.path myapp-db-watch.path myapp-update.timer; do
  systemctl --user stop "$unit" 2>/dev/null || true
done

# 2. Graceful service stop (SIGTERM, waits for workload)
systemctl --user stop myapp-pod.service myapp-worker.service myapp-db.service 2>/dev/null || true

# 3. Clean up SIGKILL residuals
systemctl --user reset-failed myapp-pod.service myapp-worker.service 2>/dev/null || true

# 4. MASK — filesystem-level, faster than `systemctl mask` per unit
for unit in myapp.target myapp-pod.service myapp-worker.service myapp-db.service \
            myapp-compute-watch.path myapp-db-watch.path myapp-update.timer; do
  rm -f ~/.config/systemd/user/"$unit"
  ln -sf /dev/null ~/.config/systemd/user/"$unit"
done
systemctl --user daemon-reload
```

**To bring everything back:**
```bash
for unit in <same list>; do
  systemctl --user unmask "$unit" 2>/dev/null || true
done
systemctl --user daemon-reload
systemctl --user start myapp.target
```

**Why filesystem masking (`ln -sf /dev/null`) instead of `systemctl mask`:**
`systemctl mask` calls the daemon per unit — slow with 20+ units. Direct
symlink + single `daemon-reload` is instant and equally effective.

**Shutdown order matters:**
1. Watchers/timers (`.path`, `.timer`) — stop triggers first
2. Services — graceful stop (SIGTERM, wait for workload to finish)
3. reset-failed — clean up SIGKILL residuals
4. Mask — prevent any restart policy from firing

**Podman quadlet pitfall: Pod stop ≠ member stop.**
`systemctl stop myapp-pod.service` does NOT stop member containers if they
were started independently or have their own `WantedBy=default.target`.
Stop all members explicitly.

### Shutting down a supervised stack: controller FIRST, then containers

When the target stack is a supervisor/controller plus its managed workers
(a systemd user service polling an API, podman containers it manages, llama-server
backends it spawns), the shutdown order matters: **stop the controller FIRST**.
A controller that keeps running will re-poke, respawn, or hold open the very
things you are trying to stop.

Procedure (canonical: turbohaul/turbofit stack, 2026-08-01 — full procedure in
mazemaker id 1075665):

1. **Inventory the stack, don't assume it's all containers.** `podman ps -a`,
   `systemctl --user list-units --type=service | grep -iE 'turbo|...'`,
   `ss -tlnp` for the known ports. The turbofit stack had TWO containers
   (turbohaul-manager :11401 containing the llama-server backend on :11500,
   turbofit-control-plane :8091) PLUS a native systemd user service
   (turbofit-controller.service) polling the manager every ~2s.
2. **Stop the controller first:** `systemctl --user stop turbofit-controller.service`.
3. **Then the containers:** `podman stop -t 20 turbohaul-manager turbofit-control-plane`.
4. **Expect SIGKILL on inference stacks.** Both containers ignored SIGTERM for the
   full 20s grace and exited with 137 (SIGKILL) — busy llama-server processes don't
   drain cleanly. Don't loop; 20s is enough, podman escalates on its own.
5. **Verify:** `podman ps -a` shows `Exited`, `ss -tlnp` shows no listeners on the
   stack's ports, `systemctl --user is-active <controller>` = inactive, no leftover
   processes (`ps aux | grep -iE 'llama-server|turbohaul|turbofit'`).
6. **Do not touch unrelated lookalikes.** The ollama service runs its own
   llama-server (port 38711) — different ownership, leave it running unless asked.

Also useful: a stale podman pod in `Created` state with 0 containers next to a
standalone container of the same name is harmless leftover — don't let it confuse
the inventory.

### Diagnose "silent CPU degradation" in a supervised worker (OOM-thrash loop)

When the operator reports the box is silently CPU-pegged again (mazemaker dream-worker
was the recurring case, 2026-08-01), the first check is: **is the pod actually
degraded, or is a supervised worker thrashing?** The MCP/pod answering in single-digit
ms (e.g. an `initialize` call returns HTTP 200 in 0.011s) while `top` shows a python
process at ~70-100% CPU proves the pod is FINE and the burn is a worker.

Root cause pattern (dream-worker): the worker's consolidation cycle grew past its
memory cap as the corpus grew (213k memories now, cycle peak 12.2G → 14G), so it
crossed `MemoryMax`, the kernel OOM-killed it (status=137), systemd auto-restarted it,
and it re-ran the whole heavy NREM/REM/Insight+louvain cycle — pegging CPU in a loop.
Journal signature:
```
The kernel OOM killer killed some processes in this unit.
Main process exited, status=137
Scheduled restart job, restart counter is at 1
Consumed 4min 49s CPU · 14G memory peak
```

**Diagnosis order:** (1) real MCP call round-trip time (fast = pod healthy); (2) `top`
/ `ps -eo pid,pcpu,comm --sort=-pcpu` for the burner; (3) `journalctl --user -u
<worker>.service --since "20 min ago"` for OOM-kill + restart lines; (4)
`systemctl --user show <worker>.service -p MemoryCurrent` to see it near the cap.

**The fix — raise the cap at the authoritative Quadlet source, not the generated
unit.** The unit `/run/user/1000/systemd/generator/<name>.service` is auto-generated
from the Quadlet `.container` file (`~/.config/containers/systemd/<name>.container`).
Editing the generated unit gets clobbered on `daemon-reload`. Edit BOTH in the
`.container`:
- `PodmanArgs=--memory=<new>g --memory-swap=<new+swap>g` (the container limit; make
  `--memory-swap` strictly greater than `--memory` to allow a bounded swap allowance)
- `[Service] MemoryMax=<new>G` (must match the podman `--memory`)
Then `systemctl --user daemon-reload` (regenerates the unit), and restart via the
worker's owning **target**, not the service directly — if the unit is
`BindsTo=<name>.target`, a bare `systemctl --user restart <name>.service` gets
"Cancelled" and does nothing while the target is inactive.

Design tension to respect: the operator's past notes deliberately set `--memory-swap
== --memory` (zero swap) to force a clean OOM-kill instead of hours of unbounded
swap-thrash (the 2026-06-09 8G RAM + 8G swap disaster). When raising the cap, keep the
swap allowance **bounded** (e.g. 18G RAM + 4G swap) — give the cycle room to finish
without reintroducing unbounded thrash. Annotate the change in the `.container` with a
dated comment (operator values the "why" next to the value).

### Migrate an existing foreground process to durable

1. Find the launch command (`ps -ef | grep <pattern>`)
2. Create the unit file
3. Kill the old process (it'll have PPid=your-terminal-PID)
4. `systemctl --user enable --now <name>.service`
5. Verify with `ps -o pid,ppid,cmd -p <new-PID>` — PPid must be systemd

## Multi-Provider Model Pools for Crew Loops

When running a perpetual crew loop with free model pools across multiple providers
(Nous Portal + OpenRouter), the `--provider` flag is REQUIRED on every `hermes -z`
call. `hermes -m "provider/model"` does NOT reliably route — it uses the default
provider from config.yaml.

Full reference: `references/perpetual-crew-loop-model-pools.md`

Key pattern:
```bash
# Format: "provider:model" — split on first colon
split_model() {
  WM_PROVIDER="${1%%:*}"
  WM_MODEL="${1#*:}"
}
WORKER_MODEL="nous:tencent/hy3:free"
split_model "$WORKER_MODEL"
hermes -z "$prompt" -m "$WM_MODEL" --provider "$WM_PROVIDER" --cli
```

## Worked example: BTQuant agency

The 2026-06-18 daemon (PID 3192582) was launched from a terminal
with no daemonization. When that terminal closed at 23:23:01,
the process died with SIGTERM. Migrating to a systemd user
service is in `btquant-autonomous-agency/references/agency-loop-restart-2026-06-19.md`.

## Worked example: perpetual rework crew loop (2026-08-03)

Second production instance of the same unit-file shape: `mazemaker-rework-loop.service`
supervises an infinite bash loop (`loop-supervisor.sh`) that runs headless agent ticks via
`hermes -z "$(cat prompt)" --cli` — one full agent session per loop iteration, no TTY needed,
exit code returned. This is the canonical way to make an autonomous agent LOOP durable:
the supervisor script is the service, and each tick is a fresh `hermes -z` process.
Key unit details that mattered: `ExecStart=/bin/bash <proj>/loop-supervisor.sh` (not the agent
directly — the script owns the loop), `Environment=HOME=/home/alca` + `PATH` with
`/home/alca/.local/bin` (hermes lives there, not in /usr/bin), `ReadWritePaths` must include
BOTH the project dir AND `/home/alca/.hermes` (the agent writes sessions/memories) AND the
worktree dir. Without HOME/PATH set, the headless hermes tick fails to find its config.
Full architecture + pitfalls: `loop-engineering` skill, Loop Type 8 and
`references/perpetual-worktree-crew-loop.md`.

The key insight: this is the same pattern that will apply to
ANY agent process the operator wants to keep running. ComfyUI
sessions, the dream-worker (already on the watchlist for the
`vram-clean` noop bug — see `hermes-mcp-security-audit`), MCP
servers, custom daemons. If a process needs to outlive the
agent session, systemd user service is the only durable path.

## Related skills

- `hermes-s6-container-supervision`: Inside-Docker supervision
  via s6-overlay. Different domain (containers vs. host) — but
  the same principle: don't trust the launch shell, always
  supervise under a real init.
- `btquant-autonomous-agency`: The longest-running example of
  this pattern in production. See
  `references/agency-loop-restart-2026-06-19.md` for the
  specific unit file and the 9-file patch-up that went with
  it.
- `cron-job-discord-delivery`: Cron jobs are supervised by the
  Hermes scheduler; they don't need their own systemd unit.
  But the principle (don't trust the launch context, supervise
  under a real init) is the same.
- `hermes-mcp-security-audit`: The `vram-clean` noop bug
  documented there is a process-supervision-adjacent failure —
  the cron job runs but does nothing because the script's
  model of how VRAM cleanup works is wrong. Worth pairing with
  this skill when auditing the dream-worker.

## References

- `references/perpetual-crew-loop-model-pools.md` — multi-provider model pool
  patterns for crew loops.
- `references/quadlet-mask-unmask-mazemaker.md` — full worked example of the
  mask/unmask pattern applied to a 30-unit podman quadlet stack (mazemaker).
