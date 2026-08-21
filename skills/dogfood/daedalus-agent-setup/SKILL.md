---
name: daedalus-setup
description: Help users configure Daedalus Agent — CLI usage, setup wizard, model/provider selection, tools, skills, voice/STT/TTS, gateway, and troubleshooting. Use when someone asks to enable features, configure settings, or needs help with Daedalus itself.
version: 1.1.0
author: Daedalus Agent
tags: [setup, configuration, tools, stt, tts, voice, daedalus, cli, skills]
---

# Daedalus Agent Setup & Configuration

Use this skill when a user asks about configuring Daedalus, enabling features, setting up voice, managing tools/skills, or troubleshooting.

## Key Paths

- Config: `~/.daedalus/config.yaml`
- API keys: `~/.daedalus/.env`
- Skills: `~/.daedalus/skills/`
- Daedalus install: `~/.daedalus/daedalus/`
- Venv: `~/.daedalus/daedalus/venv/`

## CLI Overview

Daedalus is used via the `daedalus` command (or `python -m daedalus_cli.main` from the repo).

### Core commands:

```
daedalus                          Interactive chat (default)
daedalus chat -q "question"       Single query, then exit
daedalus chat -m MODEL            Chat with a specific model
daedalus -c                       Resume most recent session
daedalus -c "project name"        Resume session by name
daedalus --resume SESSION_ID      Resume by exact ID
daedalus -w                       Isolated git worktree mode
daedalus -s skill1,skill2         Preload skills for the session
daedalus --yolo                   Skip dangerous command approval
```

### Configuration & setup:

```
daedalus setup                    Interactive setup wizard (provider, API keys, model)
daedalus model                    Interactive model/provider selection
daedalus config                   View current configuration
daedalus config edit              Open config.yaml in $EDITOR
daedalus config set KEY VALUE     Set a config value directly
daedalus login                    Authenticate with a provider
daedalus logout                   Clear stored auth
daedalus doctor                   Check configuration and dependencies
```

### Tools & skills:

```
daedalus tools                    Interactive tool enable/disable per platform
daedalus skills list              List installed skills
daedalus skills search QUERY      Search the skills hub
daedalus skills install NAME      Install a skill from the hub
daedalus skills config            Enable/disable skills per platform
```

### Gateway (messaging platforms):

```
daedalus gateway run              Start the messaging gateway
daedalus gateway install          Install gateway as background service
daedalus gateway status           Check gateway status
```

### Session management:

```
daedalus sessions list            List past sessions
daedalus sessions browse          Interactive session picker
daedalus sessions rename ID TITLE Rename a session
daedalus sessions export ID       Export session as markdown
daedalus sessions prune           Clean up old sessions
```

### Other:

```
daedalus status                   Show status of all components
daedalus cron list                List cron jobs
daedalus insights                 Usage analytics
daedalus update                   Update to latest version
daedalus pairing                  Manage DM authorization codes
```

## Setup Wizard (`daedalus setup`)

The interactive setup wizard walks through:
1. **Provider selection** — OpenRouter, Anthropic, OpenAI, Google, DeepSeek, and many more
2. **API key entry** — stores securely in the env file
3. **Model selection** — picks from available models for the chosen provider
4. **Basic settings** — reasoning effort, tool preferences

Run it from terminal:
```bash
cd ~/.daedalus/daedalus
source venv/bin/activate
python -m daedalus_cli.main setup
```

To change just the model/provider later: `daedalus model`

## Skills Configuration (`daedalus skills`)

Skills are reusable instruction sets that extend what Daedalus can do.

### Managing skills:

```bash
daedalus skills list              # Show installed skills
daedalus skills search "docker"   # Search the hub
daedalus skills install NAME      # Install from hub
daedalus skills config            # Enable/disable per platform
```

### Per-platform skill control:

`daedalus skills config` opens an interactive UI where you can enable or disable specific skills for each platform (cli, telegram, discord, etc.). Disabled skills won't appear in the agent's available skills list for that platform.

### Loading skills in a session:

- CLI: `daedalus -s skill-name` or `daedalus -s skill1,skill2`
- Chat: `/skill skill-name`
- Gateway: type `/skill skill-name` in any chat

## Voice Messages (STT)

Voice messages from Telegram/Discord/WhatsApp/Slack/Signal are auto-transcribed when an STT provider is available.

### Provider priority (auto-detected):
1. **Local faster-whisper** — free, no API key, runs on CPU/GPU
2. **Groq Whisper** — free tier, needs GROQ_API_KEY
3. **OpenAI Whisper** — paid, needs VOICE_TOOLS_OPENAI_KEY

