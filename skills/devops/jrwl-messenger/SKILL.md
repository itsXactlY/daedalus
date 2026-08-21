---
name: jrwl-messenger
description: Censorship-resistant E2E encrypted messenger built on JackrabbitDLM with Threema-style IDs
category: devops
---

# JRWL Messenger — Skill Reference

**Project:** End-to-end encrypted messenger with XID identity system
**Path:** ~/projects/jrwl-messenger/
**Status:** v0.9 COMPLETE — Production-ready, debug mode, comprehensive README
**Last Updated:** 2026-04-21
**README:** 684 lines — poetic intro, full API reference, architecture, security, deployment

## Quick Commands

```bash
cd ~/projects/jrwl-messenger
python3 gateway.py --port 9091   # Start gateway (NEVER foreground — use background=true)
python3 e2e_test.py              # Run E2E test suite
python3 benchmark.py             # Performance benchmarks
python3 fix_permissions.py       # Repair data directory permissions
make run                         # Via Makefile
docker-compose up                # Containerized

# Kill before restart
fuser -k 9091/tcp 9092/tcp 2>/dev/null; sleep 1
```

## Architecture

```
Browser (WebUI) ←→ Gateway (HTTP:9091 + WS:9092) ←→ DLM (37373)
                      ↓
               ECDH P-256 + AES256-GCM
```

- **crypto.py** (899 lines) — ECDH P-256, AES256-GCM, HKDF, X3DH, Double Ratchet, Safety Numbers
- **gateway.py** (2518 lines) — HTTP+WS server, routing, rate limiting, security, federation
- **message_relay.py** (613 lines) — In-memory relay, DLM federation, offline queue
- **identity_store.py** (251 lines) — XID identity persistence, key management
- **config.py** (111 lines) — JSON config + env var overrides
- **logging_setup.py** (54 lines) — Structured JSON logging
- **ui.html** (2209 lines) — Single-page WebUI with all features
- **e2e_test.py** (212 lines) — Full E2E test suite (8 tests, all passing)
- **benchmark.py** (81 lines) — Performance testing (212k msg/sec, 561k ack/sec)
- **fix_permissions.py** (54 lines) — Data directory permission repair

## Features (v0.8)

- 8-char hex IDs (Threema-style anonymous identity)
- E2E encryption (ECDH P-256 + AES-256-GCM)
- X3DH key agreement + Double Ratchet forward secrecy
- Safety Numbers (out-of-band contact verification)
- WebSocket real-time delivery with typing indicators
- Delivery receipts: ✓ sent, ✓✓ delivered, ✓✓ (green) read
- Auto-read receipts (sent automatically when chat is open)
- Offline store-and-forward queuing
- Multi-gateway DLM federation
- File sharing (base64, max 1MB)
- Group chats
- Message search
- Contact search
- Theme toggle (dark/light)
- QR code pairing
- PWA manifest
- Sound notification on new message (Web Audio API)
- Offline indicator banner when WS disconnects
- Keyboard shortcuts: Enter to send, Escape to close chat/modals
- Export chat history as .txt file
- XSS pattern detection, rate limiting, security headers

## API Endpoints

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/api/identity/create` | `{name?}` | `{id, display_name, fingerprint, public_key}` |
| POST | `/api/pairing/create` | `{identity_id}` | `{pairing_token, expires_in}` |
| POST | `/api/pairing/accept` | `{identity_id, pairing_token}` | `{status:'paired', auth_codes, contact_id}` |
| POST | `/api/auth/verify` | `{identity_id, auth_code}` | `{status:'verified', contact_id}` |
| POST | `/api/message/send` | `{from, to, message}` | `{status:'sent', message_id}` |
| POST | `/api/message/send-file` | `{from, to, file_name, file_type, file_data}` | `{status:'sent', message_id}` |
| POST | `/api/chat/history` | `{identity_id, contact_id}` | `{messages:[{id, text, sent, timestamp, receipt}]}` |
| POST | `/api/chat/search` | `{identity_id, contact_id?, query}` | `{results:[...]}` |
| POST | `/api/group/create` | `{name, identity_id, members}` | `{group}` |
| POST | `/api/group/send` | `{from, group_id, message}` | `{status:'sent'}` |
| GET | `/api/groups/{id}` | — | `{groups:[...]}` |
| GET | `/api/status` | — | `{dlm_connected, identities, ws_clients}` |
| WS | `ws://host:9092/ws` | First: `{identity_id}` | `{type:'message', from, text, timestamp}` |

## WebSocket Protocol

1. Connect to `ws://host:9092/ws`
2. First message: `{"identity_id": "xxx"}`
3. Send message: `{type:"message", from, to, text}`
4. Receive message: `{type:"message", from, text, timestamp, id}`
5. Typing: `{type:"typing", from/to}`
6. Receipt: `{type:"receipt", message_id, status:"delivered"|"read", from}`
7. Presence: `{type:"presence", status:"online"|"offline"}`

## Test Results (v0.8)

- E2E Tests: 8/8 PASS
- Benchmark: 212k msg/sec send, 561k ack/sec
- Import checks: gateway OK, crypto OK
- Total Python: ~5000 lines across 9 files
- Total UI: 2209 lines (single HTML file)

## Git History

