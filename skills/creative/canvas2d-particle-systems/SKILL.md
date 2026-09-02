---
name: canvas2d-particle-systems
description: "Zero-dependency Canvas 2D particle animations — no Three.js, no WebGL, no CDN calls"
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  daedalus:
    tags: [canvas2d, particles, zero-dependency, creative-coding, generative-art, visualization, animation]
    related_skills: [p5js, threejs-living-viz, ascii-video, visual-mockup]
---

# Canvas 2D Particle Systems

Build zero-dependency particle animations and visual effects using only `CanvasRenderingContext2D` — no Three.js, no WebGL, no CDN calls. Use when the user wants animated visuals but can't or shouldn't use external libraries (no importmap, no npm, no network requests beyond site assets).

## When to use this skill

- User wants particle text, glowing effects, floating cards, starfields, glitch animations
- Three.js/Canvas 3D is not available (no importmap, no module support)
- Site has zero-dependency constraints (CDN blocks, offline-first, minimal payloads)
- Building art pieces, trailers, visualizations where the aesthetic matters more than performance
- The `wall-of-shame` pattern: particle text title + orbiting floating cards + ambient particles

## Core techniques

### 1. Particle text from pixel scan

Convert rendered text to particles by scanning pixel data from an offscreen canvas:

```js
function textToParticles(text, fontSize, color, canvasW, canvasH) {
  const offscreen = document.createElement('canvas');
  offscreen.width = canvasW;
  offscreen.height = canvasH;
  const octx = offscreen.getContext('2d');
  
  // Render white text on black background
  octx.fillStyle = '#000';
  octx.fillRect(0, 0, canvasW, canvasH);
  octx.font = 'bold ' + fontSize + 'px "JetBrains Mono", monospace';
  octx.fillStyle = '#fff';
  octx.textAlign = 'center';
  octx.textBaseline = 'middle';
  octx.fillText(text, canvasW / 2, canvasH / 2);

  // Scan pixels and collect white ones
  const imageData = octx.getImageData(0, 0, canvasW, canvasH);
  const positions = [];
  const spacing = 3; // px between particles (lower = denser)

  for (let y = 0; y < canvasH; y += spacing) {
    for (let x = 0; x < canvasW; x += spacing) {
      const idx = (y * canvasW + x) * 4;
      if (imageData.data[idx] > 128) { // white pixel
        positions.push(x - canvasW / 2, canvasH / 2 - y, 0);
      }
    }
  }

  return { positions: new Float32Array(positions), count: positions.length / 3 };
}
```

### 2. Floating cards with pre-rendered textures

Render card content to an offscreen canvas ONCE (not per frame), then draw with perspective scaling:

```js
function renderCardTexture(failure, cardW, cardH) {
  const tc = document.createElement('canvas');
  tc.width = cardW;
  tc.height = cardH;
  const cctx = tc.getContext('2d');
  
  // Draw card background, border, text, etc. on the texture canvas
  cctx.fillStyle = 'rgba(20, 0, 5, 0.85)';
  cctx.fillRect(0, 0, cardW, cardH);
  cctx.strokeStyle = '#ff0040';
  cctx.lineWidth = 3;
  cctx.strokeRect(4, 4, cardW - 8, cardH - 8);
  // ... more card content (title, description, category) ...
  
  return tc; // Return the canvas element
}

// In animation loop: draw with perspective scaling
const scale = FOV / (FOV + z);
ctx.save();
ctx.translate(sx, sy);
ctx.scale(cardScreenW / CARD_W, cardScreenH / CARD_H);
ctx.drawImage(texture, -CARD_W / 2, -CARD_H / 2, CARD_W, CARD_H);
ctx.restore();
```

### 3. Starfield + ambient particles

**Starfield on a sphere** (uniform distribution via spherical coordinates):
```js
for (let i = 0; i < STAR_COUNT; i++) {
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  const r = 300 + Math.random() * 600;
  stars.push({
    x: r * Math.sin(phi) * Math.cos(theta),
    y: r * Math.sin(phi) * Math.sin(theta),
    z: r * Math.cos(phi),
    brightness: 0.3 + Math.random() * 0.7
  });
}
```

