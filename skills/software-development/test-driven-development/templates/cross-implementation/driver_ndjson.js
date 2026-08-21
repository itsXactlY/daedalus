// Minimal NDJSON driver template for cross-implementation contract testing.
//
// Copy this file, replace the `// IMPLEMENTATION:` markers with your
// extracted class/module, and implement the op dispatchers for the
// operations you want to test.
//
// CLI:
//   echo '{"op":"decrypt","seed_b64":"...","envelope":{...}}' | node driver_template.js
// Prints one result per input line: plaintext strings as plain text,
// state objects as JSON.

const { webcrypto } = require('node:crypto');
globalThis.crypto = webcrypto;

// ── base64 <-> Uint8Array helpers ──────────────────────────────────
// IMPORTANT: byteOffset + byteLength for slices — see SKILL.md "Cross-platform
// b64 differences" pitfall.
function base64ToBytes(b64) {
  const bin = Buffer.from(b64, 'base64');
  return new Uint8Array(bin.buffer, bin.byteOffset, bin.byteLength);
}
function bytesToBase64(bytes) {
  return Buffer.from(bytes).toString('base64');
}

// ── IMPLEMENTATION: paste your extracted class/module here ────────
// Example: class SenderKeyRatchet { ... }

// ── Op dispatchers (customize per feature) ────────────────────────
// Each op takes input from the NDJSON line and pushes ONE result to `out`.
// The result is either a string (printed as plain text) or an object
// (printed as JSON). Errors are caught per-line and printed as
// `{"error": "..."}` so one bad op doesn't kill the driver.

async function dispatch(op) {
  if (op.op === 'decrypt') {
    // Example: const r = await SenderKeyRatchet.fromSeed(op.seed_b64);
    //          return await r.decrypt(op.envelope);
    throw new Error('decrypt op: replace with your implementation');
  }
  if (op.op === 'decrypt_seq') {
    // Decrypt N envelopes on ONE ratchet instance, preserving state
    // across decrypts. Returns [pt0, pt1, ..., ptN-1, serialized_state]
    // as separate lines.
    throw new Error('decrypt_seq op: replace with your implementation');
  }
  if (op.op === 'serialize') {
    // Return the ratchet's serialised state (for persisted-state roundtrip tests).
    throw new Error('serialize op: replace with your implementation');
  }
  if (op.op === 'version_check') {
    // Lightweight: just verify envelope.version is what we expect.
    if (op.envelope.version !== 1) throw new Error('bad version');
    return 'ok';
  }
  throw new Error('unknown op: ' + op.op);
}

// ── NDJSON driver loop ────────────────────────────────────────────
async function readStdin() {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}

(async () => {
  const input = await readStdin();
  const lines = input.trim().split('\n').filter(Boolean);
  const out = [];
  for (const line of lines) {
    try {
      const op = JSON.parse(line);
      out.push(await dispatch(op));   // ← AWAIT is critical here
    } catch (e) {
      process.stderr.write(`error on line: ${e.message}\n`);
      console.log(JSON.stringify({error: e.message}));
    }
  }
  for (const r of out) {
    if (typeof r === 'string') {
      process.stdout.write(r + '\n');
    } else {
      process.stdout.write(JSON.stringify(r) + '\n');
    }
  }
})();
