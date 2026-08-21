#!/usr/bin/env python3
"""
HAUS-SUCHE MASSIVE v6 — Vollständiger deutscher Immobilien-Markt
===============================================================
Camoufox (Anti-Detection) + JSON-LD Extraction für Kleinanzeigen
+ 8 Regionen × 5 Quellen

Cron: haus-suche-stuendlich (alle 15 Min)
"""
import json, subprocess, re, time, sys, os, urllib.parse, datetime
sys.stdout.reconfigure(line_buffering=True)

WEBHOOK_URL = "https://discord.com/api/webhooks/1164313161093103716/swOaRW2QRNf82uZxIHtcONb15zizkfhmgITeSFINAJaWgLGl0i-GPvKAaoBz6Z2VWvs7"
MAX_PRICE = 1300
MAX_DETAIL_FETCH = 100

REGIONS = [
    ('MeckPomm', 'mecklenburg-vorpommern', 'l4276'),
    ('Thüringen', 'thueringen', 'l9684'),
    ('Sachsen', 'sachsen', 'l4711'),
    ('Sachsen-Anhalt', 'sachsen-anhalt', 'l8646'),
    ('Hessen', 'hessen', 'l4279'),
    ('Berlin', 'berlin', 'l305'),
    ('Brandenburg', 'brandenburg', 'l4615'),
    ('Niedersachsen', 'niedersachsen', 'l4338'),
    ('Rheinland-Pfalz', 'rheinland-pfalz', 'l5321'),
    ('Saarland', 'saarland', 'l5766'),
    ('Schleswig-Holstein', 'schleswig-holstein', 'l4987'),
    ('Bremen', 'bremen', 'l384'),
]

HARD_KILLS = [
    'reihenhaus','reihenmittelhaus','reiheneckhaus','reihenendhaus',
    'doppelhaushälfte','doppelhaus','doppel-haus','doppelmehrfamilienhaus',
    'mehrfamilienhaus','mehrfamilien','mfh','wohnanlage',
    'wohnung','apartment','dachgeschosswohnung','untergeschosswohnung',
    'ortslage','ortsmitte','zentrum','stadtteil','stadtmitte','stadtnah',
    'hauptstraße','durchgangsstraße','bundesstraße',
    'suche','gesucht','sucht','suchen','nachmieter','untervermietung',
    'urlaub','ferien','gewerbe','büro','praxis','kantine','hotel',
    'galerie','sanierungsobjekt','pflegeheim','betreutes wohnen',
    'siedlung','dorfzentrum','dorfmitte','in der stadt','stadtbus','innenstadt',
    'reserviert','gelöscht','geändert'
]

LISTING_KILLWORDS = ['suche','gesucht','sucht','suchen','reihenhaus','reihenendhaus',
                     'doppelhaushälfte','doppelhaus','wohnung','apartment','mehrfamilien',
                     'urlaub','ferien','gewerbe','nachmieter']


def price_num(s):
    if not s: return 0
    nums = re.findall(r'[\d]+', str(s).replace('.','').replace(',',''))
    return int(nums[0]) if nums else 0


def haustier_ok(text):
    t = text.lower()
    if any(v in t for v in ['keine haustiere','haustiere nicht','haustiere verboten']): return 'verboten'
    if any(e in t for e in ['haustiere erlaubt','haustiere willkommen','haustiere möglich',
                             'hunde erlaubt','haustiere jeder art','haustiere aller art',
                             'haustiere kein problem','haustiere nach vereinbarung','tierisch willkommen']):
        return 'ok'
    return 'unbekannt'


