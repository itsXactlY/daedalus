# Full Clean Restart — Mazemaker Podman Stack

Verified 2026-07-20 after the `mazemaker-mcp` preflight gate left the whole stack in a
bad/escalating state and the operator demanded a complete kill + clean restart.

## When to use
- User reports the stack is "not normal" / escalating / "kill it all and clean-restart".
- Prefer this over incremental unit-patching when multiple symptoms coincide or the
  operator explicitly asks for a clean slate.

## 0. Recon (snapshot before touching anything)
```bash
systemctl --user list-units --type=service --state=running | grep -i mazemaker
podman pod ps --format '{{.Name}}  {{.Status}}'
podman ps -a --format '{{.Names}}  {{.Status}}' | grep -i mazemaker
podman volume ls | grep -i 'pg\|maze\|postgres'   # confirm pgvector is a bind-mount (empty = bind-mount, safe from pod rm)
```

## 1. STOP (mask → stop → pod rm → unmask → daemon-reload)
A plain `systemctl --user stop <all>` FAILS ("Job ... canceled") because
`mazemaker-mcp.service Requires=mazemaker-pod.service` (Pod=) → transaction conflict.

```bash
UNITS="mazemaker-apk-gateway-mdns.service mazemaker-apk-gateway.service \
mazemaker-hermes-bridge.service mazemaker-dream-worker.service \
mazemaker-embedding-worker.service mazemaker-wonderland.service \
mazemaker-license-client.service mazemaker-mcp.service \
mazemaker-pgvector.service mazemaker-pod.service"

systemctl --user mask   $UNITS     # block Restart=always respawn during kill
systemctl --user stop   $UNITS
podman pod rm -f mazemaker          # SIGKILL all containers; pgvector bind-mount data survives
systemctl --user unmask $UNITS      # restore startability
systemctl --user daemon-reload      # REGENERATES quadlet .service files deleted by mask
```

### PITFALL — mask deletes quadlet .service files
`systemctl mask` writes a `/dev/null` symlink over the unit file (deletes the original).
For quadlet units this is recoverable: `daemon-reload` regenerates them from
`~/.config/containers/systemd/*.container` + `mazemaker.pod`. Drop-ins in
`*.service.d/` survive. For a *hand-written* real `.service` file, mask errors
"already exists" and skips (no loss). Always `daemon-reload` after `unmask`.

## 2. START (ordered — mcp LAST)
```bash
systemctl --user start mazemaker-pod.service mazemaker-pgvector.service \
  mazemaker-license-client.service mazemaker-embedding-worker.service \
  mazemaker-wonderland.service mazemaker-dream-worker.service \
  mazemaker-hermes-bridge.service mazemaker-apk-gateway.service mazemaker-apk-gateway-mdns.service

# pgvector does WAL crash-recovery (~60s) after the SIGKILL — wait for "ready to accept connections"
for i in $(seq 1 12); do
  podman logs systemd-mazemaker-pgvector 2>&1 | tail -5 | grep -q "ready to accept connections" && break
  sleep 5
done

systemctl --user start mazemaker-mcp.service   # LAST: drop-in restarts hermes-gateway (session drop) + warmup
```

## 3. Verify
```bash
curl -fsS http://127.0.0.1:8765/health        # {"status":"ok",...}
systemctl --user show hermes-gateway.service --property=MainPID   # new PID = 31 tools re-registered
systemctl --user is-active mazemaker-mcp-warmup.service           # activating = GpuRecallEngine loading (transient 1-3 min wedge)
```

## Notes
- If mcp was dead due to the preflight engine-staleness gate, rebuild + RETAG first
  (see SKILL.md Class B Fix + TAG-GAP pitfall). The clean restart alone will NOT
  clear a preflight failure — the image's `engine_sha` must match the Pro source.
- pgvector crash recovery is normal and non-destructive; never restore from backup
  just because you see "redo in progress".
- The mcp start intentionally drops the session via the gateway reload. That is the
  proof the 31 tools re-registered — the NEXT session has them.
