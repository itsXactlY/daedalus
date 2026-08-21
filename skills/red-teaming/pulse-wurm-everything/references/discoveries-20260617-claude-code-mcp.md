# Claude Code MCP Integration Discoveries (2026-06-17)

## Overview
Pulse-Wurm 2.0 tick discovered 5 novel repositories related to Claude Code MCP integration patterns.

## Key Discoveries

### 1. Opendray/opendray
**URL:** https://github.com/Opendray/opendray
**Description:** Self-hosted gateway that runs Claude Code · Codex · Gemini · shell sessions on your own infra with a simple interface.

**Key Features:**
- Multi-agent orchestration (Claude Code, Codex CLI, Gemini, shell sessions)
- Self-hosted - no cloud dependency
- Simple web interface for managing agent sessions
- Runs on any infrastructure with Docker

**Relevance:** Enables secure, local-first AI agent deployment without vendor lock-in.

### 2. applicate2628/mcp-local-hub
**URL:** https://github.com/applicate2628/mcp-local-hub
**Description:** Run one shared MCP server daemon per workstation — instead of each client (Claude Code, Codex CLI, Gemini CLI, etc.) spawning its own MCP server processes.

**Key Features:**
- Single daemon per workstation
- Reduces resource consumption
- Shared state across multiple AI clients
- Eliminates port conflicts

**Relevance:** Solves MCP server proliferation problem in multi-client environments.

### 3. LIVELUCKY/fastcontext-integrations
**URL:** https://github.com/LIVELUCKY/fastcontext-integrations
**Description:** One-click MCP server for microsoft/fastcontext — add repo exploration to Claude Code, Cursor, Copilot, etc.

**Key Features:**
- Drop-in MCP server for FastContext
- Works with all major AI coding tools
- Simplified setup process

**Relevance:** Accelerates context-aware coding workflows.

### 4. SheikhSheave/Claude-Code-CLI-Reference
**URL:** https://github.com/SheikhSheave/Claude-Code-CLI-Reference
**Description:** Comprehensive CLI reference for Claude Code, Codex, GitHub, Anthropic, agentic coding systems, terminal assistant, codebase, git.

**Key Features:**
- Complete command reference
- Examples and best practices
- Integration patterns for various tools

**Relevance:** Essential documentation for Claude Code workflows.

### 5. the911fund/skill-of-skills
**URL:** https://github.com/the911fund/skill-of-skills
**Description:** The autonomous discovery engine for AI coding tools. Indexes skills, plugins, MCP servers, agents, and more.

**Key Features:**
- Autonomous discovery and indexing
- Aggregates AI coding tools ecosystem
- Self-updating catalog

**Relevance:** Central registry for AI agent capabilities and skills.

## Triple-Memory Pattern Applied
- **discovery:** This file (main entry)
- **fact:** Claude Code MCP integration enables self-hosted multi-agent orchestration
- **decision:** Evaluate Opendray for local agent deployment; consider mcp-local-hub for resource optimization