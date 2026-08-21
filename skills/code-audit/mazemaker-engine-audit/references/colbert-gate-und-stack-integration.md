# ColBERT-Gate, Stack-Integrationstests, Lizenz-Falle (2026-08-08)

Ergänzung zu `audit-2026-08-08-cycle-and-integration.md` — die letzten drei
Befunde der Session (nach dem ersten Audit-Pass).

## 1. ColBERT-Env-Gate an zwei Orten (a512c36)

- Symptom: embed_colbert-HTTP-Calls feuerten im Dream-Cycle im Sekundentakt,
  obwohl `MM_COLBERT_ENABLED=0` gesetzt war (Journal 2026-08-08 05:25).
- Ursache: Der Env-Knopf gated nur den WRITE-Pfad (`_colbert_write_enabled`,
  memory_client ~1569). Der READ-Kanal (`self._channel_weights["colbert"]`)
  kam aus zwei anderen Quellen:
  1. Mode-Presets (memory_client ~1536-1542): skynet → 1.2, advanced/hybrid → 0.5
  2. compute.toml-Overlay: `colbert_weight = 1.5` (gerendert)
  Keine davon konsultierte die Env — der Kommentar "explicitly opt in via env"
  war eine Lüge (die Preset-Logik setzte das Gewicht trotzdem).
- Fix: die Env gewinnt ZULETZT — nach allen Presets/Overlays:
  `if not (os.environ.get("MM_COLBERT_ENABLED","0") in ("1","true","yes","on")): self._channel_weights["colbert"] = 0.0`
- Verhaltens-Test-Matrix (hermes-verify-colbert-gate.py):
  - Env=0 + advanced-Preset → 0.0
  - Env=0 + skynet-Preset (1.2) → 0.0
  - Env=0 + caller-Overlay {colbert: 1.5} → 0.0 (Env gewinnt zuletzt)
  - Env=1 + advanced → 0.5 (Preset gilt bei opt-in)
  - Kein Env + advanced → 0.0 (NEUER sicherer Default — vorher 0.5-Preset!)
- Lektion: Ein Operator-Gate, das nur einen von zwei Pfaden schaltet, ist ein
  Lügen-Knopf. Vor dem Fix ALLE Konsumenten einer Funktion auditen (Write +
  Read + die Presets + die Overlays), nicht nur den offensichtlichen.

## 2. Lizenz-Falle bei PG-Container-Tests

- Symptom: PG-Integrationstests im Container liefen "grün", aber die Engine
  fiel still auf SQLite zurück: "MM_DB_BACKEND=postgres requested but the
  Postgres backend is a Pro feature; falling back to SQLite".
- Ursache: Keine Pro-Lizenz im Test-Container → `has_feature("postgres")` =
  False → SQLite-Fallback. Die Tests testeten unbemerkt SQLite, nicht PG.
- Fix: license.jwt + jwt.v1.pub.ed25519 mounten + Envs setzen (wie der echte
  mcp):
  ```
  -v ~/.mazemaker/license.jwt:/root/.mazemaker/license.jwt:ro \
  -v ~/.mazemaker/jwt.v1.pub.ed25519:/secrets/jwt.v1.pub.ed25519:ro \
  -e MAZEMAKER_LICENSE_PATH=/root/.mazemaker/license.jwt \
  -e MAZEMAKER_PUBKEY_PATH=/secrets/jwt.v1.pub.ed25519
  ```
- Zusätzlich die compute.toml mounten (sonst entscheiden die DEFAULTS — z.B.
  stage_s_enabled war True → Synthesis lief im Test ohne toml).
- PG-Zugriff aus dem Host geht NICHT (Pod-Ports nicht exponiert) — PG-Tests
  laufen im Pod-Netzwerk (`podman run --pod <pgvector-pod>` + das Secret als
  Env: `--secret mazemaker_pg_password,type=env,target=MM_POSTGRES_PASSWORD`).
  Immer gegen eine WEGWERF-DB (mazemaker_test), nie die Produktions-DB.

## 3. Exhaustive PG-Store-Verifikation (die 66/66- und 37/37-Lücken)

Nach dem Coverage-Befund (postgres_store 66/66 + dream_postgres_store 37/37
NULL Suite-Coverage) wurden ALLE Funktionen gezielt mit Verhaltens-Tests
gegen eine Test-DB aufgerufen (audit-exhaustive-pg.py, im Container):
- Ergebnis: 75/75 bestanden, 0 Befunde (nach Korrektur der Test-Signaturen —
  die meisten "Befunde" waren falsch geratene Argumente, KEINE Code-Bugs).
- Echter Fund dabei: `get_all(include_embeddings=False)` SELECTete immer alle
  9 Spalten, aber der Unpack erwartete 7 → ValueError auf jedem vector-losen
  get_all (fc1d508). SELECT/Unpack müssen im Gleichschritt bleiben.
- SQLiteDreamBackend ist NICHT self-contained: braucht das volle Mazemaker-
  Schema (SQLiteStore-Init) vor der Nutzung auf einer frischen DB.
- `upsert_dae_vectors` auf SQLite crasht bewusst (Free-Grenze: keine Pro-Tabelle
  im SQLite-Schema — der no-leak-Guard, NICHT ein zu fixender Bug).

## 4. Operator-Präferenz: Host-Tests statt Container-Ketten

Der Operator will Verhaltens-Tests DIREKT auf dem Host (Python-Aufrufe der
Engine-Methoden gegen tmp-DBs), keine podman/build/deploy-Ketten für Tests.
Der Host hat kein torch → GPU-Pfade sind dort nicht testbar — aber Gates,
Kanal-Gewichte, Paging, Signatur-Mismatches sind host-testbar (und wurden es).
Sofortige Zwischenzahlen (verstrichene Zeit, aktive Phase, laufende PG-Query)
statt "warte auf den Watcher". Fixes gehören an EINE Quelle (mazemaker-pro);
vor Änderungen den Code-Zustand prüfen (git log) — parallele Sessions
überschreiben Arbeit.
