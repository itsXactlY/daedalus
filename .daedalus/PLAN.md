# `daedalus --yolo` braucht >1 Minute zum Start
Status: active
Asked: "jetzt noch immer das problem, das: daedalus --yolo braucht >minute zum starten" / "es braucht wieder 1 volle minute um daedalus zu starten, ffs!"
Done when: der Startpfad ist gemessen und die Ursache benannt — NICHT geraten.

Abandoned: "toter Schalter / pod druck / retry druck" — committed 5c7fc75 + 04ddc57.

## KORREKTUR der Diagnose (2026-09-27, wichtig)
Die frühere Zuordnung "Probe bremst den Start" war FALSCH. Gemessen:
- pty, Prompt interaktiv: **2,2s**, konstant über 9 Läufe, alt wie neu.
- `initialize()` läuft NICHT auf dem Startpfad. `cli.py:7034` ruft
  `_init_agent()` aus dem Message-Pfad, danach druckt es "Initializing agent...".
  Im pty-Kind mit 6s langsamem Pod wird `initialize()` nachweislich gar nicht
  aufgerufen (Trace-Marker erscheinen nicht), der Prompt ist trotzdem bei 2,2s live.
- Die Probe bremst also die ERSTE ANTWORT, nicht den Prompt.

## URSACHE DER MINUTE (2026-09-27 abends, gefunden)
Nicht der Pod allein: der **MCP-Connect im Startpfad**. `connect_timeout`
Default 60s, und er wird **zweimal** angewendet (Content-Type-Preflight +
`session.initialize()`), weil der mazemaker-Server `skip_preflight` nicht
setzte. Bei festgefahrenem Pod kostete das 2 x Timeout vor dem Banner.
Isolationsbeleg: mazemaker-MCP aus -> Prompt 2,2s; an -> 23,6s. Differenz 21,4s
= 2 x 10s nach dem ersten config-Fix.
Fix: `skip_preflight: true` + `connect_timeout: 5` in `config.yaml`
(Backup: `config.yaml.bak-connect-timeout`).
Gemessen: Prompt **23,6s -> 7,1s** (3 Läufe: 7,08 / 7,09 / 9,59), auch bei
totem Pod. Ohne MCP-Connect liegt die Basis bei 2,2s.

## Messregel
KEIN `daedalus -q <prompt>` (belegt den llama-Slot) und KEIN pty-Kind mit
echter Frage: der Kind-Agent konkurriert um dieselbe LLM, das Ergebnis
(90s ohne Turn-Ende) war ein Messartefakt, kein Harness-Befund.
Gemessen wird in-process bzw. unter pty, jeweils mit und ohne Fix auf derselben
Binary, im Wechsel, damit der Pod-Zustand nicht die Differenz erklärt.

## Schritte
- [x] 1. Startpfad unter pty vermessen — Prompt interaktiv nach 2,2s.
- [x] 2. Täter eingrenken: `brain_ready()` = echter stats-Call, 4s Budget.
      Nutzer-Log 96 Starts: 42x `mazemaker_stats failed ... TimeoutError`.
- [x] 3. Fix: Probe aus `initialize()` in einen Daemon-Thread, main thread frei.
- [x] 4. Nachgemessen — erster Turn (`.daedalus/measure_first_turn.py`, n=3 je):
        Pod schnell : ALT median 4,28s  ->  NEU 0,80s
        Pod +6s     : ALT median 10,28s ->  NEU 0,79s
      Promptzeit unveraendert 2,2s (siehe Korrektur).
- [x] 5. Nebenwirkung gefunden und behoben: `is_available()` ist ein Schema-Gate
      (filtert 37 mazemaker-Tools). `bool(None)` = False haette Memory im ersten
      Turn stillschweigend abgeschaltet. UNKNOWN ist jetzt != DOWN.
      Zweiter Fehler darin: `is_available()` loeste selbst eine Probe aus und
      raeumte damit einen echten Wedge weg ("MEMORY RECOVERED ... after 0s wedged").
      Jetzt副作用-frei: kein Pod-Traffic, nur Join einer laufenden Probe.
- [x] 6. Die ">1 Minute" ist erklaert: MCP-Connect, 2x 60s bei totem Pod.
      Fix `skip_preflight` + `connect_timeout: 5`; Prompt 23,6s -> 7,1s.
