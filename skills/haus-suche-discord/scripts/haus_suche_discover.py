#!/usr/bin/env python3
"""
Haus-Suche DISCOVER: Dynamische Quellen-Entdeckung + Multi-Portal Scraping

Sucht automatisch nach neuen Immobilien-Portalen via DuckDuckGo/Startpage,
scraped Kleinanzeigen, Immoscout und alle neu gefundenen Quellen.
Postet Treffer an Discord.
"""
import json, subprocess, re, time, sys, os, traceback
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1164313161093103716/swOaRW2QRNf82uZxIHtcONb15zizkfhmgITeSFINAJaWgLGl0i-GPvKAaoBz6Z2VWvs7"
MAX_PRICE = 700

REGIONS = [
    ('MeckPomm', 'mecklenburg-vorpommern', 'l4276'),
    ('Thüringen', 'thueringen', 'l9684'),
    ('Sachsen', 'sachsen', 'l4711'),
    ('Sachsen-Anhalt', 'sachsen-anhalt', 'l8646'),
    ('Hessen', 'hessen', 'l4279'),
]

# Known working sources with their search URL patterns
KNOWN_SOURCES = {
    'kleinanzeigen': {
            'type': 'listing',  # returns list of items directly
            'search_pattern': 'https://www.kleinanzeigen.de/s-{kw}/{loc_id}/preis::{max_price}/c205{loc_id}',
            'global_search': 'https://www.kleinanzeigen.de/s-{kw}/preis::{max_price}/c205',
            'keywords': ['alleinlage', 'einzellage', 'freistehend', 'wald', 'bungalow', 'bauernhaus'],
            'region_params': lambda r: (r[1], r[2]),  # region_slug, loc_id
        },
    'immoscout': {
            'type': 'listing',
            'search_pattern': 'https://www.immobilienscout24.de/Suche/de/{region}/haus-mieten?price=-{max_price}.0&buildingfreestanding=1',
            'keywords': [],  # uses URL params instead
            'region_params': lambda r: (r[1],),  # region_slug only
        },
}

# Sources that need DuckDuckGo/Startpage discovery for new URLs
DISCOVERY_SOURCES = ['kleinanzeigen', 'immoscout']

def price_num(s):
    if not s: return 0
    nums = re.findall(r'[\d]+', str(s).replace('.','').replace(',',''))
    return int(nums[0]) if nums else 0

def haustier_ok(text):
    t = text.lower()
    if any(v in t for v in ['keine haustiere', 'haustiere nicht', 'haustiere verboten']): return 'verboten'
    if any(e in t for e in ['haustiere erlaubt', 'haustiere willkommen', 'haustiere möglich', 'hunde erlaubt', 'haustiere jeder art', 'haustiere aller art', 'haustiere kein problem', 'haustiere nach vereinbarung']): return 'ok'
    return 'unbekannt'

def alleinlage_score(text):
    t = text.lower()
    score = 0
    for kw in ['alleinlage', 'einzellage', 'alleinstehend', 'keine nachbarn', 'ohne nachbarn', 'waldrand', 'waldhaus', 'im wald', 'waldnähe', 'eigener feldweg', 'abgelegen', 'abgeschieden', 'einsam', 'außerhalb', 'naturgrundstück', 'kein direkter nachbar']:
        if kw in t: score += 2
    for kw in ['freistehend', 'bungalow', 'landhaus', 'bauernhaus', 'gehöft', 'fachwerkhaus']:
        if kw in t: score += 1
    for kw in ['ortslage', 'ortsmitte', 'zentrum', 'hauptstraße', 'reihenhaus', 'doppelhaus']:
        if kw in t: score -= 3
    return max(0, score)

def post_discord(msgs):
    for m in msgs:
        subprocess.run(["curl", "-s", "-X", "POST", WEBHOOK_URL, "-H", "Content-Type: application/json", "-d", json.dumps({"content": m})], capture_output=True, timeout=15)
        time.sleep(1)

