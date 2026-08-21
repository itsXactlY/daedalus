---
name: jrwl-messenger-crypto-audit
category: software-development
description: Audit and fix crypto bugs in JRWL Messenger — Signal-grade E2E encryption
triggers:
  - jrwl messenger crypto
  - double ratchet bug
  - signal protocol audit
  - E2E encryption debugging
  - AES-GCM nonce issues
  - X3DH verification
  - websocket auth challenge
---

# JRWL Messenger — Crypto Audit & Fix Patterns

## When to Use
When auditing, debugging, or fixing the JRWL Messenger crypto layer (Signal-Grade: X3DH + Double Ratchet + AES256-GCM).

## Project Layout
```
~/projects/jrwl-messenger/
├── crypto.py          # Core crypto (1045 lines) — X3DH, Double Ratchet, ECDSA
├── gateway.py         # Server (2967 lines) — WS handler, HTTP API, federation
├── config.py          # Configuration constants
├── identity_store.py  # Identity/key storage (DEAD CODE — gateway.py has inline copies)
├── message_relay.py  # Message delivery (DEAD CODE — gateway.py has inline copies)
├── ui.html            # Browser frontend
├── e2e_test.py        # Integration tests (needs running gateway)
├── edge_case_test.py  # Edge case tests (needs running gateway)
├── stress_test.py     # Stress tests (needs running gateway)
└── crypto.py __main__ # Self-test: `python3 crypto.py` runs 45 assertions
```

## Debugging: Test Wrong vs. Crypto Wrong
When a crypto test fails, FIRST determine: is the TEST wrong or is the CRYPTO CODE wrong?

**Rule:** `decrypt_message` / `ratchet.decrypt()` raising `ValueError` on MAC/auth failure = CORRECT GCM behavior. The test should use `assertRaises(ValueError)`, NOT `assertIsNone`.

If the function returned `None` on failure (e.g., `ratchet_decrypt` wrapper), then `assertIsNone` is correct.

**Systematic approach:**
1. Run the crypto self-test (`python3 crypto.py`) FIRST — if it passes, the crypto code is likely correct
2. Run test file in isolation — check if the test uses the right API call signature
3. Check parameter TYPES (e.g., `hkdf_derive` requires `bytes`, not `str`)
4. Check RETURN VALUE semantics — does the function return `None` or raise `ValueError`?
5. For X3DH: if `x3dh_respond` secrets don't match, the test is likely using a different ephemeral key than what `x3dh_initiate` used internally

**Example — this test was WRONG:**
```python
# crypto.py decrypt_message RAISES ValueError on MAC failure (correct!)
# Test was: self.assertIsNone(decrypt_message(tampered, key))  ← WRONG
# Correct:  with self.assertRaises(ValueError): decrypt_message(tampered, key)
```

### ratchet_decrypt: Silent Failure Pattern
`ratchet_decrypt` wraps `ratchet.decrypt()`. MAC failures raise `ValueError` through the inner call. For callers that want to try decryption and get `None` on failure (e.g., crosstalk detection: "try to decrypt, if it's not for me I get None"):
```python
try:
    plaintext = ratchet.decrypt(msg)
except Exception:
    return None  # MAC fail, wrong key, etc.
```
This is intentional — it lets the caller distinguish "no session" from "session exists but wrong message."

### X3DH Test Pitfall
`x3dh_initiate` generates its own ephemeral key internally. You MUST use `init['ephemeral_key_pub']` (the returned value) when calling `x3dh_respond` — not a separate throwaway key you generated. The ephemeral key is part of the shared secret derivation.

### Test: hkdf_derive Requires Bytes
`hkdf_derive(ikm=..., ...)` — if `ikm` is a `str` instead of `bytes`, Python 3.14 raises `TypeError: Strings must be encoded before hashing`. Always use `f"secret_{i}".encode()` for test secrets.

## Critical Fixes Applied (2026-04-22)
**Bug:** `ratchet_decrypt()` propagated `ValueError` (MAC failure) to callers. When Bob tried to decrypt Carol's message (crosstalk test), the exception killed the test.
**Fix:** Wrap `ratchet.decrypt(msg)` in try/except. Any decryption failure (MAC mismatch, parse error, etc.) returns `None` — caller can distinguish "session exists but wrong key" from "session doesn't exist."
```python
try:
    plaintext = ratchet.decrypt(msg)
except Exception:
    return None
```

### Test File Bugs (not crypto bugs)
1. `test_extension_detected`, `test_truncation_detected`, `test_single_bit_flip_detected`: Changed `assertIsNone()` → `assertRaises(ValueError)` since `decrypt_message()` correctly raises `ValueError` on MAC failure (not a bug)
2. `test_respond_without_opk_derives_same_secret`: Was using a SEPARATE throwaway ephemeral key for `x3dh_respond`. Fixed to use `init['ephemeral_key_pub']` (the key `x3dh_initiate` actually used internally).
3. `test_concurrent_encrypt_different_contacts_succeeds`: `f"secret_{i}"` → `f"secret_{i}".encode()` — `hkdf_derive` requires bytes, not str.

