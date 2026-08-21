# Three.js Living Viz — Refactoring Tips & See-Also Details

Refactoring guidance (retarget animate(), central data object, mazemaker.online
design tokens) formerly inline in SKILL.md. Load with
`skill_view(file_path='references/refactoring-tips.md')`.

---

### Retarget animate() When Refactoring the Rendering Path

When a refactor swaps the underlying Three.js object (e.g. `InstancedMesh`
→ `Points` + `ShaderMaterial`, or `Mesh` → `InstancedMesh`), the
`animate()` function that drives the visual every frame must be rewritten
in lockstep — it has a different contract with the new object.

| Old (InstancedMesh) | New (Points + ShaderMaterial) |
|---------------------|------------------------------|
| Per-frame: loop 5,000 nodes, `setMatrixAt(i, …)` | Per-frame: push 5 uniforms |
| Per-frame: loop again, `setColorAt(i, …)` on fired events | Per-frame: nothing else — all animation in vertex shader |
| GC pressure from `new Object3D()` per frame | Zero allocations |
| 6,000+ matrix updates/frame | 5 uniform writes/frame |

The failure mode when you forget to retarget: console throws
`TypeError: NEURAL_NODES.setMatrixAt is not a function` (or silent no-op
if it's a method that exists on Points but does nothing). The pod init
log fires *before* the error because `podInit()` runs in a separate
async chain — checking only the console log is not enough; the HUD
position must be advancing too.

**Audit grep for the refactor**:
```bash
# Find every per-instance API call that won't exist on Points:
grep -n 'setMatrixAt\|setColorAt\|instanceMatrix\|instanceColor' path/
# All of these should be REMOVED when the rendering path is Points+Shader.
```

**Real example** (Pandora's Box 2026-06-22): the `animateNeuralPool()`
function iterated 5,000 nodes calling `setMatrixAt` + `setColorAt` on
what was now a `Points` mesh after the refactor. Module load completed,
pod connected, but the per-frame loop threw and the page froze at
`HUB · 0.0,1.6,14.0` (loop never advanced). Fixed by rewriting
`animateNeuralPool` to 4 lines that just push shader uniforms.

### Central Data Object Refactor — Grep ALL Downstream References First

When removing a central data object (e.g. `const CORPUS = {...}` →
delete), `grep` for every consumer BEFORE the deletion, not after:

```bash
grep -n 'CORPUS' path/file.html | head -20
```

Direct uses (`CORPUS.memories`) are obvious. Easy-to-miss consumers:
- Property-chain access on a const assignment: `const BRIDGE_SKILLS = CORPUS.topSkillsSample;`
- Iterate-then-extract patterns: `for (const k of Object.keys(CORPUS)) {...}`
- `Object.assign(FOO, CORPUS)` or `{...CORPUS, ...}` spread
- String template interpolation: `\`${CORPUS.backend} at port ${CORPUS.port}\``
- Object-as-namespace patterns: `CORPUS.dream.sessions` in setInterval callbacks

**The rebuild pattern is symmetric**: removing one rendering path needs
the matching `animate()` function to be retargeted to the new path's
uniform-driven contract (above pitfall). Removing a data object needs
every reference either inlined to a new constant or rewritten to use
the new data source.

**Audit pattern after the refactor**:
1. `grep -n 'OLD_NAME' path/` — must return zero hits
2. `node --check` on the extracted module body — catches syntax + let/const errors
3. Open in browser, check DevTools console for `ReferenceError: OLD_NAME is not defined`
4. The pod-connected log (if applicable) firing BEFORE the error tells you whether init succeeded but a later reference failed, vs. init failed entirely

### When Building 3D for mazemaker.online, Use the Site's Design Tokens

The main site at `/mazemaker-v2-stack/frontend/website/style.css` defines
canonical design tokens:

```css
:root {
  --bg:           #0a0a0d;
  --bg-elev:      #0e0e13;
  --surface:      #13131a;
  --surface-2:    #18181f;
  --border:       #23232b;
  --border-hi:    #34343f;
  --text:         #ededf2;
  --text-mute:    #9a9aa8;
  --text-dim:     #5e5e6b;
  --accent:       #8b5cf6;   /* single violet, the only brand color */
  --accent-hi:    #a78bfa;
  --ok:           #10b981;   /* status only */
  --warn:         #f59e0b;
  --err:          #ef4444;
  --ui-font:      'Inter', system-ui, sans-serif;
  --mono-font:    'JetBrains Mono', ui-monospace, monospace;
}
```

**Hard rules** for any 3D experience embedded on mazemaker.online:
- **Single accent**: `#8b5cf6` violet. No rainbow palettes, no phosphor green, no Matrix Reloaded CRT aesthetic unless explicitly requested.
- **Inter for UI chrome, JetBrains Mono only for code/data blocks**. Don't use mono everywhere — the site is editorial, not terminal.
- **Post-processing: BLOOM 0.20-0.30 baseline, NOT 0.55+**. The site is calm, not cinematic. RGB shift only on phase transitions, then decays to zero. Subtle vignette and faint scanline, both brand-tinted.
- **Lighting: hemisphere with brand violet above, ink-dark below**. `AmbientLight(0x2a2a3a, 0.55)`, `HemisphereLight(0x8b5cf6, 0x0a0a0d, 0.35)`, accent point light in the focal chamber.
- **Status indicators use `--ok / --warn / --err` ONLY** for the three states. Never use a fourth "info" color — fold info into `--text-mute`.

**Tone down from cinematic to editorial**:
- Bloom strength: 0.55 → 0.22
- Phase bloom multiplier: ×0.35 (not raw phase.bloom)
- RGB shift kick on phase change: 0.012 → 0.005
- Scanline opacity: 0.7 → 0.45, mix-blend-mode `multiply` → `screen`
- Drop the heavy `text-shadow: 0 0 4px + 0 0 18px` phosphor glow — use `text-shadow: 0 0 0 transparent` or none
- HUD panel opacity: 0.78 → 0.65, border-left 1px solid accent (not 1px all-around)

**The acceptance test**: a screenshot of the 3D experience should be
indistinguishable from the surrounding site at a glance — same palette,
same typography hierarchy, same level of restraint. If it looks "more
impressive" than the site, it's not aligned.