def alleinlage_score(text):
    t = text.lower()
    score = 0
    for kw in ['alleinlage','einzellage','alleinstehend','keine nachbarn','ohne nachbarn',
               'waldrand','waldhaus','im wald','waldnähe','eigener feldweg','abgelegen',
               'abgeschieden','einsam','außerhalb','naturgrundstück','kein direkter nachbar']:
        if kw in t: score += 2
    for kw in ['freistehend','bungalow','landhaus','bauernhaus','gehöft','fachwerkhaus',
               'einzeln stehend','nachbarfrei','keine direkten nachbarn','naturgrundstück']:
        if kw in t: score += 1
    for kw in ['ortslage','ortsmitte','zentrum','hauptstraße','reihenhaus','doppelhaus',
               'siedlung','dorfzentrum','dorfmitte','in der stadt','stadtbus','innenstadt']:
        if kw in t: score -= 3
    return max(0, min(20, score))


def post_discord(msgs):
    for m in msgs:
        try:
            subprocess.run(["curl","-s","-X","POST",WEBHOOK_URL,
                          "-H","Content-Type: application/json",
                          "-d",json.dumps({"content":m})],
                         capture_output=True, timeout=15)
            time.sleep(1.2)
        except Exception as e:
            print(f"  DISCORD ERR: {str(e)[:80]}")


def scrape_immoscout(page, region_name, region_slug):
    """Scrape ImmoScout24 using .listing-card selector (Camoufox works here)."""
    results = []
    url = f"https://www.immobilienscout24.de/Suche/de/{region_slug}/haus-mieten?price=-{MAX_PRICE}.0&buildingfreestanding=1&nr=1"

    try:
        page.goto(url, timeout=25000)
        time.sleep(3)

        try:
            btn = page.locator('button:has-text("Alle akzeptieren")')
            if btn.is_visible(timeout=3000):
                btn.click()
                time.sleep(1)
        except: pass

        body_text = page.evaluate(r'''function() { return document.body?.innerText?.substring(0,500) || ""; }''')
        if 'captcha' in body_text.lower() or 'gesperrt' in body_text.lower():
            print(f"    BLOCKED (captcha/gesperrt)")
            return results

        listings = page.evaluate(r'''function() {
            var items = [];
            document.querySelectorAll('.listing-card').forEach(card => {
                var id = card.getAttribute('data-obid');
                var title = card.querySelector('h3,h2')?.textContent?.trim();
                var cardText = card.textContent?.trim()?.substring(0,400) || '';
                var dds = Array.from(card.querySelectorAll('dd')).map(d=>d.textContent.trim());
                var loc = card.querySelector('[class*=address],[class*=locality]')?.textContent?.trim()||'';
                if (id && title) items.push({
                    id: id, title: title, location: loc, cardText: cardText,
                    price: dds[0]||'', sqm: dds[1]||'', rooms: dds[2]||'',
                    url: 'https://www.immobilienscout24.de/expose/'+id
                });
            });
            return items;
        }''')

        for l in listings:
            tl = (l.get('title','') + ' ' + l.get('cardText','')).lower()
            if any(k in tl for k in LISTING_KILLWORDS): continue
            results.append({**l, 'source': 'ImmoScout', 'region': region_name})

        print(f"    ImmoScout {region_name}: +{len(listings)}")
        time.sleep(2)

    except Exception as e:
        print(f"    ImmoScout {region_name}: ERR {str(e)[:60]}")

    return results


def scrape_kleinanzeigen_jsonld(page, region_name, loc_id):
    """Scrape Kleinanzeigen by extracting JSON-LD from script tags."""
    results = []
    keywords = ['alleinlage','einzellage','freistehend','wald','bungalow','bauernhaus']

    for kw in keywords:
        url = f"https://www.kleinanzeigen.de/s-{kw}/{loc_id}/preis::1350/c205{loc_id}?page=1"

        try:
            page.goto(url, timeout=15000)
            time.sleep(4)

            try:
                btn = page.locator('button:has-text("Alle akzeptieren")')
                if btn.is_visible(timeout=3000): btn.click(); time.sleep(0.5)
            except: pass

            listings = page.evaluate(r'''function() {
                var items = [];
                var scripts = document.querySelectorAll('script[type="application/ld+json"]');
                for (var i = 0; i < scripts.length; i++) {
                    try {
                        var data = JSON.parse(scripts[i].textContent);
                        if (data.title && (data.description || data.contentUrl)) {
                            items.push({
                                title: data.title, description: (data.description||'').substring(0,300),
                                image: data.contentUrl||'', url: 'https://www.kleinanzeigen.de',
                                source: 'Kleinanzeigen', region: '???'
                            });
                        }
                    } catch(e) {}
                }
                return items;
            }''')

            for l in listings:
                tl = l.get('title','').lower()
                if any(k in tl for k in LISTING_KILLWORDS): continue
                results.append({**l, 'region': region_name})

            print(f"    KA {kw} {region_name}: +{len(listings)}")
            time.sleep(1)
        except Exception as e:
            print(f"    KA {kw} {region_name}: ERR {str(e)[:60]}")

    return results