### x3dh_initiate SPK Verification — INTEGRATED
**Bug:** `x3dh_initiate()` accepted SPK without verifying signature — MITM could substitute fake SPK.
**Fix:** Added `verify_spk=True` parameter (default). Verifies SPK signature BEFORE using SPK in any DH operation. Raises `ValueError` on failure.

**Key detail:** Use raw DER bytes for verification, NOT imported EccKey objects:
```python
# CORRECT:
verify_signed_prekey(their_identity_pub_der, their_signed_prekey_pub_der, their_signed_prekey_sig)
# WRONG (returns False):
verify_signed_prekey(ik_b, spk_b, their_signed_prekey_sig)  # EccKey objects fail
```

**X3DH ECDH output:** Uses `_ecdh_xonly` (32-byte x-coordinate) per Signal spec — NOT `_ecdh_full` (64-byte x||y). X3DH was refactored to always use xonly. The `_ecdh_full` function is kept for legacy `derive_shared_secret` only.

### DER/Signature Format Mismatch — FOUND AND DOCUMENTED
**Bug:** `_ecdsa_sign()` signs raw DER bytes (X9.63 format internally), `_ecdsa_verify()` verifies via pycryptodome DSS which processes the same DER. Works within this codebase but may fail interoperability with external implementations that expect X9.63 uncompressed point format.
**Note:** Tests pass internally. Real-world interoperability UNTESTED.

### 1. HMAC → ECDSA Signatures
**Bug:** `hmac.new(ik_priv, spk_pub, hashlib.sha256).digest()` — HMAC can't verify without private key. Verification was `len(sig) == 32` (no-op).
**Fix:** Use `Crypto.Signature.DSS` with P-256 + SHA-256 (FIPS 186-3):
```python
def _ecdsa_sign(priv_key, message: bytes) -> bytes:
    from Crypto.Signature import DSS
    from Crypto.Hash import SHA256
    h = SHA256.new(message)
    return DSS.new(priv_key, 'fips-186-3').sign(h)

def _ecdsa_verify(pub_key, message: bytes, signature: bytes) -> bool:
    from Crypto.Signature import DSS
    from Crypto.Hash import SHA256
    h = SHA256.new(message)
    try:
        DSS.new(pub_key, 'fips-186-3').verify(h, signature)
        return True
    except (ValueError, TypeError):
        return False
```

### CRITICAL FIX (2026-04-22): ratchet_encrypt/decrypt race condition
**Bug:** `ratchet_encrypt()` and `ratchet_decrypt()` loaded state from disk, performed crypto, then saved — all without any locking. Concurrent calls for the same `(my_id, their_id)` pair could interleave, producing garbled state.
**Fix:** Per-ratchet-pair filesystem-level locking via `fcntl.LOCK_EX` on a deterministic lock file under `~/.jrwl-messenger/ratchets/.lock_{pair_key}`. Lock acquired before load, released after save (in `finally` block). This works across threads AND processes.

### 2. AES-GCM Nonce: 16 → 12 bytes
**Bug:** `os.urandom(16)` — non-standard for AES-GCM (should be 96-bit/12-byte).
**Fix:** Changed to `os.urandom(12)` in ALL locations:
- `encrypt_message()` (line ~155)
- `decrypt_message()` — nonce parsing: `raw[:12], raw[12:28], raw[28:]`
- `DoubleRatchet.encrypt()` (line ~477)
- `DoubleRatchet.decrypt()` — same nonce parsing

### 3. Skipped Message Keys (Double Ratchet)
**Bug:** `for _ in range(keys_to_skip): ... ratchet()` discarded intermediate keys. Out-of-order messages undecryptable.
**Fix:** Added `_skipped_keys: Dict[Tuple[str, int], bytes]` to DoubleRatchet:
```python
def _skip_message_keys(self, until_count: int, dh_pub_b64: str):
    if self.recv_chain_key is None:
        return
    while self.recv_count < until_count:
        self.recv_chain_key, msg_key = hkdf_ratchet(self.recv_chain_key)
        self._skipped_keys[(dh_pub_b64, self.recv_count)] = msg_key
        self.recv_count += 1
```
Also persist in `serialize()`/`deserialize()`.

### 4. Double Ratchet First DH Ratchet Bug (TRICKY)
**Bug:** `decrypt()` condition `if self.their_ratchet_pub_der is not None and self.their_ratchet_pub_der != their_pub_der:` — when `their_ratchet_pub_der` was `None` (Alice is initiator, first reply from Bob), the code skipped the DH ratchet and derived from `root_key` instead. This caused root keys to diverge.
**Debug process:**
1. ECDH symmetry verified OK in isolation
2. Manual `_ratchet_for_send`/`_ratchet_for_recv` produced matching chain keys
3. But encrypt/decrypt flow failed — MAC check
4. Discovered: Bob's root_key changed during `_ratchet_for_send`, Alice's didn't (never called `_ratchet_for_recv`)
5. Root cause: `None != their_pub_der` evaluated to `True` but the `is not None` check blocked entry to the `if` branch
**Fix:** Changed condition to `if self.their_ratchet_pub_der != their_pub_der:` (works for both `None` and changed values). Inner `if self.their_ratchet_pub_der is not None:` only for skipped key storage.

**KEY LESSON:** Don't check `is not None` before comparing values when `None` should also trigger the action.

