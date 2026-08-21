# Pulse Glow Aura — InstancedMesh Layering

**Session:** maze-crew-trailer (2026-05-25)
**Technique:** Co-located glow mesh via `getMatrixAt()`/`getColorAt()` readback

## The Problem

With a single `InstancedMesh(SphereGeometry(0.55))`, activation pulses are visible but lack dramatic presence. Bloom post-processing (EffectComposer + UnrealBloomPass) is expensive and overkill for a single-pulse glow — especially in a loop that must run at 60fps on mid-range GPUs.

The alternative: **layer a second InstancedMesh** at the same positions, with a larger sphere geometry, lower opacity, and shifted color. No post-processing.

## The Pattern

### Setup

```js
// Core pulse — small, bright, white
const PULSE_GEO = new THREE.SphereGeometry(0.55, 10, 6);
const PULSE_MAT = new THREE.MeshBasicMaterial({
  color: 0xffffff, transparent: true, opacity: 1,
  blending: THREE.AdditiveBlending, depthWrite: false,
});

// Glow aura — larger, softer, tinted
const GLOW_GEO = new THREE.SphereGeometry(1.8, 8, 5);  // ← ~3.3× larger radius
const GLOW_MAT = new THREE.MeshBasicMaterial({
  color: 0x8855ff, transparent: true, opacity: 0.18,   // ← low opacity, violet tint
  blending: THREE.AdditiveBlending, depthWrite: false,
});
```

### Build

Both meshes get the same instance count:

```js
let pulseMesh, pulseGlowMesh;

function buildPulseMesh() {
  pulseMesh = new THREE.InstancedMesh(PULSE_GEO, PULSE_MAT, 180);
  pulseMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(pulseMesh);

  pulseGlowMesh = new THREE.InstancedMesh(GLOW_GEO, GLOW_MAT, 180);
  pulseGlowMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  scene.add(pulseGlowMesh);
}
```

### Animate — Read back from primary, scale up for glow

The key insight: **don't duplicate the position/color math.** Instead, write the primary mesh first, then read its transforms back via `getMatrixAt()` and `getColorAt()` and apply them with modifications to the glow mesh.

```js
// ── WRITE primary mesh (standard pulse update loop) ──
let pCount = 0;
for (const p of allPulses) {
  // ... compute _dummy.position, _dummy.scale, _pCol ...
  _dummy.updateMatrix();
  pulseMesh.setInstanceMatrix(pCount, _dummy.matrix);
  pulseMesh.setColorAt(pCount, _pCol);
  pCount++;
}
// Hide unused instances
for (let i = pCount; i < 180; i++) {
  _dummy.position.set(0, -9999, 0);
  _dummy.scale.setScalar(0);
  _dummy.updateMatrix();
  pulseMesh.setInstanceMatrix(i, _dummy.matrix);
}
pulseMesh.instanceMatrix.needsUpdate = true;
if (pulseMesh.instanceColor) pulseMesh.instanceColor.needsUpdate = true;
pulseMesh.count = pCount;

// ── READ primary, WRITE glow ──
for (let i = 0; i < 180; i++) {
  if (i < pCount) {
    // Clone primary's matrix — all position/rotation inherited
    pulseMesh.getMatrixAt(i, _dummy.matrix);
    const s = _dummy.scale.x;            // read the scale from the cloned matrix
    _dummy.scale.setScalar(s * 2.6);      // scale up for glow halo
    _dummy.updateMatrix();
    pulseGlowMesh.setInstanceMatrix(i, _dummy.matrix);

    // Clone and tint primary's color
    pulseMesh.getColorAt(i, _pCol);
    _pCol.lerp(new THREE.Color(0x6644ff), 0.35);
    pulseGlowMesh.setColorAt(i, _pCol);
  } else {
    // Hide unused (same as primary)
    _dummy.position.set(0, -9999, 0);
    _dummy.scale.setScalar(0);
    _dummy.updateMatrix();
    pulseGlowMesh.setInstanceMatrix(i, _dummy.matrix);
  }
}
pulseGlowMesh.instanceMatrix.needsUpdate = true;
if (pulseGlowMesh.instanceColor) pulseGlowMesh.instanceColor.needsUpdate = true;
pulseGlowMesh.count = pCount;
```

## Why This Works

| Property | Core pulse | Glow aura | Effect |
|----------|-----------|-----------|--------|
| Radius | 0.55 | 1.8 | 3.3× bigger → visible halo |
| Scale multiplier | 0.3–1.0 | 0.78–2.6 | Scales proportionally → aura tracks core |
| Opacity | 1.0 | 0.18 | Soft, fades into background |
| Color | white | violet (#8855ff) | Warm→cool gradient through space |
| Blend | Additive | Additive | Both layers accumulate → bright core + soft glow |

## Performance

Two InstancedMeshes with 180 instances each = 360 draw calls. Three.js batches these efficiently. The `getMatrixAt()`/`getColorAt()` readback is a GPU → CPU round-trip per call, but at 180 instances it's well within budget at 60fps.

**If this becomes a bottleneck** (sustained 10k+ instances): pre-compute glow positions on CPU each frame instead of reading back from GPU. But for <500 instances, the readback approach is simpler and fine.

## Variations

- **Two-layer stacking**: add a third mesh (radius 4.0, opacity 0.06) for a very wide, very soft outer glow
- **Animated tint**: lerp the glow color toward different hues based on phase or beat
- **Rotated offset**: offset the glow mesh slightly (0.3 units) from the core for a directional flare effect
- **Size-based depth**: scale `s * 2.6` can be modulated by distance from camera for depth-of-field feel
