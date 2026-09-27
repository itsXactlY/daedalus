# `daedalus --yolo` braucht >1 Minute zum Start
Status: active
Asked: "jetzt noch immer das problem, das: daedalus --yolo braucht >minute zum starten"
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

## Messregel
KEIN `daedalus -q <prompt>` (belegt den einzigen llama-Slot).
Gemessen wird in-process bzw. unter pty, jeweils mit und ohne Fix auf derselben
Binary, im Wechsel, damit der Pod-Zustand nicht die Differenz erklärt.

## Schritte
- [x] 1. Startpfad unter pty vermessen — Prompt interaktiv nach 2,2s.
- [x] 2. Täter eingrenzen: `brain_ready()` = echter stats-Call, 4s Budget.
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
- [ ] 6. OFFEN: die ">1 Minute" ist damit NICHT erklaert. Prompt = 2,2s gemessen.
      Naechster Schritt: der Nutzer beobachtet entweder die Zeit bis zur ersten
      ANTWORT (nicht bis zum Prompt) oder ein anderer Pfad ist lang.

## Messfallen, die schon Zeit gekostet haben
- pty-Echo: mit angeschaltetem Terminal-ECHO misst man den Kernel, nicht die App
  (konstantes 2,28s, egal ob blockiert). ECHO ist jetzt aus.
- Echo per Zeichen zaehlen ist wertlos: "x" steht in "e[x]ecute_code", "e[x]plore".
  Jetzt Zufalls-Token mit Exakt-Match.
- grep/find finden `plugins/memory/mazemaker/__init__.py` nicht: es ist ein Paket,
  kein Modul. `grep` ist hier ugrep und liefert bei Dateipfaden leer.

## Entscheidungen
- Timeout-Konstante `_BRAIN_PROBE_TIMEOUT_S = 4.0` bleibt: aus echter Messung
  (1,5s erklärte einen nur beschäftigten Pod für tot). Kürzer = häufiger
  Timeout, nicht schnellerer Start.
- Fix ist Umlagerung, nicht Rausdrehen: Aufrufer-Pfad bleibt unangetastet.
- Kein Neustart von Diensten, kein Eingriff in den Pod.

## Notizen
- Ausreißer: bei 6s-Pod war EINER von drei NEU-Läufen 7,19s statt 0,79s. Der
  Fix raeumt die Probe weg, aber andere Pod-Calls im ersten Turn (Resume-Block,
  Mission-Key) koennen weiter blockieren. Nicht beziffert.
- 18/96 Starts zeigen gar kein stats-Ereignis (abgebrochen). Nicht verfolgt.
- `.daedalus/probe_*.py`, `pty_startup.py`, `measure_first_turn.py`,
  `child_yolo.py` sind Messskripte, kein Produktivcode.
