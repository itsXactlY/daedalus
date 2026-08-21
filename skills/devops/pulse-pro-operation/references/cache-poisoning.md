# Cache Poisoning (pulse-pro Search returns stale junk)

## Symptom
You patch `query_router.py` (e.g. add a `graphics_tech` type) or the worm anchor,
redeploy, run a research job — and still get Reddit drama / Arxiv "Ti"=Titan
metallurgy / Polymarket GPU-price bets. `anchor-filter` drops 60 → 0, or the
worm digs junk. The code change had NO effect.

## Root cause
The Search phase reads from a SQLite cache BEFORE hitting live sources. The cache
(`~/.cache/pulse/cache.db` + `-wal` + `-shm`, ~44 MB) was seeded by the FIRST
runs, which returned junk (the heuristic matched "Ti" → Titan metallurgy, routed
to arxiv; `w3.org` allow-list → "XHTML namespace"; Polymarket GPU-price bets).
Every later run returns the CACHED junk, so:
- `query_router` classification is never exercised (cached results already chosen)
- `use_cache:false` in the request does NOT bypass this — the source-level
  `CACHE_CHECK` still returns `got=list` from the DB even with caching "off".

Debug signature (run `pipeline.run` in the container or watch source logs):
```
CACHE_CHECK: source=rss got=list val=[{'id': 'rss-1', 'title': 'Responsible and safe use of AI', ...}]
CACHE_CHECK: source=arxiv got=list val=[{'id': 'arxiv-1', 'title': 'NLTE effects of Ti~I in M dwarfs', ...}]
```
If you see `got=list` with OLD/junk titles, the cache is poisoned. After a clean
clear + restart you should see `got=NoneType` (live fetch) instead.

## Fix
1. Stop + remove the pod (frees the open DB handles):
   `systemctl --user stop pulse-api.service && podman rm -f systemd-pulse-api`
2. Delete the cache DB files:
   `rm -f ~/.cache/pulse/cache.db ~/.cache/pulse/cache.db-shm ~/.cache/pulse/cache.db-wal`
3. Restart: `systemctl --user start pulse-api.service`
4. Re-run the research job — now sources are hit live and the router/anchor
   changes actually take effect.

## When to clear
- After ANY change to `query_router.py`, `pipeline.py`, source scoring, or when
  you see unexplained junk that your code patch should have fixed.
- Also safe to clear when the pod has been running a long time and you suspect
  stale topic routing. Deleting cache.db does NOT touch `lineage.db` or
  `dig_values.db` (those are separate; leave them unless told otherwise).