def scrape_wohnungsboerse(page, base_url):
    results = []
    url = f"{base_url}/haus-mieten-{MAX_PRICE}.html"

    try:
        page.goto(url, timeout=15000)
        time.sleep(2)

        listings = page.evaluate(r'''function() {
            var items = [];
            var links = document.querySelectorAll('a');
            for (var i = 0; i < links.length; i++) {
                var a = links[i];
                if (a.href && a.textContent.trim().length > 15 && a.href.includes('/immobilien/') && !a.href.includes('.html?')) {
                    items.push({title: a.textContent.trim().substring(0,80), url: a.href});
                }
            }
            return items;
        }''')

        for l in listings[:20]:
            tl = l.get('title','').lower()
            if any(k in tl for k in LISTING_KILLWORDS): continue
            results.append({**l, 'source': 'Wohnungsboerse', 'region': base_url.split('.')[0].split('/')[-1]})

        print(f"    wohnungsboerse: +{len(listings[:20])}")
        time.sleep(1.5)

    except Exception as e:
        print(f"    wohnungsboerse: ERR {str(e)[:60]}")

    return results


def scrape_immosurf(page, region_name, region_slug):
    results = []
    url = f"https://immosurf.de/mieten/haus/{region_slug}"

    try:
        page.goto(url, timeout=15000)
        time.sleep(2)

        listings = page.evaluate(r'''function() {
            var items = [];
            var links = document.querySelectorAll('a[href*="/immobilien/"], a[href*="/mieten/"]');
            for (var i = 0; i < links.length; i++) {
                var a = links[i];
                if (a.textContent.trim().length > 15 && a.href) items.push({title: a.textContent.trim().substring(0,80), url: a.href});
            }
            return items;
        }''')

        for l in listings[:20]:
            tl = l.get('title','').lower()
            if any(k in tl for k in LISTING_KILLWORDS): continue
            results.append({**l, 'source': 'ImmoSurf', 'region': region_name})

        print(f"    ImmoSurf {region_name}: +{len(listings[:20])}")
        time.sleep(1.5)

    except Exception as e:
        print(f"    ImmoSurf {region_name}: ERR {str(e)[:60]}")

    return results


def scrape_ohne_makler(page):
    results = []
    url = "https://www.ohne-makler.net/themen/besondere-lage/alleinlage/miete/"

    try:
        page.goto(url, timeout=15000)
        time.sleep(2)

        listings = page.evaluate(r'''function() {
            var items = [];
            var links = document.querySelectorAll('a[href*="/immobilien/"], a[href*="/haus/"]');
            for (var i = 0; i < links.length; i++) {
                var a = links[i];
                if (a.textContent.trim().length > 15 && a.href) items.push({title: a.textContent.trim().substring(0,80), url: a.href});
            }
            return items;
        }''')

        for l in listings[:20]:
            tl = l.get('title','').lower()
            if any(k in tl for k in LISTING_KILLWORDS): continue
            results.append({**l, 'source': 'OhneMakler', 'region': 'DE-weit'})

        print(f"    OhneMakler: +{len(listings[:20])}")
        time.sleep(1.5)

    except Exception as e:
        print(f"    OhneMakler: ERR {str(e)[:60]}")

    return results


