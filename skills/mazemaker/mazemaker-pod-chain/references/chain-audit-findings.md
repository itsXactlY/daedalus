# Chain-Audit Findings (Repo→Image→Unit→Pod→Runtime) — verified 2026-08-07, READ-ONLY audit

Audit der Verkettungskette auf der Operator-Box (Pro-Tier, lokaler Pod). Alle Punkte code-verifiziert;
Stand: Pod nach `mazemaker off` (23:16), alle Autonomie-Units disabled.

## Update-Kette (mazemaker-update, ~/.local/bin)

- **Quadlet-Templates werden verbatim kopiert** (mazemaker-update Z. 288-294): `AddDevice=nvidia.com/gpu=all`
  (mcp.container:98, dream-worker:79, embedding-worker:37, llm:29) wird auf CDI-losen Hosts von
  install.sh gestrippt (install.sh:2102-2103) — der Update-Pfad strippt NICHT → nächster Pod-Start
  auf CPU-Pod = CDI-Fehler. Auf GPU-Boxen unsichtbar (deshalb still). Fix: Strip-Logik im Update reproduzieren.
- Precedence env > conf > default: gefixt in 01ee51f (vorher schlug update.conf die Env — Rollout-Verifikation log).
- cp-truncate des laufenden Skripts: gefixt a86b8b5 (mv statt cp) — rc14-Update brach mitten im Lauf ab,
  sah aber "angewendet" aus.
- **Lokaler Build+Retag stampft installed.image_tag NICHT**: VERSION=rtm.5 lokal gebaut und auf
  localhost:latest/:gpu getaggt, aber installed.image_tag=rtm.4 → Tag-Drift, Preflight "grün" für
  ein nie signiertes Image. desired/installed via `mazemaker status` prüfen.

## `mazemaker off` Coverage-Gaps (cmd_off, ~/.local/bin/mazemaker Z. 135-159)

- Stoppt: POD_MEMBERS (mcp, wonderland, embedding-worker, license-client, pgvector, mcp-socket-bridge) +
  MASTER_UNITS (pod, pulse-pod, hermes-bridge) + mazemaker.target. Dream-Target mit --no-block
  (sonst 150s Block, 07-08-Halbzustand, gefixt b62d9b4), Stop mit --job-mode=replace-irreversibly
  (sonst canceln Restart-Jobs den Stop).
- **Stoppt NICHT**: mazemaker-llm.service (~6,5 GB RAM; seit 8d0f792 im Stack, nie in die Stop-Liste
  aufgenommen), mazemaker-apk-gateway(.mdns), ALLE watch.path/timer (update.timer, selftest.timer,
  image-refresh-watch, compute/db/upgrade-watch, hermes-compress-guard).
- **Kein STOPPED-Guard in refresh-images.sh**: Nightly-Update (03:30) → trigger_image_refresh →
  image-refresh.request → Watch re-pullt und RESTARTET die Pod-Surface. Ein per `mazemaker off`
  abgeschalteter Pod kommt nachts von selbst wieder hoch.

## engine_sha-Mechanik

- engine-sha.sh hasht den ARBEITSBAUM (find . | sha256sum), inkl. UNTRACKED files unter python/.
  Kein Commit-Bezug. Exclude-Listen von engine-sha.sh (tools/, demo.py, setup_fast.py) ≠
  build-all-locked.sh sync_engine (die schließt tools/demo.py NICHT aus) — synchron halten.
- Preflight (mazemaker-mcp-preflight): blockt nur bei deterministischem Mismatch; FAIL-OPEN bei
  fehlendem/`unknown` Label (Z. 137-138) und fehlender Quelle (Z. 135-136) → Pre-Stamp-Images ungeschützt.
- rtm.4-Image (Label e0620d31…) vs Quelle (f4ecb993…) → Preflight hätte nächsten Restart geblockt.
- Label-Einführung: c8e02b2 (2026-06-18); tier-aware: 9c92d3c (2026-07-08).

## Test-Traps (warum Suiten keine Regression fangen)

- `tests/test_suite.py` (Repo-Root) verbindet gegen PRODUKTIONS-DB ~/.mazemaker/engine/memory.db
  (Z. 131) — 0 Bytes seit PG-Umzug (Mai) → testet die tote SQLite-Schicht und schreibt hinein.
- `tests/test_upside_down.py` Sektion [15] (Z. 805) verlangt python/cpp_dream_backend.py — gelöscht in
  93e6b91 (2026-05-01, MSSQL-Exzision) → Suite seitdem DAUERHAFT ROT.
- Alle Suiten: use_cpp=False + embedding_backend="hash" → C++-Bridge, BGE-M3/Worker/Socket/HTTP-Kette,
  PG-Backend, GPU-Recall, Dream/AFE/DAE/ColBERT/Supersedes NIE getestet.
