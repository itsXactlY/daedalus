# Three.js Living Viz — Walkable 3D Worlds + Cinematic Overlays

§15 Cinematic Post-Processing Overlays and §19 Walkable 3D Worlds
(PointerLock + Chambers + Doors), formerly inline in SKILL.md. Load with
`skill_view(file_path='references/walkable-3d.md')`.

---

### 15. Cinematic Post-Processing Overlays (Vignette + Film Grain)

For trailers and screen-recordable footage, two DOM overlay layers dramatically improve cinematic quality:

**Vignette** (pure CSS, zero runtime cost):
```css
#vignette {
  position: fixed; inset: 0; pointer-events: none; z-index: 4;
  background: radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.55) 100%);
}
```

**Film Grain** (throttled canvas noise):
- 128×128 canvas, monochrome random noise, updated at 20Hz (every 50ms)
- `mix-blend-mode: overlay` at 3.5% opacity — adds texture without obscuring detail
- `willReadFrequently: true` context hint for putImageData performance
- Cost: ~1.3MB/s memory bandwidth, negligible
- Pattern gives footage an organic film-stock feel vs "clean render" look

**Film grain is optional** — omit for dashboard/embedded views where it adds noise to text. Use for trailers, livestreams, and recordings.

## 19. Walkable 3D Worlds (PointerLock + Chambers + Doors)

A "maze" can be a beautiful orbiting cloud of nodes — but a **walkable** maze is a
different beast. The user is a person, not a camera. They expect rooms, doors,
floors, ceilings, and a way to know where they are. This section codifies the
pattern that emerged from building the mazemaker **Pandora's Box** (27 walkable
chambers, 8,300+ visible 3D objects, 5,000 instanced graph nodes, 7,800 edges,
first-person navigation): a hub-and-spoke world of interconnected rooms where
every door is a real portal and every chamber has a real description.

### 19.1 The Pattern in One Glance

```
                 ┌─ MONITORS HALL (N)  ─ 4×3 grid of 12 monitor rooms
                 │
                 ├─ CENTRAL NEURAL POOL (E)  ─ 5000 nodes, 7800 edges
                 │
HUB (atrium) ────┼─ 4 PHASE CHAMBERS (S)  ─ AWAKE / NREM / REM / INSIGHT
                 │
                 ├─ RECALL LIBRARY (W)  ─ bookshelves, recall terminal
                 │
                 └─ BRIDGE (N corridor)  ─ 32 skill archways → PEER_BRIDGE
                                          ↑ observation deck (y=8)
                                          ↗ portals hall (SE)
                                          ↘ federation vault (SE)
                                          ↙ atomizer (SW)
```

### 19.2 Stack Additions Beyond the Base Three.js Recipe

On top of the importmap + scene + camera + bloom pattern in Section 1, a walkable
world adds:

```js
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
const controls = new PointerLockControls(camera, renderer.domElement);
// Reasonable pitch limits prevent looking straight up/down (cinematic + safe)
controls.minPolarAngle = 0.2;
controls.maxPolarAngle = Math.PI - 0.2;
```

Pointer-lock is the only control scheme that gives true first-person presence.
The browser blocks the call until a user gesture — gate it behind a splash
overlay and call `controls.lock()` from a click handler. On macOS Safari the
request sometimes silently fails; in Chrome it always works.

### 19.3 The Room Catalog Pattern

Don't hardcode room coordinates in your movement logic. Build a **catalog**
where every room is a record with its own group, position, doors, and
description. This makes the world declarative and the navigation handler
dumb (look up `currentRoom.doors` and follow them):

