# Cross-Implementation Contract Testing

When the same logic exists in two languages (Python ↔ JS, Go ↔ Rust,
Python ↔ WASM, etc.), the wire format and crypto output MUST be byte-
identical. Unit-testing each side in isolation does NOT prove the
contract — only a test that runs both sides against the same inputs
and compares outputs does.

## When to use

- Any crypto, encoding, or serialization logic that has parallel
  implementations (client + server, frontend + backend, native + JS).
- Wire-format protocols where the producer and consumer are different
  languages (JSON-envelope APIs, gRPC between polyglot services,
  WebSocket message schemas).
- Migration scenarios: rewriting a module from language A to language B
  and needing to prove behaviour-preservation.

## The pattern (Python orchestrator + Node driver)

```
┌──────────────────┐                  ┌──────────────────┐
│  Python test     │  NDJSON stdin    │  Node driver     │
│  (pytest)        │ ───────────────► │  (subprocess)    │
│                  │ ◄─────────────── │                  │
│  - calls Python  │  NDJSON stdout   │  - imports code  │
│    encrypt/A     │  (results)       │    under test    │
│  - feeds env     │                  │  - runs decrypt/B│
│    to driver     │                  │  - emits results │
│  - asserts match │                  │                  │
└──────────────────┘                  └──────────────────┘
```

### Why this shape

- **Node is the only widely-available JS runtime with WebCrypto on
  CLI.** No browser, no jsdom, no playwright needed for crypto tests.
- **NDJSON over stdin/stdout** is the simplest cross-process contract:
  one op per line, easy to debug (`cat driver.js | node driver.js`).
- **Python orchestrator** stays in the existing test runner
  (`pytest`). All assertions, fixtures, and reporting happen where
  the rest of the suite lives.
- **Node driver is single-purpose**: extract the JS class, wire
  up a CLI, run ops. Throwaway once the test passes — but keep
  it in tree as a regression canary.

### Driver skeleton

```javascript
// driver.js — drop-in template for cross-impl contract tests
const { webcrypto } = require('node:crypto');
globalThis.crypto = webcrypto;

// 1. <PASTE THE JS CODE UNDER TEST HERE>
//    (extracted from the production source verbatim)
//    If it depends on globals like base64ToBytes, paste those too.

async function readStdin() {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}

(async () => {
  const lines = (await readStdin()).trim().split('\n').filter(Boolean);
  const out = [];
  for (const line of lines) {
    try {
      const op = JSON.parse(line);
      // 2. <HANDLE EACH OP> — e.g.:
      //    if (op.op === 'decrypt') {
      //      const r = await Klass.fromSeed(op.seed_b64);
      //      out.push(await r.decrypt(op.envelope));   // <-- await!
      //    }
    } catch (e) {
      process.stderr.write(`error: ${e.message}\n`);
      console.log(JSON.stringify({error: e.message}));
    }
  }
  for (const r of out) {
    if (typeof r === 'string') {
      process.stdout.write(r + '\n');      // strings plain
    } else {
      process.stdout.write(JSON.stringify(r) + '\n');  // objects as JSON
    }
  }
})();
```

### Orchestrator skeleton (Python)

```python
# test_xyz_contract.py
import base64, json, os, shutil, subprocess, sys, unittest
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)  # so 'import sender_key' works
import sender_key as py_impl       # the Python side under test

NODE = shutil.which('node')
DRIVER = os.path.join(PROJECT_ROOT, 'tests', 'driver.js')

def _run(ops):
    stdin = '\n'.join(json.dumps(o) for o in ops) + '\n'
    p = subprocess.run([NODE, DRIVER], input=stdin,
                       capture_output=True, text=True, timeout=30)
    if p.returncode != 0:
        raise RuntimeError(f'driver failed: {p.stderr}')
    return [l for l in p.stdout.split('\n') if l]

@unittest.skipUnless(NODE, 'node not installed')
class TestCrossImpl(unittest.TestCase):
    def test_roundtrip(self):
        seed = os.urandom(32)
        py_obj = py_impl.SomeClass.from_seed(seed)
        env = py_obj.encrypt('hello')
        out = _run([{'op': 'decrypt',
                     'seed_b64': base64.b64encode(seed).decode(),
                     'envelope': env}])
        self.assertEqual(out, ['hello'])
```

## Pitfalls (learned the hard way)