**Ambient floating particles** (box distribution with drift):
```js
for (let i = 0; i < AMBIENT_COUNT; i++) {
  ambientParticles.push({
    x: (Math.random() - 0.5) * W,
    y: (Math.random() - 0.5) * H,
    z: (Math.random() - 0.5) * 40 - 10,
    vx: (Math.random() - 0.5) * 0.3,
    vy: (Math.random() - 0.5) * 0.2,
    vz: (Math.random() - 0.5) * 0.1
  });
}
```

### 4. 3D projection helper

Simple perspective projection — no matrix libraries needed:

```js
const FOV = 600;
function project(x, y, z) {
  const scale = FOV / (FOV + z);
  return { sx: x * scale + W / 2, sy: y * scale + H / 2, scale: scale };
}
```

**PITFALL — z-unit mismatch (bites silently):** `FOV/(FOV+z)` assumes z is in
normalized units (~[-1,1]). If your base positions are in PIXEL units (e.g. a
cloud of radius ≈235px), z spans ±300 and the divide collapses far nodes to
~0.01 scale — and any node with z < -FOV gets a NEGATIVE scale, so sprites
draw with negative dimensions and vanish. No error is thrown; `drawImage`
with NaN/negative dims silently no-ops. Fix: normalize before the divide and
clamp outliers:

```js
const zn = clamp(z / CLOUD_RADIUS, -1, 1);       // px → unit
const scale = FOV / (FOV + zn * FOV_DEPTH);      // now sc ∈ [~0.75, ~1.5]
```

Detection trick: instrument one frame and assert `mean(spriteRadius) > 0` and
`min(scale) > 0`. A mean radius of ≈0 or negative means unit mismatch, not
"too small art".

### 5. CSS-only effects (cheaper than canvas)

Use CSS for overlay effects — they're composited by the browser and don't hit the animation loop:

| Effect | Technique |
|--------|-----------|
| **Scanlines** | `repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.04) 2px, rgba(0,0,0,0.04) 4px)` |
| **Vignette** | `radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.7) 100%)` |
| **Cursor glow** | `radial-gradient(circle, rgba(255,0,64,0.08) 0%, transparent 70%)` + mouse tracking |
| **Chromatic aberration** | CSS pseudo-elements (`::before`/`::after`) with `transform: translate()` animation |
| **Glitch strips** | CSS `@keyframes` toggling `opacity: 0` → `1` on overlay elements |

### 6. Canvas glitch effects

Random horizontal strip displacement via `getImageData`/`putImageData`:

```js
// Random horizontal strip displacement
if (Math.random() < 0.02) {
  const stripY = Math.random() * H;
  const stripH = 2 + Math.random() * 8;
  const shift = (Math.random() - 0.5) * 30;
  const slice = ctx.getImageData(0, Math.floor(stripY), W, Math.floor(stripH));
  ctx.putImageData(slice, Math.floor(shift), Math.floor(stripY));
}

// Chromatic aberration on glitch strip
if (Math.random() < 0.3) {
  const sliceR = ctx.getImageData(0, Math.floor(stripY), W, Math.floor(stripH));
  ctx.putImageData(sliceR, 2, Math.floor(stripY));
}
```

### 7. Bloom/glow via canvas overlay pass

After drawing main content, add a subtle bloom overlay:

```js
const bloomStrength = 1.8 + Math.sin(elapsed * 0.5) * 0.3;
if (bloomStrength > 2.0) {
  ctx.fillStyle = 'rgba(255, 0, 64, ' + ((bloomStrength - 1.8) * 0.05).toFixed(3) + ')';
  ctx.fillRect(0, 0, W, H);
}
```

## Architecture: the Wall of Shame pattern

The `wall-of-shame.html` file demonstrates the complete architecture:

```
┌─────────────────────────────────────┐
│  CSS overlays (scanlines, vignette) │ ← Compositor layer, no JS
├─────────────────────────────────────┤
│  Canvas 2D (main render loop)      │
│  ┌───────────────────────────────┐  │
│  │ Starfield (sphere distribution)│  │
│  │ Ambient particles (box drift)  │  │
│  │ Title particles (pixel scan)   │  │
│  │ Floating cards (painter's alg) │  │
│  └───────────────────────────────┘  │
├─────────────────────────────────────┤
│  DOM overlays (title, counter)      │ ← Selectable text, not canvas
└─────────────────────────────────────┐
```

Key design decisions:
- **DOM for selectable text** (title, counter) — canvas text is not selectable or accessible
- **CSS for overlays** (scanlines, vignette, cursor glow) — browser compositor handles these, zero JS cost
- **Canvas for content** (particles, cards, starfield) — needs per-frame animation
- **Painter's algorithm** for card depth sorting (sort by Z before drawing)

## Performance targets

| Metric | Target |
|--------|--------|
| Frame rate | 60fps sustained |
| Particle count (rect fills) | 2,000-5,000 at 60fps |
| Starfield points | 500-1,000 at 60fps |
| Card textures | Pre-rendered once, drawn via `drawImage` per frame |
| File size (HTML) | < 30KB self-contained |

## Performance tips

- **Pre-render textures once.** Never call `renderCardTexture()` inside the animation loop — create textures in init and reuse them with `drawImage`.
- **Use `Float32Array` for particle positions.** Typed arrays are faster than regular arrays.
- **Skip off-screen particles.** Check bounds before drawing: `if (pp.sx < -10 || pp.sx > W + 10) continue;`
- **CSS for overlays, canvas for content.** Scanlines, vignette, cursor glow — all pure CSS. Canvas is expensive.
- **Particle density = spacing².** A spacing of 3px gives ~1/9 the particles of 1px spacing. Tune to target FPS.

## Advanced visualization patterns

### Phase state machine (NREM → REM → INSIGHT)

Drive visual transitions between discrete states with timed duration and per-phase behavior:

```js
const PHASE_DURATIONS = { AWAKE: 4, NREM: 6, REM: 5, INSIGHT: 3 }; // seconds
let currentPhase = "AWAKE";
let phaseTimer = 0;

function updatePhase(elapsed) {
  const duration = PHASE_DURATIONS[currentPhase];
  phaseTimer += 1/60;

  if (phaseTimer >= duration) {
    phaseTimer = 0;
    const phases = ["AWAKE", "NREM", "REM", "INSIGHT"];
    const idx = phases.indexOf(currentPhase);
    currentPhase = phases[(idx + 1) % phases.length];
    // Phase transition: trigger effects
    onPhaseChange(currentPhase);
  }

  // UI update
  document.getElementById("statPhase").textContent = "phase: " + currentPhase;
}

function onPhaseChange(phase) {
  if (phase === "NREM") {
    // Slow drift, grey tones, dim connections
    particles.forEach(p => { p.vx *= 0.5; p.vy *= 0.5; });
  } else if (phase === "REM") {
    // Attraction to targets, ember flickering
    particles.forEach(p => {
      const target = memories[Math.floor(Math.random() * memories.length)];
      p.vx = (target.x - p.x) * 0.02;
      p.vy = (target.y - p.y) * 0.02;
    });
  } else if (phase === "INSIGHT") {
    // Burst of energy, golden particles, memory consolidation
    consolidateMemories();
    particles.forEach(p => {
      p.vx = (Math.random() - 0.5) * 6;
      p.vy = (Math.random() - 0.5) * 6;
    });
  }
}
```

Per-phase visual effects map to colors, particle speed, connection density, and trail alpha:

| Phase | Particle color | Trail alpha | Connection style | Special effect |
|-------|---------------|-------------|-----------------|----------------|
| AWAKE | violet (139,92,246) | 0.10 | moderate glow | subtle breathing pulse |
| NREM | grey (107,114,128) | 0.12 | dim, sparse | slow drift, nodes dim randomly |
| REM | ember (209,85,43) | 0.08 | flickering lines | random horizontal flicker strips |
| INSIGHT | amber (245,158,11) | 0.06 | bright, dense | golden burst particles |

