### 14. Orbit Control API Symmetry

When wrapping Three.js orbit state in a public `orbitCtrl` object (with `theta`, `phi`, `radius`), **all three properties must have matching getter/setter treatment**. A common asymmetry bug:

```js
// ❌ WRONG
orbitCtrl = { updateCam,
  get theta() { return theta; set theta(v) { theta = v; updateCam(); } },
  radius, phi   // ← plain properties — writes bypass updateCam()
};
// Any external code that does orbitCtrl.phi = newVal skips the camera matrix update.

// ✅ RIGHT
orbitCtrl = { updateCam,
  get theta()  { return theta;  set theta(v)  { theta = v;  updateCam(); } },
  get phi()    { return phi;    set phi(v)    { phi = v;    updateCam(); } },
  get radius() { return radius; set radius(v) { radius = clamp(v, 8, 120); updateCam(); } }
};
// All three invalidate the camera matrix transparently — no call site needs workarounds.
```

**Why it fails:** `radius += delta` in a scroll handler reads from the stale `orbitCtrl.radius` plain-copy (unchanged by the actual scroll) and writes to a second unrelated copy. The real closure `radius` inside the constructor is never updated, so `updateCam()` never gets the new value. The camera drifts or snaps back on the next user gesture — making the bug look non-deterministic.

**Fix:** `get/set` on every orbitCtrl property. Clamp inside the setter, not at the call site.
