# Communication Patterns Violations Reference

Evidence from mazemaker memory graph (204,485 memories analyzed). All findings sourced from mazemaker.

## 1. Verbosity Inconsistency

**Evidence:** memory id=118277
- Oscillates between 7-token recalls and 709-token technical dumps
- User preference: "zero fluff" / direct, terse, command-focused responses
- Violation: Large dumps provided unprompted when user wants brevity

**Example from memory id=118277:**
> "Inconsistent — oscillates between too terse (7-token recalls with no context) and too verbose (709-token technical dumps unprompted)"

## 2. Markdown in CLI Usage

**Evidence:** memory id=217445
- Heavy markdown: **bold**, ##headers, tables
- User context: Terminal-first workflow on Garuda Linux (memory id=22542)
- Impact: Most markdown won't render in CLI environment

**Example from memory id=217445:**
> "Heavy markdown (**bold**, ##headers, tables) despite system instruction to use terminal-friendly formatting"

## 3. MemPalace Citation Compliance Failure

**Evidence:** memory id=118277, 579378
- Zero mentions of "mempalace" in 21,515+ messages
- MCP server 96% failure rate (24/25) blocking citations
- Agent says "I'll remember" but never cites MemPalace as source

**Example from memory id=118277:**
> "MemPalace citation: **Not used at all.** Zero mentions of 'mempalace' in 21K+ messages"

**MCP Failure from memory id=579378:**
> "MCP mempalace: ~96% failure rate (24/25) — server unreliable"

## 4. Duplicate Responses Across Sessions

**Evidence:** memory id=217449, 122604, 573697, 25121
- "favorite color" appeared 4+ times across sessions
- DUPLIKAT-SPAM: dieselbe Memory 1.035× geschrieben
- 6,000+ duplicates identified: "Hauptsächlich sync_turn() Müll"
- Conflict detection bug creates duplicates instead of recognizing existing

**Examples:**
- memory id=122604: "6,000+ Duplikate! Hauptsächlich sync_turn() Müll"
- memory id=25121: Conflict detection flaw - _content_differs returns False for similar content
- memory id=217449: "Same responses duplicated across sessions (favorite color answer appeared 4+ times)"

## User Profile Context

**Evidence sources:**
- memory id=22542: USER.md prior memory - timezone Europe/Berlin, direct style preference
- memory id=571604: "German when user speaks German, English otherwise"
- memory id=574857: Favorite color neon purple #FF9D4EDD extracted via AFE

## Fix Priorities

1. MCP server reliability (blocking MemPalace citations)
2. Conflict detection in memory system (prevents duplicates)
3. Adaptive verbosity detection for CLI sessions
4. Plain-text formatting enforcement for CLI
5. Language adaptation documentation