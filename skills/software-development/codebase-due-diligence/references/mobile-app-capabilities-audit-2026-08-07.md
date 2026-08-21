# Mazemaker-Mobile Capabilities-Audit — Stream C (2026-08-07)

Kontext: Teil des 3-Stream-Audits mazemaker-mobile. Checkout `feat/thebox-autoupdate` (v1.4.1 / versionCode 8).
Fragestellung: On-Device-Fähigkeiten der App, Lücke zum vollen Mazemaker-Umfang, jackbox/TheBox-Entflechtung.
Alle Pfade relativ zu `android/app/src/main/java/dev/mazemaker/mobile/`.

## Transports (App → Pod/VM) — was läuft wirklich on-device

- **LocalPodHermes.kt** (`data/LocalPodHermes.kt`): Hermes-Chat gegen die Podroid-VM.
  BASE_URL `http://127.0.0.1:8088` (Z.156; AVF vsock / QEMU hostfwd). Key per-Install generiert in der VM
  (`/opt/hermes/api_server.key`, SettingsScreen Z.235), Operator-paste → DataStore `pod_api_key`
  (`data/preferences/PreferencesManager.kt` Z.75–78), nie gebaked. `isUp()` = `GET /v1/models` mit Bearer
  (Z.56–67, enforct Auth); `chatStream()` = `POST /v1/chat/completions` SSE, Model fix `"hermes-agent"`
  (Z.159). Nur Textchat — kein Tool-Call-Feld.
- **LocalPodMcpProxy.kt**: Bindet AVF/CrosVM-TAP-Interface (Z.197–208, Präfixe avf|crosvm|tap), Port 8790
  (Z.214), guest-only. Kette: guest-hermes → `POST /mcp` (plain MCP JSON-RPC) → Phone-Proxy :8790 →
  `GatewayClient.pod("POST","/mcp")` → Desktop-Gateway :8443 → `cmd:pod` → mazemaker :8765/mcp.
  **Repeater, keine Engine** — die Memory lebt auf dem Desktop-Pod. Kein Gateway gepairt → 503
  (Z.138–140). Proxy läuft nur bei gepairtem Gateway (MazemakerViewModel Z.520–529).
- **PodWebSocket.kt** (`data/realtime/`): `ws://<host>/ws` (host = `_currentHost`, der **externe** Pod-Host,
  nicht die VM). Erwartet Events `type` ∈ health|stats|dream_complete|dream_stats|graph_update
  (MazemakerViewModel Z.686–731); Reconnect-Backoff 1s→30s (Z.149–165); 403/404 → unavailable.
  **KEIN Server implementiert `/ws`**: wonderland daemon.py (mazemaker-v2-stack) hat nur
  `/architect/mirror/stream` (Z.1418); podroid (jrwl-messenger) nichts. Settings UI Z.533:
  "WebSocket not supported by this pod version". → **dormant contract, keine Server-Implementierung.**
- Kernaussage: **"On-device" = nur der Hermes-Chat in der VM** (mit OpenRouter-Upstream, kein lokales LLM —
  Hard Constraint: keine GPU in der VM, ~1 GB RAM). Alle 31 Mazemaker-Tools laufen gegen den externen Pod.

## Tool-Surface (MazemakerRepository, `data/MazemakerRepository.kt`)

Transport: WonderlandApi direkt `http://<host>/` (ViewModel Z.658–673) ODER GatewayWonderlandApi →
`gw.pod("POST","tools/call")` (`data/gateway/GatewayWonderlandApi.kt` Z.29–43).

- **Von der App aufgerufen (20):** recall (Z.127), remember (Z.150), think (Z.164), get (Z.172),
  browse (Z.182), graph (Z.224), stats (Z.253), dream (Z.284), dream_stats (Z.307), dream_config get/set
  (Z.339/346), dream_control (Z.359), supersedes_log (Z.373), afe_facts (Z.383), diagnose (Z.394),
  prune (Z.407), health (Z.420), quota (Z.428), dream_nrem (Z.437), dream_rem (Z.446), dream_insight
  (Z.455) + REST `pod/settings`.