- [x] 7. Turn-Pfad gegen festgefahrenen Pod durchgemessen
      (`.daedalus/probe_turn_path.py`, `_tool` instrumentiert):
      session_resume_context 1,81s (browse, TO 1,8) + continuity_context 1,80s
      + prefetch 18,04s (recall, TO 18) = **~21,7s einmalig**, danach
      "going cold, no further calls for 120s" — Sicherungskreis greift,
      Rest der Calls 0,00s. Kein 30s-Default im Weg (RESUME_TIMEOUT=1,8).
- [x] 8a. ANNAHME (Nutzer hat nicht geantwortet, Timeout = keine Zustimmung):
      Pod wird NICHT angefasst. Erster Neustart-Vorschlag wurde einmal explizit
      abgelehnt, ein Timeout ist keine Erlaubnis. Harnesseite ist damit fertig.
- [ ] 8. OFFEN und nicht von hier loesbar: der Pod ist seit 17:31 festgefahren
      (letzter OK 7692s her, 9 Fehlschlaege, /mcp 212->625s, 36% CPU, 0 Restarts).
      Nur ein Neustart heilt das. Nutzer hat Neustart abgelehnt -> Entscheidung liegt
      beim Nutzer. 21 spooled Writes ueberleben den Neustart.

## Was `skip_preflight` wirklich ueberspringt (geprueft, mcp_tool.py:2628)
Nur `_preflight_content_type`, und nur solange `not self._ready.is_set()` und
nicht sse/oauth. Zweck des Aufrufs: `NonMcpEndpointError`, wenn die URL auf einen
NICHT-MCP-HTTP-Dienst zeigt. Also Diagnose-, keine Funktionsprobe — bei korrekter
URL verhaltensidentisch. Preis: bei spaeter falsch werdender URL kommt der Fehler
als Connect-Fehler statt als klare Meldung. Bewusst akzeptiert.

## Messfallen, die schon Zeit gekostet haben
- pty-Echo: mit angeschaltetem Terminal-ECHO misst man den Kernel, nicht die App
  (konstantes 2,28s, egal ob blockiert). ECHO ist jetzt aus.
- Echo per Zeichen zaehlen ist wertlos: "x" steht in "e[x]ecute_code", "e[x]plore".
  Jetzt Zufalls-Token mit Exakt-Match.
- TUI-Reply-Erkennung per "irgendein Text" meldet FALSCH FERTIG: Echo der
  gesendeten Frage und die CPR-Warnung matchen. Nur eine **leere** Prompt-Zeile
  nach dem Senden gilt als Turn-Ende.
- `grep`/find finden `plugins/memory/mazemaker/__init__.py` nicht: es ist ein Paket,
  kein Modul. `grep` ist hier ugrep und liefert bei Dateipfaden leer.
- `ls` ist `eza` mit kaputter Config -> immer `/bin/ls`.

## Entscheidungen
- Timeout-Konstante `_BRAIN_PROBE_TIMEOUT_S = 4.0` bleibt: aus echter Messung
  (1,5s erklärte einen nur beschäftigten Pod für tot). Kürzer = häufiger
  Timeout, nicht schnellerer Start.
- Fix ist Umlagerung, nicht Rausdrehen: Aufrufer-Pfad bleibt unangetastet.
- Kein Neustart von Diensten, kein Eingriff in den Pod (Nutzer hat abgelehnt).
- `connect_timeout: 5` statt 3: ein wirklich kalter Pod braucht ein paar
  Sekunden; 5s ist bei gesundem Pod (0,1-0,5s) kostenlos und deckelt den
  Schadensfall bei ~7s statt ~23s.

## Notizen
- llama-server laeuft mit `-np 12`, nicht 1 Slot (alte Notiz war falsch).
- `_browse_rows` (plugins/memory/mazemaker/__init__.py:1379) ruft `_tool`
  OHNE Timeout -> 30s Default. Aktuell nur im Prefetch-Pfad, der nach dem
  Circuit-Breaker nicht mehr erreicht wird. Latentes Risiko, nicht beziffert.
- config.yaml beschreibt mazemaker mit "31 tools", der Block filtert aber 19.
  Nicht verfolgt.
- `.daedalus/measure_boot.py`, `measure_ready.py`, `probe_turn_cost.py`,
  `probe_turn_path.py` sind Messskripte, kein Produktivcode.