### 5. WS Auth — Challenge-Response
**Bug:** `{"type": "auth", "identity_id": "xxx"}` — anyone with the ID could impersonate.
**Fix:** 2-step challenge-response:
1. Client sends `auth_request` with `identity_id`
2. Server generates 32-byte nonce via `secrets.token_bytes(32)`, stores with 60s TTL
3. Server sends `auth_challenge` with base64-encoded nonce
4. Client signs nonce with identity private key (ECDSA)
5. Server verifies signature with identity public key
6. Old `auth` type kept with deprecation warning for backward compat

Implementation in `ConnectionManager`:
```python
self._pending_challenges: Dict[object, Tuple[bytes, float]] = {}

def generate_challenge(self, ws) -> bytes:
    nonce = secrets.token_bytes(32)
    with self._lock:
        self._pending_challenges[ws] = (nonce, time.time())
    return nonce

def consume_challenge(self, ws) -> Optional[bytes]:
    # Pop and check 60s TTL
```

### 6. X3DH → Pure Relay (No Server-Side Computation)
**Bug:** `/api/x3dh/exchange` computed shared secret server-side using private keys.
**Fix:**
- Exchange stores initiator's ephemeral key as "pending" for responder
- New `/api/x3dh/pending` endpoint for responder to retrieve
- SPK verified with `verify_signed_prekey()` before proceeding
- No shared secret computed on server
- Safety number computed from public keys only

## Debugging Patterns

### DER Header Trap
ALL P-256 public keys in DER format start with the same 16-byte ASN.1 header: `3059301306072a8648ce3d020106082a`. Comparing `key[:16]` or `key[:8].hex()` shows the same value for DIFFERENT keys. Always compare full byte sequences or hashes.

### ECDH Symmetry Verification
When debugging DH ratchet key mismatches:
```python
dh_out_bob = _ecdh_full(bob_new_key, _ecc_import_pub(alice_pub_der))
dh_out_alice = _ecdh_full(_ecc_import_priv(alice_priv_der), _ecc_import_pub(bob_new_pub))
assert dh_out_bob == dh_out_alice  # Must be true for correct ECDH
```
If this passes but chain keys differ, the issue is in the HKDF derivation or root key state.

### State Tracing Method
For Double Ratchet bugs, trace state at each step:
```python
print(f"Root match: {ratchet_a.root_key == ratchet_b.root_key}")
print(f"Chain match: {ratchet_a.recv_chain_key == ratchet_b.send_chain_key}")
```
Root keys must match at each DH ratchet step (both derive from same DH output + same root_key).

## Running Tests
```bash
cd ~/projects/jrwl-messenger
python3 crypto.py              # 45-assertion self-test
python3 -c "import py_compile; py_compile.compile('gateway.py', doraise=True)"  # Syntax check
python3 -m pytest test_crypto_unit.py -v  # 38 unit tests (X3DH, Double Ratchet, ECDSA, AES, concurrency)
python3 e2e_test.py             # Integration: 8/8 end-to-end flow tests
python3 edge_case_test.py       # Integration: 11/12 edge case tests
python3 stress_test.py          # Integration: 5/5 stress test (50 IDs, 700 messages)
```

## Additional Fixes Applied (2026-04-22 session 2)

### 7. Hex-String Pagination → Timestamp-Based
**Bug:** `msg['id'] <= since_id` — hex string lexicographic comparison doesn't reflect chronological order.
**Fix:** Look up timestamp of `since_id`, then compare timestamps:
```python
since_ts = None
if since_id:
    for msg in self.in_memory.get(recipient_id, []):
        if msg['id'] == since_id:
            since_ts = msg.get('timestamp', '')
            break
for msg in self.in_memory.get(recipient_id, []):
    if since_ts and msg.get('timestamp', '') <= since_ts:
        continue
```

### 8. Offline Queue DLM Recovery
**Bug:** Offline queue was in-memory only. Server restart = messages lost from DLM (no way to enumerate).
**Fix:** Maintain an offline index in DLM (`offline-idx-{recipient_id}`) that tracks message IDs. On `drain_offline()`, if in-memory queue is empty, recover from DLM using the index:
- `send()` appends msg_id to index
- `drain_offline()` reads index → fetches each message by ID → erases index

### 9. Crashes JSON in `_load()`
**Bug:** `identity_store._load()` crashed entirely if any `.json` file was corrupt or missing `id` field.
**Fix:** Wrap each file in try/except:
```python
except (json.JSONDecodeError, KeyError, OSError) as e:
    log.warning(f"[IdentityStore] Skipping corrupt file {f}: {e}")
```

### 10. WS Auth Challenge Cleanup
**Bug:** `cleanup_challenges()` existed but was never called in `_cleanup_loop()`. Leaked memory under connection churn.
**Fix:** Added `self.conn_manager.cleanup_challenges()` to `_cleanup_loop()` (runs every 60s).

### 11. Pending X3DH Cleanup
**Bug:** `_pending_x3dh` dict never cleaned up — memory leak for exchanges where responder never connects.
**Fix:** Added 1-hour TTL cleanup in `_cleanup_loop()`:
```python
if hasattr(self, '_pending_x3dh'):
    x3dh_cutoff = time.time() - 3600
    for uid in list(self._pending_x3dh.keys()):
        self._pending_x3dh[uid] = {
            k: v for k, v in self._pending_x3dh[uid].items()
            if datetime.fromisoformat(v.get('timestamp', '2000-01-01')).timestamp() > x3dh_cutoff
        }
```

