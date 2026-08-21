# Dream-Worker Steady-State 12.5 GB — THESE-E-Verifikation 2026-08-07 (READ-ONLY)

Verdikt: Steady-State = geladener Zustand (Korpus-Materialisierung in Python-Objekten), KEIN Leak, KEIN Cycle-Problem. oomd killt wegen Host-Überzeichnung (User-Slice-Druck). Fix 94cdc80 committet, aber am Messtag noch NICHT deployed (Image-Staleness).

## Timeline (der Schlüssel)

- Image `localhost/mazemaker-v2-mcp:gpu` gebaut: **2026-08-07 20:25 UTC** (podman image inspect {{.Created}}).
- Fix-Commit 94cdc80 ("stop holding the whole corpus as Python objects — 12.9 GB to 1.43 GB"): **21:12 UTC**.
- ⇒ Alle 4 analysierten Worker-Runs (20:53, 21:15, 22:02, 22:47 CEST) liefen mit dem ALTEN Code: voller `_load_from_store()` mit Embeddings. Source sah bereits gefixt aus; Logs zeigten neue Strings (Streaming-Arm, Recall-only-Socket) — die waren ältere Fixes (38a0efc 10:31, 52e8e15 10:52), die im Image waren. 94cdc80 nicht.

## Lauf-Daten (journalctl --user -u mazemaker-dream-worker.service)

| Start | Ende | Peak | Kill |
|---|---|---|---|
| 20:53:06 | 21:14:39 | 12.5G | oomd (Slice 83.52% > 80%) |
| 21:15:39 | 22:01:10 | 12.6G | oomd (Slice 87.04% > 80%) |
| 22:02:10 | 22:31:31 | 12.4G | TERM/KILL (Operator) |
| 22:47:15 | 23:16:00 | 12.8G | TERM/KILL (Operator) |

Jeder Lauf: `GPU recall arm: streamed 215243 vectors onto cuda, decoded on-device` (4 s, streaming — KEIN 12.3-GB-Arm-Fallback), kein "graph load", kein HNSW-Build, keine get_all-Funnel. Trotzdem 12.4–12.8 GB gehalten. Kill 22:01 kam **30 min nach Zyklusende** (DAE-Log 21:31) — Worker idle im Sleep-Loop bei 12.6 GB ⇒ Steady-State, kein Spike.

## RAM-Halte-Karte (215k-Korpus, pre-Fix)

| Attribut | Größe | Lebensdauer | Evict |
|---|---|---|---|
| `_graph_nodes` (Voll-Load `_load_from_store`) | 9–13 GB: Embeddings list[float] 5.7–7.3 GB + Contents 2.2–5.4 GB + Connections 0.2–0.4 GB | Prozess, **nie geleert** (kein Evict-Pfad) | 94cdc80: lazy + `include_embeddings=not _armed` + Top-up nur letzte 2000 IDs |
| `GpuRecallEngine._contents/_labels/_ids` | 2–5.5 GB (215k Strings) | Prozess (served Recall-Socket) | kein Evict; Option: Contents per-Result aus PG |
| `_emb_tensor` | 880 MB **VRAM** (cuda) | Prozess | n/a |
| np-float32-Staging | 0.8–0.9 GB | transient (Arm) | weg (Streaming) |
| `_hnsw_index` | 0 (nie gebaut) | — | bei GPU-Ausfall +1–1.5 GB retained, +8–9 GB transient |
| Phasen-Strukturen (REM/Insight) | 0.2–0.7 GB | transient | weg (Insight: numpy + C++ Louvain, kompakt) |
| Base (torch/numpy/psycopg/Python) | 0.8–1.2 GB | Prozess | n/a |

Parent-Probe "5741+5199+815 MB" = 11.75 GB ≈ Embedding-lists + Content-Strings + np-float32-Kopie (exakte Split ohne Live-Probe nicht auflösbar; Summe stimmt).

## oomd-Beweiskette (journalctl -u systemd-oomd, 21:14:37 & 22:01:09)

- "Marked ... for killing due to memory pressure for /user.slice/user-1000.slice/user@1000.service/app.slice being 83.52% / 87.04% > 80.00% for > 20s with reclaim activity"
- Worker-Cgroup: "Memory Pressure Limit: 0.00%" (eigenes ManagedOOMMemoryPressure nicht gesetzt — 80% = Parent-Slice-Default), "Current Memory Usage: 12.5G / 12.6G", "Pressure: Avg10: 89.52 / 92.60", "Pgscan: 419892 / 1766013".
- systemd-oomd läuft system-weit (PID 745, seit Aug 04); Config: DefaultMemoryPressureLimit=80%, DefaultMemoryPressureDurationSec=20s (Drop-in).

