---
name: daedalus-maintenance-upgrade
description: Use when daedalus is stale, models fail, or config outdated.
version: 1.0.0
author: Daedalus Agent
tags: [daedalus, upgrade, maintenance, context, config, migration]
---


> Ported from `hermes-maintenance-upgrade` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Maintenance & Upgrade

Class-level skill for keeping the Daedalus Agent install current, the config migrated, and the context window healthy. Covers the git-based upgrade path, config version migration, and the context bloat diagnostic that explains why models stop behaving autonomously.

Load this skill when:
- Daedalus is N commits behind upstream (check: `git log --oneline HEAD..origin/main | wc -l`)
- `daedalus doctor` warns about config version outdated
- Models fail at autonomous skill loading, tool discovery, or follow-the-instructions
- The user says "upgrade", "update", "bring it back", "something is broken", "it's dumb"
- Prompt-size output shows excessive system prompt / skills index / tool schema bytes

---

## 1. Git-based upgrade workflow

Daedalus installed from git (`Install method: git`) upgrades via git, not `daedalus update`.

### CRITICAL RULE: NEVER drop git stashes

The operator's stashes contain intentional work-in-progress. Even old patches represent deliberate decisions. `git stash drop` is NEVER acceptable without explicit user instruction. Keep stashes indefinitely.

### Standard upgrade path

```sh
cd ~/projects/daedalus

# 1. Stash ANY local changes
git stash push -m "pre-upgrade patches (<version> <description>)"

# 2. Fetch upstream
git fetch origin main

# 3. Check delta
git log --oneline HEAD..origin/main | wc -l

# 4. Fast-forward merge
git merge origin/main --no-edit

# 5. Reinstall into venv (NOT system python — Arch blocks that)
./venv/bin/pip install -e .

# 6. Migrate config
daedalus config migrate

# 7. Verify
daedalus --version
daedalus doctor
daedalus prompt-size
```

### Pitfalls

| # | Pitfall | Fix |
|---|---------|-----|
| 1 | `pip install -e .` fails with `externally-managed-environment` | Use `./venv/bin/pip install -e .` — the wrapper script sources this venv |
| 2 | Local patches from old era (0.8.0~) won't apply to 0.19+ codebase | Keep stash as reference; reimplement feature against new code if still needed |
| 3 | `daedalus update` overwrites local state | Use git merge instead for git-installed instances |
| 4 | Config migration warns about unknown toolsets | Non-blocking — platform references a toolset not in current codebase |
| 5 | Stash has no description | Always include version + what the patches do in the stash message |

### When upstream has implemented your local feature

After upgrade, check if the stash's feature exists upstream:
```sh
git stash show -p stash@{0}  # inspect what's in there
git log --oneline HEAD..origin/main | grep -i "<feature keyword>"
```
If upstream has it, the stash is pure history. If not, reimplment against the new codebase.

---

## 2. Config migration

`daedalus config migrate` handles version-gated schema changes. The migration is table-driven: each version bump has a function that transforms the config.

### What migration does
- Adds new keys with sane defaults
- Removes deprecated keys
- Normalizes provider slugs (e.g. vendor-prefixed → canonical)
- Updates toolset references

### When to run
- After any `git merge` that crosses config versions
- When `daedalus doctor` warns "Config version outdated"
- After cloning a profile from an old install

### Verification
```sh
daedalus config migrate        # apply
daedalus doctor                # check warnings
daedalus config get <section>  # spot-check key values
```

---

## 3. Context bloat diagnosis

When models stop following instructions, stop loading skills autonomously, or seem "dumb" across multiple models, the cause is almost always **context bloat** — not model capability.

### Diagnostic steps

```sh
# 1. Get the full prompt breakdown
daedalus prompt-size

# 2. Check compression
daedalus config get compression.enabled

# 3. Check skill count impact
daedalus prompt-size  # look at "skills index" bytes

# 4. Check tool schema overhead
daedalus prompt-size  # look at "Tool schemas" bytes
```

### Red flags