```
9b31c60 docs: comprehensive README — 684 lines, API reference, architecture, security, deployment
653988c v0.9: debug/verbose mode — --debug flag, 30+ debug points, layer/timing/payload_hash/request_id
cae6a60 v0.9: file sharing fix, read receipts, sound, offline, shortcuts, export
1a2c886 v0.8 polish: fix deprecations, typos, hardcoded paths, config drift, README update
f15a4bf v0.8: groups, PWA manifest, theme toggle, test suites
d04bd42 v0.7 Final: production hardening, DevOps, security audit, benchmarks
```

## DevOps Assets

- **Dockerfile** + **docker-compose.yml** — Container deployment
- **Makefile** — Build/run/test/dev targets
- **jrwl-messenger.service** — systemd unit
- **SECURITY_AUDIT.md** — 300-line security review
- **config.json** — Runtime configuration

## Pitfalls

1. **NEVER run gateway in foreground** — `python3 gateway.py` blocks forever. Use `background=true` + `timeout` + `watch_patterns`.
2. **API params are `from`, `to`, `message`** — NOT `sender_id`, `recipient_id`, `text`.
3. **Pairing endpoint is `/api/pairing/create`** — NOT `/api/pair/initiate`.
4. **Auth is `/api/auth/verify`** — NOT `/api/pair/verify`.
5. **DLM max payload ~5KB** — oversized values silently rejected.
6. **`DLMLocker.IsLocked()` always returns `"locked"`** — lock enforcement at `Lock()` level.
7. **Port conflicts** — Gateway needs BOTH 9091 (HTTP) and 9092 (WS). Kill with `fuser -k` before restart.
8. **neural_recall FIRST** — Before any gateway work, check what's known about API format.
9. **Sent messages stored under `_sent_{sender}_{recipient}`** — for bidirectional chat history.
10. **Federation loop** — `threading.Event.wait()` for instant SIGINT/SIGTERM shutdown.
11. **File messages stored as encrypted JSON** — `{type:"file", file_name, file_type, file_data}`.
12. **Read receipts** — UI auto-sends `status:'read'` when chat is open or messages load.

## Crew Orchestration (How This Was Built)

**12 sequential crew agents** built this while the architect observed.

### RULE: You are the ARCHITECT. Crew agents do the work.

1. `neural_recall` BEFORE spawning — check what's known
2. Spawn ONE focused agent — not 3 parallel (shared rate limits on same provider)
3. Observe — don't take over (user gets VERY frustrated if you do)
4. `neural_remember` AFTER each agent — store findings (NOTE: neural_remay be broken — see pitfalls)
5. Spawn next agent based on what's still missing
6. On 429 rate limit: wait 30s, retry. NEVER give up.

### Scope: max_iterations=40-60, single task per agent, sequential.

### What worked:
- Focused audits (security, reliability, hardening) — each agent found real gaps
- Incremental commits between agents — easy to roll back if broken
- E2E test after each agent — caught regressions immediately

### What didn't work:
- 3 parallel agents — all share rate limits, all hit 429 at same time
- 100 max_iterations — too long, agents get lost in rabbit holes
- Agent doing the architect's job — user directive violated, frustration

## Neural Memory Pitfall (Critical, 2026-04-21)

**`neural_remay be BROKEN** — always returns the same ID (1256 = "peer:alca") instead of creating new memories. 

- The `NeuralMemory` client works correctly when called directly (returns real IDs)
- The tool routing through `MemoryManager.handle_tool_call()` appears to be broken
- NULL embedding entries in the DB crash `get_all()` on initialization
- **Workaround**: Delete NULL embedding rows: `sqlite3 ~/.mazemaker/data/memory.db "DELETE FROM memories WHERE embedding IS NULL;"`
- **Workaround**: Call the `NeuralMemory` client directly via `execute_code` instead of using the `neural_remember` tool
- Embedding dimension: existing DB has 1024-dim (FastEmbed), new client uses 384-dim (all-MiniLM-L6-v2) — mismatch causes issues

## Debug/Verbose Mode

Activate: `python3 gateway.py --debug` or `DEBUG=true` env or `"debug": true` in config.json.

When active, logs EVERYTHING with structured JSON at DEBUG level:
- **HTTP**: Full request/response headers + body + timing_ms
- **WS**: Connect/disconnect + all messages + ping/pong
- **DLM**: Lock/Get/Put + payload size + timing
- **MSG**: Encrypt/decrypt + send/poll + offline queue operations
- **ID**: Identity create + pairing flow + auth codes
- **FED**: Peer scan + relay + registration

Log format includes: `layer`, `request_id`, `timing_ms`, `payload_hash` (SHA256[:8] — never log full encrypted payloads).

Zero-cost when disabled: every debug call guarded by `if DEBUG_ENABLED:`.

## Crew Improvement History

- **v0.1**: Core messenger (ECDH+AES256-GCM, DLM relay, WebUI)
- **v0.2**: WebSocket real-time, connection status, typing indicator, QR pairing
- **v0.3**: Structured logging, config support, delivery receipts
- **v0.4**: Module extraction (config.py, logging_setup.py, message_relay.py)
- **v0.5**: README, .gitignore, requirements.txt, git, 8 error handling fixes
- **v0.6**: systemd, Docker, Makefile, env var config
- **v0.7**: Security audit (CORS, file perms, memory bounds), benchmark (212k msg/sec)
- **v0.8**: Groups, theme toggle, message search, file sharing fix, read receipts, sound notification, offline indicator, keyboard shortcuts, export chat
- **v0.9**: Debug/verbose mode (--debug flag, 30+ debug points, layer/timing/payload_hash/request_id)