LISTING_KILLWORDS = ['suche', 'gesucht', 'sucht', 'suchen', 'reihenhaus', 'reihenendhaus',
                     'doppelhaushälfte', 'doppelhaus', 'wohnung', 'apartment', 'mehrfamilien',
                     'urlaub', 'ferien', 'gewerbe']

HARD_KILLS = ['reihenhaus', 'reihenmittelhaus', 'reiheneckhaus', 'reihenendhaus',
              'doppelhaushälfte', 'doppelhaus', 'doppel-haus',
              'mehrfamilienhaus', 'mehrfamilien', 'mfh',
              'wohnung', 'apartment', 'dachgeschosswohnung',
              'ortslage', 'ortsmitte', 'zentrum', 'stadtteil', 'stadtmitte',
              'hauptstraße', 'durchgangsstraße',
              'suche', 'gesucht', 'urlaub', 'ferien',
              'galerie', 'werkskantine', 'bahnhofshotel', 'sanierungsobjekt',
              'pflegeheim', 'gewerbe', 'büro', 'praxis',
              'siedlung', 'dorfzentrum', 'dorfmitte',
              'in der stadt', 'stadtbus', 'innenstadt']

# ===== DISCOVERY PHASE: DuckDuckGo + Startpage source discovery =====
def discover_sources_ddg(page, region_name):
    """Use Camoufox browser to search DuckDuckGo and discover new real estate portals."""
    discovered_urls = []
    
    # DDG queries that might reveal new portals
    ddg_queries = [
        f'freistehendes haus mieten alleinlage {region_name}',
        f'bungalow mieten {region_name}',
        f'haus mieten keine nachbarn {region_name}',
        f'mietkauf haus alleinlage {region_name}',
        f'immobilienmakler {region_name} haus miete',
    ]
    
    for query in ddg_queries:
        try:
            encoded = query.replace(' ', '+')
            page.goto(f'https://duckduckgo.com/?q={encoded}&kl=de-de&ia=web', timeout=15000)
            time.sleep(2)
            
            # Extract all links from the results
            links = page.evaluate('''() => {
                const items = [];
                document.querySelectorAll('a').forEach(a => {
                    if (a.href && !a.href.includes('duckduckgo.com') && a.textContent.trim().length > 10) {
                        items.push({title: a.textContent.trim().substring(0,120), url: a.href});
                    }
                });
                return items;
            }''')
            
            for link in links:
                # Filter for real estate domains
                if any(domain in link['url'].lower() for domain in [
                    'immobilienscout24', 'kleinanzeigen', 'immowelt', 'immonet',
                    'immokralle', 'ohne-makler', 'immosuchmaschine', 'immosurf',
                    'immobilo', 'trvit', 'nestoria', 'wunderflats'
                ]):
                    discovered_urls.append({'url': link['url'], 'title': link['title']})
            
            time.sleep(0.5)  # Rate limit DDG
            
        except Exception as e:
            print(f"    DDG query '{query[:30]}...': ERR {str(e)[:40]}")
            continue
    
    return discovered_urls

def discover_sources_startpage(page, region_name):
    """Use Startpage for additional source discovery."""
    discovered_urls = []
    
    queries = [
        f'freistehendes haus mieten alleinlage deutschland',
        f'haus mieten alleinlage {region_name}',
    ]
    
    for query in queries:
        try:
            encoded = query.replace(' ', '+')
            page.goto(f'https://www.startpage.com/do/search?q={encoded}&language=de&sp_squ=', timeout=15000)
            time.sleep(2)
            
            links = page.evaluate('''() => {
                const items = [];
                document.querySelectorAll('a').forEach(a => {
                    if (a.href && !a.href.includes('startpage.com') && a.textContent.trim().length > 10) {
                        items.push({title: a.textContent.trim().substring(0,120), url: a.href});
                    }
                });
                return items;
            }''')
            
            for link in links:
                if any(domain in link['url'].lower() for domain in [
                    'immobilienscout24', 'kleinanzeigen', 'immowelt', 'immonet',
                    'immokralle', 'ohne-makler', 'immosuchmaschine', 'immosurf',
                    'immobilo', 'trvit', 'nestoria', 'wunderflats'
                ]):
                    discovered_urls.append({'url': link['url'], 'title': link['title']})
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"    Startpage query '{query[:30]}...': ERR {str(e)[:40]}")
            continue
    
    return discovered_urls

