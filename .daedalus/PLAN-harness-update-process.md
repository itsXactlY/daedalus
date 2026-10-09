# Harness-Update-Prozess sauber: Preflight, Snapshot, Postflight, Rollback
Status: active
Asked: "harness updater / update process endlich sauber hinbekommen — Leute sollen bei jedem Daedalus-Update nicht ihren Harness brechen"
Done when: `python -m daedalus_cli.install_health` exit 0 auf der Live-Install, Update-Pfad in einer Wegwerf-Klon-Install grün (Erfolg + Rollback), Regression-Suite ohne neue Fehler gegenüber Baseline

## Steps
- [x] 1. Root cause: `pyproject.toml` listet Top-Level-Module von Hand; neue Module (`daedalus_state_common`, `_schema`, `_search`, `_portability`) fehlten → Wheel ohne Importe. Editable Checkout verdeckt es (4 Entry-Points schieben Repo-Root auf sys.path). Fix: alle vier in py-modules
- [x] 2. `daedalus_cli/install_health.py`: static_findings / runtime_findings / smoke_modules / repair, CLI `python -m daedalus_cli.install_health [--repair]`
- [x] 3. Update-Pfad in `daedalus_cli/main.py`: `_update_preflight` (repariert VOR dem Pull), Pre-Update-Ref `refs/daedalus/pre-update/<ts>`, `_update_postflight` (Smoke-Test aus neutralem cwd → 1× repair → rollback + exit 1). Fehlgeschlagener Dependency-Install bricht nicht mehr ab, der Postflight entscheidet
- [x] 4. `daedalus doctor --fix` benutzt dieselbe Quelle
- [x] 5. Wegwerf-Klon-Test (updatetest) für happy path + Rollback-Pfad
- [x] 6. `can_verify()`: ohne pyproject.toml ist das Urteil "unbekannt", nicht "kaputt" → Postflight rollt nicht auf Unknown zurück. Fix für 7 echte Regressionen in tests/daedalus_cli/test_update_autostash.py
- [ ] 7. Volle Regression gegen Baseline (proc_133fc0ca5c1a läuft) — nur Fehler vergleichen, die NICHT in der Baseline stehen
- [ ] 8. Commit + Skill-Patch fertigstellen (daedalus-maintenance-upgrade Abschnitt 0 ist gepatcht, Pitfall 3 korrigiert)

## Decisions
- Postflight per Import-Probe aus neutralem cwd statt "interne Funktionen funktionieren" — ein Neustart beweist nichts, der Import-Fehler ist der Beweis
- Pre-Update-Ref wird IMMER angelegt, nicht nur im Diverged-Zweig
- Rollback = `git reset --hard` auf den Ref + Reinstall + Re-Check + exit 1, danach `git checkout` zurück auf den ursprünglichen Branch
- Kein Update-Abbruch bei fehlgeschlagenem Dependency-Install: der Postflight ist die Instanz-Aussage, `git pull` ist die Code-Aussage

## Notes
- Baseline 92187e0 (vor meinen Commits) hat 9 Fehler in tests/gateway/test_update_command.py — die sind NICHT von mir, waren schon vorher da
- Voller Suite-Lauf hat 288 failed / 49 errors; die große Masse ist Firecrawl-ImportError + fehlende optional-skills/Dateien (Upstream-Drift), nicht Update-Code
