# Test Fixture Patterns for Crew Coders Writing Tests

Reusable patterns extracted from the iris-messenger Phase 7 round
3 (WS ratchet) and round 2 (mesh cleanup) tests. Use these as
boilerplate when prompting a coder to write tests against a real
`gateway.py` handler that has coroutines, side effects, and
upstream mocks.

---

## Pattern 1: FakeWebSocket (drop-in for websockets.WebSocket)

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List
import json

@dataclass
class FakeWS:
    """Drop-in replacement for the websockets WebSocket connection.

    The real ws object exposes send(coroutine) and a close()
    coroutine. We only need send for these tests; if the handler
    ever calls close() on the fake, that means the WS connection was
    dropped on a crypto failure, which is exactly what some tests
    guard against.
    """
    sent_frames: List[dict] = field(default_factory=list)
    closed: bool = False

    async def send(self, payload: str) -> None:
        # payload is a JSON string per websockets protocol; parse so
        # tests can assert on the frame shape.
        self.sent_frames.append(json.loads(payload))

    async def close(self) -> None:
        self.closed = True
```

---

## Pattern 2: Run a coroutine to completion (per-test event loop)

```python
import asyncio

def _run(coro):
    """Run a coroutine to completion in a fresh event loop.

    Each test gets its own loop so the handler's awaits don't leak
    state between tests.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Pitfall:** never share an event loop across tests; pytest-asyncio
fixtures are fine but `asyncio.run()` in module scope will fail
when the module is reloaded.

---

## Pattern 3: FakeConnManager (record broadcast_to + configurable is_online)

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class FakeConnManager:
    """Capture broadcast_to calls without touching the real queue/batcher."""
    frames: List[Dict[str, Any]] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)

    def broadcast_to(self, identity_id: str, message: dict) -> int:
        self.calls.append(identity_id)
        self.frames.append({'to': identity_id, 'message': message})
        return 1

    def is_online(self, identity_id: str) -> bool:
        # Default offline — exercises the offline-store branch without
        # depending on the real ConnectionManager. Tests that want the
        # online path must patch this.
        return False
```

---

## Pattern 4: Pytest fixture for a real Gateway under tmp IRIS_DATA_DIR

```python
import os
import tempfile
import pytest

@pytest.fixture
def gw():
    """Real Gateway() under a tmp IRIS_DATA_DIR with use_dlm=False.

    use_dlm=False skips the redis DLM adapter so the test doesn't need
    a running podman stack. IRIS_DATA_DIR is set BEFORE the Gateway()
    is constructed so the IdentityStore / ContactManager / GroupStore
    pick up the tmp paths.
    """
    d = tempfile.mkdtemp(prefix="jrwl-test-<unique>-")
    os.environ['IRIS_DATA_DIR'] = d
    from gateway import Gateway
    g = Gateway(use_dlm=False)
    return g


@pytest.fixture
def authenticated_client():
    """A WSClient with authenticated=True and a fixed identity_id."""
    fake_ws = FakeWS()
    from gateway import WSClient
    c = WSClient(ws=fake_ws)
    c.identity_id = "abc12345"  # 8-char hex (validate_identity_id format)
    c.authenticated = True
    return c


@pytest.fixture
def fake_broadcast(gw):
    """Replace gw.conn_manager.broadcast_to + is_online with a recorder."""
    fake = FakeConnManager()
    gw.conn_manager.broadcast_to = fake.broadcast_to  # type: ignore
    gw.conn_manager.is_online = fake.is_online  # type: ignore
    return fake
```

---

## Pattern 5: Per-iteration mock side_effect setup (the critical pattern)

When the handler has two short-circuiting mocked functions
(e.g. `has_ratchet_session` then `ratchet_decrypt` where
no_session returns early), shared counters desync. Use per-iteration
setup inside the test loop:

```python
def test_handler_with_short_circuits(gw, authenticated_client, fake_broadcast):
    # Each entry: (input, has_session_return, decrypt_return, decrypt_raises)
    cases = [
        ({"id": 1}, True, "ok", False),     # decrypt called, returns
        ({"id": 2}, False, None, False),    # no session, short-circuits
        ({"id": 3}, True, None, True),      # decrypt raises
    ]

    has_session_mock = MagicMock()
    ratchet_decrypt_mock = MagicMock()

    with patch.object(gw.contact_manager, "get_shared_secret", return_value=b"\x33"*32), \
         patch.object(gw.message_relay, "send", side_effect=fake_relay_send), \
         patch.object(gw.conn_manager, "is_online", return_value=True), \
         patch.object(gateway, "METADATA_PAD_ENABLED", False):

        for i, (env, has_session_v, decrypt_ret, decrypt_raises) in enumerate(cases):
            # Configure mocks to read THIS iteration's entry. Default args
            # capture the value at lambda-creation time, so each iteration
            # gets a fresh lambda with the right v/ret/raises.
            has_session_mock.side_effect = lambda _a, _b, v=has_session_v: v
            if decrypt_raises:
                ratchet_decrypt_mock.side_effect = (
                    lambda _a, _b, _m, idx=i: (_ for _ in ()).throw(
                        RuntimeError(f"decrypt failure #{idx}")
                    )
                )
            else:
                ratchet_decrypt_mock.side_effect = lambda _a, _b, _m, r=decrypt_ret: r

            with patch.object(gateway, "ratchet_decrypt", ratchet_decrypt_mock), \
                 patch.object(gateway, "has_ratchet_session", has_session_mock):
                _run(handler(env))

    # Now assert: has_session called len(cases) times, decrypt called N times
    # where N = cases where has_session was True.
    assert has_session_mock.call_count == len(cases)
    assert ratchet_decrypt_mock.call_count == sum(1 for c in cases if c[1])
```

**Why per-iteration:** if you set `side_effect` once at module
level using a counter, envelope[1] (no_session) makes the counter
advance once (has_session), but NOT twice (no decrypt call) — so
envelope[2] reads the wrong slot. Per-iteration setup uses the
loop index `i` to pick the right entry every time, regardless of
how many calls each iteration makes.

---

## Pattern 6: "Already in target state" — the Coder 2 trick

When the task is "modify X to do Y" and Y may already be what X
does, AST-walk X to confirm:

```python
import ast

with open('gateway.py') as f:
    tree = ast.parse(f.read())

for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_push_message_to_client':
        # Look for ratchet_decrypt call sites
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and getattr(sub.func, 'id', None) == 'ratchet_decrypt':
                print(f"WARN: ratchet_decrypt called in _push_message_to_client at line {sub.lineno}")
                # If you find none, the function is already in target state
```

If the function is already correct, the coder's value-add is
**regression tests** that pin the behavior. Document the existing
implementation with a citation to the commit/round that added it.

---

## Pattern 7: AES-GCM non-determinism — structural assertion

`encrypt_message(plaintext, secret)` uses AES-GCM with a random
nonce, so the same inputs produce different ciphertexts each call.
Don't compare exact bytes:

```python
import base64

stored_payload = mirror_stores[0]["payload"]
decoded = base64.b64decode(stored_payload)
assert len(decoded) > len(plaintext) + 20, (
    f"Stored payload should be AES-GCM ciphertext "
    f"(plaintext + ~28B overhead), got {len(decoded)} bytes for "
    f"plaintext of {len(plaintext)} bytes"
)
assert plaintext.encode() not in decoded, (
    "Stored payload must NOT contain plaintext bytes — encryption failed"
)
```

---

## Pattern 8: Pre-emptive prompt boilerplate (paste into every test-writing coder prompt)

```
KNOWN TEST DESIGN GOTCHAS (avoid these):
  - AES-GCM uses random nonce — never compare exact ciphertext bytes
  - validate_identity_id needs 8-char hex recipient ("b0b12345", not "bob-test-id")
  - shared mock counters desync with short-circuits — use per-iteration side_effect
  - is_online=False → federation forward path (no recipient inbox store)
  - get_shared_secret=None → handler returns before storage even for ratchet
  - METADATA_PAD_ENABLED may be True from prior tests — patch to False if comparing bytes
  - For WebSocket tests, the recipient must pass validate_identity_id (8-char hex)
  - Sender IDs set via test fixture bypass validation, but recipients don't
  - federation.peers is empty in unit tests → "no_peers" receipt, not "queued"
```

Including this in the prompt saves 30+ minutes of parent-side
test-fix patches per coder. From round 3 data: ~10 patches to
fix test design issues in coder 1's test file, vs ~5 lines of
gateway.py that coder 1 actually added.