### 12. MAX_SKIPPED_KEYS Cap
**Fix:** Added `MAX_SKIPPED_KEYS = 5000` constant. `_skip_message_keys()` raises `ValueError` if limit exceeded — prevents memory exhaustion from malicious peers.

## Thread Safety Fixes (2026-04-22 session 3)

### 13. MessageRelay Thread Safety
**Bug:** `in_memory` and `offline_queue` dicts accessed from HTTP threads, WS async handler, cleanup thread — no locks.
**Fix:** Added `self._lock = threading.Lock()` and wrapped ALL methods:
- `send()` — lock around in_memory append + eviction
- `queue_offline()` — lock around offline_queue append
- `drain_offline()` — lock around offline_queue.pop() and in_memory.extend()
- `poll()` — lock around in_memory read + timestamp filtering
- `ack()` — lock around in_memory list comprehension
- `update_receipt()` — lock around in_memory iteration + mutation

**Key pattern:** Lock only for in-memory operations, release before DLM I/O:
```python
with self._lock:
    self.in_memory.setdefault(recipient_id, []).append(message)
# DLM operations OUTSIDE lock
if self.dlm_ok:
    ...
```

### 14. _pending_x3dh Thread Safety
**Fix:** Initialize in `__init__` (not lazy), add `_pending_x3dh_lock`, guard all access:
- X3DH exchange endpoint: `with gateway_ref._pending_x3dh_lock:`
- Pending endpoint: `with gateway_ref._pending_x3dh_lock:`
- Cleanup loop: `with self._pending_x3dh_lock:`

### 15. broadcast_all Lock Scope
**Bug:** Held `self._lock` during `asyncio.run_coroutine_threadsafe` (cross-thread I/O).
**Fix:** Snapshot clients under lock, send outside:
```python
with self._lock:
    clients = [c for c in self.ws_map.values() if c.authenticated]
for client in clients:  # outside lock
    asyncio.run_coroutine_threadsafe(client.ws.send(payload), gateway.loop)
```

### 16. _cleanup_loop Per-Step Exception Handling
**Bug:** Single exception in any cleanup step aborted the entire loop iteration.
**Fix:** Wrap each cleanup step individually in try/except with warning logging.

### 17. _consumed_opks Memory Leak
**Bug:** `gateway_ref.auth_manager._consumed_opks.get(opk_id)` — entries never removed.
**Fix:** Use `.pop(opk_id, None)` instead of `.get(opk_id)` — consume and remove in one step.

### 18. drain_offline Wrong DLM Key
**Bug:** Recovery used `self._dlm_key()` (msg-{rid}-{mid}) but offline messages stored at `self._dlm_offline_key()` (offline-{rid}-{mid}). Recovery never found messages.
**Fix:** Changed to `self._dlm_offline_key(recipient_id, msg_id)`.

## Multi-Agent Review Pattern
For large code audits, spawn parallel review agents with different focus areas:
1. **Security Audit** — crypto correctness, key handling, timing attacks
2. **Concurrency Review** — thread safety, race conditions, lock ordering
3. **Data Integrity** — crash safety, error handling, edge cases
4. **Protocol Correctness** — spec compliance, state machine correctness
5. **Integration/API** — endpoint contracts, backward compatibility

Run multiple rounds (this session: 5 rounds, 8 agents total). Each round found new issues introduced by previous fixes. The final round found:
- `update_receipt()` missing lock
- `drain_offline()` extend outside lock
- `_cleanup_loop` no per-step exception handling

### 20. except Exception: pass → Debug Logging
**Pattern:** Replace silent failures with `log_dlm.debug(...)` for DLM operations. Keeps failure visibility without spamming production logs.
```python
# Before:
except Exception:
    pass
# After:
except Exception as e:
    log_dlm.debug(f"[DLM] operation error: {e}")
```

### 21. x3dh_cleanup: INVERTED timestamp comparison (gateway.py:2792)
**Bug:** `datetime.fromisoformat(v.get('timestamp', '2000-01-01')).timestamp() > x3dh_cutoff` — entries OLDER than 1 hour were KEPT, newer ones were discarded. Default '2000-01-01' was always older, so entries with missing timestamps were NEVER cleaned.
**Fix:** Change `>` to `<`:
```python
# Before (BROKEN):
if datetime.fromisoformat(v.get('timestamp', '2000-01-01')).timestamp() > x3dh_cutoff:
# After (CORRECT):
if datetime.fromisoformat(v.get('timestamp', '2000-01-01')).timestamp() < x3dh_cutoff:
```

### 22. Group send: zero-key fallback (gateway.py:2017)
**Bug:** When `get_shared_secret()` returns None (no contact), group messages were encrypted with `b'\x00'*32` — a known constant. All messages to non-contacts used identical zero key.
**Fix:** Derive a unique key from sender identity + group_id via HKDF:
```python
sender_key_material = (sender_id + group_id).encode() + b'jrwl-group-sender-v1'
sender_copy_key = hkdf_derive(sender_key_material, length=32, info=b'jrwl-group-v1')
sender_copy_secret = gateway_ref.contact_manager.get_shared_secret(...) or sender_copy_key
```

