---
name: jrwl-messenger-maintenance
description: Maintenance, debugging, and security hardening workflow for JRWL Messenger (E2E encrypted messenger with Signal-grade crypto)
triggers:
  - jrwl messenger
  - jrwl-messenger
  - messenger debug
  - crypto audit
  - signal protocol
  - x3dh
  - double ratchet
  - e2e encryption review
---

# JRWL Messenger Maintenance & Debugging

## Deployment & Netzwerk (verified 2026-08-07)
- Production läuft als rootless Podman-Pod (`~/projects/jrwl-messenger/quadlet/`): `iris.pod` + `iris-gateway.container` (Nuitka-Binary `iris-messenger.bin`) + `iris-dlm.container` (JackrabbitDLM-Bus, pod-intern 127.0.0.1:37373) + `iris-proxy.container` (Caddy).
- **EINZIGER öffentlicher Ingress: 80 + 443 (Caddy, TLS-Termination).** Der Gateway bindet pod-intern an 127.0.0.1:9091; der historische `PublishPort=9091:9091` wurde BEWUSST entfernt ("collapses the public attack surface to one port (443)"). Gateway-Debug: `podman exec -it iris-gateway /usr/local/bin/iris-messenger --api-status`.
- Domain: `iris.mazemaker.online`. Firewall-Regel (UFW): 80/tcp + 443/tcp offen (Router forwardet); alles andere default-deny.
- AUDIT-Datei: `docs/AUDIT_iris_chat_federation_2026-07-17.md` — P2-1: `/api/federation/relay-circuit` vor öffentlicher Freigabe ratelimitieren/auth-en (open-relay-Risiko, aktuell nur mit pinned keys hinter Caddy).
- `iris-messenger.service` (Projekt-Root) ist die ALT-Einzelprozess-Unit (--port 9091) — NICHT der Pod-Pfad; nicht verwechseln.

## Project Structure
- `~/projects/jrwl-messenger/`
- `crypto.py` — Signal-grade crypto (X3DH, Double Ratchet, ECDSA, AES-GCM)
- `gateway.py` — Main server (~2800 lines, contains inline copies of all classes)
- `config.py` — Configuration loader
- `identity_store.py` — Standalone module (unused in production, gateway.py has inline copy)
- `message_relay.py` — Standalone module (unused in production)

## CRITICAL: gateway.py Contains Inline Copies
gateway.py has inline copies of IdentityStore, ContactManager, AuthManager, GroupStore, MessageRelay, DLMFederation. When fixing bugs, you MUST fix the gateway.py inline copies — the standalone modules (identity_store.py, message_relay.py) are dead code.

## CRITICAL: Don't git checkout gateway.py
All changes are in a single file. `git checkout gateway.py` loses everything. Always use targeted patches.

## Crypto Architecture Notes

### DoubleRatchet DH Ratchet Bug (FIXED)
When `their_ratchet_pub_der` is None (Alice as initiator hasn't received from Bob yet), the decrypt path must still do the DH ratchet step on first reply. The condition `if self.their_ratchet_pub_der is not None and self.their_ratchet_pub_der != their_pub_der:` is WRONG — it skips the ratchet when None. Use `if self.their_ratchet_pub_der != their_pub_der:` instead.

### AES-GCM Nonce
Standard is 12 bytes (96 bits), NOT 16. All encrypt/decrypt paths must be consistent. Changing nonce size is a BREAKING CHANGE for existing ciphertexts.

### Skipped Message Keys
Must be stored for out-of-order decryption. Use `Dict[Tuple[str, int], bytes]` keyed by (dh_pub_b64, msg_num). Serialize as `"{dh_b64}:{msg_num}"` compound key — base64 never contains `:`, so `rsplit(':', 1)` is safe.

### ECDSA with pycryptodome
Use `Crypto.Signature.DSS.new(key, 'fips-186-3')` for deterministic ECDSA on P-256. HMAC-based "signatures" are NOT verifiable without the private key.

## Thread Safety Patterns

### MessageRelay
Needs `threading.Lock()` on: `send()`, `queue_offline()`, `drain_offline()`, `poll()`, `ack()`, `update_receipt()`. Critical pattern:
```python
with self._lock:
    clients = [c for c in self.ws_map.values() if c.authenticated]  # snapshot
for client in clients:  # iterate OUTSIDE lock
    asyncio.run_coroutine_threadsafe(client.ws.send(payload), gateway.loop)
```

### IdentityStore, ContactManager, AuthManager
All need locks. IdentityStore: lock in `create()`, `get()`, `list_all()`. ContactManager: lock on `_secret_cache` in `add_contact()` and `get_shared_secret()`. AuthManager: lock on all pending_* dicts.

### consume_prekey Race
`load → pop → save` is TOCTOU. Wrap with `threading.Lock()` at module level.

## WS Auth (Challenge-Response)
1. Client sends `auth_request` with `identity_id`
2. Server generates 32-byte nonce via `secrets.token_bytes(32)`, stores with 60s TTL
3. Client signs nonce with identity private key (ECDSA)
4. Client sends `auth_response` with signature
5. Server verifies against stored identity public key
6. Legacy `auth` type kept for backward compat (logs deprecation warning)

## X3DH Pure Relay (E2E)
Server relays ephemeral key data but does NOT compute shared secret.
- `/api/x3dh/bundle` — returns PUBLIC keys only
- `/api/x3dh/exchange` — stores pending exchange (initiator's ephemeral key) for responder
- `/api/x3dh/pending` — responder retrieves pending exchanges on connect
- Safety number computed from public keys only (safe for server)

## DLM Offline Recovery
Offline messages stored in DLM at `offline-{recipient_id}-{msg_id}`. Index stored at `offline-idx-{recipient_id}` as JSON list of msg_ids. On `drain_offline()`, if in-memory queue is empty, read index and fetch each message from DLM.

## Testing
- `python3 crypto.py` — runs 45 self-tests
- `python3 -c "import py_compile; py_compile.compile('gateway.py', doraise=True)"` — syntax check
- Integration tests (e2e_test.py, stress_test.py, etc.) require a running gateway

## Known Issues (2026-08-12)
- Packaged Nuitka binary `iris-messenger.bin` FAILS with `ImportError: cannot import name 'KademliaDHTDiscovery'` from `dht_discovery` → **DHT federation is broken in the compiled binary** (source tree may import fine). Always smoke-test the packaged bin before a release, not just `python3 gateway.py`.
- Read-only audit without starting the server: `iris-messenger --audit-ratchet-state` (prints ratchet table + key state, exits). Use this before touching the pod — don't start stray gateways just to inspect state.

## Common Pitfalls
1. Fixing identity_store.py instead of gateway.py inline copy
2. Using 16-byte AES-GCM nonces (standard is 12)
3. Hex string `<=` comparison for pagination (use timestamps)
4. Holding locks during I/O (snapshot first, then iterate)
5. `except Exception: pass` in DLM operations (add debug logging)
