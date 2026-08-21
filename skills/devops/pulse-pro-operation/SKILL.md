---
name: pulse-pro-operation
description: Operate the pulse-pro research Pod and fix its Wurm drift.
---

# pulse-pro-operation

pulse-pro is a license-gated rootless Podman Pod exposing a FastAPI surface on
`http://127.0.0.1:8770`.

## ⚠️ USER CORRECTION — community `pulse` BEATS pro-worm for niche/technical topics
The user said **"nutz die community version erstmal"** after an 11-run, 4-image-rebuild
Pro investigation returned ONLY junk (Reddit drama, Arxiv "Ti"=Titan metallurgy,
Polymarket GPU-price bets) for a WebGL/GPU/instancing query. That session PROVED
the reverse of this skill's original premise:
- `pulse` (community, `/home/alca/.hermes/skills/devops/pulse`) with
  `--depth deep --emit full --no-llm` returns the REAL signals for niche tech:
  MDN WebGL best practices, WebGPU Render Bundle post-mortem (Loke.dev),
  NullGraph (data-oriented WebGPU), Three.js TSL instancing, PlayCanvas HW
  instancing docs, NVIDIA GPU Gems Ch.3 Geometry Instancing, ECS-vs-OOP benchmarks.
- pro-worm returned 0 usable candidates EVEN AFTER: anchor-filter patch,
  `graphics_tech` query_router patch, strict host allow-list, llama.cpp/Gemma
  backend wired in, AND `~/.cache/pulse/cache.db` deleted. Run 11 (v4 image +
  cleared cache) still reported `anchor-filter | dropped 60 kept 0`.

**Therefore: for niche/technical/research topics, START with the community
`pulse` skill (`--depth deep --emit full`).** Only reach for pro-worm if the
community version is insufficient AND you accept a long debugging cycle
(cache clear + image rebuild + redeploy via `systemctl`) that may still yield
nothing. The pro-pod's Search-fan-out has a deeper defect (even with
`graphics_tech` routing + cleared cache it returns non-WebGL results) that the
anchor/router patches in `references/` do NOT fully resolve. The pro-pod is fine
for broad/social "what are people saying" topics; it is unreliable for precise
technical retrieval. See `references/community-vs-pro.md` for the exact working
command + the curated WebGL findings that came out of this session.

## ⚠️ DEEP-WURM IS NON-FUNCTIONAL ON THIS POD (learned 2026-08-17)
Deep-wurm on this pod has two fatal flaws:
1. **Anchor filter is too aggressive** — drops 90%+ of candidates (e.g. 59/60,
   49/60, 55/60 across three parallel jobs). The strict topic lock kills even
   relevant results instead of keeping them for manual curation.
2. **API doesn't expose candidate content** — `/research/jobs/{job_id}/result`
   returns "Not Found" even when jobs complete with `state:"done"`. The job
   pipeline runs internally (search→anchor-filter→dig) but never surfaces
   candidates through the REST API.

**Workaround: use iterative mode instead.** It actually returns usable content:
```bash
# Single topic, sequential rounds — works with single-slot llama-server
python3 -m pulse_cli.research --topic "<query>" --depth deep --emit md --iterative --max-rounds 3 --no-llm
```
Iterative mode gave us 65 items across three runs (WebGL SIMD 21, WebGPU Compute 19, Shader Opt 25) with actual content. Crew mode times out on single-slot setups.

**Bottom line:** For niche/technical topics on this pod, skip deep-wurm entirely.
Use iterative mode or the community CLI build. Deep-wurm is a dead end here.


## Architecture
```
llama.cpp (Gemma Q8) :8080  ─┐
                              ├─> Ollama-compat proxy :11435 ─> pulse-api Pod :8770 (FastAPI) ─> Wurm
Ollama (host) :11434        ─┘   (translates /api/tags + /api/generate
                                 to /v1/chat/completions)
```
CRITICAL: the Pod speaks **only Ollama protocol** (`/api/tags`, `/api/generate`).
llama.cpp speaks OpenAI-compat. The proxy bridges them — you cannot point the
Pod directly at llama.cpp :8080.

## Running a research job (async — REQUIRED for deep/wurm)
Deep + wurm dives run 30–120 min; the MCP/HTTP client kills sync calls at
~120s. ALWAYS use the async flow:
```
POST /research/start  {topic, depth:"deep", wurm:true, max_wurm_rounds:N,
                        lookback_days:100, llm_filter:bool, n:50, emit:"md"}
   -> {job_id, state:"running"}
GET  /research/jobs/{job_id}         # poll state / phases / heartbeat_age_seconds
GET  /research/jobs/{job_id}/result  # full ranked candidates when done
```
`llm_filter` caveat: the post-rank filter uses the SAME LLM. Aggressive /
uncensored models (e.g. Gemma "Aggressive") often return `none` → the filter
drops EVERYTHING (seen: kept 0 / 103). **Set `llm_filter:false`** to keep raw
candidates and curate manually — this is the normal operating mode.

## Two failure modes + fixes
### 1. LLM-filter collapse
Symptom: 400+ candidates aggregated, filter keeps 0. Cause: the on/off-topic
judge model is too aggressive. Fix: `llm_filter:false`.