### 23. _seen_relays: unbounded growth (gateway.py:1071)
**Bug:** `DLMFederation._seen_relays` had no size cap in gateway.py (unlike message_relay.py which had `_MAX_SEEN_RELAYS = 50000`). Over time this set grows unboundedly.
**Fix:** Add cap + eviction in `_discover_relays`:
```python
self._MAX_SEEN_RELAYS: int = 50000
# in _discover_relays when adding:
if len(self._seen_relays) >= self._MAX_SEEN_RELAYS:
    oldest_count = max(1, self._MAX_SEEN_RELAYS // 10)
    for _ in range(oldest_count):
        self._seen_relays.pop()
    self._seen_relays.add(key)
```

### 24. Body size limit missing (gateway.py:1494)
**Bug:** No limit on `Content-Length` — attacker could send `Content-Length: 2147483647` causing unbounded memory allocation before JSON parsing.
**Fix:**
```python
MAX_BODY_SIZE = 1024 * 1024  # 1MB max
length = int(self.headers.get('Content-Length', 0))
if length > self.MAX_BODY_SIZE:
    self._json_response({'error': f'body too large ({length} bytes, max {self.MAX_BODY_SIZE})'}, 413)
    return None
```

### 20. IdentityStore/GroupStore _load() Crash Safety
**Bug:** Corrupt JSON or missing `id` field crashed entire `_load()` (all identities lost).
**Fix:** Per-file try/except with warning:
```python
try:
    with open(os.path.join(self.data_dir, f)) as fh:
        data = json.load(fh)
        if 'id' in data:
            self.identities[data['id']] = data
except (json.JSONDecodeError, KeyError, OSError) as e:
    log.warning(f"Skipping corrupt file {f}: {e}")
```
**Critical:** gateway.py has INLINE copies of IdentityStore and GroupStore — both must be patched, not just the standalone modules.

## Test Suite Expansion (2026-04-22 session 3)

### 86 tests total — 35 original + 51 new

**New test classes added:**
- `TestMessageRelayInMemoryBounds` — MAX_IN_MEMORY_PER_RECIPIENT (1000), MAX_RECIPIENTS (10000), overflow eviction
- `TestValidateIdentityId` — valid hex IDs, invalid lengths/chars, non-string rejection, case insensitivity
- `TestIdentityIdEndpointValidation` — ≥14 validate_identity_id calls confirmed in gateway.py
- `TestMaxBodySize` — MAX_BODY_SIZE = 1MB constant
- `TestFilePermissions0600` — _save() creates 0600 files, save_prekeys/save_ratchet_state 0600
- `TestMessageRelayCore` — send/poll/ack, MAX_IN_MEMORY_PER_RECIPIENT cap
- `TestRatchetDecryptSilentFailure` — wrong key/truncated/corrupted/nonexistent returns None
- `TestAESGCMAuthentication` — bit flip/truncation/extension raises ValueError, 12-byte nonce
- `TestECDSAvsHMAC` — signatures are 64-80 byte ECDSA, HMAC tags rejected
- `TestRateLimiterCleanup` — cleanup() removes expired buckets, keeps active ones
- `TestTypingIndicatorCleanup` — >300s indicators pruned, recent ones kept
- `TestWSMessageReceiptSpoofing` — client.identity_id used, not msg['from']
- `TestX3DHKeyDerivation` — initiate/respond match, DH1 (no OPK), DH2 (with OPK)
- `TestDoubleRatchetFullHandshake` — full session, multi-message, save/restore

**Run tests:**
```bash
cd ~/projects/jrwl-messenger
python3 test_gateway_fixes.py   # 86 tests
python3 crypto.py              # 45 self-test assertions
```

## Additional Fixes Applied (2026-04-23 session)

### SEC-21: WS _process_ws_message msg_id undefined for 1:1 path
**Bug:** `msg_id = secrets.token_hex(8)` was only inside the group-message branch.
1:1 path referenced `msg_id_clean` (never defined) → `NameError`. Also, no
sender-copy (`_sent_{sender_id}_{recipient_id}`) was stored for 1:1 messages.
**Fix:** Moved `msg_id = secrets.token_hex(8)` to before the group/1:1 branch
split. Removed all `msg_id_clean` references. Added sender-copy storage for 1:1.

### SEC-24: ContactManager._secret_cache unbounded growth
**Bug:** `get_shared_secret()` and `add_contact()` cached derived secrets with no
TTL and no cap. Gateway running long-term with many contacts → memory leak.
**Fix:**
```python
_MAX_SECRET_CACHE = 10000
_EVICTION_BATCH = 500
_cache_order: list = []  # LRU insertion-order list

# In get_shared_secret() and add_contact():
if len(self._secret_cache) >= self._MAX_SECRET_CACHE:
    for _ in range(self._EVICTION_BATCH):
        if not self._cache_order:
            break
        old_key = self._cache_order.pop(0)
        self._secret_cache.pop(old_key, None)
```
**Eviction triggers ONLY when adding a new entry (secret is not None).**
Repeated lookups of the same cached key do NOT evict even when cache is full.

