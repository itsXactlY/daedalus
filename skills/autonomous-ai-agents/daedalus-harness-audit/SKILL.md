---
name: daedalus-harness-audit
description: Use when auditing the Daedalus harness for flaws (network exposure, update behavior, cron/gateway liveness, MCP health, disk hygiene of ~/.daedalus).
version: 1.0.0
category: autonomous-ai-agents
tags: [daedalus, audit, security, mcp, cron, firewall, cleanup]
---


> Ported from `hermes-harness-audit` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Harness Audit + Safe Fixes

Proven procedure from the 2026-08-07 full audit (findings + applied fixes live in
mazemaker: `fact:daedalus-harness-audit-2026-08-07` #1153570, `ops:daedalus-harness-audit-fixes-2026-08-07`
#1153572, `ops:pulse-v4-pro-install-2026-08-07` #1153574). Use the memory IDs for
current host state; this skill carries the HOW.

## When to use

- User asks to audit the daedalus harness / agent install / "find every flaw"
- Anything touching: network exposure of the host, `daedalus update` behavior,
  cron/gateway liveness, MCP server health, disk hygiene of ~/.daedalus
- Cautious cleanup ("vorsichtig!" = move to Trash/archive, never delete)

## Full procedure: references/harness-audit-checklist.md

The checklist has exact commands for: install location, git divergence (update
black hole), port/NFS/firewall exposure, /proc listener identification,
secret-safe inspection, systemd user units, log triage, stale-artifact checks
(venv.stale vs .daedalus-runtime — CHECK pyvenv.cfg first), cron jobs.json parse.

## Key fix patterns (all verified working)

1. **MCP /tmp bootstrap trap**: `curl | bash` installers extract to
   `mktemp -d -t <name>-install-*` and register THAT path in
   `config.yaml mcp_servers.<name>` — trap dies on exec, dir survives to
   reboot, then crash-loop + unbounded `logs/mcp-stderr.log`. Fix: extract
   tarball to `~/.local/share/<name>`, run `INSTALL_NO_BOOTSTRAP=1 bash install.sh`
   from there, verify the registered path, live-test via `mcp__<name>__*_diagnose`.
   Full recipe: references/mcp-installer-stable-path.md
2. **Log rotation without root**: process holds the fd open → copytruncate-style
   user script (`cp` + `: >` truncate, keep N gz) + `systemd --user` timer
   (OnUnitActiveSec=1h). Template: references/logrotate-user-timer.md
3. **Firewall needs sudo — two clean paths**: (a) prepare the full script and
   have the OPERATOR run it once: `sudo ~/.local/bin/<name>-firewall-setup.sh`;
   (b) better for repeat runs: operator adds ONE sudoers entry
   `echo 'alca ALL=(root) NOPASSWD: /home/alca/.local/bin/<name>-firewall-setup.sh' | sudo tee /etc/sudoers.d/<name>`
   then the agent runs `sudo -n` itself. NOTE: a sudo timestamp from the
   operator's terminal is TTY-bound — `sudo -n` will still fail for the agent;
   a password typed into the CLI is masked and never reaches the agent.
   Verification WITHOUT root: `/etc/ufw/ufw.conf` `ENABLED=yes` (readable,
   survives reboot) + `systemctl is-active ufw`. On Arch, `ufw status` /
   `nft list ruleset` are root-only; `journalctl -u ufw` showing
   "Skip starting firewall: ufw (not enabled)" at service start is EXPECTED
   ordering (systemd start runs before `ufw --force enable`), not a failure.
   Baseline: default deny incoming, allow ssh 22, libvirt virbr0, NFS ports
   from LAN only; keep ollama/http.server/passt ports loopback-only.
   Exposure matrix (verified 2026-08-07): iris messenger = ONLY 80/443 (Caddy,
   pod-internal gateway; see jrwl-messenger-maintenance), apk-gateway
   8443/38374 KEPT OPEN (operator decision), ollama 11434 used only at
   localhost (mazemaker recall), 8765/8788 have no external consumers.
   FW-test gotcha: `curl http://<own-LAN-IP>:port` routes via `lo`
   (`ip route get <own-ip>` → `local dev lo`) — loopback is always allowed,
   so local tests prove NOTHING. Real test from another device (phone):
   blocked port must hang (DROP), allowed port must answer.
4. **Rebase of the runtime branch — safe mid-session variant**: NEVER rebase
   blind while a session runs (live interpreter lazily imports from the
   working tree). If a dry-run in a separate worktree is CONFLICT-FREE
   (`git worktree add /tmp/rebase-dry HEAD && git -C /tmp/rebase-dry rebase --onto origin/main <merge-base>`),
   a real rebase with `git branch backup/<branch>-pre-rebase-<date>` first is
   acceptable — then verify `py_compile` on changed files + `daedalus --version`
   smoke test + confirm compress-fix still present, remove worktree, and tell
   the user to restart daedalus afterwards (old code stays in memory until then).
   On conflict: `git rebase --abort`, offer as post-session step.
5. **Secret-safe inspection**: never dump auth.json/.env values. Walk JSON
   printing key paths + length + `plaintext_like` flag; grep with
   `sed -E 's/(KEY=).{0,4}.*/\1***/'`.
6. **Trash/archive instead of delete** (operator preference, "vorsichtig"):
   `mv` to `~/.local/share/Trash/files/<name>-<date>/` or
   `~/.daedalus/.archive-<date>/`; curator runs are prune-only (mark stale, don't
   archive) unless explicitly told otherwise.
7. **Fork installs** (verified 2026-08-07): remote layout on this host —
   `origin` → NousResearch (official), `fork` → itsXactlY (operator, ssh),
   `upstream` → NousResearch (alias for update_cmd's sync path). Sync fork
   main: `git fetch upstream main`, compare
   `git rev-list --count origin/main..upstream/main`, push only if 0 ahead:
   `git push fork upstream/main:main --force-with-lease` — target the
   OPERATOR fork remote (named `fork` here), NOT `origin`. **`daedalus update`
   DOES touch the checkout**: it switches to main for the update; before fix
   a3cd13bbb the switch-back only existed in the no-commits path, so a
   feature-branch runtime silently stayed on upstream main after real
   updates (reflog: 'checkout: moving from context-budget-manager to main').
   Fix commit adds `_restore_original_branch()` in all four paths
   (no-commits, update-complete, reset-failure, rollback) — verified by
   scripts/run_tests.sh (23 update test files, 175 passed). Branch-safe sync
   tool: `~/.local/bin/daedalus-upstream-sync.sh` (fetch, fork-main ff+push,
   branch rebase with backup ref + abort-on-conflict). NOTE: its push target
   is `origin` — on this host it must be `fork`; only the --check path was
   verified, the push path is NOT yet exercised.
8. **Verify native upstream fix before cherry-picking a fork monkeypatch**:
   read the guard/patch script first — it may self-report "UPSTREAM" (fix
   absorbed upstream, patching = regression). Check code:
   `grep -n "sanitize_memory_context" agent/conversation_compression.py`.
9. **npm audit with unreleased fix**: before forcing anything, prove the fix
   version exists (`npm view undici versions` / ETARGET error = not released
   yet; 2026-08-07: undici 6.28.0 AND 7.29.0 did NOT exist). Check who really
   depends on the package (`npm ls undici` — the root copy may be extraneous
   test-tree only, e.g. jsdom). Transitive-vuln fix = root package.json
   `overrides` (pattern already used: lodash, yauzl, protobufjs) — but only
   when the override version exists. NEVER `npm audit fix --force` on a
   production install (major bumps: electron/mermaid). Re-audit later; git
   tree must stay clean if you reverted.
10. **Config hardening knobs** (`daedalus config set <dot.path> <value>`,
    backup config.yaml first): `security.tirith_fail_open false` (scanner
    fails CLOSED; verify normal tool calls still pass) and
    `agent.verify_on_stop true` (matches operator ALLES=COMPLETE).
11. **node_modules strip, workspaces stay** (2026-08-07): removing ALL
    node_modules (~1.4GB → Trash) is safe (nothing runs, gitignored, rebuilt
    on demand; every `daedalus update` rebuilds ~300MB — move to Trash again
    afterwards). Do NOT `git rm` the npm workspaces without an explicit
    operator order — the Python core depends on them: main.py auto-restores
    `ui-tui/dist/entry.js` (TUI), gui.py launches `apps/desktop/release`,
    model_catalog.py reads `website/static/api/model-catalog.json`,
    npm_engine.py reads root package.json engines. Stripping = broken
    features + modify/delete conflicts on every upstream sync.

## Pitfalls

- **Skill-stack autonomy audit (2026-08-12)**: the name-only skills index
  (commit a55e540a2) left skill selection to LLM compliance — signature:
  `daedalus curator status` shows `activity=0 last_activity=never` on every
  skill. The fix is `agent/skill_router.py` (deterministic per-turn router,
  injected at the `_injections` site in run_agent.py, API-call-time only,
  config `skills.auto_route{,_top_n,_min_score}`). Verify with
  `python3 -c "from agent.skill_router import route_skills; print(route_skills('dayz loot economy', top_n=3))"`.
  Also fixed: `bump_view()` was defined in tools/skill_usage.py but NEVER
  called — wire it into `tools/skills_tool.py::skill_view` (single choke
  point, covers the /command path too); verify `view_count` increments in
  `.usage.json`. Test: `pytest tests/agent/test_skill_router.py`.
- **ACP import trap**: `acp_adapter/server.py` imported
  `SetSessionModelResponse`, which does NOT exist in installed
  agent-client-protocol 0.12.0 — the whole ACP server died at import.
  Removed the hallucinated `set_session_model` handler (protocol has no
  `session/set_model` route). Check via
  `python3 -c "import acp_adapter.server"` — must not raise ImportError.
- `daedalus-harness-internals`, `daedalus-provider-model-resolution` and
  `jrwl-messenger-maintenance` were successfully PATCHED during the
  2026-08-07 session (skill_manage returned success) — they ARE writable on
  this host. Only if a patch is refused should you recommend
  `daedalus curator adopt <name>`.
- `.daedalus-runtime/` inside the install is NOT junk — the active venv's
  `pyvenv.cfg` points into it. Only `venv.stale.runtime-*` is removable.
- `daedalus doctor` is the fast health pass; run it before deep-diving.
- Never delete old /tmp MCP installs before the live MCP test passes — the
  running `daedalus mcp serve` may still use them until its next restart
  (don't kill it blindly: on this host it's a child of `claude bg-spare`).
- The hardcoded-model trap (claude-opus-4.6) is FIXED in v0.20.0 code — check
  `auth.json active_provider` vs `config.yaml model.provider` mismatch instead.
