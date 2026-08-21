# Bug Patterns From Real Crew Rounds (iris-messenger Phase 7)

The specific bugs that surfaced in iris-messenger Phase 7 rounds 4–8
(2026-06-21) — captured for future coder briefs on crypto/storage/IDB
work. Each pattern includes: what went wrong, why, the fix, and the
detection recipe. Use as a pre-emptive checklist when prompting a
coder to write or modify code in these domains.

These are DOMAIN-SPECIFIC (crypto, secure storage, IDB, HTTP
handlers). They complement the generic "test design gotchas" in
`test-fixture-patterns.md`.

Round 6-8 data (JS template literal gotcha, audit-leave-untracked
pattern, round 6-8 stability data) is in
`references/round-6-7-8-stability-data.md`.

---

## 1. AES-GCM `size` field semantics: plaintext length, not ciphertext

**Where it bit:** `ui/iris-ratchet-store.js:_rowForSave` (round 4)

**Bug:** The `_rowForSave(myId, theirId, iv, ciphertext)` builder
used `size: ciphertext.length` to record the ratchet state size in
the IDB row. AES-GCM ciphertext = plaintext + 16-byte auth tag, so
`size` was 16 bytes larger than the actual ratchet state. Tests
asserted `len(plaintext) == row.size` and failed (157 ≠ 173).

**Why:** the function name (`_rowForSave`) and the call site both
imply "this is about the data being stored" — the user thinks of
`size` as "how big is the ratchet state I'm storing." But the
implementation picked `ciphertext.length` because that's what
`row` had direct access to.

**Fix:** add an explicit `plaintextLen` parameter to `_rowForSave`
and pass `ratchetStateBytes.length` from `save()`:

```js
function _rowForSave(myId, theirId, iv, ciphertext, plaintextLen) {
  return { myId, theirId, iv, ciphertext, mtime: Date.now(), size: plaintextLen };
}
// in save():
const row = _rowForSave(myId, theirId, iv, ciphertext, ratchetStateBytes.length);
```

**General rule:** for any audit/metadata field that represents
"how big is the data the user is storing," use PLAINTEXT length,
not ciphertext. The 16-byte GCM auth tag is implementation detail
that should not leak into user-visible metadata.

**Detection:** grep for `size:` in IDB row builders / store
implementations. If the value comes from `ciphertext.length`,
it's wrong. Should come from the plaintext arg.

---

## 2. Fake IndexedDB mock parity: `req.result` must be a property

**Where it bit:** `tests/ratchet_store_node.js:FakeObjectStore._req` (round 4)

**Bug:** The fake IDB's `_req(result)` returned a request object
where `result` was only accessible via the event payload:

```js
_req(result) {
  const req = {};
  Object.defineProperty(req, 'onsuccess', {
    set(fn) {
      if (fn) Promise.resolve().then(() => fn({ target: { result } }));
    },
  });
  return req;
}
```

Real IDB exposes `event.target.result === req.result` — both
forms are valid. But the JS module's `_idbReq` helper reads
`req.result` directly:

```js
function _idbReq(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
  });
}
```

So all `load()` calls under the fake IDB returned `undefined`,
which the test interpreted as "not found." The bug was invisible
until tests failed with "load returns null" assertions.

**Fix:** expose `result` as a property on the request object so
fake IDB matches real IDB semantics:

```js
_req(result) {
  const req = { result };  // <-- add this
  Object.defineProperty(req, 'onsuccess', {
    set(fn) {
      if (fn) Promise.resolve().then(() => fn({ target: req }));
    },
  });
  return req;
}
```

**General rule:** when mocking IndexedDB (or any event-based
async API), the mock must support BOTH event-delivery AND direct
property access for result data. The standard pattern is
`req.result = result` + `event.target = req` (so they're the
same object). Real IDB does this; mocks that only do one half
will silently break code paths that use the other.

