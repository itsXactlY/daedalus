// Minimal in-memory IndexedDB stub for browser-persistence code paths.
//
// Use when your JS implementation uses IndexedDB and you want to test
// it under Node without installing the `fake-indexeddb` npm package.
//
// HOW TO USE:
//   1. Copy the global setup (window, indexedDB, _idbStore) into your
//      driver file, BEFORE the extracted production code.
//   2. The extracted production code will call window.indexedDB.open(...)
//      etc. transparently — the stub satisfies those calls.
//   3. The stub persists across operations within a single Node run
//      (in-memory Map). It does NOT persist across runs.
//
// LIMITATIONS vs the real IndexedDB:
//   - No transactions: each operation is atomic, but read-then-write
//     sequences are NOT isolated. If the production code relies on
//     transaction isolation, this stub will hide bugs.
//   - No indexes: object stores are plain key-value Maps.
//   - No cursors: getAll() returns all values; iteration is plain Map
//     iteration.
//   - No versioning: db.objectStoreNames.contains() / createObjectStore
//     work, but onupgradeneeded is a no-op.
//
// If you need real IndexedDB semantics in Node, use the npm package
// `fake-indexeddb` instead. It's ~50 KB and a well-maintained drop-in.

// ── Setup (paste at top of driver file, before extracted code) ─────
const _idbStore = new Map();          // global Map keyed by (storeName, key)
globalThis.window = globalThis;       // production code uses `window.indexedDB`

// ── Stub IndexedDB ────────────────────────────────────────────────
globalThis.indexedDB = {
  open(dbName, version) {
    const req = { result: null, error: null };
    const handlers = { onsuccess: null, onerror: null, onupgradeneeded: null };
    setImmediate(() => {
      const db = makeFakeDb(dbName);
      req.result = db;
      // Production code often calls db.createObjectStore in
      // onupgradeneeded. Our stub already pre-creates stores on demand.
      if (handlers.onupgradeneeded) handlers.onupgradeneeded({ target: req });
      if (handlers.onsuccess) handlers.onsuccess({ target: req });
    });
    return req;
  }
};

function makeFakeDb(name) {
  return {
    name,
    version: 1,
    objectStoreNames: {
      contains(n) { return _idbStore.has(`${name}/${n}`); },
    },
    createObjectStore(n) {
      _idbStore.set(`${name}/${n}`, new Map());
      return { name: n };
    },
    transaction(storeNames, mode) {
      // For multi-store calls, take a list. Single string is fine too.
      const names = Array.isArray(storeNames) ? storeNames : [storeNames];
      const completed = { fired: false };
      const txHandlers = { oncomplete: null, onerror: null, onabort: null };
      const tx = {
        objectStore(storeName) {
          const mapKey = `${name}/${storeName}`;
          if (!_idbStore.has(mapKey)) _idbStore.set(mapKey, new Map());
          const map = _idbStore.get(mapKey);
          return {
            put(value, key) {
              const r = { result: key, error: null };
              map.set(key, value);
              setImmediate(() => completeTx(txHandlers, completed, tx));
              return r;
            },
            get(key) {
              const r = { result: null, error: null };
              r.result = map.has(key) ? map.get(key) : null;
              setImmediate(() => completeTx(txHandlers, completed, tx));
              return r;
            },
            delete(key) {
              const r = { result: null, error: null };
              map.delete(key);
              setImmediate(() => completeTx(txHandlers, completed, tx));
              return r;
            },
            getAll() {
              return Array.from(map.values());
            },
          };
        },
        ...txHandlers,
        // Async helpers to wait for the tx to settle.
        async _waitComplete() {
          while (!completed.fired) {
            await new Promise(r => setImmediate(r));
          }
        },
      };
      return tx;
    },
    close() {},
  };
}

function completeTx(txHandlers, completed, tx) {
  // A real tx fires oncomplete after ALL pending requests settle. Our
  // stub fires oncomplete once per put/get. For multi-step txs this
  // under-fires; in practice the production code only does 1-2 ops per
  // tx so this works. If you need multi-op atomicity, use fake-indexeddb.
  if (!completed.fired) {
    completed.fired = true;
    if (txHandlers.oncomplete) txHandlers.oncomplete({ target: tx });
  }
}

// ── Optional: in-memory localStorage stub ─────────────────────────
// If the extracted code also touches localStorage (e.g. for migration
// tests), include this too:
const _localStorage = new Map();
globalThis.localStorage = {
  getItem(k) { return _localStorage.has(k) ? _localStorage.get(k) : null; },
  setItem(k, v) { _localStorage.set(k, String(v)); },
  removeItem(k) { _localStorage.delete(k); },
};
