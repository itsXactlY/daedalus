---
name: jackrabbit-wonderland
description: LAN-based Hermes control system - control your AI from any device. Encryption is the obvious part.
category: devops
version: 1.1
tags: [wonderland, lan-gateway, dlm, volatile-vault, ios-shortcuts, netcat, zero-knowledge, multi-device]
priority: high
---

# Jackrabbit Wonderland

> *The provider logs everything. But logs full of base64 blobs are just... logs.*
> *Your house search. Your trades. Your thoughts. Hidden in plain sight.*

**Hermes-Jackrabbit-wonderland-crypto-layer** — control your AI agent from ANY device on your LAN.

The encryption? That's the obvious part. Anyone with half a brain gets that.

The REAL value:

## What This Actually Is

A system that lets you **talk to your AI from your phone, your tablet, a browser, netcat, iOS Shortcuts, ANY HTTP client** — while the cloud provider sees nothing useful.

| Component | What It Does |
|-----------|-------------|
| **JackrabbitDLM** | Volatile key vault — keys in memory only, TTL-bound, auto-destroy on crash. Think Redis but single-file, zero deps, stdlib only. |
| **LAN Gateway** | HTTP + raw TCP server — control Hermes from any LAN device. Browser, curl, netcat, iOS Shortcuts. |
| **remember:: protocol** | Base64 transport that LLMs can decode. Provider sees "memory recall protocol." Nobody reviews base64 in logs. |
| **AES256-GCM** | Real encryption for local storage (Neural Memory, PULSE cache). The cherry on top. |

## The Foundation: JackrabbitDLM

[JackrabbitDLM](https://github.com/rapmd73/JackrabbitDLM) by Robert APM Darin. 1,003 lines. Single file. JSON-over-TCP.

- **Zero dependencies** — stdlib only (`socket`, `select`, `json`)
- **Language-agnostic** — any device that speaks TCP can talk to it
- **Volatile by design** — data lives in memory. Server crash = data gone. For keys, this is a *feature*
- **TTL-bound** — keys auto-destroy after expiry. No cleanup code needed
- **Ownership enforcement** — only the ID that stored a value can retrieve it
- **Custom Encoder/Decoder** — Robert left the door open. We injected AES256.

## LAN Gateway

```
Any Device (phone, laptop, tablet)
    |
    | HTTP :8080 or TCP :37374
    v
LAN Gateway
    |
    +---> JackrabbitDLM :37373 (key vault)
    |
    +---> Hermes Agent (AES256 encrypt/decrypt)
              |
              v
         Provider sees: base64 blobs
```

### Access Methods
```bash
# Browser
http://192.168.0.2:8080

# curl
curl -X POST http://192.168.0.2:8080/command -d '{"cmd":"status"}'

# netcat
echo '{"cmd":"status"}' | nc 192.168.0.2 37374
```

## remember:: Protocol

LLMs can't do AES256. But they CAN decode base64.

`remember::<base64>` = decode internally, respond in plain text.
Provider sees: persona system prompt + remember:: strings.
Looks like a memory recall protocol. Because it IS one — that also happens to hide your queries.

## Components (1,892 lines total)

| File | Lines | Purpose |
|------|-------|---------|
| remember_protocol.py | 408 | Base64 transport + AES256 storage, persona header |
| lan_gateway.py | 620 | HTTP + TCP server, session management |
| crypto_middleware.py | 283 | AES256-GCM, key rotation, chaff injection |
| crypto_plugin.py | 241 | Hermes plugin — session lifecycle hooks |
| dlm_vault.py | 340 | JackrabbitDLM client bridge |

## DLMLocker API
- Constructor: `Locker(filename, Host='', Port=37373, ID=None)` — `Host` and `Port` are CAPITAL
- Methods: `Lock()`, `Unlock()`, `Put(expire, data)`, `Get()`, `Erase()`, `Version()`, `IsLocked()`
- NOT `Store()`/`Retrieve()` — those don't exist
- Data is volatile: exists only while Lock is held. Unlock = data gone.
- `Put()` returns bytes `b'{"Status":"Done"}'`, `Get()` returns dict `{"Status":"Done","DataStore":"value"}`
- Wire format: alphabet soup byte encoder (Robert's "ZERO effort security")

## 114 Tests (4 suites)
- crypto (51): AES256-GCM, nonce uniqueness, tamper detection, rotation, memory leak
- gateway (22): HTTP API, concurrent sessions, session bomb
- dlm (18): key lifecycle, TTL, locking, identity isolation
- plugin (23): plugin lifecycle, tool encryption, neural memory

## Pitfalls
- DLM `IsLocked()` always returns `"locked"` — lock enforcement is at `Lock()` level
- DLM max payload ~5KB — silent rejection above
- ThreadingTCPServer fix needed — single-threaded TCPServer drops concurrent connections
- Key history cap at 5 — oldest evicted after rotation

## Integration
- Hermes Plugin: auto-injects on session start/end
- PULSE: searches through encrypted gateway
- Neural Memory: auto-encrypt at store, decrypt at recall
- iOS Shortcuts: HTTP commands to gateway
- Whitelisted (NOT encrypted): neural_remember, neural_recall, neural_think, neural_graph, skill_view, skills_list, read_file, search_files, browser_snapshot

## Gateway Commands

| Command | Description | Example |
|---------|-------------|---------|
| status | Gateway health | `{"cmd":"status"}` |
| shell | Run shell command | `{"cmd":"shell","args":"hostname"}` |
| hermes | Run hermes CLI | `{"cmd":"hermes","args":"chat -q Hello -m kilo-auto/free"}` |
| pulse | Run PULSE search | `{"cmd":"pulse","args":"bitcoin"}` |
| encrypt | Encrypt text | `{"cmd":"encrypt","args":"secret text"}` |
| decrypt | Decrypt text | `{"cmd":"decrypt","args":"base64blob"}` |
| chaff | Generate decoy | `{"cmd":"chaff"}` |

### hermes command requirements
The `hermes` command runs `hermes` as a shell command. If hermes is in a venv, create a wrapper:

```bash
sudo tee /usr/local/bin/hermes << 'EOF'
#!/bin/bash
source /path/to/hermes-agent/venv/bin/activate
export PYTHONPATH=/path/to/hermes-agent
python3 -m hermes_cli.main "$@"
EOF
sudo chmod +x /usr/local/bin/hermes
```

Without this wrapper, the gateway returns `{"error": "hermes not found on PATH"}`.

### Desktop -> VM testing
VM Gateway port mapping: `-netdev user,id=net0,hostfwd=tcp::9080-:8080,hostfwd=tcp::9373-:37373`

```bash
# From desktop
curl -s -X POST http://localhost:9080/command -d '{"cmd":"status"}'
curl -s --max-time 60 -X POST http://localhost:9080/command -d '{"cmd":"hermes","args":"chat -q HALLO -m kilo-auto/free"}'
```

## Crypto Middleware API Notes
- `encrypt_outbound(message)` -> returns `Tuple[str, bool]` (ciphertext, is_chaff)
- `decrypt(ciphertext_b64)` -> returns plaintext string (use this directly)
- `decrypt_inbound(response)` -> expects `ENC_MSG:` prefix format, returns `Optional[str]`
- Use `encrypt()` + `decrypt()` for direct round-trip (not `encrypt_outbound`/`decrypt_inbound`)
