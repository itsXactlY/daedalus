---
name: alice-routing-debugging
description: "Debug why Alice-Router (:8801) delegation is bypassed — tool-name double registration (provider unprefixed vs MCP-client mcp__ prefixed), guard fail-open, system prompt forcing the wrong name, bootstrap compact stripping the router field."
category: devops
version: 1.2
tags: [alice, router, mcp, delegation, mazemaker, debugging, hermes]
priority: high
---

# Alice-Routing Debugging — why the bridge doesn't fire

## Trigger
- User says "Routing wird ignoriert" / "Alice routing is ignored" / "route_mcp_through_router: true but no router field in results"
- Alice (:8801) shows no traffic while the session makes mazemaker_recall calls
- Need to prove whether the ALICE bridge actually fired for a given tool call

## Architecture — two parallel tool paths (THE root cause class)
The SAME mazemaker tools are registered TWICE in one process:
1. **Memory provider** (`memory.provider: mazemaker`) → registers UNPREFIXED names (`mazemaker_recall`, ... 12 tools). The ALICE bridge hangs HERE only:
   - `agent/run_agent.py` `_invoke_tool` → `elif self._memory_manager and has_tool(name)` → `_route_mcp_through_alice(name, args)`
   - Bootstrap path also calls the bridge with the unprefixed name.
2. **MCP client** (`mcp_servers.mazemaker.enabled: true`, `tools/mcp_tool.py`) → registers PREFIXED names (`mcp__mazemaker__mazemaker_recall`, ... 34 tools). These go through `handle_function_call` → Registry → MCP-Client → pod DIRECTLY — NO Alice.

ALICE_ROUTE_TOOLS (`agent/alice_router.py`) contains only unprefixed names (`mazemaker_recall`, `mazemaker_recall_multi`), and the guard `if function_name not in ALICE_ROUTE_TOOLS: return None` FAILS OPEN for `mcp__...` names.

## Diagnostic sequence (proven 2026-08-11)
1. **Check both registrations in startup log** (`~/.hermes/logs/agent.log`):
   ```
   Memory provider 'mazemaker' registered (12 tools)   ← unprefixed, bridge attached
   MCP server 'mazemaker' registered 34 tool(s)        ← mcp__ prefixed, NO bridge
   ```
2. **Check what the system prompt forces**: `config.yaml` MAZEMAKER MEMORY PROTOCOL block often says `call mcp_mazemaker_mazemaker_recall ...` — this makes the LLM pick the MCP-prefixed name → guard fails open → direct pod call, 0% Alice.
3. **Prove with journald, not guesses**: Alice runs as systemd user service:
   ```bash
   systemctl --user list-units | grep alice          # alice-router.service
   journalctl --user -u alice-router --since "HH:MM" --no-pager | grep launch_slot
   ```
   - Small `prompt eval ... / N tokens` values are NORMAL (llama-server cache: only NEW query tokens evaluated; route prompt is cached). Don't conclude "not a route call" from tiny N.
   - Correlate timestamps with your tool calls. Bridge calls from bootstrap appear ~1 per turn; real tool calls appear when the LLM uses the UNPREFIXED name.
4. **Read the actual guard** to confirm fail-open:
   ```bash
   grep -n "ALICE_ROUTE_TOOLS\|not in ALICE_ROUTE_TOOLS\|normalise_route_name" ~/.hermes/agent/alice_router.py
   ```
   Note: `normalise_route_name` strips `mcp__server__` but is only used on Alice's ANSWER, not on the incoming function_name guard.
5. **Even when the bridge fires (bootstrap path), the router field is invisible**: `_compact_neural_recall_result` (run_agent.py ~line 2790) rebuilds the payload as `{"auto_bootstrap": true, ...}` WITHOUT the `router`/`router_tool` keys → the LLM never sees Alice routed. Check journal counts to prove the bridge DID fire even though results show no router field.

## Fix options (pick with operator)
- **A (cleanest):** `mcp_servers.mazemaker.enabled: false` — provider path already has bridge + bootstrap + prefetch. Only if nothing else needs the MCP server (dashboard/gateway consumers may).
- **B:** Add bridge into the MCP dispatch (`handle_function_call`/registry path) for mcp__ names.
- **C:** Apply `normalise_route_name` to the incoming function_name in the guard, so `mcp__mazemaker__mazemaker_recall` maps to `mazemaker_recall` before the `not in ALICE_ROUTE_TOOLS` check.

