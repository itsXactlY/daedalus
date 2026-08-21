# Iris federation runtime reference (Pixel 7 Pro / 9a, Podroid guest)

Condensed from the 2026-07-16 debugging session. Companion to the
"Runtime: accessing the live Podroid guest" + "Iris federation triage"
sections in SKILL.md.

## Guest access (how Claude actually did it)
- App terminal tab in Podroid app = `podroid:~#` inside crosvm guest. RELIABLE.
- `adb shell input text` = FRAGILE. Real spaces, no `%s`, no `$()`/`|`/`>`.
- SSH :2222 = key-only, host `~/.ssh/*` are NOT accepted. Skip it.
- Host-side verify without vision: `adb forward tcp:9091 tcp:9091` then
  `curl 127.0.0.1:9091/api/status`.

## Endpoint map (iris gateway on guest :9091)
- `/api/status`          -> 200, open. Returns `gateway_id`, `identities`,
                           `federation_peers`, `dlm_connected`.
- `/api/identity/create` -> 200, open (PUBLIC_POSTS). Bootstrap identity.
- `/api/auth/challenge`  -> 200, open. Returns nonce (300s TTL).
- `/api/auth/login`      -> 200, open. Sign (nonce ISO-ts) raw r s ECDSA-SHA256
                           -> `X-Session-Token`.
- `/api/config|relay|peers|handshake` -> **401** (session-gated). App-only.
- POST `/api/federation/relay-circuit` -> 400 "dest_gateway + envelope required"
                           (endpoint live; needs payload).
- `/status`, `/health` (no /api prefix) -> 401. Iris app never calls these.

## Gateway-ID collision bug (THE pairing blocker)
- Shipped `config.yaml` default `dlm_identity: "gateway-1"` -> every install
  gets the same id. Two phones = "cannot pair with self".
- Fix: Podroid PR #1 `fix/unique-gateway-id` (per-install `gw-<12hex>`,
  persisted, survives reboot). Committed + pushed.
- Runtime workaround if image not rebuilt — in guest, per phone, UNIQUE value:
  ```sh
  mkdir -p /etc/iris
  echo 'IRIS_DLM_IDENTITY=gw-'$(tr -d - < /proc/sys/kernel/random/uuid | cut -c1-12) >> /etc/iris/runtime.env
  rc-service iris-pod restart
  ```

## Relay config (makes cross-NAT/LTE pairing possible)
Relay `iris.mazemaker.online` is LIVE (2026-07-16): cloudflared tunnel ->
rootless podman `iris-relay` on mazemaker-prod, circuit role on :9093, REST on
:9091, Kademlia DHT on 8468. Public: /api/status 200, wss /circuit 426 (wants
real upgrade).

Guest `/etc/iris/runtime.env` (per phone, UNIQUE id each):
```sh
IRIS_DLM_IDENTITY=gw-<unique-per-phone>
IRIS_FEDERATION_RELAY_URL=wss://iris.mazemaker.online/circuit
IRIS_FEDERATION_RELAY_HTTP=https://iris.mazemaker.online
```
Then `rc-service iris-pod restart`. After restart, `/api/status` shows the
gateway registered at the relay -> "federated".

## Three states the operator conflates
1. **Pod alive** — /api/status 200. If dead: podman may be down (readonly-db
   bug cascades iris down but hermes stays up independently).
2. **Relay-wired / "federated"** — both gateways registered at relay. NOT peers.
3. **Mutual peer paired** — app added other phone's `iris://gw-XXXX#key` on
   BOTH sides. `federation_peers` goes 0 -> 1. Without this, no conversation.
4. **App can compose federated chat** — KNOWN GAP (2026-07): native iris app
   shows handshake + paste-to-pair, but message-compose against a federated
   peer was not verified working. If paired-but-no-chat, it's app-side.

## Stale-session 401 bug (if handshake screen loops "loading…/401")
SessionManager caches the session token without validating it; no 401 handler,
no force-reregister path. Pod restart wipes in-memory sessions -> permanent 401
until `pm clear dev.itsxactly.iris` + relaunch. Fix lives in iris-android repo
(reauth on 401), not in the guest config.

## Triage checklist for "kein chat geht"
[ ] pod alive (/api/status 200 + gateway_id present)
[ ] unique gateway_id per phone (NOT both "gateway-1")
[ ] runtime.env has relay URL+HTTP, iris-pod restarted
[ ] /api/status shows registered at relay (federated)
[ ] app shows the OTHER phone in peers (mutual add of handshake URL)
[ ] app opens a conversation against that peer (if not -> app gap, dev work)