| Signal | Threshold | Impact |
|--------|-----------|--------|
| System prompt total | > 25 KB | Models lose instructions in the noise |
| Skills index | > 10 KB (50+ skills) | Models can't find relevant skills |
| Tool schemas | > 40 KB | Models skip tool calls |
| Compression disabled | `false` | Context accumulates without bound |
| MCP tools deferred | tool_search required | Models never discover MCP tools |

### The 3-layer overhead problem

The system prompt has 3 layers that ALL load every turn:

1. **Identity layer** (SOUL.md + MEMORY.md + USER.md) — who the agent is, rules for behavior, user preferences. Typically 10-15 KB.
2. **Skills index** — names + descriptions of ALL installed skills. 137 skills = ~14 KB. Models see "skill X exists" but don't have its content.
3. **Tool schemas** — JSON parameter definitions for all direct tools. 28 tools = ~45 KB.

Total overhead before user speaks: **~70-80 KB**. Most models drown.

### Fix priority

1. **Enable compression**: `daedalus config set compression.enabled true`
2. **Trim MEMORY.md**: Cut meta-rules to ~2 KB. Most rules should be in skills, not memory.
3. **Trim SOUL.md**: Cut philosophy to ~1.5 KB of actionable instructions. Models need commands, not poetry.
4. **Archive unused skills**: Reduces skill index. `daedalus curator run` or manual `skill_manage(action='delete', absorbed_into='')`.
5. **Make MCP tools direct**: If models can't discover MCP tools via tool_search, check if the MCP servers are enabled and tools are registered.

### Why "deferred tools" break autonomy

MCP tools (mazemaker, pulse, etc.) are not in the direct tool list. Models must:
1. Call `tool_search(query='mazemaker')` — discover the tool exists
2. Call `tool_describe(name='...')` — get the parameter schema
3. Call `tool_call(name='...', arguments={...})` — invoke it

Most models skip step 1 entirely because they see 28 direct tools and assume that's all there is. The `tool_search` mechanism is not intuitive.

### Compression mechanics

When enabled, compression triggers when context exceeds `threshold` (default 0.85 = 85% of context window). It summarizes older messages to fit within `target_ratio` (default 0.50). Key settings:

```yaml
compression:
  enabled: true              # MUST be true for long sessions
  threshold: 0.85            # when to trigger
  target_ratio: 0.50         # compress down to this fraction
  protect_last_n: 50         # never compress recent messages
  protect_first_n: 3         # never compress system prompt + first exchanges
```

---

## 4. Version delta awareness

Large version deltas (>500 commits) accumulate breaking changes that affect:
- Tool schemas (new parameters, renamed fields)
- Config schema (new sections, deprecated keys)
- Prompt assembly (new blocks, reordered sections)
- MCP integration (new discovery patterns)
- Compression behavior (new thresholds, strategies)

When diagnosing agent competence issues, **always check the version delta first**. A model that worked great on v0.19.0 with v24 config may fail on the same code because the config is stale, not because the model regressed.

```sh
daedalus --version                                            # current
cd ~/projects/daedalus && git log --oneline HEAD..origin/main | wc -l  # delta
daedalus doctor | grep "Config version"                       # config staleness
```

---

## 5. Skills index is redundant when mazemaker has everything vectorized

The system prompt injects a **skills index** (~14 KB for 137 skills) listing every installed skill by name + description. This is pure overhead when the operator's skills are also indexed in mazemaker's vector graph.

**The model doesn't need the static index.** It should:
1. Use `mazemaker_recall` to find relevant skills (REGEL 1)
2. Call `skill_view(name)` to load the matched skill's content

The skills index exists as a fallback for models that can't use mazemaker, but on a setup with mazemaker wired, it's 14 KB of noise competing with actual instructions.

