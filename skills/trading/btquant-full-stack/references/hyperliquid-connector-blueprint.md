# Hyperliquid Connector — Zwei Optionen

Stand: 2026-05-25

## Option A: Full BTQuant Integration (nicht gebaut)

Siehe SKILL.md Section 12. Dateibaum für alle neuen Files:

```
dependencies/backtrader/
├── brokers/hyperliquid_broker.py    ← EIP-712 signing, order placement
├── stores/hyperliquid_store.py      ← WS streams, info queries  
├── stores/hyperliquid_auth.py       ← ECDSA wallet auth wrapper
├── feeds/hyperliquid_feed.py        ← L2 book → OHLCV
├── config/hl_config.py              ← Wallet config
└── dontcommit.py                    → +hl_wallet_address, +hl_private_key

hotspine/hl_hotspine_bridge.py       ← Python → SHM writer

tests/new/detectors/
├── funding_anomaly.cpp              ← Neu
└── liquidation_cascade.cpp          ← Neu

autonomous_agency/config.py          → +live_exchange="hyperliquid"
```

## Option B: Standalone Python Script (skizziert)

~200 Zeilen, kein BTQuant-Umbau. Direkte HL API via `eth-account` + `requests`.

### Dependencies
```bash
pip install eth-account requests
# eth-account → ECDSA signing (pure python)
# requests → REST calls
```

### Auth

HL verwendet **keine API Keys**. Signatur mit L1-Wallet-EC-Key via EIP-712.

Ablauf pro Order:
1. Baue Action-Dict (OrderAction)
2. Baue EIP-712 TypedData (domain, types, message)
3. Signiere mit `eth_account.sign_typed_data(private_key, domain, types, message)`
4. POST `https://api.hyperliquid.xyz/exchange` mit `{action, signature, nonce}`

### Kernlogik

```
HLSession:
  - __init__(private_key) → Account.from_key(), initial nonce
  - info(payload) → POST /info (query only, no signing)
  - exchange(action) → sign EIP-712 → POST /exchange

Trade-Lifecycle für $25 3x Long HYPE:
1. Check balance (info type=clearinghouse)
2. Set leverage (exchange action=updateLeverage, asset=159(HYPE), leverage=3, isCross=True)
3. Get price (info type=allMids → HYPE)
4. Place buy (exchange action=order, asset=159, buy=True, sz=1.21, p=61770)
5. Monitoring loop (alle 5s): position status, PnL, liquidation price
6. Exit on Ctrl+C or SL/TP (exchange action=order, buy=False)
```

### HYPE Asset Specs (Live 2026-05-25)

| Kennzahl | Wert |
|----------|------|
| Asset Index | 159 |
| Max Leverage | 10x |
| Price | $61.77 |
| Sz Decimals | 2 (size = e-4) |
| Maintenance Leverage | 20x (=2 × maxLev) |
| Liquidation Price (3x) | ~$43.35 |
| Funding Rate | -0.00184%/h (shorts pay longs) |

### Fee-Tabelle (Base Tier)

| | Taker | Maker |
|---|-------|-------|
| Perps | 0.045% | 0.015% |
| Maker Rebate (Tier 3) | — | -0.003% (nur bei >3% maker vol share) |

Negative Maker Fees (Exchange zahlt dir) erst ab Tier 4+ (>$500M 14d Vol) oder Maker Rebate Tier 3.

### Key API Endpoints

```
REST:
  POST https://api.hyperliquid.xyz/info
    allMids, metaAndAssetCtxs, clearinghouse, userNonce, openOrders
  POST https://api.hyperliquid.xyz/exchange
    order, cancel, updateLeverage, updateIsolatedMargin

WebSocket:
  wss://api.hyperliquid.xyz/ws
  Subscriptions: l2Book, trades, allMids, userEvents, funding
```

### Beträge die sich lohnen

| Kapital | Realistisch? |
|---------|-------------|
| $25 3x | ❌ Zum Lernen ok, aber Fees (0.045%) fressen Gewinn |
| $500 3x | ⚠️ Grenzwertig — 19 Trades nötig um Fees wieder reinzuholen |
| $5.000 3x | ✅ Sinnvoll — Fees sind 0.045% = $6.75 pro Roundtrip |
| $50.000 3x | ✅ Tier 2 (>$25M) → Taker 0.035%, Maker 0.008% |
| $500.000+ | ✅ Tier 4 → Maker 0.000%, lohnt MM wirklich |