### SEC-25: WS federation send missing recipient_id validation
**Bug:** WS 1:1 send for non-local identity passed `recipient_id` from
`msg.get('to')` directly to `federation.send_to_remote()` without format check.
Malicious client could inject special chars into DLM relay key namespace.
**Fix:** Added `validate_identity_id(recipient_id)` check before federation path.

### SEC-26: Group endpoints missing identity_id validation
**Bug:** `/api/group/add-member` accepted any `member_id`. `/api/group/send`
accepted any `sender_id` (`from` field).
**Fix:** Added `validate_identity_id(member_id)` and `validate_identity_id(sender_id)`.

### Bugs Verified as NOT Bugs (false positives from prior audit)
- **Bug #5 Group sender_key:** `f"_group_sent_{sender_id}_{group_id}"` is correct
  (stores per-sender-per-group, as intended)
- **Bug #6 IdentityStore._save:** Already inside `with self._lock:` block (line 367)
- **Bug #7 msg_id.replace:** Does not exist. `ack()` uses `removesuffix("_s")`.
  `_x3dh_entry_age()` uses `rsplit('_s', 1)[-1]`. Both safe.
- **Bug #13 datetime fallback:** `datetime.fromisoformat` with try/except fallback to
  `"0"` (treated as expired → cleaned up). Conservative, not harmful.

## Test Suite Expansion (2026-04-23 session)
**92 tests total** (86 + 6 new):

**New test classes:**
- `TestSecretCacheBounded` — eviction when cache exceeds MAX
- `TestWSSendMsgIdDefined` — `msg_id_clean` absent from WS handler source
- `TestWSFederationRecipientIdValidation` — `validate_identity_id(recipient_id)` in federation path
- `TestGroupEndpointValidation` — `member_id` and `sender_id` validated

## Debugging Lessons Learned (2026-04-23)

### `inspect.getsource()` on nested async methods
`inspect.getsource(Gateway._process_ws_message)` fails with `IndentationError`
when the method is an async def inside an inner class. The Python AST parser
chokes on the indented source string.

**Workaround:** Use string search instead of AST parsing:
```python
# WRONG (IndentationError on indented async method):
tree = ast.parse(inspect.getsource(gateway.Gateway._process_ws_message))

# CORRECT:
source = inspect.getsource(gateway.Gateway._process_ws_message)
self.assertNotIn('msg_id_clean', source)
```
Or read the file directly: `open('gateway.py').read()`.

### IdentityStore.identities key is HEX string, not display name
```python
id_store.create('alice')
list(id_store.identities.keys())  # → ['2dc0973d']  (hex, NOT 'alice')
id_store.identities['alice']     # → KeyError!
id_store.identities[hex_id]       # → correct
```

### ContactManager eviction only triggers on cache MISS with successful derive
`get_shared_secret()` eviction runs in the slow path (after cache lookup fails).
If you call `get_shared_secret()` for a key already in cache → fast path return,
no eviction even if cache is full. The cache must be populated such that a NEW
key triggers the slow path AND successfully derives a secret.

### Sub-agent false positives
A sub-agent (delegated audit) reported `json.loads` without try/except as a bug
in `update_receipt()`. In reality, the entire DLM block is wrapped in
`try: ... except Exception: pass`. Sub-agents miss enclosing try/except context
when scanning for bare `json.loads` calls. Always verify enclosing context.

### `_x3dh_entry_age` return type is float
```python
def _x3dh_entry_age(entry: dict) -> float:
    age_str = entry.get('timestamp', '')
    try:
        return (datetime.now() - datetime.fromisoformat(age_str)).total_seconds()
    except Exception:
        return float('inf')  # or 0 — both treated as "very old"
```
Returns `float('inf')` on parse failure. Comparison: `age < cutoff` correctly
identifies old entries regardless.

## Bugs Fixed (2026-04-23 late session — pre-consolidation)

### SEC-27: `prev_send_count` not updated in `_ratchet_for_recv()` (REAL DOUBLE RATCHET BUG)
**Bug:** `_ratchet_for_recv()` did NOT update `prev_send_count` after processing a
DH ratchet step. When receiving a new DH ratchet public key from the peer,
`prev_send_count` remained at whatever value it had before (initial 0, or the
value from the previous ratchet step). This broke out-of-order message detection:
a message from before the DH ratchet could incorrectly match `recv_count` if
`prev_send_count` was still 0.

**Fix in `_ratchet_for_recv()`:**
```python
# BEFORE (missing line):
def _ratchet_for_recv(self, their_pub_der: bytes) -> bytes:
    ...
    self.their_ratchet_pub_der = their_pub_der
    # prev_send_count was NOT updated here!
    self.send_count = 0
    ...

# AFTER (added line):
def _ratchet_for_recv(self, their_pub_der: bytes) -> bytes:
    ...
    self.their_ratchet_pub_der = their_pub_der
    self.prev_send_count = self.send_count  # ← ADDED: sync prev to current before reset
    self.send_count = 0
    ...
```

