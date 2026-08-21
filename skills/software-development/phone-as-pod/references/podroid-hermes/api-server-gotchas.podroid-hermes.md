# api_server gotchas — native podroid hermes-agent

Code-level detail behind the pitfalls in SKILL.md. All line numbers are for
hermes-agent v0.15.1 (pyproject `requires-python ">=3.11,<3.14"`).

## 1. api_server is aiohttp, not FastAPI/uvicorn
`gateway/platforms/api_server.py` imports `from aiohttp import web` and binds
an `aiohttp.web` app. Default host/port are `127.0.0.1:8642` (overridden by
`API_SERVER_HOST` / `API_SERVER_PORT` env from gateway/config.py:1511-1512).
If `aiohttp` is absent, `AIOHTTP_AVAILABLE = False` and the adapter is a no-op.
**`aiohttp` is NOT in the `[termux]` extra** — it lives in `[messaging]`,
`[slack]`, `[homeassistant]`, `[sms]`, `[matrix]` only (pyproject:114,116,157,158).
Symptom: `hermes gateway run` prints the banner, then the log shows
`WARNING gateway.run: ✗ api_server failed to connect` and
`Gateway started with no connected platforms`. Fix: `pip install /build[termux] aiohttp==3.13.3`.

## 2. API_SERVER_KEY is mandatory for EVERY bind
`gateway/platforms/api_server.py:4158`:
```python
if not self._api_key:
    logger.error("[%s] Refusing to start: API_SERVER_KEY is required for the API server, "
                 "including loopback-only binds on %s.", self.name, self._host)
    return False
```
There is NO env bypass. The error text says "including loopback-only binds on
<host>" — confirmed empirically: even `API_SERVER_HOST=127.0.0.1` refuses to
start with an empty key. A placeholder check (`has_usable_secret(..., min_length=8)`)
only fires for `is_network_accessible(self._host)` (line 4168), i.e. non-loopback.
Fix: set a non-empty `API_SERVER_KEY` in start.sh, e.g. `openssl rand -hex 32`.

## 3. `hermes gateway` ≠ `hermes gateway run`
`hermes --help` lists `gateway` with subcommands
`{run,start,stop,restart,status,install,uninstall,list,setup,migrate-legacy}`.
`hermes gateway` with NO subcommand prints only the banner
("⚕ Hermes Gateway Starting... / Messaging platforms + cron scheduler") and
exits the loop — the api_server never binds. The foreground runner is
`hermes gateway run` (help note: "recommended for WSL, Docker, Termux").

## 4. Kotlin HermesGatewayClient mismatch (old Nuitka ELF API)
File: `android/hermes-android/.../pod/HermesGatewayClient.kt`. The new
api_server's routes (api_server.py:4104-4107, 4135+) are:
`/health`, `/health/detailed`, `/v1/health`, `/v1/models`, `/v1/chat/completions`,
`/v1/responses`, `/api/sessions`, ...  — there is NO `/api/health` and NO
`/api/status`.

The client (as written) does THREE wrong things vs the new server:
- `healthCheck()` → `GET $baseUrl/api/health`  (404 → app never reaches Ready;
  fix: `/health`)
- `status()` → `GET $baseUrl/api/status`  (404; fix: `/health/detailed`)
- `sendMessageStream()` → `POST $baseUrl/v1/chat/completions` with NO
  `Authorization` header (server returns 401; fix: `.header("Authorization",
  "Bearer $API_KEY")`).

Minimal patch (applied this session):
```kotlin
// companion object:
private const val API_KEY = "070e..." // EQUAL start.sh API_SERVER_KEY

// healthCheck:
Request.Builder().url("$baseUrl/health").get()
    .header("Authorization", "Bearer $API_KEY").build()

// status:
Request.Builder().url("$baseUrl/health/detailed").get()
    .header("Authorization", "Bearer $API_KEY").build()

// sendMessageStream:
.header("Accept", "text/event-stream")
.header("Authorization", "Bearer $API_KEY")
```
The `supervisor` already spawns `hermes-agent.bin --gateway --host 0.0.0.0
--port 8088`; the static ELF wrapper ignores those args and start.sh hardcodes
`API_SERVER_HOST=0.0.0.0 PORT=8088`, so the pod binds 0.0.0.0:8088 inside
proot, which the app reaches on host loopback 127.0.0.1:8088.

## 5. Verify recipe (host x86_64 + qemu-aarch64 binfmt)
```bash
podman run --rm --platform=linux/arm64 \
  -v "$REPO/android/hermes-android/app/src/main/assets/hermes-pod/rootfs.tar:/rootfs.tar:ro" \
  arm64v8/alpine:3.23 sh -c '
    mkdir -p /r; tar -xf /rootfs.tar -C /r
    chroot /r /opt/hermes/hermes-agent.bin --gateway --host=0.0.0.0 --port=8088 >/r/tmp/gw.log 2>&1 &
    GW=$!
    for i in $(seq 1 60); do wget -qO- http://127.0.0.1:8088/health >/dev/null 2>&1 && break; sleep 1; done
    echo "health:"; wget -qO- http://127.0.0.1:8088/health
    echo "models:"; wget -qO- http://127.0.0.1:8088/v1/models | head -c 400
    kill $GW; tail -n 30 /r/tmp/gw.log'
```
Expect: `/health` → 200 `{"status":"ok",...}`, `/v1/models` → 200, and the
log shows the api_server listening (no "failed to connect"). Without a key the
server never binds → connection refused.