- CI (.github/workflows/ci.yml): Triggers nur [master, main]; free-Repo-Default-Branch ist main-v2
  → Free-CI läuft nie. Pro-Repo: letzte dokumentiert grüne Suite dd3964e/f12ffd2 (2026-04-21).
- Regressions, die KEIN Test fing (alle 08-06/08-07 durch Inspektion/selftest/bench gefunden):
  Stage-B-Noop (84fea5b), Supersedes-Firehose (eab7a9f), 3M-Audit-Rows (38a1848), get_all-Bloat
  (94cdc80), EMBED_BACKEND=http ignoriert (d8fa3d6), FTS-Config-no-op (5d637e9), Stage-C-Modell nie
  installiert (932cb76), Session-Aggregation 9% (193692c), pgvector-Vector-Dead-Recall (1e7fe70).

## Stille Tode — Erkennung

- **Autonomie-Units enabled-aber-inaktiv / disabled**: `systemctl --user is-enabled` für
  selftest.timer, update.timer, image-refresh-watch.path, compute/db/upgrade-watch.path,
  hermes-compress-guard.path prüfen. `mazemaker on` startet sie nur TRANSIENT; ein Update
  re-enabled sie. 2026-08-06: Request lag 40 min, desired=rtm.1 vs installed=rc16, alles "grün".
- **User-Journal volatil**: journalctl --user kann bei User-Manager-Neustart auf eine späte
  Zeitgrenze zurückfallen → frühe Selftest-Runs (05:34-Fail) forensisch verloren. Selftest-Output früh sichern.
- **Memprobe/Bisect-Tod am GPU-Arm**: Mazemaker.__init__ ist NICHT lazy — HttpEmbeddingBackend
  feuert beim Konstruktor einen 1-Token-Probe-POST (embed_provider.py:1426-1443, default 10s,
  MM_EMBED_TIMEOUT); GPU-Arm Tier 2/3 (memory_client.py:1574-1830): gpu_cache leer → AUTO-BUILD →
  store.get_all() materialisiert den Korpus (~12,9 GB Host-RAM vor 94cdc80). Konstruktor ohne
  laufenden Embedding-Worker stirbt sofort/hängt.

## Zeitlinien-Anker (Pro-Repo / v2-stack)

- 04-09 8773f3c erster Commit · 04-11 0748c86 Dream Engine · 04-17 ae73160 Shared Embed Server (Socket)
- 04-21 dd3964e/f12ffd2 letzte dokumentiert grüne Suiten · 04-30 717589b V3.1-Squash/Lockdown
- 04-30/05-01 f23bffc/fc68600 PG+pgvector, MSSQL-Exzision (test_upside_down rot ab hier)
- 05-08 b0ffc3f/a4e587f Dream-Worker-Daemon, socket-based remote recall · 05-10 9cad51d License-Gates
- 05-18 561c595 _lib_finder (sync.sh nie aktualisiert) · 05-20 66157d6 HttpEmbeddingBackend
- 06-01 7be1904 Free/Pro-Split (free = 8 Commits, Cherry-Picks) · 06-11 3512ab2 Autoupdater
- 06-18 c8e02b2 Preflight+engine_sha-Label · 07-02 7a26b75 mazemaker-off-Teardown
- 07-08 9c92d3c tier-aware Preflight · 07-10 5ee8fc0 pgvector-0.5.0-Pin ("recall-dead rc7/rc8")
- 08-05 df23df9/6138daa/6f6659c eine Tag-Konstante, Push-Auth, Digest-Signierung · fcef6db refresh-restart-Fix
- 08-06 24da5ab Supersedes-Writer PG · 5cf209a "konvergiert nicht = sieht gesund aus"
- 08-07 38a1848 3M-Audit-Rows · 84fea5b/394e456 Stage-B + spaCy · 94cdc80 get_all 12,9→1,43 GB ·
  14f240e/52e8e15/b9c88c1 eine BGE-M3, mcp=Thin Client · d1ffd91 rtm.5

## Cross-Repo (mazemaker vs mazemaker-pro)

- Deployed hier: Pro (build-all-locked.sh rsynct mazemaker-pro/python; assert_pro_src verhindert Free-Quelle).
- Pro-only by design (no-leak-guardet): afe, build_gpu_cache, colbert_helper, compute_config, dae,
  dream_postgres_store, dream_worker, gpu_recall, migrate_*, postgres_store, synthesis.
- 5 gemeinsame Dateien divergieren (dream_engine, embed_provider, license, mcp_schemas, memory_client);
  free hat Shareables als Cherry-Picks (JSON-Cache, GPU-First, recall_multi ✓) — aber die
  08-06/08-07-Engine-Fixes (Supersedes, NREM dead-man b7dfd56, adaptive decay 9d87bbe) fehlen im free-Stand.
- sync.sh (Kopie von 7 Dateien, _lib_finder/lstm_knn_bridge fehlen) vs install.sh v2 (Symlinks):
  sync.sh-Nutzung bricht Plugin-Import + C++ still.