**Do NOT try to suppress the index** — there's no config option for it. Instead, ensure:
- `compression.enabled: true` (so context doesn't accumulate)
- MEMORY.md is trimmed (rules < 2 KB)
- SOUL.md is trimmed (instructions < 1.5 KB)
- The model follows REGEL 1 (mazemaker first) and REGEL 5 (skill first if matched)

---

## 6. Dead skill references in system prompt

The system prompt may reference skills that were consolidated or renamed. Example: `hermes-agent` was consolidated into `daedalus-core-capabilities` but the system prompt still says "Load the `hermes-agent` skill". This wastes a tool call when models try to follow the instruction.

**After any upgrade**, check for dead references:
```sh
grep -r "hermes-agent" ~/.daedalus/SOUL.md ~/.daedalus/memories/MEMORY.md 2>/dev/null
```

If found, the reference is cosmetic — it doesn't break anything, but it wastes a turn. The fix is in the harness code (system prompt template), not in user files.

---

## 7. Deletion discipline — never nuke without checking

**Pitfall**: Deleting directories/files without verifying contents first. Example: deleting `.claude/worktrees` or `models/` directories without checking if they contain important data.

**Rule**: Before any `rm -rf`, check contents:
```sh
du -sh <target>           # how big is it?
find <target> -name "*.gguf" -o -name "*.safetensors"  # any model files?
ls -la <target>/          # what's in there?
```

The operator guards their data. Stashes, models, configs, worktrees — all represent intentional work. Nuking without checking is a trust violation.

---

## 8. Download discipline — never fetch full repos when one file is needed

**Pitfall**: Running `git clone` or `setup.sh` on a demo repo when you only need one specific file. Example: cloning the entire Bonsai demo repo (6.5 GB venv + 10 GB models) when the user only needs a single GGUF file.

**Rule**: Before downloading, ask:
1. What specific file(s) does the user need?
2. Can I download just those files directly via curl/wget?
3. Does the user already have some of these files?

Direct file download:
```sh
curl -LsSf "https://huggingface.co/<repo>/resolve/main/<file>" -o <local_path>
```

Full repo clone (only when you need the code/scripts):
```sh
git clone --depth 1 <repo>  # shallow clone saves bandwidth
```

---

## 9. Autonomous loop management — hard-won rules

When running a perpetual agent loop (systemd service, 24/7 workers), these session-tested pitfalls cause the most damage:

### Rule: Continue existing work, never rebuild from scratch

Before touching ANY project file, call `mazemaker_recall` to find the actual current state. The user's project has history — files, commits, decisions, prior worker output. "From scratch" is almost never what the user wants. If the user says "DA SOLLEN DIE SUBCREW AGENTS WEITER BAUEN" — "weiter" means CONTINUE, not restart.

```sh
# ALWAYS check what exists first
git log --oneline -5
find . -maxdepth 2 -name '*.js' -o -name '*.css' | head -20
```

### Rule: No worktrees unless user explicitly requests them

If the user says "keine Worktrees" or expresses hatred for git worktree complexity — workers commit DIRECTLY in the main repo directory. No branches, no worktrees, no merge step. The supervisor runs workers with `cd "$FORK_DIR" && daedalus -z ...` instead of `cd "$WORKTREE" && daedalus -z ...`. This is simpler and the user can see changes immediately.

### Rule: Never overwrite existing files

NEVER overwrite index.html, style.css, or any existing asset without explicit permission. Use `patch` for targeted edits, or `git checkout HEAD -- <file>` to restore accidentally clobbered files. Read first, extend second.

### Rule: Act, don't narrate

When the user says "MACH", "BAU", "WEITER", "GO" — stop reading files and start executing. Context-gathering has a budget of 3-5 reads per action. After that, act. Endless "let me check..." loops cause rage.

### Rule: Use verified model/provider combinations

If a model/provider was verified working this session (e.g. `nous:tencent/hy3:free`), USE IT for subsequent rounds. Don't re-test every permutation. Document the working combination and stick with it.

### Rule: The user's path IS the path

The user says "/home/alca/projects/rework/website/" — that IS the directory. Not site-visual-fork, not old/, not a new from-scratch dir. Don't second-guess, don't look for alternatives, don't check if something else exists.

### Rule: Execute systemctl when user says GO

If the user explicitly says GO/start/weiter/lässt, execute the systemctl command immediately. Don't ask for confirmation. Don't explain what you're about to do. Just do it.

## References

- `references/typical-subsystems.md` — catalog of subsystems that may need attention, common failure patterns per subsystem
- `references/free-model-provider-config.md` — verified working free model providers and model IDs for the rework loop
