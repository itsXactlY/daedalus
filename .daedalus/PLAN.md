# Toter Schalter-Müll raus, Pod-Druck raus, Retry-Druck raus
Status: done — committed als 5c7fc75 (6 Dateien, +254/-13)
Asked: "raus mit dem toten schalter müll, und den pod druck raus, retry druck raus, usw!"
Done when: (1) kein Config-Key mehr ohne Leser, (2) der Turn-Pfad erzeugt höchstens einen
       Pod-Write pro Pace-Fenster und wartet nicht auf Retry, (3) Tests grün + Voll-Lauf grün.

Abandoned: "Warum sind daedalus-Tools langsamer als hermes" — Messung war abgeschlossen,
nur der Feedback-Loop (d6c0afe) blieb. Nicht mehr aktiv.

## Schritte
- [x] 1. Tote Schalter raus: `prefetch_on_turn`, `soak_ttl_seconds`, `memory_soak` —
       verifiziert: repo-weites grep findet sie nur noch in diesem PLAN, YAMLs parsen,
       `Soak()` liefert genau 3 Felder
- [x] 2. Pod-Druck raus: `_PodPacer` im mazemaker-Plugin. Takt = 3x letzte Write-Dauer,
       Boden 1.0s. `sync_turn` verschiebt den Soak statt ihn zu stapeln; Destillat nur
       bei gesundem Pod. 12 Tests in tests/plugins/memory/test_mazemaker_pacer.py, grün.
- [x] 3. Retry-Druck raus: `_replay_allowed()` — kein Replay bei kaltem Pod (Pop +
       Spool-Rewrite + Requeue pro Turn, ohne Zustand zu gewinnen) und kein Replay vor
       dem Taktfenster. Bewusst KEIN Dauerverbot bei langsamem Pod: das füllte den
       200er-Spool und liefe die ältesten Turns raus.
- [x] 4. Tests + Volllauf — Volllauf (tests/agent + tests/run_agent + 2 gateway):
       mit Patch 17 failed / 2085 passed, Baseline (git stash, identischer Kommando)
       17 failed / 2085 passed — **identische Fehlerliste**, also kein Regressionsschaden.
       Die 14 nicht-mazemaker-Fehler sind Reihenfolge-Verschmutzung (bestehen isoliert).
       61 memory-Tests + 81 config-Tests grün, 12 davon neu.

## Live-Messung gegen das echte Pod (write_latenz 16,71 / 10,42 s, 1x 502)
  pacer.interval() 40,7 s statt _SOAK_MIN_INTERVAL 0,1 s → 3 statt ~0,03 Writes pro Minute
  is_slow=True → Destillation fällt aus, Replay wartet aufs Taktfenster
  Kalibrierzeilen (ops:pacer-probe-*) wieder gelöscht, verifiziert leer.

## Befund Schritt 1 (verifiziert per grep, nicht geraten)
  TOT   `_soak_prefetch_on_turn`  run_agent.py:1667 gesetzt, NIRGENDS gelesen
  TOT   `soak_ttl_seconds`         run_agent.py:1668 → initialize-kwarg; mazemaker-Plugin
                                  ignoriert alle kwargs außer session_id (id 1335030)
  TOT   `_soak_cfg_for_provider`   run_agent.py:1669 → `memory_soak` → ebenfalls ignoriert;
                                  repo-weit kein zweiter Leser
  TOT   `prefetch_on_turn`         harness_config.py:181, config_defaults.py:645,
                                  config.sample.yaml:48
  TOT   `ttl_seconds`              harness_config.py:182 + defaults
  LEBEND `_soak_window_turns`      run_agent.py:1064 (Gate), :4335 (build_mazemaker_guidance),
                                  :4639 — plus 6 Testdateien setzen es. BLEIBT.

## Entscheidungen
- `_soak_window_turns` bleibt: es ist kein toter Schalter, es giert den Memory-Zweig
  (run_agent.py:1064). Vorherige Annahme war falsch.
- Kein Hintergrund-Thread: der Turn-Pfad bleibt synchron, wird aber gepocht. Thread wäre
  die eigentliche Reparatur, verlangt aber eine eigene Queue — zu groß für diesen Schritt.
- Verlorene Turns sind der Preis: bei langsamem Pod werden Soak-Turns übersprungen, nicht
  gepuffert. Wird geloggt (debug) und in PLAN.md notiert.

## Notizen
- Doppel-Schreiben möglich: bricht der HTTP-Call nach dem Commit des Pods ab, landet der
  Turn im Spool UND im Pod. Spool ist auf 200 gedeckelt (`_FAILED_SPOOL_MAX`), ok.
