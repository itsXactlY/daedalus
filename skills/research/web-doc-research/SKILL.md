---
name: web-doc-research
category: research
description: Cascading access strategy for web documentation research with source verification
version: 1.0.0
tags: [research, web, documentation, scraping, access-strategy]
priority: high
created: 2026-04-20
---

# Web Documentation Research

Systematic approach to accessing and researching web documentation when standard HTTP access is blocked or restricted.

## Cascading Access Strategy

When researching web documentation, try access methods in this order. Each tier is progressively more resource-intensive but more likely to succeed.

### Tier 1: GitHub Raw Content
Fastest, most reliable for open-source projects.

```bash
# Direct raw content access
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

# Example: Get README
curl -s "https://raw.githubusercontent.com/owner/repo/main/docs/api.md"
```

Advantages: Fast, no rate limiting for reasonable use, always latest version.

### Tier 2: Browser Automation
Use when sites require JavaScript rendering or have anti-bot measures.

```python
# Using playwright or selenium
from playwright.sync_api import sync_playwright

def fetch_with_browser(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        content = page.content()
        browser.close()
        return content
```

Use for: SPAs, sites requiring cookie/session, dynamic content.

### Tier 3: Community Mirrors
Often overlooked but highly valuable.

Known working mirrors:
- StarDZ wiki: Proven alternative for DayZ documentation
- Arch Wiki mirrors
- Community-maintained documentation forks
- Awesome-* lists on GitHub

Search pattern:
```
"{topic}" site:github.com wiki
"{topic}" documentation mirror
"{topic}" community docs
```

### Tier 4: Wayback Machine
For historical content or when original is down.

```bash
# Check if URL is archived
curl -s "https://archive.org/wayback/available?url={encoded_url}"

# Get latest snapshot
curl -s "https://web.archive.org/web/2024/{url}"

# Get specific timestamp
curl -s "https://web.archive.org/web/20240101120000/{url}"
```

### Tier 5: Google Cache
Last resort, content may be stale.

```bash
# Google cache prefix
curl -s "https://webcache.googleusercontent.com/search?q=cache:{encoded_url}"
```

## Known Access Restrictions

### Bohemia Interactive (community.bistudio.com)
**Status:** BLOCKS ALL AUTOMATED ACCESS

- `community.bistudio.com` returns 403 to all non-browser requests
- Even browser automation may be blocked by Cloudflare
- Rate limiting is aggressive

**Workaround:** Use StarDZ wiki as proven alternative for DayZ documentation.

```
Instead of: community.bistudio.com/dayz/
Use:        dayz.fandom.com or community-maintained wikis
```

## Source-Verified Report Structuring

Every research report must include source verification:

### Report Template

```markdown
# Research Report: {Topic}
Date: {date}
Researcher: {agent}

## Sources

| Source | URL | Access Method | Status | Verified |
|--------|-----|---------------|--------|----------|
| Official Docs | https://... | GitHub Raw | 200 OK | Yes |
| API Reference | https://... | Browser Auto | 200 OK | Yes |
| Community Wiki | https://... | Direct | 403 | No - used mirror |
| Mirror | https://... | Direct | 200 OK | Yes |

## Findings

### Finding 1: {Title}
- **Source:** {source name from table}
- **Confidence:** High/Medium/Low
- **Evidence:** {quote or specific reference}
- **Notes:** {any caveats about source reliability}

### Finding 2: {Title}
...

## Access Issues Encountered

| URL | Issue | Resolution |
|-----|-------|------------|
| community.bistudio.com/... | 403 Blocked | Used StarDZ wiki alternative |
| old-docs.example.com | DNS failure | Retrieved from Wayback Machine |

## Verification Steps Taken

1. Cross-referenced Finding 1 across 3 independent sources
2. Verified API behavior matches documentation
3. Tested code examples from source X - confirmed working
```

## Research Workflow

```bash
# 1. Start with GitHub raw for known repos
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"

# 2. If blocked, try browser automation
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('{url}')
    print(page.content())
    browser.close()
"

# 3. Search for community mirrors
# Use search tools to find alternative documentation sources

# 4. Check Wayback Machine
curl -s "https://archive.org/wayback/available?url={url}"

# 5. Google cache as last resort
```

## Tips

- Always record which access method succeeded for each source
- Note when content was last updated (may differ from live site)
- Cross-reference findings across multiple sources
- Be aware that cached/archived content may be outdated
- Community wikis often have more practical examples than official docs