def scrape_makler_sites(page):
    results = []
    maklers = [
        ('RTL Immobilien', 'https://www.rtl-immobilien.de/Mietangebote.htm'),
        ('Antaris', 'https://www.antaris-immobilien.de/immobilien/?kategorie=vermietung'),
    ]

    for name, url in maklers:
        try:
            page.goto(url, timeout=15000)
            time.sleep(2)

            listings = page.evaluate(r'''function() {
                var items = [];
                var links = document.querySelectorAll('a[href*="/immobilien/"], a[href*="/miet/"]');
                for (var i = 0; i < links.length; i++) {
                    var a = links[i];
                    if (a.textContent.trim().length > 15 && a.href) items.push({title: a.textContent.trim().substring(0,80), url: a.href});
                }
                return items;
            }''')

            for l in listings[:20]:
                tl = l.get('title','').lower()
                if any(k in tl for k in LISTING_KILLWORDS): continue
                results.append({**l, 'source': name, 'region': 'DE-weit'})

            print(f"    {name}: +{len(listings[:20])}")
            time.sleep(1.5)

        except Exception as e:
            print(f"    {name}: ERR {str(e)[:60]}")

    return results


def scrape_detail_cdp(page, item):
    try:
        url = item.get('url', '')
        if not url or not url.startswith('http'): return None

        page.goto(url, timeout=10000)
        time.sleep(1)

        detail = page.evaluate(r'''function() {
            var d = {title:'',price:'',location:'',description:'',attrs:{}};
            var h1 = document.querySelector('h1');
            if (h1) d.title = h1.textContent.trim().replace(/^Reserviert\s*[•·]\s*Gelöscht\s*[•·]*/,'');
            var priceEl = document.querySelector('h2[class*=price],#contactBoxTop .font-bold,[class*=price-detail]');
            if (priceEl) d.price = priceEl.textContent.trim();
            var locEl = document.querySelector('[data-qa="locality"],[id*=locality],.zip-region-and-country');
            if (locEl) d.location = locEl.textContent.trim();
            var descEl = document.querySelector('#viewad-description-text,[data-qa="description"] p,[class*=description] p,[id*=description] p,[class*=adDescriptionText]');
            if (descEl) d.description = descEl.textContent.trim().substring(0,800);
            var critEls = document.querySelectorAll('[class*=criterions] li,dl dt,dl dd,[class*=key-fact]');
            for (var i = 0; i < critEls.length; i++) {
                var el = critEls[i];
                d.attrs[el.className?.substring(0,30)||'x'] = el.textContent?.trim()?.substring(0,60);
            }
            try {
                var scripts = document.querySelectorAll('script');
                for (var i = 0; i < scripts.length; i++) {
                    var t = scripts[i].textContent || '';
                    var hm = t.match(/"Haustyp"\s*:\s*"([^"]+)"/);
                    if (hm && !d.attrs['Haustyp']) d.attrs['Haustyp'] = hm[1];
                    var wm = t.match(/"Warmmiete"\s*:\s*"([^"]+)"/);
                    if (wm && !d.attrs['Warmmiete']) d.attrs['Warmmiete'] = wm[1]+' €';
                }
            } catch(e){}
            return d;
        }''')

        if not detail or not detail.get('title'):
            try:
                body = page.evaluate(r'''function() { return document.body?.innerText?.substring(0,3000) || ""; }''')
                if len(body) > 200:
                    h1 = page.evaluate(r'''function() { return document.querySelector("h1")?.textContent?.trim() || ""; }''')
                    if h1:
                        detail['title'] = h1
                        idx = body.find('€\n') if '€\n' in body else body.find('€ ')
                        detail['description'] = body[idx:idx+500].strip() if idx > 0 else body[300:800].strip()
            except: pass

        return detail if (detail and detail.get('title')) else None

    except Exception as e:
        print(f"      DETAIL ERR: {str(e)[:60]}")
        return None