def extract_new_portal_domains(discovered_urls):
    """Extract unique portal domains from discovered URLs."""
    portals = set()
    for item in discovered_urls:
        url = item['url']
        # Extract domain
        m = re.search(r'https?://([^/]+)', url)
        if m:
            domain = m.group(1).lower()
            # Only keep real estate domains
            if any(kw in domain for kw in ['immobilien', 'haus', 'immo', 'kleinanzeigen', 'scout', 'welt', 'net']):
                portals.add(domain)
    return portals

# ===== SCRAPING FUNCTIONS =====

def scrape_kleinanzeigen(page, region_name, loc_id):
    """Scrape Kleinanzeigen for the given region."""
    results = []
    
    keywords = ['alleinlage', 'einzellage', 'freistehend', 'wald', 'bungalow', 'bauernhaus']
    
    for kw in keywords:
        url = f'https://www.kleinanzeigen.de/s-{kw}/{loc_id}/preis::1350/c205{loc_id}'
        try:
            page.goto(url, timeout=12000)
            try:
                btn = page.locator('button:has-text("Alle akzeptieren")')
                if btn.is_visible(timeout=2000): btn.click(); time.sleep(0.5)
            except: pass
            
            listings = page.evaluate('''() => {
                const items = [];
                document.querySelectorAll('article[class*=aditem]').forEach(a => {
                    const t = a.querySelector('a[class*=ellipsis]')?.textContent?.trim();
                    const l = a.querySelector('a[class*=ellipsis]')?.href;
                    const p = a.querySelector('[class*=price]')?.textContent?.trim();
                    const loc = a.querySelector('[class*=top--left]')?.textContent?.trim();
                    if (t && l) items.push({title:t,price:p||'?',location:loc||'?',url:l});
                });
                return items;
            }''')
            
            for l in listings:
                tl = l.get('title', '').lower()
                if any(k in tl for k in LISTING_KILLWORDS):
                    continue
                results.append({**l, 'source': 'KA', 'region': region_name})
            
            time.sleep(0.2)
        except Exception as e:
            print(f"    KA {kw}: ERR {str(e)[:40]}")
            continue
    
    return results

def scrape_immoscout(page, region_name, region_slug):
    """Scrape Immoscout for the given region."""
    url = f'https://www.immobilienscout24.de/Suche/de/{region_slug}/haus-mieten?price=-1300.0&buildingfreestanding=1'
    results = []
    
    try:
        page.goto(url, timeout=25000)
        time.sleep(2)
        try:
            btn = page.locator('button:has-text("Alle akzeptieren")')
            if btn.is_visible(timeout=3000): btn.click(); time.sleep(1)
        except: pass
        
        body_text = page.evaluate('() => document.body?.innerText?.substring(0,300) || ""')
        if 'captcha' in body_text.lower() or 'gesperrt' in body_text.lower():
            print(f"    Immoscout {region_name}: BLOCKED")
            return []
        
        listings = page.evaluate('''() => {
            const items = [];
            document.querySelectorAll('.listing-card').forEach(card => {
                const id = card.getAttribute('data-obid');
                const title = card.querySelector('h3,h2')?.textContent?.trim();
                const cardText = card.textContent?.trim()?.substring(0,300) || '';
                const dds = Array.from(card.querySelectorAll('dd')).map(d=>d.textContent.trim());
                const loc = card.querySelector('[class*=address],[class*=locality]')?.textContent?.trim()||'';
                if (id && title) items.push({
                    id, title, location: loc, cardText,
                    price: dds[0]||'', sqm: dds[1]||'', rooms: dds[2]||'',
                    url: 'https://www.immobilienscout24.de/expose/'+id
                });
            });
            return items;
        }''')
        
        for l in listings:
            tl = l.get('title', '').lower() + ' ' + l.get('cardText', '').lower()
            if any(k in tl for k in LISTING_KILLWORDS):
                continue
            results.append({**l, 'source': 'Immoscout', 'region': region_name})
        
        print(f"    Immoscout {region_name}: +{len(listings)}")
        time.sleep(1)
    except Exception as e:
        print(f"    Immoscout {region_name}: ERR {str(e)[:40]}")
    
    return results

