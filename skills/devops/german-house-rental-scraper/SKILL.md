---
name: german-house-rental-scraper
title: German House Rental Scraper
description: Search for freestanding houses for rent in Germany, filter by criteria, post to Discord webhook. Hourly cron capable.
---

# German House Rental Scraper

Search for houses (Haus mieten) across German real estate portals with specific criteria, post results to Discord.

## Trigger
When user wants: Haus mieten, freistehendes Haus, house rental Germany, ländliches Haus mieten.

## Portal Landscape (tested 2026-08)

### WORKING Portals (Camoufox-based discovery approach)
1. **Kleinanzeigen.de** ✅ — best source, Camoufox works reliably
   - URL pattern: `https://www.kleinanzeigen.de/s-{kw}/{loc_id}/preis::1350/c205{loc_id}`
   - Keywords: `alleinlage`, `einzellage`, `freistehend`, `wald`, `bungalow`, `bauernhaus`
   - Region slugs + loc_ids: `mecklenburg-vorpommern/l4276`, `thueringen/l9684`, `sachsen/l4711`, etc.

2. **ImmobilienScout24** ✅ via Camoufox — CAPTCHA-free with proper browser fingerprinting
   - URL: `https://www.immobilienscout24.de/Suche/de/{region}/haus-mieten?price=-{max_price}.0&buildingfreestanding=1`

3. **Discovered portals** (auto-discovered via DDG/Startpage): immowelt.de, ohne-makler.net, immosuchmaschine.de, immobilo.de
   - Scraped with generic URL patterns: `/mieten/haus/`, `/suche/haus-mieten/`

### BLOCKED Portals
- ImmobilienScout24 — aggressive CAPTCHA (bypassable via Camoufox)
- Immowelt — 410 Gone / 403 on most region URLs
- Immonet — redirects to Immowelt

## Discovery-Based Scraping (Recommended Approach)

The `haus_suche_discover.py` script auto-discovers new real estate portals using search engine queries, then scrapes them. This is the preferred approach over a hardcoded portal list.

### Step 1: Source Discovery via Search Engines
Use Camoufox to query DuckDuckGo and Startpage with targeted queries:
```python
# Example DDG queries per region
ddg_queries = [
    f'freistehendes haus mieten alleinlage {region_name}',
    f'bungalow mieten {region_name}',
    f'haus mieten keine nachbarn {region_name}',
]
```
Extract portal domains from results, filter for real estate keywords (immobilien, haus, immo).

### Step 2: Known Source Scraping (Camoufox)
Kleinanzeigen + Immoscout via Camoufox browser — avoids CAPTCHAs that break curl.

### Step 3: New Portal Scraping
For each discovered portal domain, try generic URL patterns:
```python
search_urls = [
    f'https://{portal_domain}/mieten/haus/',
    f'https://{portal_domain}/suche/haus-mieten/',
]
```
Extract listing links from the page DOM.

### Step 4: Detail Scraping & Filtering
Scrape detail pages, filter by Alleinlage keywords, price ≤1300€, no pet bans.

See script: `scripts/haus_suche_discover.py` (full implementation).

## Scraping Approach

### Step 1: Fetch Kleinanzeigen per region
```python
import subprocess, re, json

regions = {
    "MeckPomm": "mecklenburg-vorpommern",
    "Thueringen": "thueringen",
    "Sachsen": "sachsen",
    "SachsenAnhalt": "sachsen-anhalt",
    "Hessen": "hessen"
}

for name, slug in regions.items():
    url = f"https://www.kleinanzeigen.de/s-haus-mieten/{slug}/preis::1100/c203"
    result = subprocess.run(
        ["curl", "-s", "-L", "--max-time", "15",
         "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
         "-H", "Accept-Language: de-DE,de;q=0.9", url],
        capture_output=True, text=True, timeout=20)
    html = result.stdout
```

### Step 2: Parse articles
```python
articles = re.findall(
    r'<article[^>]*class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>',
    html, re.DOTALL)
```

### Step 3: Extract fields per article
```python
title_match = re.search(r'<a[^>]*class="[^"]*ellipsis[^"]*"[^>]*>([^<]+)</a>', article)
link_match = re.search(r'href="(/s-anzeige/[^"]+)"', article)
price_match = re.search(r'<[^>]*class="[^"]*aditem-main--middle--price[^"]*"[^>]*>([^<]+)</[^>]+>', article)
location_match = re.search(r'<[^>]*class="[^"]*aditem-main--top--left[^"]*"[^>]*>([^<]+)</[^>]+>', article)
```

### Step 4: Filter for houses
Kleinanzeigen c203 includes ALL rentals (apartments too). Must filter by keywords:
```python
house_keywords = ['haus', 'freistehend', 'einfamilien', 'alleinlage', 'bauernhof',
                  'landhaus', 'mietkauf', 'doppelhaus', 'reihenhaus',
                  'hof', 'gut', 'villa', 'landanwesen', 'forsthaus', 'mühle']
if any(kw in title.lower() for kw in house_keywords):
    results.append({...})
```

### Step 5: Also search with specific keywords
```
https://www.kleinanzeigen.de/s-alleinlage/{slug}/preis::1100/c203
https://www.kleinanzeigen.de/s-freistehend/{slug}/preis::1100/c203
https://www.kleinanzeigen.de/s-einfamilienhaus-mieten/{slug}/preis::1100/c203
```

## Discord Webhook Posting

```python
import json, subprocess

WEBHOOK_URL = "https://discord.com/api/webhooks/..."

def post_to_discord(title, description, url):
    payload = json.dumps({
        "embeds": [{
            "title": title,
            "description": description,
            "url": url,
            "color": 5814783  # purple
        }]
    })
    subprocess.run([
        "curl", "-X", "POST", "-H", "Content-Type: application/json",
        "-d", payload, WEBHOOK_URL
    ], capture_output=True)
```

## Cron Setup

```python
cronjob(action='create',
    name='haus-suche-deutschland',
    schedule='1h',
    deliver='local',
    prompt='Search Kleinanzeigen.de for freistehende Häuser zur Miete in MeckPomm, Thüringen, Sachsen, Sachsen-Anhalt, Hessen (max 1100€ warm, prefer Mietkauf). Post new finds to Discord webhook. See skill: german-house-rental-scraper.')
```

## Deduplication
Store seen URLs in a file (`~/.hermes/haus-suche/seen_urls.json`) to avoid reposting.

## Pitfalls
- Kleinanzeigen c203 is NOT house-specific — heavy filtering needed
- Many results are sponsored/promoted (TOP tags) — may not be relevant
- Immowelt/Immonet unreliable via curl — use browser_navigate as fallback but expect bot detection
- Title parsing may miss entries with unconventional formatting
- "Maisonette" in title is usually an apartment, not a house — filter carefully
