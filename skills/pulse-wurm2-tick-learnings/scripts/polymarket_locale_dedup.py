#!/usr/bin/env python3
"""
polymarket_locale_dedup.py — pulse-wurm2 PITFALL #88 / class #9 defense.

When a pulse_research_result has heavy Polymarket locale-clone pollution
(15+ language variants of the same market URL), this script extracts the
canonical (no-locale) URL for each slug and surfaces the substantive
non-PM URLs in priority order.

Origin: tick 36 (2026-06-23) BofA deep job — 18/20 top returned candidates
were locale variants of will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026.
The load-bearing r/CryptoCurrency 1u23u6a URL (721 upvotes) was buried
in items_by_source behind 18 locale clones.

Usage:
    from polymarket_locale_dedup import dedup_kept_candidates
    kept = pulse_research_result['body']['result']['candidates']
    substantive = dedup_kept_candidates(kept)
    for c in substantive[:10]:
        print(c['url'], c['title'])
"""
import re
from typing import List, Dict, Any

# Matches /<locale>/event/<slug> in a Polymarket URL.
# Locales follow BCP 47: 2-letter language, optional region subtag.
LOCALE_EVENT_PATTERN = re.compile(
    r'^https?://polymarket\.com/'
    r'(?:[a-z]{2}(?:-[a-z]+)?/)'         # optional locale prefix
    r'event/'
    r'([^?#/]+)'                          # capture slug
    r'.*$'
)
# Also matches canonical /event/<slug> URLs (no locale).
CANONICAL_EVENT_PATTERN = re.compile(
    r'^https?://polymarket\.com/event/([^?#/]+).*$'
)
# Polymarket OG-image fetches (load-bearing for image rendering, not data).
API_OG_PATTERN = re.compile(r'polymarket\.com/api/og\?')

# Noise domains that frequently appear as worm-follow noise.
NOISE_DOMAINS = {
    'github.com',         # sidebars: /features/copilot, /pricing, etc
    'docs.github.com',
    'skills.github.com',
    'maintainers.github.com',
    'support.github.com',
    'stars.github.com',
    'archiveprogram.github.com',
    'securitylab.github.com',
    'github.io',
    'youtube.com',        # channel pages, not content
    'youtu.be',
    'web.archive.org',    # archive snapshots — only useful if explicit
    'archive.org',
    'w3.org',
    'cloudflare.com',
}


def _is_polymarket_locale_noise(url: str) -> bool:
    """True if URL is a locale-clone or API/og image fetch."""
    if API_OG_PATTERN.search(url):
        return True
    if LOCALE_EVENT_PATTERN.match(url) and not CANONICAL_EVENT_PATTERN.match(url):
        # Matches /<locale>/event/<slug> but NOT canonical /event/<slug>
        return True
    return False


def _slug_from_url(url: str) -> str:
    """Extract the Polymarket event slug from any variant URL."""
    for pattern in (CANONICAL_EVENT_PATTERN, LOCALE_EVENT_PATTERN):
        m = pattern.match(url)
        if m:
            return m.group(1)
    return url


def _is_substantive(url: str) -> bool:
    """True if URL is not a noise domain."""
    for domain in NOISE_DOMAINS:
        if domain in url:
            return False
    return True


def dedup_kept_candidates(
    candidates: List[Dict[str, Any]],
    keep_canonical_pm: bool = True,
) -> List[Dict[str, Any]]:
    """
    Deduplicate a pulse_research_result kept-candidates list.

    1. Drops API/og image fetches.
    2. Collapses locale-clone PM URLs to a single canonical entry.
    3. Optionally drops the canonical PM entry too (if the load-bearing
       finding is on a different source like Reddit/CoinDesk).
    4. Sorts with non-PM substantive URLs first, then canonical PM,
       then everything else.

    Args:
        candidates: kept-candidates from pulse_research_result.
        keep_canonical_pm: if True, retain one canonical PM URL per slug
            (useful when PM slugs are the institutional-consensus signal
            per §44). If False, drop all PM URLs.

    Returns:
        Deduped, priority-sorted candidate list.
    """
    seen_slugs: set = set()
    pm_canonicals: List[Dict[str, Any]] = []
    substantive: List[Dict[str, Any]] = []
    noise: List[Dict[str, Any]] = []

    for c in candidates:
        url = c.get('url', '')
        if not url:
            continue
        if _is_polymarket_locale_noise(url):
            continue
        if 'polymarket.com/event/' in url:
            slug = _slug_from_url(url)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            if keep_canonical_pm:
                pm_canonicals.append(c)
            continue
        if _is_substantive(url):
            substantive.append(c)
        else:
            noise.append(c)

    return substantive + pm_canonicals + noise


def locale_clone_ratio(candidates: List[Dict[str, Any]]) -> float:
    """Returns fraction of candidates that are locale-clone / og-image PM URLs.

    Use to detect PITFALL #88 / class #9 hijack: ratio > 0.5 means the
    top-20 is dominated by locale clones. Apply dedup_kept_candidates.
    """
    if not candidates:
        return 0.0
    n_locale = sum(
        1 for c in candidates
        if _is_polymarket_locale_noise(c.get('url', ''))
    )
    return n_locale / len(candidates)


if __name__ == '__main__':
    # Smoke test: synthetic kept-candidates list with locale pollution
    test = [
        {'url': 'https://polymarket.com/event/will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026', 'title': 'Canonical'},
        {'url': 'https://polymarket.com/de/event/will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026', 'title': 'German clone'},
        {'url': 'https://polymarket.com/zh-hant/event/will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026', 'title': 'Chinese clone'},
        {'url': 'https://polymarket.com/api/og?eslug=will-usd-denominated-stablecoin-market-share-fall-below-99-in-2026', 'title': 'OG image'},
        {'url': 'https://old.reddit.com/r/CryptoCurrency/comments/1u23u6a/bofa_ceo_warns_stablecoin_yield_could_drain_35_of/', 'title': 'BofA CEO Reddit'},
        {'url': 'https://github.com/features/copilot', 'title': 'GH sidebar noise'},
        {'url': 'https://fortune.com/2026/03/26/anthropic-says-testing-mythos-powerful-new-ai-model-after-data-leak-reveals-its-existence', 'title': 'Fortune Mythos leak'},
    ]
    ratio = locale_clone_ratio(test)
    print(f"Locale-clone ratio: {ratio:.0%} (expect 4/7 = 57%)")
    deduped = dedup_kept_candidates(test)
    print(f"\nDeduped to {len(deduped)} substantive URLs:")
    for c in deduped:
        print(f"  {c['title'][:60]:<60} | {c['url'][:80]}")
    # Expected order: Reddit (substantive) + Fortune (substantive) + Canonical PM + GitHub (noise)
