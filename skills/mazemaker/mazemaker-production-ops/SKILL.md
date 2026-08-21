---
name: mazemaker-production-ops
description: "Mazemaker prod ops: AFE/Dream/Recall, bakes, builds."
version: 1.0.0
tags: [mazemaker, production, dream-engine, afe, bake, deploy]
---

# Mazemaker Production Ops

Betriebswissen fuer den Mazemaker-Produktionsstack (Pro-Pod auf dieser Box).
Konsolidiert aus den Deep-Audits und der Fix-Orgie vom 2026-08-07: 10 Fix-Punkte,
3 Wurzel-Befunde, ein DeepSeek-Korpus-Bake.

## Architektur-Kurzfassung (Stand 2026-08-07)

- Repos: `/home/alca/projects/mazemaker-pro` (Engine, python/ = Source of Truth),
  `/home/alca/projects/mazemaker` (Free/Community-Fork), `/home/alca/projects/mazemaker-v2-stack/backend`
  (Deployment: client/quadlet/, build-all-locked.sh, client/bin/).
- Stack: systemd --user + podman (Pod `mazemaker`), PG16+pgvector als Korpus-DB
  (~215k Memories), SQLite nur noch als leere Huelle (0 Bytes seit PG-Umzug!).
- Services: mazemaker-dream-worker (BindsTo dream.target, nur per CLI),
  mazemaker-mcp (dünner Client via HTTP-Embedding), mazemaker-embedding-worker
  (das EINE bge-m3, HTTP :8766), mazemaker-llm (llama-server, Nachtfenster).
- compute.toml ist RENDERED vom license-client (JWT-Claim) — manuelle Edits werden
  ueberschrieben; Policy-Defaults gehoeren in `python/compute_config.py` DEFAULTS.

## DIE drei Wurzel-Befunde (nicht wiederholen)

1. **0-Byte-SQLite-Hybrid-Falle**: Die Engine ist "Hybrid" (SQLite + PG-Mirror), aber
   nach dem PG-Umzug ist die SQLite-DB leer. JEDER Code, der den SQLite-Store fuer
   Quellen nutzt, findet "0 sources" — die AFE-Kette lief so MONATE mit B=0/C=0,
   waehrend der Bench (volle SQLite) tausende Fakten produzierte. Lektion: Bei
   Hybrid-Stores IMMER pruefen, welcher Store die Daten wirklich haelt; bei AFE
   PG-first (store = self._memory._postgres_store wenn armiert).