def scrape_detail(page, item):
    """Scrape detail page for additional info."""
    try:
        page.goto(item['url'], timeout=8000)
    except Exception as nav_err:
        try:
            page.close()
        except: pass
        try:
            page = browser.new_page()
            page.goto(item['url'], timeout=10000)
        except:
            print(f"  [{item.get('id', '?')}] RECOVERY FAILED, skipping")
            return None
    
    time.sleep(0.3)
    
    detail = page.evaluate('''() => {
        const d = {title:'',price:'',location:'',description:'',attrs:{}};
        d.title = document.querySelector('h1')?.textContent?.trim()?.replace(/^Reserviert\\s*[•·]\\s*Gelöscht\\s*[•·]*/,'');
        d.price = document.querySelector('h2[class*=price],#contactBoxTop .font-bold,[class*=price-detail]')?.textContent?.trim();
        d.location = document.querySelector('[data-qa="locality"],[id*=locality],.zip-region-and-country')?.textContent?.trim();
        d.description = document.querySelector('#viewad-description-text,[data-qa="description"] p,[class*=description] p,[id*=description] p,[class*=adDescriptionText]')?.textContent?.trim()?.substring(0,800);
        
        document.querySelectorAll('[class*=criterions] li,dl dt,dl dd,[class*=key-fact]').forEach(el => {
            d.attrs[el.className?.substring(0,30)||'x'] = el.textContent?.trim()?.substring(0,60);
        });
        document.querySelectorAll('[class*=addetailslist--detail],[class*=keyFacts--detail]').forEach(el => {
            const parts = el.textContent.trim().split('\\n').map(s=>s.trim()).filter(Boolean);
            if (parts.length>=2) d.attrs[parts[0]] = parts.slice(1).join(' ');
        });
        try { for (const s of document.querySelectorAll('script')) {
            const t = s.textContent;
            const hm = t.match(/\"Haustyp\"\\s*:\\s*\"([^\"]+)\"/);
            if (hm && !d.attrs['Haustyp']) d.attrs['Haustyp'] = hm[1];
            const wm = t.match(/\"Warmmiete\"\\s*:\\s*\"([^\"]+)\"/);
            if (wm && !d.attrs['Warmmiete']) d.attrs['Warmmiete'] = wm[1]+' €';
        }} catch(e){}
        return d;
    }''')
    
    # Body fallback
    if not detail or not detail.get('title'):
        try:
            body = page.evaluate('() => document.body?.innerText?.substring(0,2000) || ""')
            if len(body) > 200:
                detail = detail or {}
                h1 = page.evaluate('() => document.querySelector("h1")?.textContent?.trim() || ""')
                if h1:
                    detail['title'] = h1
                    idx = body.find('€\n') if '€\n' in body else body.find('€ ')
                    detail['description'] = body[idx:idx+500].strip() if idx > 0 else body[300:800].strip()
        except: pass
    
    return detail

