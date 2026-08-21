---
name: github-pages-jekyll-landing
description: Create a proper landing page for a GitHub Pages site that's just serving README.md with no navigation. Covers Jekyll config, static HTML index, markdown rendering, and CDN cache issues.
category: devops
version: 1.0
tags: [github-pages, jekyll, static-site, landing-page, deployment]
---

# GitHub Pages + Jekyll Landing Page

Create a proper landing page for a GitHub-hosted project site that's currently just serving README.md with no navigation structure. Covers Jekyll config, static HTML index, markdown file rendering, and CDN cache quirks.

## When to use

- User asks to "create a landing page" or "fix the homepage" for a GitHub Pages site
- Site is at `https://<user>.github.io/<repo>/` and currently shows raw README.md
- Repo uses Jekyll (default on GitHub Pages) but has no `_config.yml` or `index.html`
- User wants proper navigation, architecture docs, component listings

## Step 1: Diagnose current state

```bash
cd /path/to/project
git log --oneline -3
curl -sL https://<user>.github.io/<repo>/ | grep '<h1>'
curl -sI https://raw.githubusercontent.com/<user>/<repo>/main/README.md
```

Check if `_config.yml` exists. Without it, Jekyll won't render markdown files as HTML pages (CHANGELOG.md stays as .md, etc.).

## Step 2: Create _config.yml (if missing)

Create `website/_config.yml` or project-root `_config.yml`:

```yaml
title: <Project Name>
description: <One-liner description>
baseurl: "/<repo>"
url: "https://<user>.github.io"
theme: jekyll-theme-minimal

# Enable markdown → HTML rendering
markdown: kramdown

# Plugins (required for github-pages)
plugins:
  - jekyll-feed
  - jekyll-seo-tag
```

Create `Gemfile`:

```ruby
source "https://rubygems.org"
gem "github-pages", group: :jekyll_plugins
```

**Why this matters:** Without `_config.yml`, Jekyll may not render `.md` files into `.html`. The `github-pages` gem in Gemfile is required for plugin resolution on GitHub Pages.

## Step 3: Create index.html

Create a static HTML landing page with these sections (adapt to the project):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><Project Name></title>
    <style>
        /* Minimal inline styles — no external deps */
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #333; }
        h1 { font-size: 2em; margin-bottom: 0.5em; }
        h2 { border-bottom: 1px solid #eee; padding-bottom: 0.3em; margin-top: 2em; }
        a { color: #0366d6; text-decoration: none; }
        a:hover { text-decoration: underline; }
        table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        td, th { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
        th { background: #f6f8fa; }
        code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
        .nav-links a { margin-right: 16px; }
    </style>
</head>
<body>
    <h1><Project Name></h1>
    <p class="nav-links">
        <a href="/<repo>/CHANGELOG.html">Changelog</a>
        <a href="/<repo>/SOUL.md">Soul</a>
        <a href="/<repo>/CONTRIBUTING.md">Contributing</a>
    </p>

    <h2>Quick Links</h2>
    <!-- Navigation to key pages -->

    <h2>Architecture</h2>
    <table>
        <tr><th>Component</th><th>Path</th><th>Purpose</th></tr>
        <!-- List all major components -->
    </table>

    <h2>Key Scripts</h2>
    <ul>
        <li><code>install.sh</code> — One-shot setup</li>
        <li><code>setup-daedalus.sh</code> — Full environment provisioning</li>
        <!-- etc -->
    </ul>

    <h2>Documentation</h2>
    <!-- Detailed refs with internal links to rendered markdown -->

    <h2>Configuration</h2>
    <!-- .env.example, config files, etc. -->

    <h2>Running Anywhere</h2>
    <pre><code># Minimal requirements
# ...</code></pre>
</body>
</html>
```

**Key design decisions:**
- No external CSS/JS dependencies — pure static HTML
- Inline styles for zero-dependency rendering
- Jekyll-rendered markdown links use `.html` suffix (e.g., `CHANGELOG.html`) where `_config.yml` enables this transformation
- Raw `.md` files served directly (GitHub serves them; Jekyll renders them if configured)

## Step 4: Handle SNAPSHOT_ENGINE / special docs pages

For individual documentation pages that need to be rendered by Jekyll:

```bash
# If SNAPSHOT_ENGINE.md exists, Jekyll will render it as SNAPSHOT_ENGINE.html
# when _config.yml has proper settings. Reference as:
# <a href="/<repo>/SNAPSHOT_ENGINE.html">Snapshot Engine</a>
```

Verify rendering works:
```bash
curl -sL https://<user>.github.io/<repo>/SNAPSHOT_ENGINE.html | head -5
# Should return HTML, not raw markdown
```

## Step 5: Deploy and verify

```bash
cd /path/to/project
git add _config.yml Gemfile index.html
git commit -m "rework: Add proper landing page with navigation"
git push origin main
```

**Verify all pages:**
```bash
for url in "/<repo>/" "/<repo>/CHANGELOG.html" "/<repo>/SOUL.md" "/<repo>/SNAPSHOT_ENGINE.html"; do
  code=$(curl -sI "https://user.github.io$url" | head -1)
  echo "$url -> $code"
done
```

## Pitfalls

1. **CDN caching is real.** GitHub Pages CDN caches for minutes after push. The old README may still show. Wait 2-5 minutes, or check `raw.githubusercontent.com` for the latest commit content.

2. **Markdown → HTML rendering requires `_config.yml`.** Without it, `.md` files are served as raw text or rendered with minimal markdown. Add `github-pages` gem + proper config to get full HTML rendering.

3. **`.html` vs `.md` links.** Jekyll transforms `CHANGELOG.md` → `CHANGELOG.html`. Reference the `.html` version in internal links for consistency. Raw `.md` files are still accessible at their `.md` URL.

4. **No `_config.yml` = no theme.** GitHub Pages falls back to a minimal default. If you want a specific theme, specify it in config. For static HTML index pages, the theme doesn't matter since `index.html` is served as-is.

5. **Gemfile required for plugins.** The `github-pages` gem must be present for Jekyll plugin resolution. Without it, `_config.yml` plugins section causes errors.

6. **Baseurl matters.** If your site is at `user.github.io/repo`, set `baseurl: "/repo"` in config so asset paths resolve correctly. For `user.github.io` (root), use empty string.

7. **Don't commit to the wrong git repo.** Some projects share a parent directory with other repos. Always verify `git remote -v` before pushing.

## Quick reference

| Problem | Fix |
|---------|-----|
| Site shows raw README.md | Add `_config.yml` + `Gemfile` for Jekyll rendering |
| Markdown pages not rendering as HTML | Ensure `github-pages` gem in Gemfile, proper `_config.yml` |
| Old content still showing after push | Wait for CDN cache (2-5 min), verify with raw.githubusercontent.com |
| 404 on `.html` links to markdown files | Jekyll needs config to transform `.md` → `.html`; reference both forms |
| Asset paths broken | Set `baseurl: "/<repo>"` in `_config.yml` |
