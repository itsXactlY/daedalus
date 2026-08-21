# Hermes memory.provider: mazemaker — RESOLVED 2026-05-29

**This gap has been resolved.** See `references/hermes-mazemaker-memory-provider.md`
for the implementation.

## Historical symptom

Auto-turn memories (`auto:turn:<session>:<timestamp>`) were not being saved
to mazemaker from Hermes sessions. Only manually-curated `mazemaker_remember`
calls (made by the agent after substantive turns) created mazemaker entries.

## Historical root cause

The config key `memory.provider: mazemaker` in `~/.hermes/config.yaml` mapped to nothing.
No `plugins/memory/mazemaker/` directory existed (neither bundled nor user-installed).
`find_provider_dir("mazemaker")` returned `None`. The load silently failed and
the memory system fell back to the built-in MemoryManager only.

## Fix

Created `client/hermes-plugins/mazemaker-memory-provider/` in the backend repo.
Committed as 9721d64. The plugin is shipped via install.sh (copies to
`~/.hermes/plugins/mazemaker/`) and bundled in source.tar.gz.