def main():
    from camoufox.sync_api import Camoufox
    
    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        seen = set()
        all_listings = []
        
        # ===== PHASE 1: Source Discovery =====
        print("=== DISCOVERY PHASE ===")
        discovered_portals = set()
        for region_name, _, _ in REGIONS[:2]:  # Discover from first 2 regions
            print(f"  Discovering sources for {region_name}...")
            
            # DDG discovery
            ddg_urls = discover_sources_ddg(page, region_name)
            portals = extract_new_portal_domains(ddg_urls)
            discovered_portals.update(portals)
            
            # Startpage discovery
            sp_urls = discover_sources_startpage(page, region_name)
            portals = extract_new_portal_domains(sp_urls)
            discovered_portals.update(portals)
        
        print(f"  Discovered {len(discovered_portals)} new portal domains: {discovered_portals}")
        
        # ===== PHASE 2: Known Sources Scraping =====
        print("\n=== KLEINANZEIGEN ===")
        for region_name, _, loc_id in REGIONS:
            listings = scrape_kleinanzeigen(page, region_name, loc_id)
            for l in listings:
                if l['url'] not in seen:
                    seen.add(l['url'])
                    all_listings.append(l)
        
        print("\n=== IMMOSCOUT ===")
        for region_name, region_slug, _ in REGIONS:
            listings = scrape_immoscout(page, region_name, region_slug)
            for l in listings:
                if l['url'] not in seen:
                    seen.add(l['url'])
                    all_listings.append(l)
        
        # ===== PHASE 3: New Portal Scraping =====
        print(f"\n=== NEW PORTALS ({len(discovered_portals)}) ===")
        for portal_domain in discovered_portals:
            print(f"  Scraping {portal_domain}...")
            try:
                # Try generic search URL patterns
                search_urls = [
                    f'https://{portal_domain}/mieten/haus/',
                    f'https://{portal_domain}/suche/haus-mieten/',
                ]
                
                for region_name, region_slug, _ in REGIONS[:2]:  # Limit regions for new portals
                    for url_template in search_urls:
                        try:
                            url = url_template.format(region=region_slug)
                            page.goto(url, timeout=15000)
                            time.sleep(1)
                            
                            # Extract listings from the portal - use domain directly instead of 'portal' variable
                            pd = portal_domain
                            listings = page.evaluate(f'''() => {{
                                const items = [];
                                document.querySelectorAll('a').forEach(a => {{
                                    if (a.href && !a.href.includes('{pd}') && a.textContent.trim().length > 10) {{
                                        const title = a.textContent.trim().substring(0,120);
                                        if (title) items.push({{url: a.href, title: title, source: 'NEU:{pd}'}});
                                    }}
                                }});
                                return items;
                            }}''')
                            
                            for l in listings:
                                if l['url'] not in seen:
                                    seen.add(l['url'])
                                    all_listings.append(l)
                            print(f"    {portal_domain}: +{len(listings)}")
                            
                        except Exception as e:
                            print(f"    {portal_domain} ({region_name}): ERR {str(e)[:40]}")
                            continue
            
            except Exception as e:
                print(f"  Portal {portal_domain}: ERROR {str(e)[:40]}")
        
        print(f"\nTotal filtered listings: {len(all_listings)}")
        
        # ===== PHASE 4: Detail Scraping & Filtering =====
        MAX_DETAIL = 60
        scrape_list = all_listings[:MAX_DETAIL]
        print(f"\n=== DETAIL SCRAPING {len(scrape_list)}/{len(all_listings)} ===")
        results = []
        
        for i, item in enumerate(scrape_list):
            try:
                if i > 0 and i % 20 == 0:
                    try:
                        page.close()
                    except:
                        pass
                    page = browser.new_page()
                
                detail = scrape_detail(page, item)
                if not detail or not detail.get('title'):
                    continue
                
                full = f"{detail.get('title','')} {detail.get('description','')} {str(detail.get('attrs',{}))}".lower()
                
                # Check Typ field specifically
                typ = detail.get('attrs',{}).get('Typ','').lower()
                if any(k in typ for k in ['doppelhaus', 'reihenhaus', 'mehrfamilien', 'wohnung']):
                    print(f"  [{i+1}] TYP-KILL: {typ} - {detail.get('title','')[:40]}")
                    continue
                
                killed = [k for k in HARD_KILLS if k in full]
                if killed:
                    print(f"  [{i+1}] KILLED: {killed[0]} - {detail.get('title','')[:40]}")
                    continue
                
                # Freistehend check (entschärft)
                if 'freistehend' not in full:
                    continue
                
                # Price check
                warm = detail.get('attrs',{}).get('Warmmiete', '')
                wn = price_num(warm) if warm else price_num(item.get('price', ''))
                if wn > MAX_PRICE:
                    continue
                
                # Haustier check
                ht = haustier_ok(full)
                if ht == 'verboten':
                    continue
                
                score = alleinlage_score(full)
                item['detail'] = detail
                item['haustier'] = ht
                item['score'] = score
                results.append(item)
                
                marker = '🌲' if score >= 4 else '🏠' if score >= 1 else '🏘️'
                print(f"  [{i+1}] {marker}[{score}] ✓ {detail['title'][:45]} | {warm or item.get('price','?')} | {ht}")
                time.sleep(0.1)
            
            except Exception as e:
                continue
        
        try:
            page.close()
        except Exception:
            pass
        
        # ===== PHASE 5: Sort & Post =====
        results.sort(key=lambda x: (-x.get('score', 0), price_num(x.get('detail', {}).get('attrs', {}).get('Warmmiete', '0'))))
        print(f"\n📊 {len(results)} Ergebnisse ({sum(1 for r in results if r.get('score', 0) >= 4)}🌲 / {sum(1 for r in results if 1 <= r.get('score', 0) < 4)}🏠 / {sum(1 for r in results if r.get('score', 0) == 0)}🏘️)")
        
        if results:
            msgs = [f"""🏠 **HÄUSER ZUR MIETE** 🏠
*Freistehend, max {MAX_PRICE}€ warm | Quellen: Kleinanzeigen + Immoscout + {len(discovered_portals)} neu gefunden*
🏠 = freistehend
*{len(results)} Angebote*
━━━━━━━━━━━━━━━━━━━━━━━━"""]
            cur = ""
            for i, item in enumerate(results, 1):
                d = item.get('detail', {})
                ht = item.get('haustier', '?')
                score = item.get('score', 0)
                marker = '🌲' if score >= 4 else '🏠' if score >= 1 else '🏘️'
                e = f"\n{marker} **{i}. {d.get('title', item.get('title', '?'))[:55]} — {item.get('price', '?')}**\n"
                e += f"📍 {d.get('location', item.get('location', '?'))} | {item['region']}\n"
                e += f"{ht_icon if 'ht_icon' in locals() else '?'} Haustiere: {'✓' if ht == 'ok' else '?'} | Score: {score}/10\n"
                a = d.get('attrs', {})
                if a.get('Warmmiete'): e += f"💰 Warm: {a['Warmmiete']}\n"
                if a.get('Wohnfläche') or a.get('Zimmer'): e += f"📐 {a.get('Wohnfläche', '')} | {a.get('Zimmer', '')} Zi\n"
                if d.get('description'):
                    desc = d['description'].replace('\\n', ' ').strip()[:150]
                    e += f"📋 {desc}\n"
                e += f"🔗 {item['url']}\n"
                if len(cur) + len(e) > 1800:
                    msgs.append(cur)
                    cur = e
                else:
                    cur += e
            if cur:
                cur += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n⏰ *Nächster Report in 1 Stunde*"
                msgs.append(cur)
            print(f"📤 Posting {len(msgs)} messages...")
            post_discord(msgs)
            print("✅ Done!")
        else:
            print("📭 Keine Treffer. Stille Meldung.")

if __name__ == "__main__":
    main()