### Pitfall 1: forgot `await` in driver → `JSON.stringify(Promise)` = `"{}"`

```javascript
// WRONG — pushes a Promise object
out.push(r.decrypt(op.envelope));

// RIGHT — awaits the Promise, pushes the resolved string
out.push(await r.decrypt(op.envelope));
```

**Symptom**: test fails with `AssertionError: Lists differ: ['{}'] != ['expected text']`.
**Why it's silent**: `JSON.stringify(Promise)` returns `"{}"` (Promise has
no enumerable own properties). The driver returns valid JSON, the
orchestrator parses it fine, but the value is meaningless.
**Defence**: emit `typeof r === 'string'` check (skeleton above). If you
see `"{}"` in test output, the first thing to check is missing awaits.

### Pitfall 2: per-op seed reload loses state between decrypts

If you call `Klass.fromSeed(seed)` for every decrypt op, each call
starts with `chain_id=0`. For stateful crypto (ratchets, sequence
counters), this works ONLY if the producer and consumer agree on the
op index — typically `op_index_in_test == chain_id`.

**Better**: add a `decrypt_seq` op that takes ONE seed + a list of
envelopes and decrypts them all on a single instance. The driver
preserves internal state across decrypts.

```javascript
} else if (op.op === 'decrypt_seq') {
  const r = await Klass.fromSeed(op.seed_b64);
  for (const env of op.envelopes) {
    out.push(await r.decrypt(env));   // state preserved!
  }
  out.push(r.serialize());            // for restore-and-continue test
}
```

### Pitfall 3: Pyright/LSP noise on `@unittest.skipUnless`

```python
try:
    import sender_key
    _HAS_PY = True
except ImportError as e:
    _HAS_PY = False
    _PY_IMPORT_ERR = e
# Later: @unittest.skipUnless(_HAS_PY, f'import err: {_PY_IMPORT_ERR}')
```

LSP complains `_PY_IMPORT_ERR` is possibly unbound. **Fix**: initialize
both branches explicitly:

```python
try:
    import sender_key
    _HAS_PY = True
    _PY_IMPORT_ERR = None   # <-- bind in both branches
except ImportError as e:
    _HAS_PY = False
    _PY_IMPORT_ERR = e
```

### Pitfall 4: `os.path.dirname(os.path.dirname(__file__))` is TWO levels up

If the test file lives in the project root, `__file__` is `<root>/test_X.py`
and `dirname(dirname(__file__))` gives the PARENT of the project root.

```python
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))   # ONE level
# not dirname(dirname(...))   # TWO levels — wrong if file is at root
```

This off-by-one makes the driver path silently wrong; the test fails
with "driver not found" instead of a meaningful crypto error.

### Pitfall 5: same test name in two test methods → silently overwrites

If you use a loop to generate tests, ensure the name is unique per
iteration. `def test_msg_0`, `def test_msg_1`, etc. — or use
`subTest`, or pytest parametrize.

## When this pattern is NOT enough

- **Visual output parity** (canvas, SVG, PDF rendering): need
  Playwright + visual diff, not just text equality.
- **Async timing / race conditions**: the driver is single-threaded
  per op; real systems have concurrent decrypts. Stress tests need
  separate infra (see `scripts/load_test_sandbox.py` for the JRWL
  containerised-load approach).
- **Binary blob parity**: NDJSON is text — for raw bytes, base64 the
  blob and decode on the other side (the seed_b64 pattern above).
- **Network-protocol parity** (full HTTP/WS round-trips): use the
  real transport, not a CLI driver. This pattern is for pure-function
  contract verification.

## Verifying the contract

A passing test proves the implementations are byte-compatible on the
tested inputs. It does NOT prove:
- The contract covers all production cases (extend tests for any new
  shape the producer emits).
- The implementations handle malformed inputs identically (add a
  negative test for each known rejection reason).
- The implementations agree on key-derivation defaults (test with
  non-default salt/info strings, not just the happy-path ones).

The minimum viable contract test suite:
1. Single round-trip (encrypt → decrypt = original)
2. N sequential ops on one instance (state persistence)
3. Fast-forward / catch-up (out-of-order delivery)
4. Serialise-and-restore (state survives a reload)
5. Negative: bad version, bad MAC, malformed envelope
6. Edge: empty payload, max-length payload, unicode

If your suite has fewer than 6 cases, you probably have a test that
passes for the wrong reason (Pitfall 1 is the classic culprit).
