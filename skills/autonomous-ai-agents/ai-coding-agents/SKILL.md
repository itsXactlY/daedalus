---
name: ai-coding-agents
description: "Orchestrate external AI coding agents (Claude Code, OpenAI Codex, OpenCode) for autonomous implementation, refactoring, PR review, and multi-agent workflows. Covers print mode, PTY orchestration, and delegation patterns."
version: 1.0.0
author: Daedalus Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  daedalus:
    tags: [Coding-Agent, Delegation, PTY, Orchestration, Refactoring, Code-Review]
    related_skills: [delegate-task, kanban-orchestrator, daedalus]
---

# AI Coding Agents — Orchestration Patterns

Delegate coding tasks to external AI agents that run autonomously in your terminal. Each agent has distinct capabilities and orchestration requirements.

## When to Use

- Complex code changes that benefit from autonomous exploration
- Refactoring large codebases with minimal supervision
- PR review at scale (multiple PRs, automated analysis)
- Multi-agent workflows (agent A builds, agent B tests)
- When `delegate_task` isn't sufficient (need PTY/tty or external CLI)

---

## Agent Comparison Matrix

| Agent | Print Mode | PTY Required | Key Strength | Model Options |
|-------|------------|--------------|--------------|---------------|
| **Claude Code** | `claude -p 'prompt'` | No (print mode) | Deep reasoning, MCP integration, subagents | Claude 3.5/3.7 Sonnet, Haiku, Opus |
| **OpenAI Codex** | `codex exec 'prompt'` | No (exec mode) | Fast iteration, git-native | GPT-4o, o1, o3 |
| **OpenCode** | `opencode run 'prompt'` | No (run mode) | Provider-agnostic, open-source | Any via OpenRouter/OpenAI/etc |

---

## 1. Claude Code Orchestration

Trigger: Delegating to Claude Code specifically.

### Prerequisites
- Install: `npm install -g @anthropic-ai/claude-code`
- Auth: `claude` (browser OAuth) or `ANTHROPIC_API_KEY`

### Print Mode (PREFERRED)
```python
terminal(
    command="claude -p 'Fix the auth bug in src/auth.py' --allowedTools 'Read,Edit' --max-turns 10",
    workdir="/path/to/project",
    timeout=120
)
```

**Benefits:** No PTY needed, skips all dialogs, exits cleanly.

### Interactive PTY Mode
```python
terminal(command="tmux new-session -d -s claude -x 140 -y 40")
terminal(command="tmux send-keys -t claude 'cd /project && claude' Enter")
terminal(command="sleep 5 && tmux send-keys -t claude Enter")  # Trust dialog
terminal(command="sleep 15 && tmux capture-pane -t claude -p -S -50")
```

**Critical:** Handle Trust dialog (Enter) and Permissions dialog (Down then Enter if using `--dangerously-skip-permissions`).

---

## 2. OpenAI Codex Orchestration

Trigger: Delegating to Codex specifically.

### Prerequisites
- Install: `npm install -g @openai/codex`
- Auth: `OPENAI_API_KEY` or Codex OAuth
- Must run inside git repo (or create temp one)

### Exec Mode (Print Mode equivalent)
```python
terminal(
    command="codex --full-auto 'Add rate limiting to API'",
    workdir="/project",
    timeout=180
)
```

### PR Review Pattern
```python
terminal(
    command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*' && gh pr checkout 42 && codex exec 'Review this PR for bugs and security issues'",
    timeout=300
)
```

---

## 3. OpenCode Orchestration

Trigger: Delegating to OpenCode specifically.

### Prerequisites
- Install: `npm i -g opencode-ai@latest` or `brew install anomalyco/tap/opencode`
- Auth: `opencode auth login`

### Run Mode (Print Mode equivalent)
```python
terminal(
    command="opencode run 'Implement the feature described in TASK.md'",
    workdir="/project",
    timeout=180
)
```

### Interactive PTY Mode
```python
terminal(command="opencode", workdir="/project", background=True, pty=True)
process(action="submit", session_id="<id>", data="Your task here")
process(action="poll", session_id="<id>")
process(action="kill", session_id="<id>")  # Use Ctrl+C or kill, NOT /exit
```

**Critical:** `/exit` is NOT valid — use `process(action="write", data="\x03")` or kill.

---

## 4. Kanban Integration (Deferred to kanban-codex-lane)

When running in a Kanban worker context, see `skill_view(name="kanban-codex-lane")` for:
- Isolated worktree/branch creation
- PMB safety constraints
- `codex_lane` metadata schema for `kanban_complete`
- Reconciliation checklist

---

## 5. Multi-Agent Patterns

### Parallel Implementation
```python
# Spin up multiple agents in parallel worktrees
terminal(command="tmux new-session -d -s impl1 && tmux send-keys -t impl1 'cd /tmp/task-a && codex exec ...' Enter", background=True, pty=True)
terminal(command="tmux new-session -d -s impl2 && tmux send-keys -t impl2 'cd /tmp/task-b && claude -p ...' Enter", background=True, pty=True)
```

### Sequential Pipeline
```python
# Write code → tests → review
terminal(command="codex exec 'Implement feature X'", workdir="/tmp/impl")
terminal(command="claude -p 'Review this implementation: $(cat file.py)' --allowedTools 'Read'", timeout=60)
```

---

## Common Pitfalls

| Agent | Pitfall | Fix |
|-------|---------|-----|
| All | Running outside git repo | Create temp dir: `cd $(mktemp -d) && git init` |
| Claude | Trust dialog blocking automation | Use print mode (-p) or tmux Enter |
| OpenCode | `/exit` opens agent selector | Use Ctrl+C (SIGINT) or process kill |
| All | Tool timeouts too short | Set timeout=300+ for complex tasks |
| All | Model override ignored | These agents use their own model selection |

---

## Decision Tree

```
Task type:
├── One-shot bounded task → Use print/exec/run mode
├── Multi-turn exploratory → Use interactive PTY via tmux
├── Safety/security constraints → Use print mode + restricted --allowedTools
├── Need to spawn from Kanban worker → Load kanban-codex-lane skill
└── Want to compare models → Run parallel agents, compare outputs
```