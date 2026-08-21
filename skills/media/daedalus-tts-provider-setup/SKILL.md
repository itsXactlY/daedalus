---
name: daedalus-tts-provider-setup
description: Install or debug custom TTS providers in Daedalus.
category: media
---


> Ported from `hermes-tts-provider-setup` during the 2026-08-21 Daedalus skills alignment. Pre-rename history lives in git and `~/.daedalus/skills-archive/2026-08-21-hermes-legacy/`.
# Daedalus TTS Provider Setup

How to wire a new text-to-speech backend into Daedalus and prove it works. Covers the `type: command` provider surface — the right answer for any HTTP/OpenAI-compatible TTS API (OpenRouter, DeepInfra, SiliconFlow, self-hosted).

## When to use this skill

- User asks to install/set a specific TTS model or provider ("install fish-audio/s2.1-pro-free:free as TTS", "make X my voice")
- User wants to change `tts.provider` in config.yaml
- A text_to_speech call fails or returns an HTML/JSON error page instead of audio

## TTS extension surfaces (resolution order)

1. **Built-ins** (always win, cannot be shadowed): `edge, openai, elevenlabs, minimax, xai, mistral, gemini, neutts, kittentts, piper, deepinfra`
2. **Command-type providers** under `tts.providers.<name>` with `type: command` — any shell pipeline; the workhorse for HTTP TTS APIs
3. **Plugin-registered providers** (`~/.daedalus/plugins/tts/<name>/`) — only needed for SDK/streaming/OAuth backends

Any `tts.provider` value NOT in the built-in set resolves to `tts.providers.<name>`.

## Procedure (HTTP/OpenAI-compatible TTS)

1. **Smoke-test the API manually FIRST** (before touching config):
   ```bash
   export KEY=$(grep -E '^OPENROUTER_API_KEY=' ~/.daedalus/.env | head -1 | cut -d= -f2- | tr -d '"'"'"' ')
   printf 'Test text' > /tmp/t.txt
   jq -n --rawfile t /tmp/t.txt '{model: "vendor/model:free", input: $t, response_format: "mp3"}' \
     | curl -sS --max-time 90 -H "Authorization: Bearer ${KEY}" -H "Content-Type: application/json" \
       -d @- https://openrouter.ai/api/v1/audio/speech -o /tmp/t.mp3 -w "HTTP %{http_code}\n"
   ffprobe -v error -show_entries format=format_name,duration /tmp/t.mp3
   ```
   Success = HTTP 200 + `format_name=mp3` (or wav) + sane duration. Anything else → fix before wiring config.

2. **Write the provider config via `daedalus config set`** (see pitfalls — patch/write_file refuse config.yaml):
   ```bash
   daedalus config set tts.provider <name>
   daedalus config set tts.providers.<name>.type command
   daedalus config set tts.providers.<name>.command '<shell pipeline with placeholders>'
   daedalus config set tts.providers.<name>.output_format mp3
   ```
   Nested-key warnings ("not a recognized config key") are noise — values save and load fine.

3. **Command placeholders** (Daedalus writes text to a temp file, runs the command, reads audio from `{output_path}`):
   `{input_path}` (text file, alias `{text_path}`), `{output_path}`, `{format}`, `{voice}`, `{model}`, `{speed}`. All shell-quoted by Daedalus. Default command timeout 120s, max text 5000 chars.

4. **Prove it**: call the `text_to_speech` tool; then verify the output file with `file` + `ffprobe` — must be real audio (MPEG ADTS etc.), NOT an HTML error page. CLI output lands in `~/.daedalus/cache/audio/tts_*.mp3`.

5. **Save the recipe to mazemaker automatically** (fact:<topic>) — never ask permission.

## Pitfalls (all hit in the field, 2026-08-01)

- **config.yaml is write-protected for agent tools.** `patch`/`write_file` refuse it ("security-sensitive configuration"). Only `daedalus config` CLI (or the user) edits it. Don't waste a call trying.
- **OpenRouter TTS endpoint is `/api/v1/audio/speech`, NOT `/api/v1/audio/tts`.** The latter returns 404 with a 133KB HTML SPA page. `/audio/speech` is OpenAI-compatible: `{model, input, voice?, response_format, speed?}`.
- **Default response has NO container** — omitting `response_format: "mp3"` returns raw bytes (`file` says "data"). Always send it.
- **Keys live in `~/.daedalus/.env`, not in the agent's shell env.** A bare `curl -H "Authorization: Bearer ${OPENROUTER_API_KEY}"` sends an empty header → 401 "Missing Authentication header". Export from .env first (see step 1). Daedalus itself loads dotenv at startup, so command providers inherit the key via `${OPENROUTER_API_KEY}` — reference the var in the command, NEVER hardcode the key in config.yaml.
- **Model may be absent from `/api/v1/models` yet work on the endpoint.** Fresh releases (days old) often lag the public model list. The live synthesis call is the source of truth, not the list. Conversely, a model that 404s on synthesis is not yet served anywhere — say so honestly.
- **Name collision:** don't name a provider after a built-in (`edge`, `openai`, ...) — built-ins always win, config silently ignored.
- **jq + curl pipeline is the reliable JSON builder** on this machine (jq present at /usr/bin/jq). Avoid python -c for the request body in the command string — quoting hell in YAML.
- **Auth debug order:** 401 "Missing Authentication header" = key not reaching server (env/expansion issue). 404 JSON with error field = endpoint/model problem. 404 HTML = wrong path.

## Verification checklist

- `daedalus config get tts.provider` returns the new name
- `daedalus config get tts.providers.<name>.type` returns `command`
- text_to_speech tool result: `"provider": "<name>"`, `"success": true`
- Output file: `file` says MPEG ADTS / WAV; `ffprobe` shows format + duration > 0
- The user can play it (mpv path)

## References

- `references/openrouter-fish-s2.1-free.md` — the full working install recipe (exact config YAML, endpoint quirks, proof artifacts) for fish-audio/s2.1-pro-free:free via OpenRouter, 2026-08-01.