### 2. Wurm seed-drift (OFF-TOPIC results)
Symptom: dig rounds grow (+80/round) but results are Reddit drama / Arxiv "Ti"
(Titan) papers / Polymarket. Cause: the crawler follows links from seed pages
with no topic lock; the Search phase also returns junk (heuristic matches the
"Ti" bigram → Titan metallurgy; a `w3.org` allow-list → "XHTML namespace").
Fix: the **anchor-filter** — see `references/worm-anchor-fix.md`. Three filter
points in `scripts/lib/worm.py` + a pre-worm filter in `pod/pulse_pod/app.py`,
plus a STRICT host allow-list (only WebGL/GPU-specific hosts pass without a text
check; generic arxiv/github/w3.org are EXCLUDED).

### 3. Cache poisoning (patched code has NO effect — stale junk returned)
Symptom: you patch `query_router.py` (e.g. add a `graphics_tech` type) or the
worm anchor, redeploy, re-run — and STILL get Reddit drama / Arxiv "Ti"=Titan
metallurgy / Polymarket GPU-price bets. The code change never executes.
Root cause: the Search phase reads from a SQLite cache BEFORE live sources. The
cache (`~/.cache/pulse/cache.db` + `-wal` + `-shm`, ~44 MB) was seeded by the
first runs (which returned junk) and is returned on every later run. Critically,
`use_cache:false` in the request does NOT bypass this — the source-level
`CACHE_CHECK` still returns `got=list` from the DB even with caching "off".
Debug signature (run `pipeline.run` in the container / watch source logs):
```
CACHE_CHECK: source=rss got=list val=[{'id':'rss-1','title':'Responsible and safe use of AI',...}]
CACHE_CHECK: source=arxiv got=list val=[{'id':'arxiv-1','title':'NLTE effects of Ti~I in M dwarfs',...}]
```
If you see `got=list` with OLD/junk titles, the cache is poisoned.
Fix — see `references/cache-poisoning.md`. TL;DR: stop pod, `rm -f
~/.cache/pulse/cache.db*`, restart. ALWAYS clear the cache after editing
`query_router.py` / `pipeline.py` / source scoring, or when a code fix produces
no change in results.

KEY DEPLOY LESSON: the REAL quadlet is `~/.config/containers/systemd/pulse-api.container`
— NOT `pod/quadlet/pulse-api.container` (that is only a template!). After editing
env: `systemctl --user daemon-reload && podman rm -f systemd-pulse-api &&
systemctl --user start pulse-api.service`. `systemctl restart` ALONE does not
pick up new env — the container is persistent, so you must `rm` + `start` to
rebuild it from the patched quadlet. Then rebuild the image if you patched Pod
code: `podman build -f pod/Containerfile -t localhost/pulse-pod:latest .`
If you changed `query_router.py` / `pipeline.py` / source scoring OR see unexplained
junk that your patch should have fixed, the Search cache is likely poisoned —
clear it: stop pod, `rm -f ~/.cache/pulse/cache.db ~/.cache/pulse/cache.db-shm
~/.cache/pulse/cache.db-wal`, restart. `use_cache:false` does NOT bypass the
source-level cache, so deletion is the only reliable clear. (See
`references/cache-poisoning.md`.)

## Wiring a local llama.cpp model (Gemma) as the backend
See `references/llama-cpp-backend.md` + `scripts/ollama-compat-proxy.py`.
Summary: start llama.cpp on :8080 with the GGUF, run the proxy on :11435, patch
the quadlet's `OLLAMA_BASE_URL`/`OLLAMA_MODEL` to point at the proxy + Gemma,
rebuild the image, redeploy.

## Verification checklist
- Pod live: `curl http://127.0.0.1:8770/healthz` → `{"status":"ok"}`
- Proxy: `curl http://localhost:11435/api/tags` → lists the Gemma model
- Env in container: `podman inspect systemd-pulse-api | grep OLLAMA`
- Good Wurm run: `anchor-filter` phase drops junk, dig rounds each +50..+90,
  final candidates are WebGL-specific (threejs.org / webgpu.com /
  developer.mozilla.org), NOT Reddit/Arxiv-Ti.
- Search NOT cached-stale: after clearing `~/.cache/pulse/cache.db*`, a fresh run
  hits live sources (debug logs show `CACHE_CHECK: source=X got=NoneType`, not
  `got=list` with old titles). If you still see `got=list` junk, cache wasn't cleared.

## Related
- `pulse` (community skill) — **PREFER THIS for niche/technical research** with
  `--depth deep --emit full --no-llm` (see `references/community-vs-pro.md`).
- mazemaker memory id 1107986 — architecture decision record for this setup.
- `references/worm-anchor-fix.md` — the anchor-filter code fix (3 points + strict host list).
- `references/cache-poisoning.md` — when patched code has no effect: Search cache is
  stale (use_cache:false does NOT bypass it); stop pod + `rm -f ~/.cache/pulse/cache.db*`.
- `references/llama-cpp-backend.md` — wiring a local llama.cpp (Gemma) model as the LLM backend.
- `scripts/ollama-compat-proxy.py` — Ollama-protocol → llama.cpp OpenAI-compat proxy.
