# BTQuant v0.0.2 — Architecture Reference Map

**Generated:** 2026-05-25 from full codebase deep-dive.
**Branch:** `0.0.2` (34 branches total, active on `0.0.2`)
**Size:** 7.1 GB (788 Python, ~39K C++, 4.2K JSON, 951 Markdown)

## 1. Data Flow (Wire → Strategy → Order)

```
Internet (Binance/OKX/Bybit WS)
  ↓
[C++ CCAPI] → WebSocket Streams
  ↓
[C++ HotSpine Writer] → /dev/shm/BTQ... Shared Memory
  ↓                          ↓                    ↓
[C++ Detectors]     [Python HotSpineStore]   [MsSQL BigBrainCentral]
(stop hunt,          → OHLCV Feeds             (canonical storage,
 spoofing, etc.)     → Strategy.next()          audit trail)
  ↓
Telegram/Discord Alerts
```

## 2. Layer Architecture

### Layer 1: C++ Performance
| Component | Path | Role |
|-----------|------|------|
| CCAPI | `dependencies/ccapi/` (submodule) | Exchange WS for Binance, OKX, Bybit, Coinbase, Kraken |
| Manipulation Detectors | `tests/new/` | 5 parallel detectors (stop hunt, spoofing, whale frontrun, liquidity imbalance, spread arb) |
| BTQ_Render_Engine | `dependencies/BTQ_Render_Engine/` (submodule, ~39K .cpp/.hpp) | Vulkan dashboard — footprint panel, watchlist, microstructure renderer, correlation heatmap, performance monitor |
| HotSpine Library | `hotspine/libhotspine_reader.so` (433KB) | Lock-free shared memory reader bridge |

### Layer 2: Python Backtrader Fork
| Component | Path | Lines | Role |
|-----------|------|-------|------|
| Engine | `dependencies/backtrader/cerebro.py` | 1,712 | Modified backtrader Cerebro (live mode, preload, runonce) |
| Broker Base | `dependencies/backtrader/broker.py` | 168 | BrokerBase with commission info, GPL |
| Strategy Base | `dependencies/backtrader/strategies/base.py` | 1,401 | BaseStrategy with DCA, SL/TP, cooldown, alerts, TransparencyPatch |
| CCXT Config | `dependencies/backtrader/ccxt_config.py` | 96 | Loads API keys from venv ccxt/ directory + env vars BTQ_{EXCHANGE}_* |

### Layer 3: AI/ML
| Component | Path | Lines | Role |
|-----------|------|-------|------|
| Orchestrator | `autonomous_agency/orchestrator.py` | ~30K | Workflow coordinator |
| Evolution Engine | `autonomous_agency/evolution_engine.py` | ~28K | Genetic strategy optimization |
| Evaluator | `autonomous_agency/evaluator.py` | ~31K | Performance evaluation |
| Neural Pipeline | `neural-memory-neural-trading-pipeline/` | — | Transformer (256d/8h/6L), CNN-LSTM, RL exit agent |

## 3. Exchange Connectors — Status Map

| Exchange | Market Data | Live Trading | Connector Type |
|----------|-------------|-------------|---------------|
| Binance | ✅ C++ WS + Python | ✅ CCXT Broker | ccapi + ccxtbroker |
| OKX | ✅ C++ WS | ❌ | ccapi only |
| Bybit | ✅ C++ WS | ❌ | ccapi only |
| Coinbase | ✅ C++ WS | ❌ | ccapi only |
| Kraken | ✅ C++ WS | ❌ | ccapi only |
| Bitget | ✅ Python | ✅ Store | bitget_store |
| MEXC | ✅ Python | ✅ Store | mexc_store |
| PancakeSwap | ✅ | ✅ Broker | pancakeswap |
| Interactive Brokers | ✅ | ✅ Broker | ibstore/ibbroker |
| OANDA | ✅ | ✅ Broker | oandastore |
| TradingView | ✅ | ❌ | tv_store |
| **Hyperliquid** | **❌** | **❌** | **No connector exists** |
| **dYdX / Vertex** | **❌** | **❌** | **No connector exists** |

**Key finding:** ALL existing connectors are SPOT. No perpetual/futures DEX or CEX connector exists in BTQuant.

## 4. Strategy Catalogue

Pre-built strategies in `dependencies/backtrader/strategies/`:

| Strategy | File Size | Type |
|----------|-----------|------|
| Vumanchu_A + B | ~1.3K/1.9K | Technical |
| MACD_ADX | 62.7K | Large composite strategy |
| QQE_Hullband_VolumeOsc | 14.6K | Technical |
| SineWeightZeroLagQQEVolMesaAdaptive | 9.6K | Ehlers-based |
| NearestNeighbors_RationalQuadraticKernel | 7.4K | ML-based |
| OrderChain + Order_Chain_Kioseff | 8.8K/4.7K | Order management |
| PancakeSwap DCA MM | 3.3K | DEX market making |
| SuperTrend variants | 2.7K/3.2K | Trend following |
| SMA_Cross variants | 1.7K/3.7K | Simple |
| StagedConvergenceStrategy | 3.5K | Mean reversion |
| Aligator_supertrend | 1.9K | Trend |
| ST_RSX_ASI | 3.2K | Technical |
| **TEMPLATE** | 5.8K | Starter template |

## 5. Autonomous Agency Pipeline

```
hypothesis_generator.py → evolution_engine.py → evaluator.py → backtester.py → deployer.py → live_deployer.py
         ↓                      ↓                    ↓              ↓                ↓
  AI generates          Genetic evolution     Performance      Historical       Sandbox live
  strategy ideas        of strategy params    scoring          simulation       deployment
```

- Uses MiMo-V2-Flash via `ai_interface.py`
- Config in `autonomous_agency/config.py` — max $10K exposure, 10% per position, 20% max drawdown
- Live exchange default: binance (spot)
- Sandbox mode: ON by default

## 6. HotSpine Shared Memory

- Named: `/btquant_hotspine` (configurable)
- Library: `hotspine/libhotspine_reader.so` — precompiled C++ .so
- Poll interval: 0.0001s (100 microseconds)
- Python bridge: `backtrader/stores/hotspine_store.py` + `backtrader/feeds/hotspine_feed.py`
- **sys.exit() bug**: ALL test files in `hotspine/` have `sys.exit()` at module level — wrapping in `if __name__` guard is needed before they can run via pytest

## 7. Known Infrastructure Issues

- **No virtual environment** — uses system Python 3.14 directly (`/usr/bin/python3`)
- **mypy not installed** — only `mypy-extensions`
- **hotspin/ directory** — unreadable via `ls` (permissions issue), `find` works
- **pip list JSON** — may have trailing non-JSON text, need `.rfind(']')` workaround
- **CCAPI submodule** — config points to MsSQL at 127.0.0.1 with auto-generated password
- **Perp DEX connectors** — ZERO exist. All trading infrastructure is spot-CCXT based.
- **Hyperliquid auth model** incompatible with BTQuant — uses ECDSA wallet signing, not API key/secret

## 8. Key Configuration Files

| File | What it configures |
|------|-------------------|
| `ccxt_config.py` | Exchange API keys (venv/ccxt/{exchange}.json + env vars) |
| `dependencies/ccapi/.../market_data_collector/config.json` | C++ WS collector (exchanges, symbols, DB) |
| `autonomous_agency/config.py` | Agency parameters, risk limits, live exchange |
| `neural-memory-neural-trading-pipeline/config/config.yaml` | ML model params (transformer, training, features) |
| `dependencies/backtrader/config/trading_config.py` | Backtrader trading config |