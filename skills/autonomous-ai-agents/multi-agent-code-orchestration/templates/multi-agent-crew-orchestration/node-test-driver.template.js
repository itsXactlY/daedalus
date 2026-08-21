// tests/<name>_node.js
// ============================================================================
// Node driver for the <library-name> library.
//
// Loaded by tests/test_<name>_js.py via `node path/to/this/file.js` with
// a single env var TEST_CMD set to one of:
//   <list the test commands you implement>
//
// Reads env vars for inputs (TEST_PLAINTEXT, etc.) and prints exactly
// one JSON line on stdout describing the test outcome.
//
// Why a separate .js file (not `node -e`):
//   - `node -e` collides with the (async () => { ... }()); top-level
//     IIFE pattern that browser-compatible libraries use.
//   - Multi-line JS payloads in Python f-strings are hard to format.
//   - A real .js file can be syntax-checked, linted, and edited.
// ============================================================================

const { webcrypto } = require('node:crypto');
globalThis.crypto = webcrypto;
const path = require('path');

const LIB = require(path.resolve(__dirname, '..', 'ui', '<library>.js'));
const { /* public class names from your library */ } = LIB;

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64ToBytes(b64) {
    return Uint8Array.from(Buffer.from(b64, 'base64'));
}
function bytesToB64(bytes) {
    return Buffer.from(bytes).toString('base64');
}

// === helpers for the library's specific types ===

async function main() {
    const cmd = process.env.TEST_CMD;
    if (!cmd) throw new Error('TEST_CMD not set');

    if (cmd === 'round_trip') {
        // ... test scenario: build session, encrypt, decrypt, print
        //     {ok: bool, ...expected fields}
    }

    throw new Error(`unknown TEST_CMD: ${cmd}`);
}

main().catch(e => {
    console.log(JSON.stringify({ ok: false, error: String(e && e.stack || e) }));
    process.exit(1);
});