```js
const ROOMS = [];  // array of room records
function addRoom(room){ ROOMS.push(room); return room; }
const ROOMS_BY_ID = new Map(ROOMS.map(r => [r.id, r]));

const hub = addRoom({
  id: 'HUB',
  name: 'HUB · central atrium',
  desc: 'the central chamber · eight corridors radiate outward',
  group: hubGroup,                    // THREE.Group, positioned via .position.copy(r.position)
  position: new THREE.Vector3(0,0,0),
  doors: [
    { to: 'MONITORS_HALL', dir: 'north', color: 0x9bf26b },
    { to: 'NEURAL_POOL',   dir: 'east',  color: 0xbf00ff },
    { to: 'PHASES',        dir: 'south', color: 0xff69b4 },
    { to: 'LIBRARY',       dir: 'west',  color: 0xffb547 },
    { to: 'BRIDGE',        dir: 'up',    color: 0x7be7ff },
  ],
});
// ... build MONITORS_HALL, NEURAL_POOL, etc., each addRoom({...})
// Then: for (const r of ROOMS) { r.group.position.copy(r.position); scene.add(r.group); }
```

**The cardinal directions in `doors[].dir` are the link between geometry and
logic.** When you enter a room through its west door, the code that handles
the transition uses `dirToVec('west')` to position you on the east side of the
new room, facing the door you just came through. See Section 19.7.

### 19.4 Building Blocks: `wall`, `floor`, `doorway`, `monitor`, `panel`

A walkable world is 80% repeated primitives. Author them once and stop
re-thinking geometry. The minimum kit:

```js
const FLOOR_Y = 0, CEIL_Y = 5.4, EYE = 1.65, WALL_T = 0.18;

function wall(w, h, d, color = 0x101015) {
  return new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshStandardMaterial({ color, roughness: 0.85 })
  );
}

function floor(w, d, color = 0x101015) {
  const m = new THREE.Mesh(
    new THREE.PlaneGeometry(w, d),
    new THREE.MeshStandardMaterial({ color, roughness: 0.9 })
  );
  m.rotation.x = -Math.PI/2;
  return m;
}

// A doorway is a glowing rectangle in a wall frame, with a sprite label
function doorway(label, opts = {}) {
  const w = opts.w || 2.6, h = opts.h || 3.4, d = 0.4;
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(w+0.3, h+0.3, d),
    new THREE.MeshStandardMaterial({ color: 0x101015, roughness: 0.7 })
  );
  const door = new THREE.Mesh(
    new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({
      color: opts.color || 0x9bf26b, transparent: true, opacity: 0.42,
      side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending,
    })
  );
  door.position.z = d/2 + 0.01;
  const outline = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.PlaneGeometry(w, h)),
    new THREE.LineBasicMaterial({ color: opts.color || 0x9bf26b })
  );
  outline.position.z = d/2 + 0.02;
  const lab = spriteLabel(label, { fontSize: 56, color: '#d6ffae', w: 1024, h: 200, scale: 3.2, aspect: 0.2 });
  lab.position.set(0, h/2 + 0.5, 0.15);
  const grp = new THREE.Group();
  grp.add(frame, door, outline, lab);
  grp.userData = { kind: 'door', label, door };
  return grp;
}

// A wall-mounted monitor with a CRT text texture
function monitor(label, opts = {}) {
  const w = opts.w || 3.0, h = opts.h || 1.9, d = 0.08;
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(w+0.18, h+0.18, d+0.05),
    new THREE.MeshStandardMaterial({ color: 0x05050a, roughness: 0.6 })
  );
  const screen = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    new THREE.MeshBasicMaterial({ map: opts.tex })
  );
  screen.position.z = 0.02;
  // glow plane behind for bloom contribution
  const glow = new THREE.Mesh(
    new THREE.PlaneGeometry(w*2.5, h*2.5),
    new THREE.MeshBasicMaterial({ color: opts.glowColor || 0x9bf26b, transparent: true, opacity: 0.18, depthWrite: false })
  );
  glow.position.z = -0.06;
  const grp = new THREE.Group();
  grp.add(frame, screen, glow);
  grp.userData = { kind: 'monitor', label, screen };
  return grp;
}
```