**Detection:** any fake IDB / fake WebSocket / fake fetch
implementation that delivers data ONLY via the event payload
(and not on the request object itself) is suspect. The bug
surfaces as "all loads return null" or "all sends return
undefined" — typically after the fake has been working for
several other operations and the test author has stopped
questioning it.

---

## 3. ratchet_pub / DH public key encoding: SPKI vs SEC1

**Where it bit:** `tests/test_x3dh_response_shape.py:test_ratchet_pub_is_actually_a_dh_public_key` (round 4)

**Bug:** The test asserted that `ratchet_pub` (a P-256 EC public
key) decoded to one of `{32, 33, 64, 65}` bytes — the raw / SEC1
compressed / SEC1 uncompressed encodings. But `crypto.py` emits
SPKI (SubjectPublicKeyInfo DER) which is 91 bytes for P-256
(26-byte SPKI prefix + 65-byte uncompressed point). The test
failed: `assert 91 in (32, 33, 64, 65) → AssertionError`.

**Why:** the test author assumed "EC public key = raw point bytes."
That's true for libsignal-style code, but Python's
`cryptography.hazmat` library emits SPKI by default
(`public_bytes(SubjectPublicKeyInfo)`). The encoding choice was
made when crypto.py was first written, but the test was added
later without checking the actual encoding.

**Fix (option A — accept both):** update the test to accept any
valid P-256 encoding:

```python
assert len(decoded) in (32, 33, 64, 65, 91), (
    f"ratchet_pub must be a real EC public key shape, got {len(decoded)} bytes"
)
```

**Fix (option B — canonicalize at the boundary):** convert SPKI
to raw SEC1 in the gateway before returning:

```python
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
raw = their_pub.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
return base64.b64encode(raw).decode()
```

Option A is faster (no code change) but leaves the encoding
ambiguous. Option B is cleaner (one canonical encoding) but
changes the wire format — verify no client depends on SPKI first.