## Fix A — executed & verified 2026-08-11 (commit 574c08f33)
1. `config.yaml`: `mcp_servers.mazemaker.enabled: true → false`
2. System prompt: change ALL references `mcp_mazemaker_mazemaker_recall` → `mazemaker_recall` and `mcp_mazemaker_mazemaker_remember` → `mazemaker_remember` (both in `personalities.architect` and `agent.system_prompt` blocks, plus the trailing `at mcp_mazemaker_*.` → `at mazemaker_*.` line). Grep for any remaining `mcp_mazemaker_` after editing.
3. Memory provider (`plugins/memory/mazemaker/__init__.py` AGENT_TOOL_ALLOWLIST, 12 unprefixed tools) becomes the ONLY mazemaker access — bridge attached in all three paths (in-loop, bootstrap, prefetch).

## Verification — direct live-bridge test (faster than journald)
Instead of correlating journald timestamps, call the bridge function directly with an execute stub:
```python
from agent.alice_router import route_mcp_through_alice
def execute(name, args):  # pod JSON-RPC call, returns raw string
    ...
result = route_mcp_through_alice('mazemaker_recall', {'query': '...', 'limit': 2}, execute=execute)
# result starts with {"result": {"jsonrpc": ...}} → bridge FIRED (Alice routed the tool)
# result is None → fail open (guard returned None)
```
Signature: `route_mcp_through_alice(function_name, function_args, *, execute=Callable, is_router=False, delegate_depth=0, alice_timeout=None)` — **execute is KEYWORD-ONLY**. Passing it positionally raises `TypeError: takes 2 positional arguments but 3 were given`.
Also verify config-side skips: `tools/mcp_tool.py` `_parse_boolish(v.get("enabled", True))` skips the server at ~lines 6256/6488; `scripts/mcp-route-monitor.py` line ~157 `if not cfg.get("enabled"): continue`.

## Pitfalls
- **Restart required**: the running TUI session (`hermes --yolo`) keeps the MCP client in memory — config change only takes effect after a session restart. Don't claim live effect in the current session.
- **Service file goes stale after model rollback** (bug:alice-service-v43-stale-config-2026-08-11): after v4.3→v4.2 rollback the systemd unit still pointed at the overfitted .gguf and crash-looped ("couldn't bind HTTP server socket, port 8801", 467 restarts) while a manual nohup llama-server held the port — health check OK (manual proc) masked a dead service. ALWAYS grep the .gguf path in `~/.config/systemd/user/alice-router.service` after a model swap; patch + daemon-reload in the same step. For cost measurement see skill `alice-ab-token-measurement`.
- Don't trust "route_mcp_through_router: true" alone — verify the actual tool NAME the LLM calls in the session (system prompt injection wins over config).
- Don't claim PASS from config reading; the direct bridge test above is the evidence (or journald timestamps + tool-call correlation).
- `mcp-route-monitoring` skill covers the monitor script (endpoint health), NOT the Alice bridge path — different problem.
- After fixing, verify: journald `launch_slot` shows a call per real tool call, and results carry `router: alice`.

## Coalescing — NOT one Alice call per tool call (operator 2026-08-11, commit e4d81a117)
Operator: **"not ONE single call per alice!"** — a burst of mazemaker calls (e.g. 15 × `mazemaker_get` in one turn) must not fire one Alice round-trip per call.

Two-layer fix:
1. **Dispatch pre-filter** (`run_agent.py` sequential `_invoke_tool` + concurrent path): bridge is only entered when `function_name in self._MCP_ROUTE_TOOLS` (i.e. `mazemaker_recall` / `mazemaker_recall_multi`). Deterministic get/browse/think/stats and writes remember go straight to the pod — zero Alice overhead.
2. **Router coalescing** (`agent/alice_router.py`): `ALICE_COALESCE_WINDOW = 2.0` s + thread-safe `_alice_coalesce_allowed()` (lock-guarded monotonic timestamp). Only the FIRST routable call in the window consults Alice; later ones fail open to the direct pod call. After the window expires, the next burst consults Alice again.

Verify like this (proven test):
- 15 × `mazemaker_get` → **0 Alice calls** (never routed, cheap guard)
- 5 × `mazemaker_recall` burst → **1 Alice call**
- after 2.2 s pause + 1 recall → Alice fires again (window expired)

Test isolation pitfall: `_alice_last_route_ts` is module-global — a test that fires Alice (chained/bootstrap) leaves the window fresh and blocks a later test's route within 2 s. Reset `_ar._alice_last_route_ts = 0.0` in `finally` of every test that exercises the bridge (see `test_coalesce_one_alice_call_per_burst`, and the resets added to `test_chained_alice_calls_still_use_parent_query` + `test_bootstrap_routes_through_alice`).

