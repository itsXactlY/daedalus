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

## Pitfalls

- **`getImageData` is synchronous and blocks.** Don't call it per-frame on large regions. Only use it for glitch effects (small strips) or pre-rendering textures (once).
- **Canvas scaling with `drawImage` can blur.** If the card texture is much larger than screen, use `imageSmoothingEnabled = false` for pixelated look, or pre-render at target size.
- **No depth buffer.** Painter's algorithm (sort by Z before drawing) is the only way to handle overlapping 3D objects in Canvas 2D.
- **Text rendering on canvas uses system fonts.** Always provide fallbacks: `'bold 22px "JetBrains Mono", monospace'`.
- **`textToParticles` scan is O(W×H).** For large canvases, increase `spacing` or reduce resolution. A 1920×200 canvas at spacing=3 scans ~128K pixels — fast enough for init, not for per-frame use.