**General rule:** when asserting on cryptographic wire-format
shapes, enumerate ALL valid encodings the codebase might
produce. For P-256:
- 32 bytes: raw X coordinate (rare)
- 33 bytes: SEC1 compressed (0x02/0x03 + X)
- 64 bytes: raw X||Y (rare, non-standard)
- 65 bytes: SEC1 uncompressed (0x04 + X + Y)
- 91 bytes: SPKI DER (Python's `cryptography.hazmat` default)
- ~120 bytes: PKCS#1 (for RSA, not EC)

For X25519: 32 bytes (raw) or 44 bytes (SPKI).

**Detection:** any test that asserts a single specific length
for a public key field is brittle. Either enumerate the
acceptable encodings OR canonicalize at the gateway boundary.

---

## 4. Handler-vs-Gateway scope confusion in nested handler classes

**Where it bit:** `gateway.py:_handle_x3dh_v2` (round 5)

**Bug:** The `/v2` handler was added as a method on
`Gateway.Handler` (the nested class inside `do_POST`). It used
`self.x3dh_response_mode` to read the active response mode. But
`x3dh_response_mode` is set on the `Gateway` instance
(`self.x3dh_response_mode = _setup_x3dh_response_mode(...)` in
`Gateway.__init__`), not on the Handler. Every /v2 request
crashed with `AttributeError: 'Handler' object has no attribute 'x3dh_response_mode'`.

**Why:** when adding a new method, the obvious instinct is
`self.attr_name`. But the Handler is a nested class with no
back-reference to its outer Gateway — config-derived attrs
and the IdentityStore / ContactManager / RatchetStateBackend
all live on `gateway_ref`, not on `self`.

**Fix:** use `gateway_ref.attr_name` for any config or
subsystem reference inside Handler methods. The pattern is
already used by every other handler in `do_POST` — the new
method just didn't follow it.

```python
def _handle_x3dh_v2(self, body, role):
    if gateway_ref.x3dh_response_mode != 'dh_only':  # NOT self.x3dh_response_mode
        self._json_response({'error': "v2 requires ..."}, 400)
        return
    ...
```

**General rule:** when adding a new method to a nested handler
class (HTTPHandler, RequestHandler, BaseHTTPRequestHandler
subclass, etc.), the rule is:

- `self` = the Handler instance (request body, response
  helpers like `_json_response`, per-request state)
- `gateway_ref` / `app_ref` / outer class name = the parent
  server (config-derived attrs, stores, subsystems)

**Detection:** grep the new method for `self.` — every reference
should be to Handler-internal state. Config-derived attrs and
shared subsystems are on the outer reference.

---

## 5. Test fixtures using `__new__` to bypass `__init__` lose config attrs

**Where it bit:** `tests/test_x3dh_response_shape.py:gateway_with_server` (round 5)

**Bug:** The pytest fixture built the Gateway via
`Gateway.__new__(Gateway)` to skip the full `__init__` (which
sets up redis/zmq listeners). It then manually assigned the
attributes the test path needed (`gw.identity_store = ...`,
`gw.contact_manager = ...`, etc.). But the new /v2 handler
needed `gw.x3dh_response_mode`, which the fixture didn't set
— so every /v2 test crashed.

**Why:** the fixture was written before the /v2 handler
existed. When the handler was added in a different commit,
the fixture wasn't updated to set the new attribute.

**Fix:** add the missing attribute assignment in the fixture,
with a comment explaining why:

```python
# Set up config-derived attributes normally set in Gateway.__init__
# so the /v2 routes (and any future config-dependent handlers) find
# what they need. The fixture uses Gateway.__new__ to bypass init,
# so these have to be set manually.
from gateway import _setup_x3dh_response_mode
gw.x3dh_response_mode = _setup_x3dh_response_mode({})
```

**General rule:** when a new handler depends on a config-derived
attribute, the test fixture that builds the Gateway must also
set that attribute. Add this in the same commit as the new
handler, with an explicit comment. Don't trust future
contributors to know the fixture bypasses init.

**Detection:** after adding a new handler that reads a new
attribute, run the test suite. If tests for the new handler
crash with `AttributeError: 'X' object has no attribute 'Y'`,
and the fixture uses `__new__` to build the object, the fix is
to set the attribute in the fixture. Grep the fixture for
`gw.` assignments and add the missing one.

**Companion fix:** the helper function (`_setup_x3dh_response_mode`
in this case) should accept an empty dict and return a sensible
default. That way the fixture can call it with `{}` to get the
default behavior without needing a full config fixture.

---

## 6. Idempotency assumption on NullBackend endpoints is wrong

**Where it bit:** `tests/test_x3dh_v2.py:test_x3dh_v2_idempotent_path_also_dh_only` (round 5)

**Bug:** The test called /v2 twice and asserted the second
call returns `status='exists'` (the /v1 idempotency contract).
But /v2 swaps the active RatchetStateBackend to NullBackend
during the request — so the server has no memory of v2
sessions. The second call returned `status='created'` (a fresh
ratchet every time).

**Why:** the test author assumed the v1 and v2 endpoints have
the same idempotency contract. They don't — v2 is
non-idempotent by design (server doesn't store ratchet state,
so it can't recognize a re-handshake).

**Fix:** rewrite the test to assert the actual v2 contract:

```python
# /v2 is NOT idempotent by design — the NullBackend swap means
# the server has no memory of v2 sessions, so each call creates
# a fresh ratchet. What MUST hold: both calls return DH-only,
# neither call persists state.
assert resp2.get('status') == 'created', (
    f"second /v2 call should return 'created' (NullBackend = "
    f"no idempotency memory), got {resp2.get('status')!r}"
)
_assert_no_forbidden_fields(resp2, '/api/x3dh/initiate-compute/v2 [2nd call]')
```

**General rule:** for any endpoint that context-swaps to
NullBackend / no-op storage, the contract is:

- Each call creates a fresh session/state
- No idempotency on repeated calls (server has no memory)
- The endpoint MUST return the correct shape on every call
- State-leak invariants still hold (server doesn't persist)

Tests should assert these explicitly. The `status` value of
the response may be `'created'` every time — that's correct,
not a bug.

**Detection:** if an endpoint swaps RatchetStateBackend (or
any other session-state store) to NullBackend within the
request handler, the test contract is "every call returns
DH-only + no state leaks + status='created' on every call."
Don't write idempotency tests for these endpoints — they
won't pass, and they shouldn't.

---

## 7. JS template literal `{}` collides with Python `str.format()`

**Where it bit:** `tests/test_js_python_spec_parity.py:_NODE_DERIVE` (round 6)

**Bug:** The test embeds a Node script as a Python string and
substitutes values via `str.format()`. JS template uses `{ webcrypto }`
for destructuring, which Python interprets as a format placeholder:

```python
_NODE_DERIVE = textwrap.dedent("""
    const { webcrypto } = require('node:crypto');
    ...
""")
script = _NODE_DERIVE.format(ikm_b64=ikm_b64)   # ← KeyError: ' webcrypto '
```

Python's `str.format()` interprets `{ webcrypto }` as a format
placeholder (with surrounding spaces as the "key name"). Fails
with `KeyError: ' webcrypto '` BEFORE the script is ever sent
to Node.

**Why:** the JS template uses `{}` for destructuring
(`const { webcrypto } = require(...)`) and object literals
(`{ name: 'HKDF', hash: 'SHA-256' }`). Python's `str.format()`
treats every `{...}` as a placeholder. Brace semantics collide.

**Fix:** replace `.format()` with explicit `.replace('{key}', value)`
chain. Cleanest and avoids the brace escape problem:

```python
script = (
    _NODE_DERIVE
    .replace('{ikm_b64}', ikm_b64)
    .replace('{secret_b64}', secret_b64)
    .replace('{iv_hex}', iv_hex)
    .replace('{pt_b64}', pt_b64)
)
```

For tests with many placeholders, a helper:

```python
def _sub(template, **subs):
    for k, v in subs.items():
        template = template.replace('{' + k + '}', v)
    return template

script = _sub(_NODE_DERIVE, ikm_b64=ikm_b64)
```

**Alternative: f-strings with `{{` / `}}` to escape braces:**

```python
script = f"""
    const {{ webcrypto }} = require('node:crypto');
    (async () => {{
        const ikm = Uint8Array.from(Buffer.from('{ikm_b64}', 'base64'));
    }})();
"""
```

Works but harder to read with many `{{`/`}}` pairs.

**General rule:** when embedding JS (or any brace-heavy DSL) in
a Python string template:
- **DO NOT use `str.format()`** — brace semantics collide
- **DO use `.replace('{placeholder}', value)`** chain or
  f-strings with explicit `{{`/`}}` escaping
- For tests with many placeholders, use a `_sub(template, **subs)`
  helper for readability

**Detection:** `KeyError: ' webcrypto '` (or any brace-pair with
spaces) on `str.format()` is the smoking gun. The error message
names the brace-pair with surrounding whitespace — diagnostic
that's hard to misinterpret once you know the pattern.

---

## 8. Coder finding a leak: leave the file UNTRACKED, parent decides

**Where it bit:** `tests/test_message_plaintext_audit.py` (round 8)

**Pattern:** A coder is dispatched to AUDIT something (message
flow, X3DH, storage) with a "leave untracked on leak" rule in
the brief. The coder finds a real leak (`/api/messages/{id}`
server-decrypts legacy AES-GCM messages for the recipient —
inconsistent with `/api/chat/history` which is opaque). Per
the spec, the coder:

1. Writes the audit tests anyway (3 tests, 2 pass + 1 fail
   on the leak)
2. **Does NOT commit** the file (it's untracked, parent
   decides)
3. Reports the leak with full evidence in the final summary

**Why this is the right sub-agent behavior:** the audit's
job is to surface problems, not fix them. The parent has full
context to decide:
- Fix the leak in this round (5-min parent patch)
- Open a new round for the fix (deferral)
- Document the exception (acknowledge + ship anyway)

**Brief template addendum for audit/pen-test coders:**

```
IF YOUR AUDIT FINDS A LEAK / VIOLATION / BUG:
  - Do NOT fix it. Do NOT commit a partial fix.
  - Leave the test file UNTRACKED on disk.
  - Include all 3 tests, including the failing one.
  - Report the leak with full evidence:
    * Which test failed
    * What the actual leaked value was
    * Where in the code the leak happens (file:line)
    * Recommended fix (1-2 lines, your best guess)
  - Parent agent decides fix-now vs fix-later.
```

**Parent recipe when an audit coder reports a leak:**

1. Read the coder's evidence (failing test + summary)
2. Read the leaked code at the file:line cited
3. Verify the leak is real
4. Decide:
   - **Fix now** if <30 lines and doesn't break other tests:
     do the fix, commit together with the audit
   - **Defer** if large or risky: leave audit untracked, open
     a new round
5. If fixing: amend the audit test if needed (the leak-
   exposing test should pass after the fix)

**The pattern from round 8:** coder found the leak, parent
fixed it with `INBOX_OPAQUE_MODE` config flag (default
`True` = AES-by-design, `False` = legacy back-compat).
Single 32-line patch in gateway.py + 32-line comment
explaining the AES-by-design mandate. Both committed
together in 7d7047d.

**Counter-recipe:** if the audit coder commits a partial
fix, the parent loses the decision point. The fix may
break legacy clients in ways the parent can't easily
revert. Always leave the audit untracked on leak discovery.

**General rule for security-audit coders:**
- Surface problems, don't fix them
- Leave evidence on disk (untracked test file)
- Report fully in the summary
- Parent owns the fix-or-defer decision

---

## Summary checklist for coder briefs on crypto/storage work (rounds 4-8)

When dispatching a coder to implement or test code in this domain,
include this list in the brief to pre-empt the bugs above:

```
KNOWN CRYPTO/STORAGE/IDB PITFALLS (avoid these):

- AES-GCM `size`/audit fields: use plaintext length, not
  ciphertext (which is plaintext + 16-byte GCM tag)
- Fake IndexedDB: expose `req.result` as a property, not just
  via the event payload (real IDB has `event.target.result ===
  req.result`)
- P-256 public key encodings: 32/33/64/65/91 bytes are all
  valid (raw / SEC1 / SPKI). Enumerate or canonicalize, don't
  assert a single length.
- Handler-vs-Gateway scope: nested Handler methods use
  `gateway_ref.attr_name` for config attrs, not `self.attr_name`
- Test fixtures using `Gateway.__new__()` to bypass init: must
  manually set every config-derived attribute the handlers need
- NullBackend endpoints are NOT idempotent by design — assert
  the actual contract (DH-only + no state leaks + status='created'
  every call)
- JS template literals in Python string templates: use
  `.replace('{key}', value)` chain, NOT `str.format()` (brace
  semantics collide — `KeyError: ' webcrypto '` on first use)
- Audit coders finding leaks: leave file UNTRACKED, report
  with full evidence (file:line, leaked value, recommended
  fix). Parent decides fix-now vs defer.
```

Including this in the brief saves 30+ minutes of parent-side
patching per coder. From round 5 data: 3 integration bugs
across 2 files, all pre-emptable by the checklist above.

## 9. Dummy byte literals for ephemeral keys — PyCryptodome SEC1 needs curve_name

**Where it bit:** `tests/test_envelope_relay_e2e.py` (round 10, replay test)

**Bug:** Test author tried to hand-craft a "dummy" ephemeral
public key as `base64.b64encode(b'\x02' + b'\x33' * 32).decode()`
thinking `\x02` (SEC1 uncompressed prefix) + 32 bytes would be
a valid EC public key shape. PyCryptodome's
`ECC.import_key(bytes)` rejected it:

```
ValueError: No curve name was provided
```

**Why:** SEC1-encoded public keys (starting with 0x02/0x03/0x04)
are just the X coordinate with a prefix — they don't embed
the curve OID. PyCryptodome needs the curve name passed
explicitly when importing raw SEC1 bytes. The 0x02 prefix tells
PyCryptodome "this is SEC1 compressed" but the curve is missing.

The 32 bytes after 0x02 are NOT a valid P-256 X coordinate
either (just `0x33` repeated), so even with `curve_name='P-256'`
it would fail validation.

**Fix:** use a properly-generated P-256 public key for the
dummy. Coder 2's test author SHOULD have used:

```python
def _dummy_ephemeral_pub_der() -> str:
    """Return a valid P-256 public-key DER (base64) for use as a
    stand-in ephemeral when the test never actually exchanges
    on the responder side."""
    global _DUMMY_EPH
    if _DUMMY_EPH is None:
        from Crypto.PublicKey import ECC
        _eph_key = ECC.generate(curve='P-256')
        _DUMMY_EPH = base64.b64encode(
            _eph_key.public_key().export_key(format='DER')
        ).decode()
    return _DUMMY_EPH
```

Generate once, reuse across the test session. The dummy is
fine as long as the test never actually decrypts with it
(only the encryption side uses the ratchet's chain state).

**General rule:** NEVER hand-craft crypto byte literals. Always
use a real generated keypair, even for "dummy" / "stand-in"
test fixtures. The bytes need to be VALID for the target
format AND VALID for the target curve. PyCryptodome, OpenSSL,
and `cryptography.hazmat` all have different opinion about
what bytes are valid.

**Detection:** `ValueError: No curve name was provided` in a
test that uses "dummy" or "fake" keys = smoking gun. The fix
is to use a real keypair, not to add `curve_name='P-256'`
to the import (the bytes are still invalid X coordinates).

**Pre-emptive brief boilerplate for crypto test coders:**

```
NEVER hand-craft EC key bytes. Even "dummy" / "stand-in"
public keys must come from a real keypair:

  from Crypto.PublicKey import ECC
  kp = ECC.generate(curve='P-256')
  dummy_pub_der = kp.public_key().export_key(format='DER')

For private keys, use the SAME keypair (or import a real
PEM/DER). Hand-crafted byte strings fail validation in
ways that look like library bugs but are actually invalid
X/Y coordinates.
```

## 10. Audit log via Python logging, not file write — capture pattern

**Where it bit:** `tests/test_audit_log_relay_endpoints.py` (round 10)

**Bug:** The `IRIS_AUDIT_LOG_PATH` env var is set in config.py
but no `FileHandler` is attached to the `GATEWAY` logger that
points at it. The audit log entries are emitted via
`log_gw.info(json.dumps({...}))` (Python `logging` module,
NOT direct file write). Tests that tried to read the file
got nothing — the file was empty.

**Why:** The audit log is a structured log line emitted via
the standard Python logging framework. The path config is a
marker for ops to point their FileHandler at, but the
production server may attach the handler in `setup_logging()`
(which the test fixture bypasses by using `Gateway.__new__`).
Tests running against a fixture-built Gateway never get the
FileHandler attached, so the env var points at a file that
nothing writes to.

**Fix:** attach a JSON-record capture handler to the GATEWAY
logger for the duration of the test, NOT read the file:

```python
import logging
import json

class _JsonRecordCapture(logging.Handler):
    """Capture log records whose message is JSON, return as list."""
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.records = []
    def emit(self, record):
        try:
            msg = record.getMessage()
            data = json.loads(msg)
            self.records.append(data)
        except Exception:
            pass  # not JSON (e.g. plain log lines)

@pytest.fixture
def audit_capture():
    handler = _JsonRecordCapture()
    log_gw = logging.getLogger('GATEWAY')
    log_gw.addHandler(handler)
    log_gw.setLevel(logging.DEBUG)
    yield handler
    log_gw.removeHandler(handler)
```

**General rule:** if the code under test emits via
`log_xxx.info(json.dumps(...))` (or any structured log
framework), use a logging.Handler subclass in tests to
capture the records, NOT file-based capture. File capture
requires the test environment to have set up the same
FileHandler the production environment uses, which is
brittle (bypassed in fixture-based tests, different paths
in CI, etc.).

**Detection:** if a test reads from a file path that comes
from a config setting (e.g. `AUDIT_LOG_PATH`) and the file is
empty, check whether the code writes to the file directly or
via a logger. If via a logger, attach a Handler to capture.

## 11. `node -e script` collides with top-level async IIFE — use a driver file

**Where it bit:** `tests/test_group_sender_key_js.py` (round 10,
initial version from Coder 1)

**Bug:** Coder 1's test used `subprocess.run(['node', '-e', script])`
to run a Node script that loaded the library and ran assertions.
The script wrapped the test body in an async IIFE:

```javascript
(async () => {
  try {
    {driver_body}
  } catch (e) { ... }
})();
```

Node's `node -e` (eval mode) choked on the IIFE call:

```
SyntaxError: Unexpected token '('
    at [eval]:55:        }();
                  ^
```

The IIFE pattern `}();` is valid in a browser script (where
the script tag auto-wraps in a function) but invalid at
top-level in `node -e` eval mode. The eval context doesn't
treat the IIFE as a statement-level expression.

**Fix:** use a dedicated driver file loaded via
`node path/to/driver.js` (CommonJS module mode), with
`TEST_CMD` env var to switch between test cases:

```python
NODE_DRIVER = _ROOT / "tests" / "group_sender_key_node.js"

def _run(cmd: str, **env_extras) -> dict:
    if NODE is None:
        pytest.skip('node not installed')
    env = os.environ.copy()
    env['TEST_CMD'] = cmd
    env.update(env_extras)
    proc = subprocess.run(
        [NODE, str(NODE_DRIVER)],
        capture_output=True, text=True, timeout=30, env=env,
    )
    out_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return json.loads(out_lines[-1])
```

And the driver file (`tests/group_sender_key_node.js`):
```javascript
const { webcrypto } = require('node:crypto');
globalThis.crypto = webcrypto;
const path = require('path');
const GSK = require(path.resolve(__dirname, '..', 'ui', 'group-sender-key.js'));
const { GroupSession } = GSK;

async function main() {
    const cmd = process.env.TEST_CMD;
    if (cmd === 'round_trip') { ... }
    if (cmd === 'three_member') { ... }
    // ... one branch per test case
}
main().catch(e => {
    console.log(JSON.stringify({ ok: false, error: String(e) }));
    process.exit(1);
});
```

**General rule:** when testing browser libraries (which use
top-level async IIFE, `window`, ES modules, etc.) from a
Python test via Node subprocess:

- **DO use a separate `.js` driver file** loaded via
  `node path/to/driver.js` (CommonJS mode)
- **DO use env vars** to switch test cases (TEST_CMD, etc.)
- **DO use `module.exports`** in the library so `require()`
  works (Coder 1 already did this — `module.exports` on Node,
  `window.GroupSenderKey` on browser)
- **DO NOT use `node -e script`** with IIFE patterns — eval
  mode doesn't support top-level async IIFE

**Detection:** `SyntaxError: Unexpected token '('` at the
closing `}();` of an async IIFE when called via `node -e` =
smoking gun. The fix is to switch to a driver file + env vars.

**Alternative: use `node --input-type=module`** if the
library uses ES modules (the `await` top-level is allowed
in ESM mode). But for CommonJS libraries (which is the
established pattern in this codebase), the driver file
is the cleaner approach.
