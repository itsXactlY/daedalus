# podroid build pipeline — condensed reference

## hermes-pod-build.sh (legacy Nuitka orchestrator)
Stages:
- **A — Nuitka ELF**: `Containerfile.hermes-nuitka` (full `gateway/run.py`) or
  `Containerfile.hermes-slim` (only `gateway/platforms/api_server.py`).
  Cross/aarch64 via Nuitka `--onefile --standalone`. Invalid flag
  `--arch=arm64` was the original bug — Nuitka picks host arch.
- **B — Alpine rootfs** (minimal, musl): `apk add bash ca-certificates tini
  libstdc++ openssl sqlite-libs`. Produces `rootfs.tar` with
  `/opt/hermes/hermes-agent.bin` + `start.sh`.
- **C — static proot** from source (`Dockerfile.hermes-builder`, debian:bookworm
  → `make -j4`, statically linked ~936 KB) so it runs on Android bionic.
- **D — bundle** → `dist/hermes-agent-arm64.tar` (proot + hermes-agent.bin + rootfs.tar).

Output goes to `android/hermes-android/app/src/main/assets/hermes-pod/`.

## hermes-agent[termux] extra (exact, from pyproject.toml)
`hermes-agent[termux]` = telegram-bot[webhooks] + `hermes-agent[cron]` +
`[cli]` + `[pty]` + `[mcp]` + `[honcho]` + `[acp]`. Each of those pulls:
- cron → croniter; cli → simple-term-menu; pty → ptyprocess/pywinpty;
  mcp → mcp + starlette(1.0.1, CVE-2026-48710); honcho → honcho-ai; acp → agent-client-protocol.
- Core deps (all pinned ==): openai, python-dotenv, fire, httpx[socks], rich,
  tenacity, pyyaml, ruamel.yaml, requests, jinja2, pydantic, prompt_toolkit,
  croniter, Markdown, PyJWT[crypto], psutil, pathspec, fastapi, uvicorn[standard], ptyprocess.

NOT in [termux]: anthropic, exa, firecrawl, fal, edge-tts, modal, daytona,
matrix, voice (faster-whisper/onnxruntime/numpy), google, web, youtube,
dingtalk, feishu, bedrock, mistral, etc. → those are lazy-installed at runtime
via tools/lazy_deps.py, so they never break a fresh [termux] install.

## API server env vars (gateway/config.py lines 1508-1520)
Read at gateway startup; enable the OpenAI-compatible `api_server` platform:
- `API_SERVER_ENABLED` (true/1/yes)
- `API_SERVER_HOST` (use `0.0.0.0` inside proot)
- `API_SERVER_PORT` (podroid default `8088`; must match HermesGatewayClient)
- `API_SERVER_KEY` (optional bearer auth)
- `API_SERVER_CORS_ORIGINS` (default `*`, allows the Kotlin Compose UI)

The `hermes gateway` CLI command runs the gateway; with the above env set it
serves `/v1/chat/completions`, `/v1/models`, `/health`. This is the exact
replacement for the Nuitka `gateway/run.py` entry.

## Rootfs runtime libs already present (stage B)
bash, ca-certificates, tini, libstdc++, openssl, sqlite-libs. These cover the
venv's runtime needs (cryptography→openssl, session DB→sqlite-libs,
C++ .so→libstdc++). The venv is self-contained (own musl python3), so no
system python3 is required in the rootfs.
