# Dream worker Nuitka path — root cause analysis 2026-05-29

## Symptom

Dream worker in crash loop: `systemctl --user status mazemaker-dream-worker.service` shows `activating (auto-restart) (Result: exit-code)`, restart counter in the hundreds.

Journal: `python: can't open file '/app/core/dream_worker.py': [Errno 2] No such file or directory`

Dream stats via MCP show `external_daemon: true` with old/historic session counts.

## Root cause

The Nuitka lockdown compiled all Python files in the `mazemaker-v2-mcp:gpu` image from `.py` → `.so`. The `dream_worker.py` became `dream_worker.cpython-311-x86_64-linux-gnu.so` at the **root of `/app/`**, not at `/app/core/dream_worker.py`.

The Quadlet Exec still referenced the old path:
```
Exec=python -u /app/core/dream_worker.py --max-memories 2000 ...
```

## Finding the fix

1. Check what files exist in the image:
   ```bash
   podman run --rm localhost/mazemaker-v2-mcp:gpu find /app -name "dream*" -type f
   # → /app/dream_worker.cpython-311-x86_64-linux-gnu.so
   ```

2. Check if the compiled `.so` module has the expected entry points:
   ```bash
   podman run --rm localhost/mazemaker-v2-mcp:gpu python3 -c "
   import sys; sys.path.insert(0, '/app'); import dream_worker
   print(dir(dream_worker))  # Should show 'main' + 'argparse'
   "
   ```

3. Verify argument parsing still works:
   ```bash
   podman run --rm localhost/mazemaker-v2-mcp:gpu python3 -c "
   import sys; sys.path.insert(0, '/app')
   sys.argv = ['dream_worker', '--help']
   import dream_worker; dream_worker.main()
   "
   # Should print the usage/help text with all CLI flags
   ```

## Fix

Replace the old Exec line with a Python inline that imports the compiled `.so` module:

```
Exec=python3 -c "import sys; sys.path.insert(0, '/app'); sys.argv = ['dream_worker','--max-memories','2000','--max-isolated','800','--cycle-interval','60','--log-level','INFO','--db','/data/memory.db']; import dream_worker; dream_worker.main()"
```

Key points:
- `sys.path.insert(0, '/app')` — the .so lives at /app/, not /app/core/
- `sys.argv = [...]` — Nuitka preserves the original argparse CLI; set argv before calling main()
- `import dream_worker` — imports the compiled .so module
- `dream_worker.main()` — calls the original entry point

## Secondary issue: GPU device on non-GPU machines

On machines without an NVIDIA GPU (e.g. tpad), the Quadlet's `AddDevice=nvidia.com/gpu=all` causes:
```
Error: setting up CDI devices: unresolvable CDI devices nvidia.com/gpu=all
```

Fix: strip the line from the quadlet:
```bash
sed -i '/AddDevice=nvidia/d' ~/.config/containers/systemd/mazemaker-dream-worker.container
```

The install.sh normally handles this (auto-detects GPU and strips the line), but pre-existing Quadlets installed before the `install.sh` GPU-detect logic was added may still have it.

## Verification

```bash
systemctl --user reset-failed mazemaker-dream-worker.service
systemctl --user daemon-reload
systemctl --user start mazemaker-dream-worker.service
sleep 3
systemctl --user is-active mazemaker-dream-worker.service
# Expected: active

journalctl --user -u mazemaker-dream-worker.service -n 5 --no-pager
# Expected: "License(tier=pro, features=[...,dream_worker,...])"
#           "loading mazemaker.Memory (embedding=auto, ...)"
```

## Multi-machine results

| Machine | Before | After | Restarts | Notes |
|---------|--------|-------|----------|-------|
| desk    | 335 restarts | running | 1  | Has GPU, no CDI issue |
| tpad    | N+1 restarts | running | 1  | Stripped AddDevice=nvidia first |

## Related

- Quadlet source: `~/projects/mazemaker-v2-stack/backend/client/quadlet/mazemaker-dream-worker.container`
- Local quadlet: `~/.config/containers/systemd/mazemaker-dream-worker.container`
- Dream worker source (pre-Nuitka): `~/projects/mazemaker/python/dream_worker.py`
- Image: `localhost/mazemaker-v2-mcp:gpu`
- Commit: `ea91b35`
- See also: `references/bridge-hermes-mcp-500-2026-05-29.md` (same Nuitka pattern for hermes-bridge)
