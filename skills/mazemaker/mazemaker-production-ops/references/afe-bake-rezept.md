# DeepSeek-AFE-Bake-Rezept (einmaliger Korpus-Bake, 2026-08-07 validiert)

Ziel: A->B->C-Extraktion ueber den GANZEN Produktionskorpus (~61k long sources)
mit deepseek-v4-flash als Stage-C-Extraktor, damit das Brain wieder echten
Production-State erreicht. Danach uebernimmt llama wieder (afe-window bleibt lokal).

## Voraussetzungen

1. afe.py-Transport mit API-Key-Unterstuetzung (Commit b0184d2): `MAZEMAKER_AFE_API_KEY`
   schaltet Cloud-Mode an (Bearer-Header, repeat_penalty DROPPED — Cloud-APIs 400 sonst).
2. PG-first fuer AFE-Quellen (e9e9670): die Phase liest aus dem Postgres-Store.
   OHNE das findet sie 0 sources (SQLite ist eine 0-Byte-Huelle).
3. `enable_llm_always` (3539c0c): C laeuft zusaetzlich zu A/B via MAZEMAKER_AFE_LLM_ALWAYS=1.
4. `MAZEMAKER_AFE_DONE_KEY` (dbcd3a6): eigener processed-Set-Key fuer den Bake.

## Env-Rezept (je Worker-Container)

```
MAZEMAKER_AFE_LLM_FALLBACK=1
MAZEMAKER_AFE_LLM_ALWAYS=1
MAZEMAKER_AFE_LLM_URL=https://api.deepseek.com/v1/chat/completions
MAZEMAKER_AFE_API_KEY=<aus ~/.hermes/config.yaml providers.deepseek.api_key, chmod 600>
MAZEMAKER_AFE_MODEL=deepseek-v4-flash
MAZEMAKER_AFE_LLM_REASONING=0          # Operator: KEIN Reasoning, keine Erfindungen
MAZEMAKER_AFE_LLM_TEMP=0.0             # deterministisch (Cloud-Modell, kein 3B-Degenerieren)
MAZEMAKER_AFE_LLM_TRUNCATE=48000       # Plain-Pfad-Default 3000 wuerde Sessions wegwerfen
MAZEMAKER_AFE_DONE_KEY=afe_processed_ids_bake
MAZEMAKER_AFE_SESSION_MAX_CHARS=32000
MAZEMAKER_AFE_MAX_PER_CYCLE=3000
MAZEMAKER_AFE_WORKER_ID=<0..N-1>       # Engine-Sharding (id % N = wid)
MAZEMAKER_AFE_N_WORKERS=<N, max 4>
MAZEMAKER_AFE_SKIP_CHUNKS=1
MM_ALLOW_CPU_RECALL=1                  # Arm auf CPU ok (Embedding bleibt GPU via HTTP-Worker)
EMBED_BACKEND=http
EMBED_CLIENT_ONLY=1
MM_EMBEDDING_WORKER_URL=http://localhost:8766
```

## Ablauf

1. Build: `bin/build-all-locked.sh --only=mcp` — KEINE python/-Commits waehrend des
   Builds (engine_sha-Label). Kette verifizieren: Image-Label == `bash client/pod/
   mazemaker/bin/engine-sha.sh` (Live-Hash) == Preflight-expected.
2. Retag: `podman tag registry.mazemaker.dev/mazemaker-mcp:1.0.0-rtm.5-gpu
   localhost/mazemaker-v2-mcp:gpu localhost/mazemaker-v2-mcp:latest`.
3. SMOKE zuerst: 1 Worker, MAX_PER_CYCLE=50, Log pruefen:
   - "AFE: N sources" (N>0 — sonst Store/DONE_KEY-Problem)
   - by_stage C>0 (sonst: ALWAYS-Env? TRUNCATE? API-Key?)
   - DeepSeek-Erreichbarkeit: `_stage_c_llm('...', 'deepseek-v4-flash')` direkt im
     Container testen (urllib loggt NICHT — ein fehlender https-Log ist kein Beweis).
4. Voller Bake: `bash /tmp/bake-afe-deepseek.sh 4 3000` (background, notify).
   Jeder Worker looped `--phase afe --once` bis "0 sources".
5. Fortschritt: `SELECT count(*) FROM memories WHERE label LIKE '%::afe::C%'` in PG.

## Verifikations-Befunde (2026-08-07)

- DeepSeek-Antwort (2.5s, temp 0.0): `[{"text": "user bevorzugt dunkle Themes", ...,
  "stage": "C"}, ...]` — sauber, keine Erfindung.
- Mock-Server-Beweis: Cloud-Mode sendet Bearer + KEIN repeat_penalty; Local-Mode
  sendet repeat_penalty + keinen Auth-Header.
- C=0 im ersten Smoke war der TRUNCATE=3000-Default (Block-Anfang ohne user-Fakten
  → DeepSeek antwortete korrekt mit []) — nicht der Transport.

## Pitfalls

- Das historische `afe_processed_ids`-Meta-Set ist ein Monster (100k+ IDs) — ohne
  `MAZEMAKER_AFE_DONE_KEY` kommt sofort "0 sources". Nie ohne frischen Key baken.
- Session-Aggregation: die 50 laengsten Quellen koennen EINE Session sein → 1 Block.
  MAX_PER_CYCLE zaehlt QUELLEN, nicht Bloecke.
- VRAM: 4 Worker max (jeder GPU-Arm 0.88 GB; Karte bei ~12/16 GB mit residentem Stack).
