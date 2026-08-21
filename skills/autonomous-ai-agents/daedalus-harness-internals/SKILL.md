---
name: daedalus-harness-internals
description: How the Daedalus Agent harness works - architecture, tool chain, plugins, gateway
category: autonomous-ai-agents
version: 1.0
tags: [daedalus, harness, architecture, plugins, gateway, tools, agent-loop]
priority: critical
---


> Ported from `hermes-harness-internals` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Harness Internals

**CRITICAL: Work in `~/daedalus-upstream/`, NOT in `~/.daedalus/` (installed runtime).**

How the agent actually works under the hood. Everything connects.

## Critical: Where To Work

**`~/.daedalus/` IS the working repo** (git repo, remote daedalus-backup — `git@github.com:itsXactlY/daedalus-backup.git`, private). There is NO `~/daedalus-upstream` checkout on this machine (operator correction 2026-08-11: "die skills sind uralt. ~/.daedalus/ nix upstream"). Edit `~/.daedalus/` directly; the installed `daedalus` binary is `~/.daedalus/venv/bin/daedalus`. Sync via `~/.daedalus/scripts/daedalus-backup-sync.sh` (hourly cronie cron) — do NOT run `daedalus update` blindly (it checks out main; this repo runs its own branches).

## Core Agent Loop (run_agent.py)

```
AIAgent.run_conversation():
    while api_call_count < max_iterations:
        response = client.chat.completions.create(model, messages, tools)
        if response.tool_calls:
            for call in response.tool_calls:
                result = handle_function_call(call.name, call.args)
                messages.append(tool_result_message(result))
        else:
            return response.content
```

Synchronous loop. OpenAI message format. Reasoning stored in `assistant_msg["reasoning"]`.

## Tool Discovery Chain

```
tools/registry.py          <- Central registry (no deps)
        ↑
tools/*.py                 <- Each calls registry.register() at import
        ↑
model_tools.py             <- _discover_tools() triggers import chain
        ↑
run_agent.py, cli.py       <- Consumer
```

New tool: create `tools/my_tool.py`, call `registry.register()` at module level.
Add to `toolsets.py` `_HERMES_CORE_TOOLS` list or discovery list in `model_tools.py`.

## Memory Plugin System (~/.daedalus/plugins/memory/)

| Plugin | Purpose |
|--------|---------|
| **mazemaker** | Default. MCP-backed semantic graph (recall/remember/think/dream/stats) over `~/.mazemaker/data/memory.db`. The active provider for this user. |
| **mcp** | Generic MCP-server adapter (HTTP or stdio). Wraps any MCP that exposes memory tools. |
| **honcho** | Conversation memory (provider session store). |
| **byterover / hindsight / holographic / mem0 / openviking / retaindb / supermemory** | Alternative providers, not currently configured. |

Mazemaker provider talks to MCP server at `http://127.0.0.1:8765/mcp` (wonderland AES proxy in front of the in-pod `mazemaker-mcp.service`). It does NOT load Python modules from a local plugin directory — the engine lives in containers and on the host as `dream_worker`. If something says "look at `~/.daedalus/plugins/memory/mazemaker/*.py`", that path is from the pre-rename era and the files are gone.

Engine source of truth: `~/projects/mazemaker/python/` (`memory_client.py`, `mazemaker.py`, `dream_engine.py`, `embed_provider.py`, `cpp_bridge.py`). Containers bind-mount this read-only at `/app/core/`.

## ALICE Delegation Bridge (whole harness — 2026-08-11)

**Operator contract: "the whole, complete harness needs delegation. cli, tui, everything."**
Single implementation in `agent/alice_router.py` (`route_mcp_through_alice`). Used by:
1. in-loop tool calls (run_agent `_invoke_tool` concurrent + sequential path)
2. neural bootstrap recall (run_agent `_build_neural_bootstrap_messages`)
3. memory-provider prefetch (`plugins/memory/mazemaker/__init__.py` `_multi_angle_recall` — the `<memory-context>` block)

Routing rules: ONLY `mazemaker_recall` / `mazemaker_recall_multi` route (id-parametric think/get/browse/stats and writes remember are NEVER routed). ALICE picks the tool TYPE; the parent's query+limit always execute (she hallucinates args — bug:alice-turn-closure-imend-2026-08-11). Fail-open: any failure returns None → direct pod call. Routed children (`router_prompt` set) and delegated agents (`_delegate_depth > 0`) never re-enter. Result wrapper: `{"result", "executed_query", "router": "alice", "router_tool", "router_args", "router_note"}`.

## Personality System (CRITICAL — "loaded" ≠ "armed")

Verified 2026-08-11 in ~/.daedalus (cli.py, gateway/run.py, hermes_cli/config.py):

- **Where personalities are DEFINED**: `agent.personalities.<name>` in config.yaml.
  Read at startup by `cli.py:2172` (`CLI_CONFIG["agent"].get("personalities", {})`)
  and by gateway `_handle_personality_command` (run.py:3843). String format:
  `{"name": "system prompt"}`; dict format: `{"name": {"description", "system_prompt", "tone", "style"}}`.
- **`display.personality` is DISPLAY-ONLY** — it only feeds the welcome banner
  print (config.py:2397). It does NOT arm anything.
- **A personality is ARMED only when `agent.system_prompt` holds its text.**
  Startup loads `agent.system_prompt` (cli.py:2168-2171, gateway run.py:899-917
  `_load_ephemeral_system_prompt`, env `DAEDALUS_EPHEMERAL_SYSTEM_PROMPT` wins).
  Nothing auto-applies `display.personality` at startup; there is NO CLI flag.
