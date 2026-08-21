---
name: daedalus-core-capabilities
description: >-
  Core Daedalus Agent capabilities — configuration, setup, extension, plugins, profiles, MGE, and container supervision.
  Triggers: user mentions Daedalus configuration, model providers, toolsets, gateway routing, profiles, plugins, or container deployment (Docker, kexec, etc.).
  Umbrella for the former agent-created skills in the daedalus-* and related domains.
version: 2.0.0
author: Daedalus Agent
license: MIT
metadata:
  daedalus:
    tags: [daedalus, setup, configuration, extension, container, profile, plugin, mcp, middleware]
    related_skills: [daedalus-harness-internals, loop-engineering, pulse-wurm-recon-tick]
---


> Ported from `hermes-core-capabilities` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Core Capabilities

Class-level umbrella for the core Daedalus Agent platform functions: configuration, deployment, plugins, profiles, and container supervision. This skill consolidates knowledge from multiple narrow skills into a single authoritative reference for:

- **Configuration** – model/providers, toolsets, gateway routing, agent lifetime
- **Extension** – authoring skills, building plugins, per-task model routing
- **Deployment** – container supervision (s6-overlay) and Architecture B reasoning
- **Profiles** – multi-isolated Daedalus instances with per-profile state
- **Middleware** – MCP clients and the MGE underpinnings
- **Lifecycle** – cron, observability, skill maintenance (Curator)

Load this skill when your task involves:
- Configuring Daedalus or exploring what Daedalus can configure
- Writing a skill for Daedalus or any part of the Daedalus extension eco-system
- Understanding how Daedalus runs, what it supervises, and how it interacts with containers and profiles
- Debugging or extending across the Daedalus platform or its plugins and middleware

This umbrella contains subsections for each major area, providing both overview and specific action patterns.

---

## A. Configuration

Daedalus core configuration lives under `~/.daedalus/config.yaml` and is mutable via `daedalus config set key val` or `daedalus config edit`. Use `daedalus config` to inspect the live document.

### Section quick reference

| Section | Keys | Typical use |
|---------|------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length` | Model selection (see `daedalus model`) |
| `agent` | `max_turns`, `tool_use_enforcement` | Agent-level runtime knobs |
| `terminal` | `backend` (local/docker/ssh/modal), `cwd`, `timeout` (default 180) | Tool execution environment |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) | Context compression behavior |
| `display` | `skin`, `tool_progress`, `show_reasoning`, `show_cost` | UI/tui presentation |
| `gateway` | `platforms.<platform>.enabled`, `workers` | Messaging gateway control |
| `toolsets` | `enabled`, `disabled` | Which tool clusters Daedalus can use |
| `memory` | `provider` (builtin/honcho/mem0), `user_profile_enabled` | Persistent memory backend |

### Global provider model workflow

1. `daedalus model` launches an interactive wizard that temporarily writes to the config YAML.
2. Under the hood, `daedalus auth add <provider>` stores encrypted credentials in `~/.daedalus/auth.json`.
3. The config reader (`daedalus config`) reads both the temporary runtime environment and the YAML live file.

### Model enumeration and provider health

- **OpenRouter**: Use `openrouter/models` API (with bearer token). Fetch list of available model IDs; cache locally for fast completion.
- **Anthropic**: Direct `/v1/models` endpoint (supports cost-per-1m-tokens metadata).
- **OpenAI Codex / other custom endpoints**: Include `custom:<provider>` entries under `providers:` and maintain `model.base_url` + `api_key`.

### Provider best practice

- **Pin providers based on expectations**: OpenRouter for coverage, Anthropic for reasoning, Z.ai GLM 5.2 (MIT) for costs.
- **Write path**: Remove cards you explicitly refuse or don't use.
- **No service–level tokens**: Do NOT attach a Bearer token to `/v1/models` requests unless authorization is otherwise required.

### Toolsets and the safe cluster

The default Daedalus agent carries `_HERMES_CORE_TOOLS`. The goal of `daedalus tools` is to toggle sets of these in or out of a container/VM/session via environment-flag refresh. They power toolset-level policies like the `safe` cluster (minimal tools only).

## B. Extension

### B.1 Skill authoring

1. **Create the directory**: `mkdir -p ~/.daedalus/skills/`.
2. **Add frontmatter**: `SKILL.md` with the YAML block shown in the `hermes-agent-extending` skill.
3. **Fill body**: sections: When to use → Workflow / steps → Pitfalls → (optional) references/, templates/, scripts/.
4. **Validator**: `script/validate-skill.py` — run it after initial writing. It checks frontmatter schema, name uniqueness in the skill index, and validates any relative links (references/, templates/, scripts()).

### B.2 Plugin authoring

1. **Package**: `pyproject.toml` or `setup.py`, declare entry point `daedalus.plugins`.
2. **Register tools**: call `tools.registry` functions during `on_load`.
3. **Optional MemoryProvider**: implement get/set/search methods, pass to Daedalus constructor.
4. **No import-time side effects**.

### B.3 Skill consolidation

- **Read first**: use mazemaker_recall to query existing skill content before adding duplicates.
- **Class-level skills**: the skill cover must capture a CLASS of tasks, not a one-off bug fix.
- **Narrow-skill demotion**: rename or delete skills whose names contain PR numbers, feature codenames, or diagnostic artifacts; repack those under subsections or support files.
- **Re-homing**: when moving content from an existing skill into this umbrella skill, follow the process in `hermes-agent-extending/SKILL.md` – rehome references/ templates/ scripts/, then archive the old skill package with `absorbed_into="daedalus-core-capabilities"`.

## C. Deployment

### C.1 Container supervision (s6-overlay)

This umbrella consolidates previously separate knowledge from `hermes-agent-extending` (section C) and `daedalus-s6-container-supervision`. It focuses on:

- **Container architecture** – s6-overlay design (Architecture B), cont-init scripts, static services, per-profile gateway lifecycle
- **Verification commands** – s6-svstat, /run/service/gateway-* status, container-boot reconciliation
- **Quirks & pitfalls** – UID/GID remap, profile directory ownership, persistency, re-registration after restart
- **Adding services** – smoke-tests, lifecycle, monitoring

**Key reference**: `reconcile_profile_gateways()` in `hermes_cli/container_boot.py` is the single source of truth for how the container matches profile state to s6 slots.

**Verification commands**

```sh
# Check service status
docker exec <c> /command/s6-svstat /run/service/gateway-<name>
# up (pid ...) … seconds   → running
# down (exitcode N) … normally up → crash loop