### 19.5 Door Raycaster — Interactive Room Transitions

A door is interactive only when the player is looking at it from close enough.
Standard pattern: every frame while `controls.isLocked`, fire a raycaster
from the camera's center, intersect the children of the current room's group
that have `userData.kind === 'door'`, and if there's a hit, show a tooltip
+ listen for the `E` key:

```js
const raycaster = new THREE.Raycaster();
raycaster.far = 4.0;
const pointer = new THREE.Vector2(0, 0);  // screen center
const keys = {};
addEventListener('keydown', e => keys[e.code] = true);
addEventListener('keyup',   e => keys[e.code] = false);

function checkDoorProximity() {
  raycaster.setFromCamera(pointer, camera);
  const room = ROOMS_BY_ID.get(currentRoomId);
  const candidates = [];
  room.group.traverse(o => {
    if (o.userData && o.userData.kind === 'door') candidates.push(o);
  });
  const hits = raycaster.intersectObjects(candidates, true);
  if (hits.length) {
    // walk up to the door group
    let g = hits[0].object;
    while (g && !(g.userData && g.userData.kind === 'door')) g = g.parent;
    if (g) {
      showTooltip(`→ ${g.userData.label}`, 'press E to enter');
      if (keys['KeyE']) {
        const target = room.doors.find(d => d.label === g.userData.label) || room.doors[0];
        if (target && target.to) switchRoom(target.to);
      }
    }
  } else hideTooltip();
}
```

**Always set `raycaster.far` to ~4 units.** Unbounded raycasters intersect
walls through floors and the player "teleports" into adjacent rooms. 4 units
matches a doorway's reach — close enough to look at the door, far enough to
glance at a corridor of doors.

**Walk up the parent chain with `while (g && !(...)) g = g.parent`.** The
raycaster hits the door's mesh child, not the group; the group is what carries
`userData`. One-liner, easy to miss.

### 19.6 Movement — WASD + Up/Down + Run

PointerLockControls only handles mouse-look. WASD needs to be wired in the
animation loop:

```js
if (controls.isLocked) {
  const speed = (keys['ShiftLeft'] || keys['ShiftRight']) ? 6.0 : 2.6;
  const forward = (keys['KeyW'] ? 1 : 0) - (keys['KeyS'] ? 1 : 0);
  const strafe  = (keys['KeyD'] ? 1 : 0) - (keys['KeyA'] ? 1 : 0);
  const upDown  = (keys['Space'] ? 1 : 0) - (keys['ControlLeft'] || keys['ControlRight'] ? 1 : 0);
  if (forward || strafe) {
    controls.moveForward(forward * speed * dt);
    controls.moveRight(strafe * speed * dt);
  }
  if (upDown) {
    camera.position.y = Math.max(0.5, Math.min(40, camera.position.y + upDown * speed * dt));
  }
  if (camera.position.y < 0.4) camera.position.y = 0.4;  // hard floor
  checkDoorProximity();
}
```

`controls.moveForward(d)` and `controls.moveRight(d)` are correctly oriented
relative to camera yaw — using raw `position.x += sin(yaw)*d` skips the
pitch compensation and players slide when looking up.

### 19.7 Room Switching — Position + Facing

When the player walks through a door, the code must (a) place them on the
opposite side of the next room, (b) face them back toward the door they came
through, (c) flash a room sign. Use the `dir` field on the door definition:

```js
function dirToVec(dir) {
  switch (dir) {
    case 'north': return new THREE.Vector3(0, 0, -1);
    case 'south': return new THREE.Vector3(0, 0,  1);
    case 'east':  return new THREE.Vector3( 1, 0, 0);
    case 'west':  return new THREE.Vector3(-1, 0, 0);
    case 'up':    return new THREE.Vector3(0,  1, 0);
    case 'down':  return new THREE.Vector3(0, -1, 0);
    default: return new THREE.Vector3(0, 0, 1);
  }
}

let currentRoomId = 'HUB';
function switchRoom(id) {
  if (!ROOMS_BY_ID.has(id)) return;
  const prev = ROOMS_BY_ID.get(currentRoomId);
  const next = ROOMS_BY_ID.get(id);
  currentRoomId = id;

  // Find the door in the new room that leads back to the previous room
  const doorEntry = next.doors && next.doors.find(d => d.to === prev.id);
  if (doorEntry) {
    const dv = dirToVec(doorEntry.dir);
    camera.position.set(
      next.position.x - dv.x * 5,
      EYE,
      next.position.z - dv.z * 5,
    );
  } else {
    camera.position.set(next.position.x, EYE, next.position.z + 4);
  }

  // Show room sign
  signName.textContent = next.name.toUpperCase();
  signDesc.textContent = next.desc;
  signEl.classList.add('show');
  setTimeout(() => signEl.classList.remove('show'), 4000);
  roomTitleEl.textContent = '// ' + next.name;
  // Log to inception queue
  pushInception(next);
}
```

The `- dv * 5` offset is critical. It places the player 5 units in the
*opposite* direction from the door — that is, *inside* the next room, facing
the wall they just walked through. Without the offset, players spawn *on top
of* the door and immediately walk back into the previous room.

### 19.8 The Canvas Mini-Map

A 2D canvas overlay showing the world from above, with the player as a
dot and a facing arrow, is the single best UX element for any walkable 3D
world. Without it, players get lost. With it, they explore confidently.

```js
const minimapC = document.getElementById('minimap');   // 230×230 HTML canvas
const mctx = minimapC.getContext('2d');

function drawMinimap() {
  const W = minimapC.width, H = minimapC.height;
  mctx.fillStyle = '#06060e';
  mctx.fillRect(0, 0, W, H);

  // grid background
  mctx.strokeStyle = 'rgba(155,242,107,0.07)';
  for (let i = 0; i < W; i += 32) { mctx.beginPath(); mctx.moveTo(i, 0); mctx.lineTo(i, H); mctx.stroke(); }
  for (let i = 0; i < H; i += 32) { mctx.beginPath(); mctx.moveTo(0, i); mctx.lineTo(W, i); mctx.stroke(); }

  // project room positions
  const cx = W/2, cy = H/2;
  const scale = 3.6;
  const offsetX = 0, offsetZ = -28;       // shift so the world fits centered
  for (const r of ROOMS) {
    if (r.id === 'OBSERVATION') continue; // skip out-of-plane rooms
    const px = cx + (r.position.x - offsetX) * scale;
    const py = cy + (r.position.z - offsetZ) * scale;
    const sz = roomSize(r);              // pick size by id
    mctx.fillStyle   = r.id === currentRoomId ? 'rgba(214,255,174,0.18)' : 'rgba(155,242,107,0.05)';
    mctx.strokeStyle = r.id === currentRoomId ? '#d6ffae' : '#4f7a37';
    mctx.fillRect(px - sz/2, py - sz/2, sz, sz);
    mctx.strokeRect(px - sz/2, py - sz/2, sz, sz);
    mctx.fillStyle = '#9bf26b';
    mctx.font = '9px JetBrains Mono';
    mctx.textAlign = 'center';
    mctx.fillText(r.id.replace(/_/g, ' '), px, py + sz/2 + 11);
  }

  // player dot + facing arrow
  const px = cx + (camera.position.x - offsetX) * scale;
  const py = cy + (camera.position.z - offsetZ) * scale;
  mctx.fillStyle = '#d6ffae';
  mctx.beginPath(); mctx.arc(px, py, 4, 0, Math.PI*2); mctx.fill();
  const dirVec = new THREE.Vector3();
  camera.getWorldDirection(dirVec);
  mctx.strokeStyle = '#d6ffae'; mctx.lineWidth = 2;
  mctx.beginPath();
  mctx.moveTo(px, py);
  mctx.lineTo(px + dirVec.x * 14, py + dirVec.z * 14);
  mctx.stroke();
}
```

