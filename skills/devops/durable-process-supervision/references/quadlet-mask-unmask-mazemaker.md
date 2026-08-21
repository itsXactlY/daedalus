# Worked Example: Mazemaker mask/unmask script (2026-08-06)

The `mazemaker` CLI (`~/.local/bin/mazemaker`) is a production implementation of the
mask/unmask pattern for a podman quadlet stack with 6 containers, 9 path-watchers,
2 timers, and 2 targets.

## Problem it solves

Mazemaker's quadlet-generated services have `Restart=on-failure`. When the operator
said `mazemaker off`, services kept restarting because:
- `systemctl stop` + `Restart=on-failure` → systemd re-queued START after SIGKILL(137)
- Path-watchers (`.path` units) triggered restarts on file changes
- `--job-mode=replace-irreversibly` prevented the race but caused hangs with many units

## Architecture

```
mazemaker.target
├── mazemaker-pod.service (infra container)
├── pulse-pod.service (sponge ingest)
├── mazemaker-hermes-bridge.service
├── Pod members:
│   ├── mazemaker-mcp.service
│   ├── mazemaker-wonderland.service
│   ├── mazemaker-embedding-worker.service
│   ├── mazemaker-license-client.service
│   ├── mazemaker-pgvector.service
│   └── mazemaker-mcp-socket-bridge.service
├── Watchers (.path):
│   ├── compute-watch, db-watch, embed-watch
│   ├── hermes-compress-guard, image-refresh-watch
│   ├── update-watch, upgrade-watch, downgrade-watch, runtime-watch
├── Timers:
│   ├── peer-sync.timer, update.timer
└── Extras:
    ├── dream-worker, mcp-warmup, rework-loop, peer-sync
    └── compute-watch.service, db-watch.service, etc.
```

## Key design decisions

1. **Graceful first, mask after.** The `off` command stops watchers/timers first
   (no new triggers), then gracefully stops services (SIGTERM, wait for workload),
   then masks. No `podman kill --all` — the operator explicitly corrected this:
   "es stopt DANN wenn aktuelle workload fertig ist" (it stops WHEN the current
   workload finishes).

2. **Filesystem masking over `systemctl mask`.** With 30+ units, `systemctl mask`
   calls the daemon 30 times. `ln -sf /dev/null` + single `daemon-reload` is instant.

3. **Dream mode is orthogonal.** The `dream` subcommand (internal/external/none)
   controls MCP engine consolidation and is independent of the on/off state.
   It's persisted in `~/.mazemaker/dream.mode` and re-applied on every `on`.

## Unit lists (hardcoded in script)

```bash
MASTER_UNITS=(mazemaker-pod.service pulse-pod.service mazemaker-hermes-bridge.service)
POD_MEMBERS=(mazemaker-mcp.service mazemaker-wonderland.service
             mazemaker-embedding-worker.service mazemaker-license-client.service
             mazemaker-pgvector.service mazemaker-mcp-socket-bridge.service)
WATCHERS=(mazemaker-compute-watch.path mazemaker-db-watch.path
          mazemaker-embed-watch.path mazemaker-hermes-compress-guard.path
          mazemaker-image-refresh-watch.path mazemaker-update-watch.path
          mazemaker-upgrade-watch.path mazemaker-downgrade-watch.path
          mazemaker-runtime-watch.path)
TIMERS=(mazemaker-peer-sync.timer mazemaker-update.timer)
TARGETS=(mazemaker.target mazemaker-dream.target)
EXTRAS=(mazemaker-dream-worker.service mazemaker-mcp-warmup.service
        mazemaker-rework-loop.service mazemaker-peer-sync.service ...)
```

## Lessons learned

- `pulse-api.service` and `pulse-pod.service` are separate — don't assume naming consistency
- `mazemaker.target` might not exist as a standalone file if it's only in quadlet `.pod`
- Always `reset-failed` after stopping — 137 residuals confuse status output
- The `on` command must unmask before starting, and `daemon-reload` after unmasking