# Watch the cont-init reconciler log
docker exec <c> tail -n 50 /opt/data/logs/container-boot.log
```

### C.2 Kubernetes/ECS idioms

Do not modify the image’s metadata (it’s read-only). Pass all config via environment variables and use initContainers (via `tools/docker_hack.py`) to seed persistent volume mounts if runtime state is needed.

## D. Profiles

A profile is an isolated Daedalus instance with:

- Its own `~/.daedalus/profiles/<name>/config.yaml`
- `~/.daedalus/profiles/<name>/skills/` (loaded via `$DAEDALUS_HOME/skills/*.md` relative to the profile)
- A mirrored memory backend (builtin/Honcho/Mem0 with profile state)
- Optional `gateway_state.json` (for the per-profile gateway under s6)

Loading a profile: `daedalus --profile name`

You can clone profiles: `daedalus profile create newname --clone existing` or `daedalus profile create newname --clone-all existing`.

## E. Pulse Wurm Research

This umbrella section consolidates `pulse-wurm-recon-tick` and `pulse-wurm2-tick-learnings` into a single comprehensive reference for autonomous research workflows.

### E.1 Pulse Wurm Recon Workflow

This skill describes the established workflow for the pulse-wurm cron job:

- **Trigger conditions**: Cron-driven autonomous research agent with multi-tick topic discovery + follow-up cycle
- **Pre-flight**: State management (state['visited_urls'], state['consistency'], state['next_seeds']), content fetching pipelines with fallbacks, LLM filtering controls
- **Error recovery**: When pulse_search fails, fallback to pulse_research, troubleshoot using state['visited_urls'] to avoid duplicate work, handle mazemaker MCP outage via session_search backup

### E.2 Key architectural details

| Component | Purpose |
|-----------|---------|
| `pulse_search(depth='quick')` | Initial shallow broadcast across 22 sources |
| `pulse_search(depth='deep')` | Deep follow-up on the most promising topics |
| `pulse_research(depth='default')` | Fallback when deep/bright fails (breaks continuity) |
| `pulse_dig(max_rounds=2, max_fetches=100)` | Wurm-style URL crawling with throttling |
| `session_search(...)` | Complementary graph search for mazemaker recall |
| `state['visited_urls']` | Central visited URL set for deduplication across all phases |

### E.3 State management patterns

**State structure reference**: Explore `references/pulse-wurm-state-schema.md` for details:

- `visited_urls` → visited URLs set (shared across script + MCP path)
- `consistency` → search consistency tracking (novel vs duplicate)
- `next_seeds` → prioritized seed queue (sorted by saturation weight)
- `discovered_topics` → topics logged for Graph enrichment (timestamp + detection + seed + classification + sat)

**Critical 2026-06-21 outcome**: Year-token detection is only in the query; add result-side year check.
**Critical 2026-06-23 outcome**: Homepage anchor protects `max=26` uniform “all” result set; enforce `mode='all'` like existing script, but IN ADDITION to `pulse_dig` fallback.

### E.4 Content fetching and enrichment

**Three-tier fallback pattern** (see references/pulse-wurm-content-fetching-fallbacks.md):

- Primary: Direct HTTP fetches (curl/wget from visited_urls)
- Secondary: Browser tools (for sites that block automated HTTP)
- Tertiary: API calls and PDF extraction (for scholarly papers, managed via arxiv API + pdftotext)

**Triple-memory enrichment pattern** (see references/triple-memory-enrichment-pattern.md):

```
mazemaker_remember(token='discovery', content='<topic>', salience=1)   # N1, larQ match
mazemaker_remember(token='fact',     content='<insight>',     salience=10)
mazemaker_remember(token='decision', content='<action>',     salience=50)
```

Push the discovery entry at low salience (<1) so it augments query recall. Use `domain_edge_prefix_override: "greybeard"` for arXiv papers to avoid extracting from non-opaque domains.

### E.5 Verification and healthy cron execution

- **Cron monitor**: `daedalus cron list` → confirm jobs show `state: scheduled`
- **Logs**: Check `~/.daedalus/loops/shared/loop_runner.log` for tick execution
- **Graph recall**: After the first tick, use `mazemaker_recall(token='discovery:*')` to confirm structured writes landed
- **Dream stats**: After first MEASURE, use `mazemaker_dream_stats()` to confirm the graph is processing outputs

### E.6 Common pitfalls

| # | Pitfall | Fix |
|---|---------|-----|
| 1 | **Pulse-search dead-end** – script returns 0 novel, overwrites state['visited_urls'] | Use MCP path: `pulse_search()` + `pulse_dig()` + `mazemaker_remember()` directly |
| 2 | **Fresh seed contribution loses cluster bias** – productive seed's saturation > script-defaults | Swap positions in `next_seeds` after mutation, promoting productive seed to position 0 |
| 3 | **Pulse-search-as-hijack-bypass** – MCP path sees unique domains (e.g., arXiv 2605.24300) | Use `pulse_search(depth='deep')` + `state['visited_urls']` dedup, then fallback for non-GitHub |
| 4 | **MAX=26 “all” result set** – script oversamples popular topics | Enforce `mode='all'` and deduplicate by visiting domain, plus visited_urls dedup above |
| 5 | **Response nesting** – `pulse_search_result` returns triple-wrapped JSON | Parse `result['body']['ranked_candidates']`, not root result |
| 6 | **Catalog types too broad** – catalog types like "article" include ads | Use `guest-author` / `highlight` / `lead` frontmatter flags and explicit url/domain filters |
| 7 | **Browser fallback costs** – browser tools are slower, need timeouts | Only trigger on `pulse_search_api` failure, limit to 30s per domain, skip: non-whitelisted or failing sites |
| 8 | **LLM filter underweights freshness** – for math/learning intent, keep old papers | For explicit year tokens (2026, 2025), apply 24-month expiration filter after LLM filter |

## F. Middleware & Core Daedalus Operations

### F.1 MCP client operations

See the native-mcp references in `hermes-agent-SKILL.md`.

### F.2 Memory graph (mazemaker)

Perform operations with `mcp__mazemaker__mazemaker_*` tools to read/write graph facts/decisions/edges (see `mazemaker/graph`). This powers AUTONOMOUS discovery and decision making.

## G. Orchestration & Management

### G.1 Loop engineering and tri-state cadence

Consolidates `loop-engineering` -> orchestrated through the graph under `ops:` prefix. 

### G.2 Delegation strategies

- `delegate_task` : isolated subagent, shared process (quick subtasks)
- Workspace spawning : fully separate process, interactive for long missions
- Multi-agent code orchestration : parallel workstreams (2 waves of 3 per-phase)

## H. Security & Safety

### H.1 Security controls

Retain as dedicated skills:
- `daedalus-mcp-security-audit` : security issues to run on MCP servers
- `daedalus-skill-supply-chain-audit` : red-flag scan procedure for skills

### H.2 Authentication and profile security

Profile isolation, gateway supervision (per-profile start/stop/restart), and human-in-the-loop controls for destructive operations in container lifecycle.

## I. Quick references

### I.1 Skill authoring front-matter

```yaml
---
name: skill-id                    # lowercase hyphens, <=64 chars
description: >-
  Trigger phrases and the task class. This is the search key.
category: devops                 # optional grouping (must be lowercase)
version: 1.0.0
author: Daedalus Agent
license: MIT
tags: [automation, tooling]      # optional discovery hints
---
```

### I.2 Skill locations

- Skills are in `~/.daedalus/skills/<skill-name>/<skill-name>/SKILL.md`
- Supporting files: references/, templates/, scripts/, assets/
- Umbrella skill lives under `~/.daedalus/skills/autonomous-ai-agents/daedalus-core-capabilities/`

### I.3 Validators

`script/validate-skill.py` (in Daedalus repo). Checks:
- Frontmatter schema
- Name uniqueness in the skill index
- Validate relative links to references/, templates/, scripts/

### I.4 Umbrella package management

- Use `skill_manage(action='patch')` to add content
- Use `skill_manage(action='delete')` for siblings with `absorbed_into="daedalus-core-capabilities"` (merge) or `absorbed_into=""` (prune)

### I.5 Misc. constants

- Minimum cluster size for consolidation: any 2+ members
- Honey-base threshold: skills with similar names or topics that suggest a common class belong under umbrella

## C. Deployment

### C.1 s6-overlay container design (Architecture B)

**File layout**

```
.dockerfile
.docker/entrypoint.sh
.docker/stage2-hook.sh                      ← cont-init.d/01-daedalus-setup
.docker/cont-init.d/02-reconcile-profiles
.docker/s6-rc.d/dashboard/run              ← optional service
.docker/s6-rc.d/main-daedalus/run            ← no-op (requirements)
docker/main-wrapper.sh                     ← container's CMD
```

**Main-wrapper role**
- Drops to daedalus via `s6-setuidgid daedalus daedalus`
- Accepts bare `--help`, `daedalus --version`, `daedalus --tui`, and full `daedalus` subcommands
- Returns daedalus's exit code to /init (container supervisor)

**After-boot**: const-init/02 reconciles per-profile gateways from a host-persistent `$DAEDALUS_HOME/profiles/<name>/` volume, recreating s6 supervision under `/run/service/gateway-<name>/`.

**Verification commands**

```sh
# UID/GID remap + seed config
docker run <img> daedalus profile create myprofile
# All heredoc/.env files get seeded from hermes_image/{.env,/config.yaml,/usr/share/daedalus/home/.sol}

# Check service status
docker exec <c> /command/s6-svstat /run/service/gateway-<name>
# up (pid ...) … seconds   → running
# down (exitcode N) … normally up → crash loop
```

### C.2 Kubernetes/ECS idioms

Do not modify the image’s metadata (it’s read-only). Pass all config via environment variables and use initContainers (via `tools/docker_hack.py`) to seed persistent volume mounts if runtime state is needed.

## D. Profiles

A profile is an isolated Daedalus instance with:

- Its own `~/.daedalus/profiles/<name>/config.yaml`
- `~/.daedalus/profiles/<name>/skills/` (loaded via `$DAEDALUS_HOME/skills/*.md` relative to the profile)
- A mirrored memory backend (builtin/Honcho/Mem0 with profile state)
- Optional `gateway_state.json` (for the per-profile gateway under s6)

Loading a profile: `daedalus --profile name`

You can clone profiles: `daedalus profile create newname --clone existing` or `daedalus profile create newname --clone-all existing`.

## E. Middleware

### E.1 MCP client

The built-in MCP client is referenced by `skill_view(name="hermes-agent", file_path="references/native-mcp.md")`.

**Life cycle**
- Server startup finds MCPs under `$DAEDALUS_HOME/.config/daedalus/mcp/` (from `./.config/daedalus/mcp/*.json`);
- `daedalus mcp add name --url <...> --command ...` persists JSON config.
- Runtime scan follows the configured servers, discovers their tool sets, and exposes them as first-class tools.

**Safety**
- `daedalus mcp configure name --tools tool1,tool2` filters the server’s published tools.
- Built-in tools are trusted; no approval needed.

### E.2 MGE

Query `daedalus-mazemaker-mazemaker_...` tools to read/edit the mazemaker graph.

## F. Lifecycle

### F.1 Cron jobs

- Use `cronjob` tool or `daedalus cron` CLI.
- Schedule: duration (`"30m"`), `every 2h`, cron (`"0 9 * * *"`), or ISO timestamp.
- Tags model provider overrides (e.g. cheap model for discovery, expensive for action).
- Delivery per job: `origin` (default), `local` (silent), or a specific channel.
- Cleanup: `daedalus cron list --all` shows paused jobs, `daedalus cron remove <job_id>`.

### F.2 Curator

`daedalus curator status` → `idle` vs `running` and current timer.`daedalus curator run` kicks the background pass.

**Archives**
- Only agent-created skills (not bundled/hub skills) can be archived.
- Move skill directories to `~/.daedalus/skills/.archive/`.
- Always pass `absorbed_into` when you delete a merged skill, or `absorbed_into=""` when truly pruning.
- Pinned skills are insulated from auto-archive.

### F.3 observability

`daedalus insights [--days N]` — token usage and rotation stats.

`daedalus doctor` — check dependencies, config health, curl timeouts.

## G. Orchestration & Management

### G.1 Delegate_task vs workspace management

- `delegate_task` → isolated subagent, shared process (quick subtasks).
- Workspace (tmux) spawning → fully separate process, interactive for long missions.

### G.2 Tasker patterns

```bash
# One-shot, no oversight
terminal(command="daedalus chat -q 'Fix auth bug'", timeout=300)

# Long mission, see progress (tmux prefix)
terminal(command="tmux new-session -d -s loop -x 120 -y 30 'daedalus -p coder'")
```

## H. Related skills

- `loop-engineering` — designs autonomous cadence loops across the maze maker graph.
- `daedalus-s6-container-supervision` — deep-dive into the s6-overlay supervision tree.
- `hermes-agent` — moves from platform usage to configuration and model selection.

## I. Quick references

**Front‑matter schema (YAML frontmatter) for any skill**

```yaml
---
name: skill-id                    # lowercase hyphens, <= 64 chars
title: Human‑readable title       # optional; used in CLI help
description: >-
  Trigger phrases and the task class. This is the search key.
category: devops                 # optional grouping (must be lowercase)
version: 1.0.0
author: Daedalus Agent
license: MIT
tags: [automation, tooling]      # optional discovery hints
---
```

**Skill location**: `~/.daedalus/skills/<skill-name>/<skill-name>/SKILL.md`

**Validator script**: Look for `scripts/validate-skill.py` in the Daedalus repo.

**Archiving**: `skill_manage(action='delete', name='<old-skill-name>', absorbed_into='daedalus-core-capabilities')`
or `skill_manage(action='delete', name='<old-skill-name>', absorbed_into='')` for pruning.

**If you're adding a new class‑level umbrella**: first confirm no existing skill covers the same class, then create with `skill_manage(action='create')`, patch into it with `skill_manage(action='patch')` after collecting sibling insights, then archive the siblings via `skill_manage(action='delete')` with absorbed_into.

---

## Structured summary

| Skill | Reason for consolidation |
|-------|--------------------------|
| `hermes-agent` | Core Daedalus knowledge, becomes default reference for basic setup and running |
| `hermes-agent-extending` | Extension/readme role, absorbed under configuration + authoring sections |
| `daedalus-s6-container-supervision` | Deep dive into container design; moved to deployment subsection |
| `loop-engineering` | Workflow dimension of autonomous loops; absorbed under G.1/G.2 orchestration |
| `pulse-wurm-recon-tick` | FOUNDER of pulse-wurm crown — moved to authentication & pattern references on the pulse side |
| `pulse-wurm2-tick-learnings` | Foundational pattern collection — moved to G.2 as reference |
| `daedalus-mcp-security-audit` | DOMAIN-SPECIFIC; keep as a specialist security skill (NO umbrella) |
| `daedalus-skill-supply-chain-audit` | DOMAIN-SPECIFIC; keep as a specialist security-skill vetting (NO umbrella) |
| `mcp-btquant-server` | DOMAIN-SPECIFIC; private MCP server for trading backend, off-limits |
| `native-mcp` | LINK (exists as `skill:${name}` not in candidate list) |

All archived skills will appear in the YAML summary below.
