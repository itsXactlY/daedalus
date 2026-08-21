# fish-audio/s2.1-pro-free:free via OpenRouter — working recipe (2026-08-01)

Full install as Daedalus TTS, verified end-to-end. Model: Fish Audio S2.1 Pro Free
(released 2026-07-29), free tier, no production latency/availability guarantees.

## Facts established that session

- OpenRouter `/api/v1/models` (336 models) did NOT list it — yet `/api/v1/audio/speech`
  accepts it and returns real MP3. Model-list lag, not a serving error.
- `/api/v1/audio/tts` → 404 with 133,906-byte HTML SPA page (wrong path on this instance).
- Without `response_format: "mp3"` the endpoint returns raw PCM-ish bytes (`file` = "data").
- `OPENROUTER_API_KEY` (73 chars) lives in `~/.daedalus/.env`; the agent shell does NOT
  have it → empty Authorization header → 401 `{"error":{"message":"Missing Authentication header","code":401}}`.
  Daedalus loads dotenv at startup, so `type: command` providers DO inherit it.

## The working command (as configured)

Single-line shell pipeline; `{input_path}` / `{output_path}` are Daedalus placeholders
(shell-quoted). jq builds the body from the text file; `&& test -s` guards empty output:

```
jq -n --rawfile t {input_path} '{model: "fish-audio/s2.1-pro-free:free", input: $t, response_format: "mp3"}' | curl -sS --max-time 110 -H "Authorization: Bearer ${OPENROUTER_API_KEY}" -H "Content-Type: application/json" -d @- https://openrouter.ai/api/v1/audio/speech -o {output_path} && test -s {output_path}
```

## Resulting config (in ~/.daedalus/config.yaml)

```yaml
tts:
  provider: openrouter-fish
  providers:
    openrouter-fish:
      type: command
      command: jq -n --rawfile t {input_path} '{model: "fish-audio/s2.1-pro-free:free", input: $t, response_format: "mp3"}' | curl -sS --max-time 110 -H "Authorization: Bearer ${OPENROUTER_API_KEY}" -H "Content-Type: application/json" -d @- https://openrouter.ai/api/v1/audio/speech -o {output_path} && test -s {output_path}
      output_format: mp3
```

Written via `daedalus config set` (4 calls). `daedalus config set tts.providers.openrouter-fish.type`
warns "not a recognized config key" — harmless, values persist and load.

## Proof artifacts

- Manual smoke: HTTP 200, MPEG ADTS layer III, 128 kbps, 44.1 kHz mono, 3.68s
- Tool proof: text_to_speech → `{"success": true, "provider": "openrouter-fish"}`,
  file `/home/alca/.daedalus/cache/audio/tts_20260801_064629_699170.mp3`
  (7.37s, ffprobe format_name=mp3)
- Played back by the operator via mpv — accepted.

## Manual curl equivalent (for debugging later)

```bash
export OPENROUTER_API_KEY=$(grep -E '^OPENROUTER_API_KEY=' ~/.daedalus/.env | head -1 | cut -d= -f2- | tr -d '"'"'"' ')
jq -n --rawfile t /tmp/t.txt '{model: "fish-audio/s2.1-pro-free:free", input: $t, response_format: "mp3"}' \
  | curl -sS --max-time 90 -H "Authorization: Bearer ${OPENROUTER_API_KEY}" -H "Content-Type: application/json" \
    -d @- https://openrouter.ai/api/v1/audio/speech -o /tmp/t.mp3 -w "HTTP %{http_code}\n"
ffprobe -v error -show_entries format=format_name,duration /tmp/t.mp3
```

## Mazemaker

Recipe saved as fact:daedalus-tts-openrouter-fish-s2.1-pro-free (mazemaker id 1076168).
