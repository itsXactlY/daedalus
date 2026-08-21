---
name: es-module-imports
description: Fix ES module import errors with bare specifiers using importmaps and type="module" scripts.
category: web
---

# ES Module Imports with ImportMaps

## The Problem

When importing ES modules via CDN URLs (e.g., jsdelivr, unpkg), some modules contain **bare specifiers** like `'three'` or `'svelte'` that can't be resolved by the browser. This happens when:

1. A module you import has bare imports inside it
2. The browser can't resolve those bare imports without an importmap

Example: `OrbitControls.js` contains `import { ... } from 'three'` — the `'three'` specifier needs a mapping.

## The Fix

### Step 1: Use bare specifiers in dynamic imports

Instead of full CDN URLs, use bare module paths:

```javascript
// WRONG — uses full URL, but OrbitControls.js has bare 'three' imports inside it
const { OrbitControls } = await import('https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js');

// RIGHT — bare specifier, resolved by importmap
const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
```

### Step 2: Add an importmap to HTML

```html
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
    "three/addons/controls/OrbitControls.js": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js",
    "three/addons/postprocessing/EffectComposer.js": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/postprocessing/EffectComposer.js"
  }
}
</script>
```

### Step 3: Use `<script type="module">` on the importing script

```html
<!-- WRONG — importmap won't work without type="module" -->
<script src="assets/maze-engine-new.js" defer></script>

<!-- RIGHT -->
<script type="module" src="assets/maze-engine-new.js" defer></script>
```

## Pitfalls

- **Bare specifiers must match the importmap keys exactly** — `'three'` maps to the build file, `'three/addons/...'` maps to examples
- **Dynamic `import()` inside async functions requires `type="module"` scripts** — regular `<script>` tags don't support dynamic imports
- **Importmaps only work with `defer` scripts or inline module scripts** — a blocking `<script>` can't use importmaps
- **CDN URLs must include `.js` extension for addon paths** — bare specifiers like `'three/addons/controls/OrbitControls'` need the `.js` suffix in the importmap

## Verification Pattern

1. Check browser console for `Uncaught (in promise) TypeError: Failed to resolve module specifier 'three'`
2. Verify importmap has all required mappings
3. Ensure script tag has `type="module"` attribute
4. Test with bare specifiers, not full URLs in dynamic imports