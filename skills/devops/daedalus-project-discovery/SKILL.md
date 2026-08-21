---
name: daedalus-project-discovery
description: How the agent discovers and works with user projects across ~/projects
category: devops
version: 1.0
tags: [daedalus, projects, discovery, workspace, navigation]
priority: high
---


> Ported from `hermes-project-discovery` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus Project Discovery

How the agent finds and works with user projects.

## Project Root

All projects live under `~/projects/`.

## Active Projects

| Project | Path | Purpose |
|---------|------|---------|
| **PubBTQuant** | `~/projects/PubBTQuant/` | Autonomous quant trading framework |
| **PULSE** | `~/projects/pulse/` | Multi-source social search engine |
| **Neural Memory** | `~/projects/neural-memory-adapter/` | Semantic knowledge graph |
| **Jackrabbit Wonderland** | `~/projects/daedalus-crypto/` | LAN-based Daedalus control system |
| **Jack-in-a-Box** | `~/projects/jack-in-a-box/` | All-in-one installer |
| **EvoMem** | `~/projects/evo_mem/` | Evolution memory benchmark |
| **MemoryAgentBench** | `~/projects/MemoryAgentBench/` | Memory agent benchmarking |
| **Copy Trading** | `~/projects/copy-trading-platform/` | Docker copy trading |
| **hermelinChat** | `~/projects/hermelinChat/` | Chat system |
| **Daedalus Agent** | `~/.daedalus/` | The agent itself (git checkout) |

## Research Workspace

`~/The Architects Palace/` contains 55+ deep dive research files:
- Geopolitics, Finance, Cybersecurity, AI
- Coding conventions research
- PULSE arXiv research
- Terminal UI research

## How To Navigate

1. `ls ~/projects/` — see all projects
2. `ls ~/.daedalus/` — see agent internals
3. Check `~/projects/<project>/README.md` for project docs
4. Check `~/projects/<project>/SKILL.md` for project-level skills

## Key Files Per Project

- `README.md` — project overview
- `SKILL.md` — agent skill (if exists)
- `install.sh` — installation script
- `pyproject.toml` or `setup.py` — Python project config
- `.git/` — git repository
- `tests/` — test suite
- `docs/` — documentation

## Pitfalls
- Don't hardcode paths — use `$HOME/projects/` or `~/projects/`
- Some projects have their own virtualenvs — check for `.venv/` or `venv/`
- Git repos may have different remotes — always check `git remote -v`
- The Architects Palace is NOT a git repo — it's a research dump