Call `drawMinimap()` once per frame. Keep the canvas at fixed size (don't
make it responsive) — minimap should be a constant visual reference, not
rescale on window resize.

### 19.9 The Inception Queue (or: "What Have I Touched?")

A walkable world has memory of its own. Surface the last N rooms entered
as a DOM-side "history" list. It serves as breadcrumb trail, focus
restoration, and proof-of-exploration:

```js
const roomHistory = [];
function pushInception(room) {
  roomHistory.unshift({ id: room.id, name: room.name, t: elapsed });
  if (roomHistory.length > 8) roomHistory.pop();
  inceptionEl.innerHTML = roomHistory
    .map(r => `<div><span class="k">${r.t.toFixed(1)}s</span> <span class="v">${r.name}</span></div>`)
    .join('');
}
```

Pair with the `switchRoom()` call. Within 30 seconds of use, the queue
becomes the most-clicked UI element — users want to jump back to chambers
they liked.

### 19.10 Real-Data-as-Scene-Content

The single biggest difference between a "demo" maze and a "real" maze is
that the latter bakes **actual corpus data** into scene geometry and
textures. In the Pandora's Box, every monitor on every wall shows a real
description, every bookshelf holds real "label-prefix" colored tiles, every
archway in the bridge corridor has a real hermes-skill name, and the
central pool's 5,000 nodes sample the actual 14-class label distribution
(skill:, decision:, bug:, fact:, etc.) with their actual corpus hues.

**The pattern is: enumerate the live facts, then build the scene from the
enumeration.** Don't pre-design a room and then try to fit real data into
it. Let the data shape the room.

```js
// Curated facts at boot:
const CORPUS = { memories: 208810, edges: 103859, /* ... */ };
// 12 monitor descriptions from the actual product surface:
const M = [
  { id:'M01', name:'RECALL', desc:'semantic search · 9 channels · BGE-M3' },
  { id:'M02', name:'DREAM',  desc:'NREM/REM/Insight · 23,732 sessions' },
  // ... 12 entries
];
// 12 portals to real website routes:
const PORTALS = [
  { name:'/architect/', desc:'the architect dashboard', color:0x9bf26b },
  // ... 12 entries
];
// 32 archway labels sampled from the live skill list:
const BRIDGE_SKILLS = ['mazemaker','hermes-agent','btquant-...', /* 32+ */];
```

This is what makes the world feel **specific** rather than generic. The
player can read a monitor and think "oh, that's the actual recall system"
— not "this is a fake room about an imaginary engine".

### 19.11 Floor & Ceiling — Don't Forget the Ceiling

Most Three.js demos leave the skybox / ceiling transparent. In a walkable
world, the player will look up — the ceiling must exist or the immersion
breaks. Use a `MeshStandardMaterial` ceiling at `y = CEIL_Y` for each
chamber, slightly tinted with the chamber's accent hue at low opacity
(0.08-0.15) so the room color identity is visible from below:

```js
const ceil = new THREE.Mesh(
  new THREE.PlaneGeometry(W, D),
  new THREE.MeshStandardMaterial({ color: phaseHue, transparent: true, opacity: 0.10, roughness: 0.9 }),
);
ceil.rotation.x = Math.PI/2;
ceil.position.y = CEIL_Y;
```

### 19.12 Performance Budget

For a 27-chamber world with 5,000 instanced nodes + 7,800 line segments
+ ~150 door/arch meshes + 32 monitors + 4 phase orbs + 200 atomizer
particles:

