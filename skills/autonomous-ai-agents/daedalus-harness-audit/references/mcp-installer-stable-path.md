# MCP Installer Path Stability — the /tmp bootstrap trap

**Symptom class** (hit 2026-08-07 with PULSE v4): an MCP server installed via
`curl -fsSL https://.../install.sh | bash` works at install time, then after
the next reboot the server crash-loops and the log grows unbounded:
```
===== [ts] starting MCP server 'pulse' =====
/usr/bin/python3: can't open file '/tmp/pulse-install-XXXXXX/pulse-daedalus/mcp_local.py': [Errno 2] No such file or directory
```
(repeated every ~5s, appended to `~/.daedalus/logs/mcp-stderr.log` — 11.8MB in
one observed case, no rotation, no spawn backoff).

## Root cause

1. The installer bootstraps: `BOOT_TMP="$(mktemp -d -t <name>-install-XXXXXX)"`
   (i.e. under `/tmp`), downloads `source.tar.gz`, extracts, then
   `INSTALL_NO_BOOTSTRAP=1 exec bash "$EXTRACTED/install.sh" "$@"`.
2. The cleanup trap (`trap 'rm -rf "$BOOT_TMP"' EXIT`) is installed in the
   FIRST shell — `exec` replaces that shell, so the trap NEVER runs. The
   /tmp dir survives… until the next reboot / tmp-cleaner run.
3. The wire/registration step (e.g. `wire.sh --all`) writes the MCP command
   path INTO `~/.daedalus/config.yaml` under `mcp_servers.<name>.args` — pointing
   at the ephemeral /tmp path. The Daedalus MCP client then retries the dead
   path forever with no backoff.

## The fix pattern (always do this instead of raw curl|bash)

1. Download the installer script FIRST and read it
   (`curl -fsSL <url>/install.sh -o /tmp/x.sh`) — look for `mktemp -d -t`,
   `exec`, and where it writes paths into configs.
2. Download `source.tar.gz`, extract to a STABLE location:
   `mkdir -p ~/.local/share/<name> && tar -xzf source.tar.gz -C ~/.local/share/<name> --strip-components=1`
3. Run the installer from there with the bootstrap disabled:
   `cd ~/.local/share/<name> && INSTALL_NO_BOOTSTRAP=1 bash install.sh`
   → wire scripts now register the stable path.
4. Verify the registered path in config.yaml:
   `grep -n '<name>-daedalus\|<name>' ~/.daedalus/config.yaml` — args must point
   to `~/.local/share/<name>/mcp_local.py` (or equivalent), never `/tmp`.
5. Live-test through the MCP channel (`mcp__<name>__<tool>_diagnose`) before
   deleting the old /tmp dir (the running `daedalus mcp serve` may still hold
   the old instance in memory; it picks up the new config on its next natural
   restart — do NOT kill `daedalus mcp serve` blindly; on this host it was a
   child of a `claude bg-spare` process).
6. Move old `/tmp/<name>-install-*` dirs to `~/.local/share/Trash/files/`
   (never rm) AFTER the live test.

## License/tier notes (Pro products)

- Cached license often lives at `~/.<name>/license.json` (e.g. `~/.pulse/`).
  Inspect structure-only, never print secrets:
  `python3 -c "import json;d=json.load(open('...'));print(d.get('tier'),d.get('pro_active'))`
- Installers often only install the extra Pro runtime (pod, worker) when a
  license KEY env var is set (e.g. `PULSE_KEY=mzm-...`) — the cached
  license.json alone does NOT trigger it. The key is usually NOT on disk
  (checked .env, configs, shell history) — ask the operator or point at the
  vendor onboard URL. `podman` presence check: `command -v podman`.
- Operator preference (learned): never settle for the community/free tier of
  a licensed product — locate the key / finish the Pro setup.
