# Plan-Datei pro Task statt ein PLAN.md pro Ordner
Status: done
Asked: "2 agents arbeiten an einem ordner, agent B hat agent A den PLAN.md überschrieben, wir
        brauchen PLAN-TASK.MD"
Done when: `pytest tests/agent/test_plan_file.py` grün UND `.daedalus/probe_plan_clobber.py`
          mit zwei echten Prozessen exit 0 liefert (nicht-erlaubter Klone → exit 1).

## Schritte
- [x] 1. Audit: Ursache belegt — plan_file.py:19 `PLAN_NAME="PLAN.md"` fest,
      default_soul.py:12 ("write .../PLAN.md FIRST") war die Anweisung zum Überschreiben.
- [x] 2. `plan_file.py` umgebaut: `PLAN-<slug>.md`, Discovery, Session-Ownership, Index-Block.
- [x] 3. Schreib-Gate in write_file/patch (`_check_plan_clobber`) → exit 1 bei Fremd-Plan.
- [x] 4. session_id an render_plan_block/plan_focus durchgereicht (3 Aufrufstellen +
      anchored_recall_query in 4 Aufrufern).
- [x] 5. PLAN_GUIDANCE + default_soul + 4 Skills auf die neue Regel umgestellt.
- [x] 6. Tests: 24 grün, 2-Prozess-Probe grün.
- [x] 7. Regressionsvergleich vorher/nachher: 0 neue Fehler, 15 behoben
      (Baseline via `git stash` belegt). Commit 015a59c.

## Entscheidungen
- Besitz wird pro PLAN-DATEI in `.daedalus/.owners/<plan>.json` geführt, eine Datei pro
  Plan: zwei Agenten, die verschiedene Pläne beanspruchen, rennen nie um dieselben Bytes.
  Besitz lebt = `os.kill(pid, 0)` auf demselben Host. Kein TTL, kein Heartbeat: stirbt der
  Agent, ist die Datei sofort wieder adoptierbar — sonst könnte ein "weiter" in einer
  neuen Session nie an den alten Plan andocken, und ein abgestürzter Agent sperrt den
  Ordner für immer.
- Das Gate erkennt einen Plan an der DATEI (PLAN*.md in einem .daedalus-Ordner), nicht am
  cwd. Erster Versuch verglich gegen TERMINAL_CWD — die 2-Prozess-Probe hat das schlagend
  bewiesen: ein Pfad über ein ssh-artiges Backend ist dem lokalen cwd fremd, ein Gate, das
  nur die eigenen Pläne kennt, bewacht nichts.
- `PLAN.md` bleibt vollwertig (Altbestände auf der Box) und ist der Default-Slug für den
  Ein-Agent-Fall: der Normalfall läuft exakt wie vorher.
- Mehrere freie offene Pläne → Index-Block, kein Raten. Genau das stille Raten war der Unfall.
- Leerer session_id schreibt KEINEN Besitz-Record: ein leerer Halter läse sich für jede
  spätere Session als "am Leben".

## Bugs, die die Probe gefunden hat (nicht die Tests)
- `_as_plan_path` stand neben der Tür (cwd-Vergleich) → im echten 2-Prozess-Fall lief der
  Klone durch, obwohl alle Unit-Tests grün waren.
- `file_tools.py`: mein Fuzzy-Patch auf die `def _check_sensitive_path`-Zeile hat den
  Parameternamen `filepath`→`path` mitgeschleppt, NameError in 8 Tests. Gefangen durch
  `git diff` (31 Zeilen rein, 0 raus) + Baseline-Messung mit stash.

## Notizen
- `.daedalus/PLAN.md` (Agent A, Bootzeit-Thema) wurde NICHT angefasst. Genau der Fehler, den
  der User meldet, wird hier nicht reproduziert — mein Plan liegt in PLAN-plan-per-task.md.
- Vorbestehend, nicht von mir (per stash-Baseline belegt): 7 Fehler in
  tests/tools/test_write_approval.py (ModuleNotFoundError), sowie ~150 in
  mcp/web/send_message-Tests. Nicht verfolgt.