- **To arm a personality**: run `/personality <name> [-s]` (sets
  `self.system_prompt` and with `-s` persists `agent.system_prompt`), OR set
  `agent.system_prompt` directly in config.yaml. A YAML alias keeps them in
  sync: `architect: &architect_prompt "..."` then `system_prompt: *architect_prompt`.
  `/personality none` clears it. `save_config_value()` does yaml.safe_load +
  modify + dump, which FLATTENS aliases to full text on the next write — safe.
- **A running gateway/CLI does NOT hot-reload** — it read the prompt at startup.
  After changing `agent.system_prompt`, restart the gateway
  (`gateway run --replace`) and tell the user a fresh CLI session is required.
- **Dead config to avoid**: a top-level `personalities: {architect}` (YAML set)
  is NOT read anywhere — remove it.

## Gateway Architecture (~/.daedalus/gateway/)

Routes messages between platforms and agent:
- `run.py` - Main loop, slash commands, message dispatch (351KB!)
- `session.py` - Conversation persistence
- `delivery.py` - Message delivery to platforms
- `hooks.py` - Hook system for platform events
- `platforms/` - Telegram, Discord, Slack, WhatsApp, HomeAssistant, Signal

## CLI Architecture (cli.py)

- **Rich** - Banner, panels, formatting
- **prompt_toolkit** - Input with autocomplete
- **KawaiiSpinner** (agent/display.py) - Animated faces during API calls
- **Skin engine** (hermes_cli/skin_engine.py) - Data-driven CLI theming
- **CommandDef** (hermes_cli/commands.py) - Central slash command registry

### Adding a Slash Command
1. Add `CommandDef` to `COMMAND_REGISTRY` in `hermes_cli/commands.py`
2. Add handler in `HermesCLI.process_command()` in `cli.py`
3. Gateway handler in `gateway/run.py` if needed

## Skill Loading

Skills auto-loaded from `~/.daedalus/skills/` at session start.
Skill commands injected as **USER message** (not system prompt) to preserve prompt caching.
Skill slash commands: `agent/skill_commands.py` scans skills directory.

## Cron System (~/.daedalus/cron/)

- `scheduler.py` + `jobs.py`
- Jobs run in fresh sessions with no chat context
- Prompts must be self-contained
- Skills can be attached to cron jobs

## Config Hierarchy

1. `~/.daedalus/config.yaml` — Settings, providers, models
2. `~/.daedalus/.env` — API keys (MSSQL, Brave, GitHub, etc.)
3. Hardcoded defaults in `cli.py` / `hermes_cli/config.py`

**WARNING**: Hardcoded default model `anthropic/claude-opus-4.6` in code overrides config.yaml for some commands. Pass `--model` explicitly or verify the config is actually loaded.

## Critical Dependencies
- `openai` — Required for API calls (not always in requirements.txt)
- `python-dotenv` — Required by hermes_cli.env_loader at import time
- `prompt_toolkit` — Required by cli.py
- `requests` — Required by agent/model_metadata.py
- `psutil` — Required by JackrabbitDLM
- `pycryptodome` — Required by Jackrabbit Wonderland

## Environments (RL Training)

- `hermes_base_env.py` - Base environment class
- `agent_loop.py` - Agent loop for RL
- `web_research_env.py` - Web research training
- `agentic_opd_env.py` - Agentic OPD environment
- `tool_context.py` - Tool context management

## Key Pitfalls

0. **Reasoning-effort live steering (fork feature)** — `agent/task_intensity.py` is a pure-function gauge: `estimate_level(user_text, messages, floor)` scores task weight (instruction length, task imperatives incl. German verb stems, tool density/errors in history, explicit depth asks) and returns a level from GAUGE_LEVELS. `conversation_loop.py` calls `adjust_agent_reasoning(agent, messages)` at the TOP of the while loop (before EVERY API call, fail-soft try/except). The lever: `agent.reasoning_config` is read per request (`reasoning_config=agent.reasoning_config` in chat_completion_helpers.py), so mutating it mid-turn takes effect on the next call. CLI enables it via `agent.reasoning_auto` (config, default true); floor = `agent.reasoning_floor` (default low). `/reasoning auto` toggles on, manual `/reasoning <level>` toggles off. Gateway/cron agents do NOT get auto (flag defaults False). Calibration: floor-jumps (1 imperative → min medium, depth ask → min high, max demand → min max), NOT pure point thresholds.

1. **`daedalus update` checks out main** — verified 2026-08-07: the update flow does `checkout main` + fast-forward, so a fork feature-branch install (context-budget-manager with the rework commits) silently loses its runtime code. AFTER every `daedalus update`, run `git checkout context-budget-manager` in ~/.daedalus (reflog: "checkout: moving from context-budget-manager to main"). The update's Web-UI build also re-creates node_modules (~300MB) — move them to Trash again if the operator wants them gone.
2. **Fork sync without checkout switch**: use ~/.local/bin/daedalus-upstream-sync.sh (fetch upstream+origin, ff fork main + push --force-with-lease, rebase current branch with backup ref + abort-on-conflict). Do NOT use `daedalus update` as the primary sync for the feature branch — it switches branches.
3. **Memory context injected as USER messages** - preserves prompt caching
4. **Skills injected as USER messages** - same reason
5. **Tool discovery is import-triggered** - importing model_tools.py triggers all tool imports
6. **Gateway run.py is 351KB** - massive, handles all platform routing
7. **AIAgent is synchronous** - no async in the core loop