def filter_and_score(item, detail):
    full = f"{detail.get('title','')} {detail.get('description','')} {str(detail.get('attrs',{}))} {item.get('cardText','')}".lower()

    typ = detail.get('attrs',{}).get('Typ','').lower()
    if any(k in typ for k in ['doppelhaus','reihenhaus','mehrfamilien','wohnung']):
        return None, f"TYP-KILL: {typ}"

    killed = [k for k in HARD_KILLS if k in full]
    if killed:
        return None, f"KILLED: {killed[0]}"

    if 'freistehend' not in full and 'bungalow' not in full and 'landhaus' not in full and 'bauernhaus' not in full:
        return None, "NOT FREISTEHEND"

    warm = detail.get('attrs',{}).get('Warmmiete','')
    wn = price_num(warm) if warm else price_num(item.get('price',''))
    if wn > MAX_PRICE:
        return None, f"PRICE {wn} > {MAX_PRICE}"

    ht = haustier_ok(full)
    if ht == 'verboten':
        return None, "HAUSTIERE VERBOTEN"

    score = alleinlage_score(full)
    return {**item, 'detail': detail, 'haustier': ht, 'score': score}, f"[{score}] ✓ freistehend | {ht}"


def main():
    from camoufox.sync_api import Camoufox

    print(f"{'='*60}")
    print(f"🏠 HAUS-SUCHE MASSIVE v6 — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    print("=== PHASE 0: BROWSER SETUP ===")
    print("  Using Camoufox (anti-detection browser)\n")

    with Camoufox(headless=True) as browser:
        page = browser.new_page()
        results = run_scrape_with_browser(page)

    print(f"\n{'='*60}")
    if results:
        results.sort(key=lambda x: (-x.get('score',0), price_num(x.get('detail',{}).get('attrs',{}).get('Warmmiete','0'))))
        high_score = sum(1 for r in results if r.get('score',0) >= 4)
        mid_score = sum(1 for r in results if 1 <= r.get('score',0) < 4)
        low_score = sum(1 for r in results if r.get('score',0) == 0)
        print(f"📊 {len(results)} Ergebnisse | 🌲={high_score} 🏠={mid_score} 🏘️={low_score}")
    else:
        print("📭 Keine Treffer.")
        return

    if results:
        msgs = [f"""🏠🌲 **HÄUSER ZUR MIETE** 🌲🏠
*Freistehend, max {MAX_PRICE}€ warm | Quellen: ImmoScout + Kleinanzeigen + Wohnungsboerse + ImmoSurf + OhneMakler + Makler*
🌲 = Alleinlage-Hinweis | 🏠 = freistehend | 🏘️ = allgemein
*{len(results)} Angebote*
━━━━━━━━━━━━━━━━━━━━━━━━"""]

        cur = ""
        for i, item in enumerate(results, 1):
            d = item.get('detail',{})
            ht = item.get('haustier','?')
            score = item.get('score',0)
            marker = '🌲' if score>=4 else '🏠' if score>=1 else '🏘️'
            ht_icon = '🐾' if ht=='ok' else '❓'

            e = f"\n{marker} **{i}. {d.get('title',item.get('title','?'))[:55]} — {item.get('price','?')}**\n"
            e += f"📍 {d.get('location',item.get('location','?'))} | {item['region']} ({item['source']})\n"
            e += f"{ht_icon} Haustiere: {'✓' if ht=='ok' else '?'} | Score: {score}/20\n"
            a = d.get('attrs',{})
            if a.get('Warmmiete'): e += f"💰 Warm: {a['Warmmiete']}\n"
            if a.get('Wohnfläche') or a.get('Zimmer'): e += f"📐 {a.get('Wohnfläche','')} | {a.get('Zimmer','')} Zi\n"
            if d.get('description'):
                desc = d['description'].replace('\\n',' ').strip()[:150]
                e += f"📋 {desc}\n"
            e += f"🔗 {item['url']}\n"

            if len(cur)+len(e) > 1800:
                msgs.append(cur)
                cur = e
            else:
                cur += e

        if cur:
            cur += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n⏰ *Nächster Report in 15 Minuten*"
            msgs.append(cur)

        print(f"📤 Posting {len(msgs)} messages to Discord...")
        post_discord(msgs)
        print("✅ Done!")
    else:
        print("📭 Keine Treffer. Stille Meldung.")


def run_scrape_with_browser(page):
    seen = set()
    all_listings = []

    print("=== TIER 1: ImmoScout24 ===")
    for region_name, region_slug, _ in REGIONS:
        results = scrape_immoscout(page, region_name, region_slug)
        for r in results:
            key = r.get('title','')[:80]
            if key and key not in seen:
                seen.add(key)
                all_listings.append(r)

    print("\n=== TIER 1: Kleinanzeigen ===")
    for region_name, _, loc_id in REGIONS:
        results = scrape_kleinanzeigen_jsonld(page, region_name, loc_id)
        for r in results:
            key = r.get('title','')[:80]
            if key and key not in seen:
                seen.add(key)
                all_listings.append(r)

    print("\n=== TIER 1: Wohnungsboerse Regional ===")
    wnb_sources = [
        ('MeckPomm', 'https://www.mecklenburg-vorpommern.wohnungsboerse.net'),
        ('Thüringen', 'https://www.thueringen.wohnungsboerse.net'),
        ('Sachsen', 'https://www.sachsen.wohnungsboerse.net'),
        ('Hessen', 'https://www.hessen.wohnungsboerse.net'),
    ]
    for region_name, base_url in wnb_sources:
        results = scrape_wohnungsboerse(page, base_url)
        for r in results:
            if r.get('url') and r['url'] not in seen:
                seen.add(r['url'])
                all_listings.append(r)

    print("\n=== TIER 2: ImmoSurf ===")
    for region_name, region_slug, _ in REGIONS[:3]:
        results = scrape_immosurf(page, region_name, region_slug)
        for r in results:
            if r.get('url') and r['url'] not in seen:
                seen.add(r['url'])
                all_listings.append(r)

    print("\n=== TIER 2: OhneMakler ===")
    results = scrape_ohne_makler(page)
    for r in results:
        if r.get('url') and r['url'] not in seen:
            seen.add(r['url'])
            all_listings.append(r)

    print("\n=== TIER 3: Makler-Seiten ===")
    results = scrape_makler_sites(page)
    for r in results:
        if r.get('url') and r['url'] not in seen:
            seen.add(r['url'])
            all_listings.append(r)

    print(f"\n📋 Total filtered listings: {len(all_listings)}")

    MAX_DETAIL = min(MAX_DETAIL_FETCH, len(all_listings))
    scrape_list = all_listings[:MAX_DETAIL]
    print(f"=== DETAIL-SCRAPING {len(scrape_list)}/{len(all_listings)} ===\n")

    results = []
    for i, item in enumerate(scrape_list):
        if i > 0 and i % 25 == 0: time.sleep(1)

        try:
            detail = scrape_detail_cdp(page, item)
            if not detail: continue

            filtered, reason = filter_and_score(item, detail)
            if filtered is None:
                print(f"  [{i+1}] ✗ {reason[:40]} — {detail.get('title','')[:35] or item.get('title','?')[:35]}")
                continue

            results.append(filtered)
            score = filtered.get('score', 0)
            marker = '🌲' if score >= 4 else '🏠' if score >= 1 else '🏘️'
            warm = detail.get('attrs',{}).get('Warmmiete','')
            print(f"  [{i+1}] {marker}[{score}] ✓ {detail['title'][:45]} | {warm or item.get('price','?')} | {filtered.get('haustier','?')}")

        except Exception as e:
            continue

    return results


if __name__ == "__main__":
    main()