- **Fehlend (11 von 31, volle Liste in `docs/dev/mcp-tools.md`):** recall_multi, recall_advanced
  (ColBERT/DAE/Temporal-Gewichte = Pro), classify_intent, dream_supersedes, dream_afe, dream_synthesize,
  dream_dae, synth_lineage, rebake, ablate (Pro-Diagnose), connections_import (Federation).
- Offline: SQLite-MemoryCache mit Fallback für recall/browse/graph/stats — einzige echte on-device-Datenhaltung.

## HermesUpstreamConfig — nur auf ungemergtem Branch

- **Fehlt im Checkout.** Liegt auf `origin/feat/hermes-upstream-config` (5 voraus/19 zurück;
  benchmarks/audit/upside-down-integration-2026-08-07.md Z.36/143). Lesen via
  `git show origin/feat/hermes-upstream-config:<pfad>`.
- Inhalt: `enum UpstreamProvider {OPENROUTER, CUSTOM}`; `buildHermesProvidersYaml()` → `default_model` +
  `providers`-Block der hermes config.yaml; `hermesConfigEnvelope()` → `type:"hermes_config"`-JSON, Push
  über PodWebSocket (`ws://host/ws`), erwartet `hermes_config_ack` (Branch-ViewModel Z.770).
  **Handler im Podroid-Image fehlt** ("Claude's lane") → Vertrag ohne Server.
- Hard Constraint (Kommentar im File): **kein lokales LLM** — Vulkan-Spike: keine GPU + ~1 GB RAM in der VM;
  nur OpenRouter/CUSTOM-Upstream, Keys nie gebaked (DataStore only).
- **Partial-Merge-Falle:** LocalPodHermes.kt + LocalPodMcpProxy.kt sind bereits im Live-Checkout
  (kamen via `release/android-1.4.0`-Merge in feat/thebox-autoupdate), HermesUpstreamConfig.kt +
  hermes-config-template.yaml desselben Branches nicht. `git diff --name-only origin/main...origin/<branch>`.

## jackbox/TheBox — Abhängigkeit & Entflechtung

- **App hat KEINE Abhängigkeit von TheBox:** 0 Treffer `thebox` in `app/src/main`; kein Gradle-Dep
  (`app/build.gradle`), kein Manifest-Eintrag. `build-box.sh` Z.45: `NEEDS[mazemaker]="com.excp.podroid"` —
  die App braucht **Podroid** (VM-Träger), nicht TheBox.
- TheBox = reiner Installer/Bündler: bündelt Podroid+Mazemaker+Iris als Payloads (`assets/payloads/` +
  `payloads.json`, unkomprimiert), streamt via PackageInstaller (`Installer.kt`), Auto-Update über
  `Updater.kt` + `UpdateWorker.kt` (12h-Tick, WorkManager), Manifest `https://iris.mazemaker.online/thebox/manifest.json`,
  `publish-thebox.sh` → mazemaker-pro (`/home/alca-iris-relay/static/thebox`).
- **Die App hat KEINEN eigenen Updater** (grep in `android/app` → nur `updated_at`-Cache-Spalten).
  Fällt TheBox weg, entfällt auch die gesamte Update-Mechanik → Update-Lücke (Updater müsste in die App
  oder manuell).
- Entflechtungs-Aufwand: `jackbox/` komplett entfernbar (eigenständiges Gradle-Projekt; MainActivity,
  Installer, Updater, UpdateWorker, Payloads, InstallReceiver + InstallBus); keine Build-Coupling;
  `build-box.sh`/`publish-thebox.sh` entfallen; Docs bereinigen (jackbox/README.md, README, docs/dev/*).
  `THEBOX_BASE_URL`/Manifest-Logik (build-box.sh Z.112–189) entfällt.

## Verifikations-Befehle

- `git show origin/<branch>:<path>` — Dateien von ungemergten Branches lesen (kein Checkout nötig).
- `grep -n '@app\.' mazemaker-v2-stack/backend/client/pod/wonderland/daemon.py` — Routeninventar des
  Pod-Servers (beweist: kein /ws, nur /architect/mirror/stream).
- `git diff --name-only origin/main...origin/<branch>` — exklusive Dateien eines Branches.