## Warum Worker statt pgvector (9G) / Desktop

- OOMScoreAdjust: dream-worker **500** ("On-Demand-Last ... zuerst opfern", im Unit-File dokumentiert), alle anderen mazemaker-Units 200, Desktop ungesetzt.
- Anon-Dominanz: Worker 12.5G anon (unreclaimbar, Pgscan 1.76M); pgvector 9G High = shared_buffers (3G) + Page-Cache (reclaimbar → wenig Druckbeitrag).
- Thrash-Verstärker: Unit MemoryHigh=12G, Container `--memory=16g --memory-swap=16g` (KEIN Swap) → 12.5G anon > High 12G → Dauer-Reclaim ohne Swap-Escape → eigener Avg10 89–92% + Slice-Druck.

## Limits-Arithmetik (systemctl --user show, 2026-08-07 Abend)

| Unit | MemoryHigh | MemoryMax | OOMScoreAdjust |
|---|---|---|---|
| dream-worker | 12G | 16G | 500 |
| embedding-worker | 2.44G | 3G | 200 |
| mcp | 3G | 4G (+2G SwapMax) | 200 |
| pgvector | 9G | 10G | 200 |
| license-client | 0.25G | 0.5G | 200 |
| llm | 3G | 4G | 200 |
| wonderland | 1.46G | 2G | 200 |
| afe-window (nur Nacht) | 8G | 12G | 200 |
| v2-api/nginx/cloudflared | ∞ | ∞ | 200 |

- **High-Summe (Tag, konkurrent): 31.2 GiB = 33.5 GB ≥ 31 GiB RAM**; mit afe-window: 39.2 GiB. **Max-Summe: 39.5 GiB = 42.4 GB** (≈ These-Wert "40,3G").
- Host-Zustand am Messtag: 31 GiB RAM, 42 GiB Swap, 10 GiB Swap belegt (19 GB beim Crash laut Operator-Kommentar); Desktop ~4–6 GB RSS (Vivaldi/Chrome/KDE/hermes/claude).
- Operator-Kommentar in `~/.config/containers/systemd/mazemaker-pgvector.container` [Service] bestätigt die These wörtlich: "the SUM ... oversubscribed physical memory by 42 %", "MemoryHigh ... when its sum also exceeds physical memory it guards nothing — ... systemd-oomd then kills the largest consumer", "its ~12.9 G steady state comes from get_all() materialising the whole corpus as Python objects", "19 GB of swap was in use by then; that was the warning nobody read".

## Fix-Design (K3)

- (a) lazy_graph + Embedding-Skip: 94cdc80 (committet 21:12 UTC). lazy_graph default True via `MM_DREAM_LAZY_GRAPH` (dream_worker.py:106, unset → True; Quadlet setzt es nicht). Claim: 12.9 → 1.43 GB. Minimal-invasiv (Flag + eine get_all-Signatur).
- (b) HNSW ohne Python-Materialisierung: unnötig solange GPU-Arm streamt; nur Fallback-Risiko bei GPU-Ausfall (dann PG-ivfflat/hnsw statt In-Process-hnswlib).
- (c) GPU-Tensor als einzige große Struktur: auf GPU-Seite erreicht (Streaming-Arm deployed seit 10:31 UTC); Tensor war nie das Host-Problem.
- Post-Fix-Residual: Engine `_contents` (2–5.5 GB) + Base (~1 GB) ⇒ Steady-State ~1.5–6.5 GB je nach avg Content-Länge.
- **Limits-Korrektur allein unzureichend** (12.5G anon in 8G-High = Thrash); Struktur-Fix + Summe < ~28G zusammen.

## Wiederholbare Diagnose-Befehle

```bash
journalctl -u systemd-oomd -n 40                        # Kill-Grund + Druck-Zahlen
journalctl --user -u mazemaker-dream-worker.service --since "..." | grep -vE 'HTTP Request|embed_colbert'
systemctl --user show <unit>.service -p MemoryHigh -p MemoryMax -p OOMScoreAdjust
podman image inspect localhost/mazemaker-v2-mcp:gpu --format '{{.Created}}'
git log --format='%h %ad %s' --date=format:'%Y-%m-%d %H:%M' -5
systemd-analyze cat-config systemd/oomd.conf
free -h; swapon --show                                # Swap-Belegung = Druck-Indikator
```