### Maze / node graph generation

Build a grid-based node structure with adjacency edges — useful for architecture diagrams, knowledge graphs, and maze-like visuals:

```js
const gridSize = 6;
const cellSize = 80;
const grid = {};
const nodes = [];
const edges = [];

// Generate grid nodes with random gaps
for (let gx = -gridSize; gx <= gridSize; gx++) {
  for (let gz = -gridSize; gz <= gridSize; gz++) {
    if (Math.random() < 0.3) continue; // random gaps
    const node = {
      x: gx * cellSize + (Math.random() - 0.5) * 20,
      y: (Math.random() - 0.5) * 100,
      z: gz * cellSize + (Math.random() - 0.5) * 20,
      gx, gz, // grid coordinates for edge generation
      pulse: Math.random() * Math.PI * 2,
      active: true
    };
    nodes.push(node);
    grid[`${gx},${gz}`] = node;
  }
}

// Connect adjacent grid nodes (with probability for organic feel)
nodes.forEach(n => {
  const dirs = [[1,0],[-1,0],[0,1],[0,-1]];
  dirs.forEach(([dx, dz]) => {
    const key = `${n.gx + dx},${n.gz + dz}`;
    if (grid[key] && Math.random() < 0.7) {
      edges.push({ from: n, to: grid[key], strength: Math.random() * 0.5 + 0.3 });
    }
  });
});
```

### Memory nodes with consolidation mechanics

Special persistent nodes that "consolidate" during certain phases — useful for dream visualization, knowledge graph evolution, and state persistence:

```js
const memories = [];

// Create memory nodes at random positions
for (let i = 0; i < 15; i++) {
  const angle = Math.random() * Math.PI * 2;
  const radius = 150 + Math.random() * 200;
  memories.push({
    x: Math.cos(angle) * radius,
    y: (Math.random() - 0.5) * 150,
    z: Math.sin(angle) * radius,
    pulse: Math.random() * Math.PI * 2,
    active: true,
    memory: true,
    id: "M" + i,
    strength: Math.random() // 0-1, increases on consolidation
  });
}

function consolidateMemories() {
  let count = 0;
  memories.forEach(m => {
    if (!m.consolidated && Math.random() < 0.3) {
      m.strength = Math.min(1, m.strength + 0.3);
      m.consolidated = true;
      count++;
    }
  });
  // Reset some for continuous dreaming
  if (count > 5) {
    memories.forEach(m => {
      if (m.consolidated && Math.random() < 0.2) {
        m.consolidated = false;
        m.strength *= 0.7; // partial decay
      }
    });
  }
}

// Draw memory nodes with glow proportional to strength
memories.forEach(m => {
  const size = (4 + m.strength * 8) * scale;
  const glowColor = m.consolidated
    ? `rgba(245,158,11,${0.3 * scale})` // amber for consolidated
    : `rgba(139,92,246,${0.15 * scale})`; // violet for unconsolidated
  ctx.beginPath();
  ctx.arc(sx, sy, size * 2, 0, Math.PI * 2);
  ctx.fillStyle = glowColor;
  ctx.fill();
});
```

### Zoom camera + mouse orbit

Combine scroll-to-zoom with mouse-driven rotation:

```js
let zoom = 1;
document.addEventListener("wheel", e => {
  zoom = Math.max(0.3, Math.min(2.5, zoom - e.deltaY * 0.001));
});

function project(x, y, z) {
  const scale = (FOV * zoom) / (FOV + z); // zoom scales FOV
  return { sx: x * scale + W / 2, sy: y * scale + H / 2, scale: scale };
}

// Mouse orbit vs auto-orbit fallback
let mouseX = 0, mouseY = 0;
let autoOrbit = true;
document.addEventListener("mousemove", e => {
  mouseX = (e.clientX / W - 0.5) * 2;
  mouseY = (e.clientY / H - 0.5) * 2;
  autoOrbit = false;
  clearTimeout(window._orbitTimer);
  window._orbitTimer = setTimeout(() => { autoOrbit = true; }, 5000);
});

function rotatePoint(x, y, z) {
  const camRotX = autoOrbit ? elapsed * 0.03 : mouseY * 0.4;
  const camRotY = autoOrbit ? elapsed * 0.06 : mouseX * 0.6;
  // Rotate around Y then X
  const cosA = Math.cos(camRotY), sinA = Math.sin(camRotY);
  const rx = x * cosA - z * sinA;
  const rz = z * cosA + x * sinA;
  const cosB = Math.cos(camRotX), sinB = Math.sin(camRotX);
  const ry = y * cosB - rz * sinB;
  return { x: rx, y: ry, z: rz };
}
```

### Trail effects with phase-specific alpha

Clear the canvas with partial transparency to create motion trails. The alpha value changes per phase for different "feel":

```js
let trailAlpha = 0.10; // default AWAKE
if (currentPhase === "NREM") trailAlpha = 0.12; // slightly more trail
else if (currentPhase === "REM") trailAlpha = 0.08; // less trail, sharper motion
else if (currentPhase === "INSIGHT") trailAlpha = 0.06; // very sharp, fast

ctx.fillStyle = `rgba(8,6,4,${trailAlpha})`;
ctx.fillRect(0, 0, W, H);
```

### DOM overlay labels tracking projected screen positions

For node labels that track their 3D position on screen, update DOM element positions each frame:

```js
// Create a DOM label for each memory node
memories.forEach(m => {
  const label = document.createElement("div");
  label.className = "node-label";
  label.textContent = m.id;
  label.style.position = "fixed";
  label.style.pointerEvents = "none";
  label.style.zIndex = "10";
  label.style.fontFamily = '"JetBrains Mono", monospace';
  label.style.fontSize = "8px";
  label.style.color = "rgba(245,158,11,0.6)";
  document.body.appendChild(label);
  m.labelEl = label; // store reference
});

// In animation loop, update positions:
memories.forEach(m => {
  const rn = rotatePoint(m.x, m.y, m.z);
  const pn = project(rn.x, rn.y, rn.z + 300);
  if (pn.scale > 0.6) { // only show when close enough
    m.labelEl.style.left = pn.sx + "px";
    m.labelEl.style.top = (pn.sy - 12) + "px";
    m.labelEl.style.display = "block";
  } else {
    m.labelEl.style.display = "none";
  }
});
```

## Pitfalls

- **`getImageData` is synchronous and blocks.** Don't call it per-frame on large regions. Only use it for glitch effects (small strips) or pre-rendering textures (once).
- **Canvas scaling with `drawImage` can blur.** If the card texture is much larger than screen, use `imageSmoothingEnabled = false` for pixelated look, or pre-render at target size.
- **No depth buffer.** Painter's algorithm (sort by Z before drawing) is the only way to handle overlapping 3D objects in Canvas 2D.
- **Text rendering on canvas uses system fonts.** Always provide fallbacks: `'bold 22px "JetBrains Mono", monospace'`.
- **`textToParticles` scan is O(W×H).** For large canvases, increase `spacing` or reduce resolution. A 1920×200 canvas at spacing=3 scans ~128K pixels — fast enough for init, not for per-frame use.
- **Phase state machine timing.** Use `1/60` (not `elapsed`) for phase timer increments to avoid drift from variable frame rates. If you need precise timing, track `phaseStartTime` and compute `elapsed - phaseStartTime`.
- **DOM overlay labels get expensive.** Don't create more than ~30 tracked DOM elements — each one needs a position update per frame. For larger sets, render labels to offscreen canvas textures instead.
- **Trail alpha too low = ghosting.** Below 0.05 the screen never fully clears and colors bleed into each other. Above 0.20 there's no trail effect at all. Sweet spot: 0.06–0.15.
