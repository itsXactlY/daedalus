# Maze Crew Loop — Session Detail

**Created:** 2026-05-24

## Context
Autonomous cron-driven iteration loop that improves three Three.js visualization files in rotation:
1. `maze-crew-bio.html` — biological organism view (nodes as tissue, traveling activation pulses)
2. `maze-crew-dream.html` — dream engine (NREM/REM/Insight phase cycling as brain sleeping/awakening)
3. `maze-crew-trailer.html` — cinematic 20s camera flythrough

Rotation: bio → dream → trailer → bio → ...

Iteration log: `public/maze-crew-ITERATION-LOG.md`

## Guiding Principles
- Visualize **cognition, not structure** — no explicit nodes/edges/labels
- Biological/cosmic aesthetic throughout
- Dream phases feel like a brain sleeping/dreaming/awakening
- Thought propagation — activation visibly travels between regions
- Infinite feel via distant fog-of-war structures
- The maze as a character — mood, heartbeat, emotional tonality
- Screen-recordable (looks amazing as a 7-second clip)

## What We Built (Run #1: maze-crew-bio.html, 710 lines)

### Architecture
- Three.js via CDN importmap (`three@0.163.0`) — no build step
- Connects to mazemaker pod at `127.0.0.1:8765` for live data + WS events
- Falls back to synthetic data if pod unreachable

### Techniques Used

**Instanced Tissue Nodes:**
`InstancedMesh(SphereGeometry(1,8,6), MeshPhongMaterial)` per region, ~600 nodes total.
Per-instance scale and color set via `dummy.updateMatrix()` + `setColorAt()`.
More organic than Three.js `Points` approach from base skill — spheres feel like cells.

**Membrane Hulls:**
`BackSide` sphere mesh around each node cluster, very low opacity (0.15), `depthWrite: false`.
Gives a translucent envelope — like a cell membrane around tissue.

**Gaussian Clustering:**
Box-Muller transform for node positions (not uniform random):
```js
function gaussian() {
  let u=0, v=0;
  while(u===0) u=Math.random();
  while(v===0) v=Math.random();
  return Math.sqrt(-2.0*Math.log(u)) * Math.cos(2.0*Math.PI*v);
}
```

**Traveling Activation Pulses:**
Discrete events (not continuous streams) — glowing spheres traveling along random edges.
Eased arc trajectory with quadratic ease-in-out + sine vertical lift.
Rendered as InstancedMesh with ~200 capacity, hiding unused instances by scale=0.

**Fog-of-War Distant Structures:**
8 wireframe IcosahedronGeometry at r=45-65 from center, opacity 0.12.
Internal glow sphere at opacity 0.06 for depth.
Suggest infinite extent beyond the visible data.

**Phase-Responsive Heartbeat (DOM):**
CSS heartbeat with `pow(sin, 6)` for sharp spike, triggered by phase pulse speed.
Not a 3D element — a fixed-position DOM overlay.

**Phase Lerping:**
Fog color, background color, tissue node colors all lerp toward phase target using:
`lerpSpeed = 1 - Math.exp(-2.5 * dt)` for frame-rate-independent smooth transitions.

### HUD Controls
- Space = advance phase manually (with RGB hue-rotate flash on transition)
- R = toggle auto-rotation
- F = toggle fullscreen
- H = toggle HUD visibility
- Drag = orbit, scroll = zoom, double-click = reset camera

### File Location
`/home/alca/projects/mazemaker-architect/public/maze-crew-bio.html`
