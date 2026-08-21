---
name: maze-deployment-pitfalls
description: Fix Three.js bare import errors, duplicate maze-engine files, and nav.js partial fetch failures on Cloudflare Pages.
category: mazemaker
---

# Maze Deployment Pitfalls — Cloudflare Pages Fixes

These are production-level deployment issues specific to the Mazemaker website (Cloudflare Pages). Load when fixing or auditing `~/projects/mazemaker-website-fork/`.

## 1. Three.js bare import errors on Cloudflare Pages

**Symptom:** Console error `Uncaught SyntaxError: Cannot use 'import.meta' outside of a module` or bare specifier failures for `'three'`, `'three/module.js'`, etc.

**Root cause:** Importmap approach with bare specifiers (`"three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js"`) doesn't work reliably on Cloudflare Pages — the importmap may not resolve, or the browser can't handle the bare specifier at runtime.

**Fix:** Replace ALL bare Three.js imports with full CDN URLs:

```javascript
// WRONG (bare specifier)
import * as THREE from 'three';

// RIGHT (full CDN URL)
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
```

Apply to all Three.js submodules too:
- `https://cdn.jsdelivr.net/npm/three@0.170.0/examples/js/controls/OrbitControls.js`
- `https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsr/controls/OrbitControls.js` (check version compatibility)
- Any other Three.js module imports

**Verification:** After fixing, run `node --check ./assets/maze-engine-new.js` to ensure syntax is valid, then check the browser console for zero import errors.

## 2. Duplicate maze-engine files

**Symptom:** Confusion about which file is being served; duplicate filenames with different content.

**Root cause:** Two copies of `maze-engine-new.js` exist:
- `website/maze-engine-new.js` (16K) — uses bare `'three'` imports via importmap, BROKEN
- `assets/maze-engine-new.js` (17K) — uses full CDN URLs, CORRECT

**Fix:** Remove the duplicate in the website root:

```bash
rm ./mazemaker-website-fork/website/maze-engine-new.js
```

Only `assets/maze-engine-new.js` should exist. The HTML must reference the assets version:

```html
<script src="assets/maze-engine-new.js" defer></script>
```

**Verification:** After removal, confirm only one maze file exists:
```bash
find ./mazemaker-website-fork/website -name "maze-engine*.js"
# Should return only: ./assets/maze-engine-new.js
```

## 3. Nav.js partial fetch failures

**Symptom:** Navigation renders empty or broken; header/footer not visible; console errors about failed partial fetches.

**Root cause:** Cloudflare Pages doesn't serve `header.html` and `footer.html` partials reliably (404 on fetch). Nav.js tries to fetch these partials but fails silently with no fallback.

**Fix:** Add embedded fallback HTML directly into nav.js so navigation renders even when CDN can't serve the partials:

```javascript
// In nav.js, define fallback templates:
const FALLBACK_HEADER = `
  <header class="site-header" role="banner" id="site-header">
    <a href="${siteRoot}" class="logo" aria-label="mazemaker home">
      <span class="logo-diamond" aria-hidden="true"></span>
      <span class="logo-text">mazemaker<span>.online</span></span>
    </a>
    <nav class="main-nav" role="navigation" aria-label="main navigation">
      <!-- nav items -->
    </nav>
  </header>`;

const FALLBACK_FOOTER = `
  <footer class="site-footer" role="contentinfo">
    <!-- footer content -->
  </footer>`;

// In the fetch error handler:
fetch('/assets/partials/header.html')
  .then(r => {
    if (!r.ok) throw new Error('Failed to load header');
    return r.text();
  })
  .then(html => {
    placeholder.outerHTML = html;
  })
  .catch(() => {
    console.warn('header.html not served, using embedded fallback');
    placeholder.outerHTML = FALLBACK_HEADER;
  });
```

**Verification:** After adding fallbacks, verify the navigation renders correctly even when the partial files are unavailable. Check that `placeholder.outerHTML` is set to the fallback in error cases.

## Deployment checklist

Before deploying any website changes:
1. Ensure no bare Three.js imports exist — all must use full CDN URLs
2. Verify only ONE maze-engine file exists (in `assets/`, not in root)
3. Confirm nav.js has embedded fallbacks for partial fetch failures
4. Run `node --check` on all JS files before deploying
5. Deploy via: `wrangler pages deploy dist-online --project-name=mazemaker-online --branch main`
6. NEVER use `deploy-pages.sh` (has `***` sanitization damage)

## Related skills

- `mazemaker-marketing-website` — Main marketing site design and rebuild patterns
- `wrangler` — Cloudflare Workers CLI reference