### Setup local STT (recommended):

```bash
cd ~/.daedalus/daedalus
source venv/bin/activate
pip install faster-whisper
```

Add to config.yaml under the `stt:` section:
```yaml
stt:
  enabled: true
  provider: local
  local:
    model: base  # Options: tiny, base, small, medium, large-v3
```

Model downloads automatically on first use (~150 MB for base).

### Setup Groq STT (free cloud):

1. Get free key from https://console.groq.com
2. Add GROQ_API_KEY to the env file
3. Set provider to groq in config.yaml stt section

### Verify STT:

After config changes, restart the gateway (send /restart in chat, or restart `daedalus gateway run`). Then send a voice message.

## Voice Replies (TTS)

Daedalus can reply with voice when users send voice messages.

### TTS providers (set API key in env file):

| Provider | Env var | Free? |
|----------|---------|-------|
| ElevenLabs | ELEVENLABS_API_KEY | Free tier |
| OpenAI | VOICE_TOOLS_OPENAI_KEY | Paid |
| Kokoro (local) | None needed | Free |
| Fish Audio | FISH_AUDIO_API_KEY | Free tier |

### Voice commands (in any chat):
- `/voice on` — voice reply to voice messages only
- `/voice tts` — voice reply to all messages
- `/voice off` — text only (default)

## Enabling/Disabling Tools (`daedalus tools`)

### Interactive tool config:

```bash
cd ~/.daedalus/daedalus
source venv/bin/activate
python -m daedalus_cli.main tools
```

This opens a curses UI to enable/disable toolsets per platform (cli, telegram, discord, slack, etc.).

### After changing tools:

Use `/reset` in the chat to start a fresh session with the new toolset. Tool changes do NOT take effect mid-conversation (this preserves prompt caching and avoids cost spikes).

### Common toolsets:

| Toolset | What it provides |
|---------|-----------------|
| terminal | Shell command execution |
| file | File read/write/search/patch |
| web | Web search and extraction |
| browser | Browser automation (needs Browserbase) |
| image_gen | AI image generation |
| mcp | MCP server connections |
| voice | Text-to-speech output |
| cronjob | Scheduled tasks |

## Installing Dependencies

Some tools need extra packages:

```bash
cd ~/.daedalus/daedalus && source venv/bin/activate

pip install faster-whisper    # Local STT (voice transcription)
pip install browserbase       # Browser automation
pip install mcp               # MCP server connections
```

## Config File Reference

The main config file is `~/.daedalus/config.yaml`. Key sections:

```yaml
# Model and provider
model:
  default: anthropic/claude-opus-4.6
  provider: openrouter

# Agent behavior
agent:
  max_turns: 90
  reasoning_effort: high    # xhigh, high, medium, low, minimal, none

# Voice
stt:
  enabled: true
  provider: local           # local, groq, openai
tts:
  provider: elevenlabs      # elevenlabs, openai, kokoro, fish

# Display
display:
  skin: default             # default, ares, mono, slate
  tool_progress: full       # full, compact, off
  background_process_notifications: all  # all, result, error, off
```

Edit with `daedalus config edit` or `daedalus config set KEY VALUE`.

## Gateway Commands (Messaging Platforms)

| Command | What it does |
|---------|-------------|
| /reset or /new | Fresh session (picks up new tool config) |
| /help | Show all commands |
| /model [name] | Show or change model |
| /compact | Compress conversation to save context |
| /voice [mode] | Configure voice replies |
| /reasoning [effort] | Set reasoning level |
| /sethome | Set home channel for cron/notifications |
| /restart | Restart the gateway (picks up config changes) |
| /status | Show session info |
| /retry | Retry last message |
| /undo | Remove last exchange |
| /personality [name] | Set agent personality |
| /skill [name] | Load a skill |

## Troubleshooting

### Voice messages not working
1. Check stt.enabled is true in config.yaml
2. Check a provider is available (faster-whisper installed, or API key set)
3. Restart gateway after config changes (/restart)

### Tool not available
1. Run `daedalus tools` to check if the toolset is enabled for your platform
2. Some tools need env vars — check the env file
3. Use /reset after enabling tools

### Model/provider issues
1. Run `daedalus doctor` to check configuration
2. Run `daedalus login` to re-authenticate
3. Check the env file has the right API key

### Changes not taking effect
- Gateway: /reset for tool changes, /restart for config changes
- CLI: start a new session

### Skills not showing up
1. Check `daedalus skills list` shows the skill
2. Check `daedalus skills config` has it enabled for your platform
3. Load explicitly with `/skill name` or `daedalus -s name`