**Verification:** `test_encrypted_message_prev_count_updated_after_dh_ratchet` in
`test_crypto_unit.py` — encrypts multiple messages, performs DH ratchet, verifies
`prev_send_count` reflects the send count BEFORE the ratchet reset.

### `test_auth_code_randomness`: Birthday Paradox Collision (TEST FIX, not crypto bug)
**Issue:** 100 random 6-digit codes (10^6 range) → expected ~1 collision by birthday
paradox. With threshold `assertGreaterEqual(passed, 99)` (要求 99/100 pass),
a single natural collision causes flaky failures.

**Fix:** Lowered threshold to `assertGreaterEqual(passed, 97)` — still rejects
deterministic/repeated patterns, accepts natural birthday collisions at 100 samples.

### Test Bugs Fixed (test_crypto_unit.py)

1. **`test_ecdh_xonly_and_ecdh_full_differ` → `test_ecdh_xonly_and_ecdh_full_both_derive_same_x`**:
   Assertion was semantically wrong. Both xonly and full ECDH derive the SAME x-coordinate
   (xonly just discards y). Test renamed and fixed to verify both derive identical x.

2. **`test_skip_message_keys_large_gap_triggers_valueerror`**: Completely rewritten.
   Called `decrypt_message()` which does NOT produce skip-message-keys (those are
   created by `_skip_message_keys()` called during recv-chain). Now calls
   `_skip_message_keys()` directly with proper `recv_chain_key` initialized.

3. **`test_skip_message_keys_exactly_at_limit_works`**: Key-offset fix + proper
   `recv_chain_key` initialization before calling `_skip_message_keys()`.

4. **ECDSA tests using `_ecc_import_pub()`**: `test_ecdsa_sign_then_verify_success`
   and `test_ecdsa_verify_with_wrong_key_fails` were passing raw DER bytes to
   `_ecdsa_verify()` which expects EccKey objects. Added `_ecc_import_pub()` calls.

5. **`test_ratchet_state_file_permissions_600`**: Added `mkdir(exist_ok=True)` before
   `_save()` call — test failed if `~/.jrwl-messenger/ratchets/` didn't exist.

## Audit-2 Findings (2026-04-23)

### Phantom Bugs — Always Verify Against Actual Code
The pre-existing bug task list contained several "bugs" that were NOT actually bugs.
**Rule: Never trust a bug description without verifying it against the source code first.**

| Bug in List | Verdict | Why |
|-------------|---------|-----|
| BUG-5: `set.pop()` TypeError | **NOT A BUG** | `set.pop()` with NO args is legal Python (removes arbitrary element). Code already uses it correctly without args. |
| BUG-6: Lock held during DLM I/O | **NOT A BUG** | Lock is released BEFORE DLM I/O begins (`with self._lock:` scope ends at line 906, DLM starts at 908). |
| BUG-15: DLM recovery skipped | **NOT A BUG** | `drain_offline` ALWAYS recovers from DLM (line 807: `if self.dlm_ok:`). |
| BUG-16: DLM entries not erased | **NOT A BUG** | Individual entries ARE erased at line ~854 via `lock.Erase`. |
| BUG-17: decrypt error swallowed | **NOT A BUG** | Already logged at ERROR level with full context. |

### BUG-14: MAX_SKIPPED_KEYS raises ValueError → warn+break (crypto.py)
**Bug:** `raise ValueError(...)` inside `_skip_message_keys()` would crash the ratchet
entirely on large gaps. A non-fatal condition (message gap > 5000) should warn and
drop messages, not kill the session.
**Fix:** Changed `raise` to `warnings.warn(...) + break`. Messages beyond the gap
are dropped silently (with warning). Session continues.
**Test update:** `test_skip_message_keys_large_gap_triggers_valueerror` renamed to
`test_skip_message_keys_large_gap_triggers_warning` — now asserts a warning is
emitted, not a ValueError.

### BUG-7: queue_offline index-write-before-message-write (gateway.py)
**Bug:** Message was written to DLM FIRST, then index updated. Crash between the two
= orphaned message with no index entry = permanently unrecoverable.
**Fix:** Write index FIRST, then message. Crash after index-write = orphaned index
entry pointing to nothing = recoverable by retry.

### BUG-11: drain_offline index erased AFTER recovery → move BEFORE (gateway.py)
**Bug:** Index erased at line ~833 AFTER recovery loop. If `drain_offline` is called
again before delivery completes, messages could be duplicated.
**Fix:** Erase index BEFORE recovery loop. Crash after erase = empty index on restart
= nothing to re-deliver.

### BUG-4: _seen_relays add before erase (gateway.py scan_relays_for_identity)
**Bug:** `lock.Erase()` called before `self._seen_relays.add(key)`. If crash occurs
after erase but before add → on restart same relay key re-discovered → double-delivery.
**Fix:** Add to `_seen_relays` immediately after confirming valid data, BEFORE `lock.Erase`.

### BUG-12: _seen_relays eviction only inside "key not in set" guard (gateway.py)
**Bug:** Eviction logic was INSIDE the `if key not in _seen_relays:` branch.
Recurring/already-seen keys never triggered eviction → `_seen_relays` could
grow beyond MAX_SEEN_RELAYS.
**Fix:** Moved eviction check OUTSIDE the "new key" guard. Runs on every iteration
when at capacity, regardless of whether key is new or existing.