| Subsystem | Cost per frame | Why it's fine |
|-----------|---------------|---------------|
| 5,000 instanced nodes | 5,000 matrix updates | Set once at build, then matrix updates only on per-node `fired` events (≤ 0.1% per frame) |
| 7,800 line segments | static after build | No per-frame work |
| 220 pulse particles | 220 matrix updates | Each one is a single Object3D.position + scale; trivial |
| 80 phase particles × 4 chambers | 320 matrix updates | Trivial |
| 4 phase orb rotations | 4 matrix updates | Trivial |
| Animation loop total | ~6,000 matrix updates/frame | < 1ms on a mid-tier GPU |

**Do NOT** use `setColorAt` on every instance every frame. Use the
`fired > 0` decay trick (Section 16) so only nodes that recently fired
need color updates. With ~5 transitions/frame out of 5,000 nodes, that's
0.1% of the per-instance color bandwidth.

### 19.13 Determinism: Mulberry32 + Seeded Box-Muller

A walkable world looks broken if the player can re-enter a room and see
different geometry. Seed everything:

```js
function rng(seed) {
  let a = seed >>> 0;
  return function() {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const RAND = rng(20260622);
function gauss() {
  let u = 0, v = 0; while (!u) u = RAND(); while (!v) v = RAND();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
```

Use `RAND()` for every random call during build. The same seed gives the
same maze. Critical for screen recording comparisons, shareable URLs, and
debugging visual glitches ("wait, was that always there?").

### 19.14 Hard Rules (Pitfalls Specific to Walkable Worlds)

**See also the consolidated Pitfalls section for cross-cutting rules
(GC, InstancedMesh API, etc.). These are walkable-world-specific:**

- **Never let camera.y go below 0.4.** A player who falls through the
  floor due to a "down" key glitch should hit a hard clamp, not fall
  forever into the void. One line: `if (camera.position.y < 0.4) camera.position.y = 0.4;`

- **Always set `raycaster.far`.** Unbounded raycasters hit through walls
  and adjacent rooms. 4 units is right for door-to-eye distance.

- **Always have a back-out path.** Every room must connect to at least one
  other room. The HUB is the safety net — if you can't find the way back,
  the player can't either. Verify connectivity: `for (const r of ROOMS) {
  if (r.doors.length === 0) console.error('orphan room:', r.id); }`

- **Don't build rooms behind conditional flags.** If a room "isn't ready",
  remove its door from the HUB. Don't hide it behind a runtime toggle —
  the player will still try to find the doorway, and the missing wall
  will be obvious.

- **Splash gate the pointer-lock call.** Browsers require a user gesture
  for `requestPointerLock`. Wrap everything in a click-to-enter overlay
  and call `controls.lock()` from the click handler. ESC releases
  pointer-lock — the player expects to be able to leave pointer-lock
  with ESC and re-enter with click.

### 19.15 The Splash Overlay — Gate the Pointer-Lock

PointerLockControls requires a user gesture. The standard pattern is a
full-screen splash overlay that the player clicks to enter:

```html
<div id="splash">
  <div class="badge">// MAZEMAKER · 2026-06-22 · alca-desk</div>
  <h1>PANDORA'S BOX<span>// every path is walkable</span></h1>
  <div class="oracle">"I can only show you the door..."</div>
  <div class="stats">
    <div><b>208,810</b>memories</div>     <!-- live data -->
    <!-- ... -->
  </div>
  <div class="start">[ CLICK TO ENTER ]</div>
  <div class="key">WASD · MOUSE · ESC to release</div>