2. **NameError-Klasse bei Policy-Refactors**: compute_config-Umstellung (02fda91)
   fuegte `_cc_get(...)`-Nutzungen in Phasen ein, aber die Funktions-Imports banden
   nur `_cc_flag` — NREM und Synthesis crashten still ("NameError: name '_cc_get'
   is not defined") und liefen als No-Op weiter. Lektion: Nach solchen Refactors
   einen AST-Scan ueber ALLE `_cc_*`-Nutzungen laufen lassen (jede Nutzung muss im
   Funktions-Scope gebunden sein).
3. **engine-sha-Fingerprint-Fallen**: (a) Default-ENGINE_SRC zeigte aufs FREE-Repo
   (`~/projects/mazemaker/python`) statt Pro — der Hash war konstant, obwohl Pro sich
   aenderte. (b) Unter `set -euo pipefail` stirbt eine `while read`-Pipeline still
   (letzter read → exit 1 → pipefail) — xargs/sha256sum bekommen nichts → konstanter
   "Leer"-Hash. (c) `printf "%s\0"` unter dash erzeugt KEIN NUL — die Trennung
   verschwindet still. Lektion: Fingerprint-Skripte auf INHALTS-SENSITIVITAET testen
   (Datei aendern → Hash muss sich aendern; revert → zurueck), nicht nur auf
   Determinismus.

## Workflow: Build/Deploy-Kette (die Kette muss stimmen)

`build-all-locked.sh --only=mcp` baut Images auf `registry.mazemaker.dev/...rtm.5-gpu`.
Die Kette: **Image-Label == Live-Baum-Hash == Preflight-expected**. Der Preflight
(fail-closed seit 2026-08-07) blockt den mcp-Start bei Mismatch. Fallstricke:
- KEINE python/-Commits waehrend eines laufenden Builds — der rsync (COPY) sieht
  einen anderen Baum als der engine_sha-Aufruf am Build-Start → Label luegt.
  Bei Bedarf Build killen, committen, neu bauen (nicht hinterherflicken).
- Nach dem Build: `podman tag registry...:rtm.5-gpu localhost/mazemaker-v2-mcp:gpu
  localhost/mazemaker-v2-mcp:latest`, Binaries (`engine-sha.sh`, `mcp-preflight`,
  `mazemaker-update`) nach `~/.mazemaker/bin/` + `~/.local/bin/` kopieren,
  `systemctl --user daemon-reload`.
- deployed engine-sha.sh MUSS die aktuelle Repo-Version sein, sonst vergleicht der
  Preflight mit einem anderen Hash.
- `~/.mazemaker/installed.image_tag` + `desired.image_tag` stampfen (rtm.5), sonst
  meckert der Selftest tag-drift.

## Workflow: AFE-Korpus-Bake mit DeepSeek (einmalig)

Vollstaendiges Rezept: siehe `references/afe-bake-rezept.md`. Kernpunkte:
- Transport: `MAZEMAKER_AFE_LLM_URL=https://api.deepseek.com/v1/chat/completions` +
  `MAZEMAKER_AFE_API_KEY` (aus ~/.hermes/config.yaml providers.deepseek.api_key,
  Datei mit chmod 600). OpenAI-kompatibel, ABER **repeat_penalty ist llama.cpp-native
  → Cloud-APIs antworten 400**; afe.py sendet es nur ohne API-Key.
- User-Praeferez (OPERATOR): KEINE erfundenen Fakten. Immer `MAZEMAKER_AFE_LLM_REASONING=0`
  (kein DeepThink) + `MAZEMAKER_AFE_LLM_TEMP=0.0` (deterministisch). Temp 0.0 ist bei
  Cloud-Modellen ok; bei kleinen lokalen 3B-Modellen degeneriert es ("user is a user"-
  Schleife) — dort 0.8 lassen.
- `MAZEMAKER_AFE_LLM_ALWAYS=1`: C laeuft ZUSAETZLICH zu A/B (Default: nur als Fallback
  wenn A+B leer). Fuer den einmaligen Bake noetig, sonst wird C fast nie ausgefuehrt.
- `MAZEMAKER_AFE_LLM_TRUNCATE=48000`: der Plain-Pfad-Default (3000) kuerzt Sessions
  weg; DeepSeek kann 64k Kontext.
- `MAZEMAKER_AFE_DONE_KEY=afe_processed_ids_bake`: EIGENER processed-Set-Key. Das
  historische `afe_processed_ids` ist ein Monster (100k+ IDs) und blockt den Bake
  sofort mit "0 sources". Nie ohne frischen Key baken.
- Parallelisierung: `MAZEMAKER_AFE_WORKER_ID`/`MAZEMAKER_AFE_N_WORKERS` (Engine-Sharding,
  id % n = wid). 4 Worker max (jeder GPU-Arm waere 0.88 GB VRAM; Karte ist bei ~12/16).
  Fuer den Bake `MM_ALLOW_CPU_RECALL=1` setzen (Arm auf CPU ok — Embedding bleibt GPU
  ueber den HTTP-Worker), sonst failt STRICT beim Arm.
- Session-Aggregation: viele Quellen derselben Session werden zu EINEM Block —
  "50 Quellen → 1 Block" ist normal. Fortschritt zaehlt Bloecke, nicht Quellen.

## Workflow: READ-ONLY-Audit mit Crew

- Crew-Dispatch (delegate_task) mit 3 Streams (Engine-Kern, Dream-Pipeline,
  Deployment-Kette) oder Thesen-Orchestratoren (5 Thesen, je bis 3 Kinder).
- **Befunde NIE blind uebernehmen** — die Workers uebersehen oft vorgeschaltete
  Sanitizer/Regexes (2x erlebt: FTS/tsquery-"Injection" widerlegt, weil das
  Token-Regex die Metazeichen schon filtert). Top-Befunde selbst im Code verifizieren
  (read-only), Severities korrigieren, Report-Datei mit Verifikations-Sektion.
- Git-History ist die Zeitlinie: fuer jeden Defekt den EINFUEHRUNGS-Commit finden
  (git log -S / git blame) — "AB WANN war was kaputt".
- Delegation-Modell: in ~/.hermes/config.yaml `delegation:` block — NIE Free-Model-
  Roulette (nemotron-free lieferte 2x leere Reports/Timeout); deepseek-v4-flash pinned.

## Workflow: Verifikations-Disziplin (hermes-verify-Muster)

Jeder Fix bekommt ein ad-hoc-Skript unter /tmp/hermes-verify-<fix>.py mit
VERHALTENS-Tests (nicht nur Text-Checks):
- HTTP-Transport: lokalen Mock-HTTP-Server im Test starten, Requests captured
  (Headers + Body), Input/Output anzeigen — beweist was WIRKLICH rausgeht.
- GPU/Device-Logik: torch per sys.modules-Fake injizieren (Host hat kein torch) —
  der echte Codepfad laeuft, nicht eine Kopie der Logik.
- Fake-Memory/Fake-Store fuer Phasen-Logik (store-Wahl, done_key-Auswahl).
- AST-Scans fuer Scope-Klassen (alle _cc_-Nutzungen gebunden).
- WICHTIG: Check-Bugs sind haeufig (f-Strings statt Literale suchen, find trifft das
  falsche Vorkommen) — Checks debuggen, nicht den Code verbiegen.
- Kein pytest: die Repo-Suiten sind Standalone-Runner (`python test_suite.py`),
  pytest wuerde die @_testcase-Wrapper falsch sammeln.

## Pitfalls-Liste (gesammelt)

- tests/test_suite.py lief gegen die PRODUKTIONS-DB (SQLite 0 Bytes) und ihr
  Cleanup-Block konnte echte Daten loeschen → isolierte tmp-DB + hash-Backend.
- test_upside_down:805 verlangte cpp_dream_backend.py (existiert nicht) → Suite
  dauerhaft rot seit Mai; Listen-Fixes + ehrliche Skips (Backend-Typ pruefen statt
  Ordner-Existenz) → 171/171.
- DAE war "aktiv obwohl unwired" (Gewicht 0.0) — 193s/Zyklus fuer nichts; Drop-in
  dae-off.conf → .disabled-20260806 hat es reaktiviert. Policy in compute.toml pruefen.
- Worker-RAM: der 12.9-GB-Steady-State war _graph_nodes (Voll-Load, lazy_graph=False)
  + Python-Float-Materialisierung — gefixt durch 94cdc80 (lazy + include_embeddings)
  und P5 (SQLite iter_for_gpu_arm + chunked HNSW). RSS nach Arm ~1 GB, im Cycle <3.5 GB.
- systemd-oomd killt den groessten Verbraucher bei Slice-Druck >80% — MemoryHigh-Summe
  aller Units UNTER die RAM-Groesse bringen (31G Host → 28.25G Summe).
- Preflight fail-closed: Label-lose Images blocken den mcp — vor dem Deploy sicherstellen,
  dass das neue Image das Label traegt.
- GPU-STRICT: MM_RECALL_GPU_STRICT=1 (in beiden Pro-Quadlets) — kein stiller CPU-Fallback
  mehr; MM_ALLOW_CPU_RECALL=1 ist der explizite Opt-in (Dev/Tests/Bake).
- **ColBERT-Env-Gate an ZWEI Orten (a512c36)**: MM_COLBERT_ENABLED=0 gated nur den
  WRITE-Pfad (`_colbert_write_enabled`) — der READ-Kanal kam aus den Mode-Presets
  (advanced/hybrid → 0.5, skynet → 1.2) und dem compute.toml-Overlay (colbert_weight=1.5).
  Folge: embed_colbert-HTTP-Calls feuerten im Cycle im Sekundentakt, obwohl die Env=0
  war (gemessen 2026-08-08 05:25 — eine echte Cycle-Zeitquelle). Fix: die Env gewinnt
  ZULETZT (nach allen Presets/Overlays `colbert=0.0` wenn Env nicht 1/true/yes/on);
  Default ohne Env ist jetzt AUS (vorher 0.5-Preset). Lektion: Operator-Gates muessen
  ALLE Pfade einer Funktion abdecken — ein Knopf, der nur einen von zwei Pfaden schaltet,
  ist ein Lügen-Knopf.
- **Lizenz-Falle bei PG-Container-Tests**: Ohne Pro-Lizenz im Test-Container fällt die
  Engine STILL auf SQLite zurück ("MM_DB_BACKEND=postgres requested but the Postgres
  backend is a Pro feature; falling back to SQLite") — die PG-Tests testen dann
  unbemerkt SQLite. Fuer echte PG-Tests: license.jwt + jwt.v1.pub.ed25519 mounten +
  MAZEMAKER_LICENSE_PATH/MAZEMAKER_PUBKEY_PATH setzen (wie der echte mcp). Test gegen
  eine WEGWERF-DB (z.B. mazemaker_test), nie die Produktions-DB.
- **compute.toml ist RENDERED (license-client aus dem JWT)** — der Render setzt
  dae_enabled/colbert_enabled wieder auf true zurueck. Die STABILE Off-Schiene ist die
  Quadlet-Env (MAZEMAKER_DAE_ENABLED=0, MM_COLBERT_ENABLED=0) + die DEFAULTS in
  compute_config.py; die toml selbst nicht als Policy-Quelle fuer Off-Schalter editieren.

## Workflow: Operator-Praeferenz (2026-08-08, mehrfach wuetend geaeussert)

- **Keine Container/podman-Ketten fuer Tests**: Der Operator will den Code DIREKT
  host-seitig testen (Python-Aufrufe der Engine-Funktionen, `curl`-artige Probes),
  nicht erst einen Build+Deploy+Container-Start. Verhaltens-Tests laufen gegen die
  Engine-Methoden auf tmp-DBs — Container-Tests nur wenn der Pfad zwingend Container
  braucht (PG-Zugriff im Pod-Netzwerk).
- **Sofortige Zwischenzahlen statt Warten**: laufende Messungen (Cycle-Zeit, Bake-
  Fortschritt) sofort mit Zwischenstand berichten (verstrichene Zeit, aktive Phase,
  laufende PG-Query) — nicht auf den Watcher-Abschluss warten.
- **Fixes an EINER Quelle**: mazemaker-pro/python = Source of Truth. Eine Funktion
  darf nicht an mehreren Stellen gesteuert werden (der ColBERT-Gate war an 2 Orten;
  der User: "alle Fixes hat die andere Session ueberschrieben"). Vor jeder Aenderung
  den Code-Zustand pruefen (git log), nicht auf fruehere Fixes vertrauen.
- **Host "GPU recall init skipped (CPU/numpy)" ist kein Produktionsfehler**: der Host
  hat kein torch; die Produktion hat CUDA (Beweis: "streamed 215k vectors onto cuda").
  Tests host-seitig ehrlich skippen, nicht als rot werten.

## Support-Dateien

- `references/afe-bake-rezept.md` — das komplette DeepSeek-Bake-Rezept (Env, Skript-Struktur, Ablauf)
- `scripts/verify-cc-bindings.py` — AST-Scan: alle _cc_*-Nutzungen muessen im Funktions-Scope gebunden sein (NameError-Klasse)