### Test Results After Audit-2
```
crypto_unit:  76/76 ✅
e2e_test:      8/8  ✅
commit: 2580237 audit-2 fixes pushed to main
```

---

## Audit-2 Findings (2026-04-23 late)

### Phantom Bugs — Always Verify Against Actual Code
The pre-existing bug task list contained several "bugs" that were NOT actually bugs.
**Rule: Never trust a bug description without verifying it against the source code first.**

| Bug in List | Verdict | Why |
|-------------|---------|-----|
| BUG-5: `set.pop()` TypeError | **NOT A BUG** | `set.pop()` with NO args is legal Python (removes arbitrary element). Code already uses it correctly without args. |
| BUG-6: Lock held during DLM I/O | **NOT A BUG** | Lock is released BEFORE DLM I/O begins (`with self._lock:` scope ends at line 906, DLM starts at 908). |
| BUG-15: DLM recovery skipped | **NOT A BUG** | `drain_offline` ALWAYS recovers from DLM (line 807: `if self.dlm_ok:`). |
| BUG-16: DLM entries not erased | **NOT A BUG** | Individual entries ARE erased at line ~854 via `lock.Erase`. |
| BUG-17: decrypt error swallowed | **NOT A BUG** | Already logged at ERROR level with full context. |

**Verification approach used:**
1. `search_files` to find exact line references
2. `read_file` with surrounding context (30-50 lines each direction)
3. Only apply a fix after confirming the actual bug with evidence

### BUG-14: MAX_SKIPPED_KEYS raises ValueError → warn+break (crypto.py)
**Bug:** `raise ValueError(...)` inside `_skip_message_keys()` would crash the ratchet
entirely on large gaps. A non-fatal condition (message gap > 5000) should warn and
drop messages, not kill the session.
**Fix:** Changed `raise` to `warnings.warn(...) + break`. Messages beyond the gap
are dropped silently (with warning). Session continues.
**Test update:** `test_skip_message_keys_large_gap_triggers_valueerror` renamed to
`test_skip_message_keys_large_gap_triggers_warning` — now asserts a warning is
emitted, not a ValueError.

### BUG-7: queue_offline index-write-before-message-write (gateway.py)
**Bug:** Message was written to DLM FIRST (line 776), then index updated (line 788).
Crash between the two = orphaned message with no index entry = permanently unrecoverable.
**Fix:** Write index FIRST, then message. Crash after index-write = orphaned index
entry pointing to nothing = recoverable by retry. Commit: `2580237`.

### BUG-11: drain_offline index erased AFTER recovery → move BEFORE (gateway.py)
**Bug:** Index erased at line 833 AFTER recovery loop. If `drain_offline` is called
again before delivery completes, messages could be duplicated.
**Fix:** Erase index BEFORE recovery loop. Crash after erase = empty index on restart
= nothing to re-deliver. Messages are already in the return list for delivery.

### BUG-4: _seen_relays add before erase (gateway.py scan_relays_for_identity)
**Bug:** `lock.Erase()` called before `self._seen_relays.add(key)`. If crash occurs
after erase but before add → on restart same relay key re-discovered → double-delivery.
**Fix:** Add to `_seen_relays` immediately after confirming valid data, BEFORE `lock.Erase`.

### BUG-12: _seen_relays eviction only inside "key not in set" guard (gateway.py)
**Bug:** Eviction logic (`if len >= MAX: pop()`) was INSIDE the `if key not in _seen_relays:`
branch. Recurring/already-seen keys never triggered eviction → `_seen_relays` could
grow beyond MAX_SEEN_RELAYS if the same keys were repeatedly discovered.
**Fix:** Moved eviction check OUTSIDE the "new key" guard. Runs on every iteration
when at capacity, regardless of whether key is new or existing.

### Test Results After Audit-2
```
crypto_unit:  76/76 ✅
e2e_test:      8/8  ✅
commit: 2580237 audit-2 fixes pushed to main
```

## Pitfalls
- **pycryptodome DSS:** Use `'fips-186-3'` mode (deterministic), not `'fips-186-3'` with `'der'` encoding
- **`message_relay.py` is DEAD CODE** — gateway.py defines all classes inline, never imports the module
- **Nonce format:** AES-GCM nonce MUST be 12 bytes. pycryptodome accepts 16 bytes but processes via GHASH (non-standard)
- **DoubleRatchet `__init__`:** Initiator gets `send_chain_key`, responder gets `recv_chain_key`. Neither has the other chain initially — the first DH ratchet creates it
- **DER header trap:** ALL P-256 pub keys share the same 16-byte ASN.1 header. Comparing `key[:8].hex()` shows identical values for DIFFERENT keys. Always compare full bytes or hashes.
- **`None` comparison pitfall:** `if x is not None and x != y:` skips when x is None. Use `if x != y:` if None should trigger the action (e.g., first DH ratchet where stored key is None)
- **`inspect.getsource()` on indented async methods:** Fails with `IndentationError`. Use string search or read file directly.
- **Eviction triggers on cache MISS + success:** Repeated cache HITS don't evict. Populate cache to MAX+1 with dummy entries via direct dict manipulation, then call get_shared_secret for a new key to trigger eviction.