</div>
```

```css
#splash {
  position: fixed; inset: 0;
  background: #06060e;
  z-index: 200;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center;
  cursor: pointer;
}
#splash.fade { opacity: 0; pointer-events: none; transition: opacity 1s ease; }
#splash .start {
  margin-top: 14px; padding: 14px 30px;
  border: 1px solid var(--phosphor);
  animation: pulse 2s ease-in-out infinite;
}
```

```js
const splash = document.getElementById('splash');
function start() {
  splash.classList.add('fade');
  setTimeout(() => splash.style.display = 'none', 1100);
  controls.lock();
}
splash.addEventListener('click', start);
addEventListener('keydown', e => {
  if (e.code === 'Enter' && !controls.isLocked) start();
  if (e.code === 'Escape') { controls.unlock(); splash.classList.remove('fade'); }
});
```

**The splash is also the perfect place to put a live-data stats block**
(memory count, edge count, skill count) — when the player clicks, they're
buying into a world with specific scale. From the Pandora's Box:

> **208,810** memories  ·  **103,859** edges  ·  **230+** skills
> **9** recall channels  ·  **7** cognition phases  ·  **4** dream phases
> **27** walkable chambers

This sets expectations before the player commits to a 30-minute walk.

### 19.16 IIFE Block-Scoped Room Construction

When you build 20+ rooms, room-local helper variables (positions, sizes,
counts, color tables) pollute the module scope if you put them all at
the top. Use an IIFE block to scope each room's build:

```js
// Section 5.5: RECALL LIBRARY
{
  const g = new THREE.Group();
  g.position.set(-38, 0, 0);
  const W = 32, D = 10;       // room-local dimensions
  const SHELF_COUNT = 14;     // room-local count
  // ... build floor, walls, ceiling, shelves, books, monitor, sign ...
  addRoom({
    id: 'LIBRARY', name: 'RECALL LIBRARY',
    desc: 'press R to open the recall input...',
    group: g, position: g.position.clone(),
    doors: [ { to: 'HUB', dir: 'east', color: 0xffb547 } ],
  });
}
```

The `{ ... }` block creates a lexical scope. `g`, `W`, `D`, `SHELF_COUNT` are
private to the room's build and can be reused in other rooms with different
values without conflict. The `addRoom()` call passes the group + a CLONED
position (so subsequent `r.group.position.copy(r.position)` in the assembly
loop doesn't double-translate the room).

**Why clone the position**: in the assembly loop:
```js
for (const r of ROOMS) { r.group.position.copy(r.position); scene.add(r.group); }
```
If `r.position` and `r.group.position` are the SAME `Vector3` (because
`g.position.set(x,0,z)` and `g.position.clone()` weren't both used), then
`.copy(r.position)` is a no-op and the group stays at (0,0,0). Pass
`position: g.position.clone()` to `addRoom`, not `g.position`.

### 19.17 Verify Existing Files Are Unchanged When Adding New Ones

When the user says "build a NEW version, DO NOT TOUCH existing code",
explicitly verify the old files are unchanged before AND after the build.
The Pandora's Box brief opened with this constraint; verifying it twice
was cheap and caught a temptation to "just add one line" to the existing
index.html that would have broken the constraint.

```bash
# BEFORE the build, capture the checksum
md5sum /path/to/architect/index.html > /tmp/before.md5
# Build the new file
# AFTER the build, verify nothing changed
md5sum /path/to/architect/index.html > /tmp/after.md5
diff /tmp/before.md5 /tmp/after.md5 && echo "UNTOUCHED" || echo "VIOLATED"
```

Or, in JS:
```js
const fs = require('fs');
const crypto = require('crypto');
const md5 = f => crypto.createHash('md5').update(fs.readFileSync(f)).digest('hex');
console.log('existing:', md5('/path/to/architect/index.html'));  // before
// ... build new file ...
console.log('existing:', md5('/path/to/architect/index.html'));  // after, must match
```

Real example from the Pandora's Box: `md5 index.html` returned
`d2fa25faca04864e9e49cd333c20b9ee` both before and after the build.
The new file went to a sibling path (`pandoras-box.html`) and the
existing file's content was byte-identical throughout the session.

- **Hard-cap upward movement.** A "fly" key (Space) is fun, but
  unbounded Y means the player leaves the world and looks at nothing.
  Cap at `y = 40` (above the highest structure, below the fog horizon).

