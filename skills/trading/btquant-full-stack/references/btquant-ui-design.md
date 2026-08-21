# BTQuant UI Design: Simplicity Through Clarity

## The Problem: 4-Layer Complexity Hidden Behind Simplicity

BTQuant's architecture spans:
- C++ HotSpine writer/reader (µs latency)
- Python Backtrader strategies (16+ strats, 788 .py files)
- AI/Autonomous Agency (strategy evolution)
- MCP data bridge (WebSocket → UI)

Users don't care about layers — they care about **signals** and **trades**.

## The Solution: Three Conceptual Layers

```
[DATA]     → Real-time feeds (HotSpine SHM, 4,381 trades/sec)
[STRATEGY] → Signal generation (detectors, confidence scores)
[EXECUTION] → Trade flow (order status, P&L)
```

## Visual Language

### Colors
- **Background**: `#08090a` (Linear dark) — reduces eye strain
- **Text**: `#f7f8f8` — proper contrast for WCAG AA
- **Accent**: `#7132f5` (Kraken purple) — signals, CTAs
- **Success**: `#27a644` — profitable trades
- **Warning**: `#ffa500` — detector warnings
- **Error**: `#ff4444` — failed states

### Typography
- **Font**: Inter Variable with `cv01, ss03` features
- **Weight 510**: Signature Linear weight (between regular/medium)
- **Mono**: JetBrains Mono for P&L, trade IDs, timestamps
- **Headings**: Negative letter-spacing (-1.056px at 32px)

### Components
- **Cards**: `rgba(255,255,255,0.02)` bg, `1px solid rgba(255,255,255,0.08)` border, 8px radius
- **Buttons**: Purple (`#7132f5`) for primary, ghost (`rgba(255,255,255,0.02)`) for secondary
- **Status dots**: Green=ok, Yellow=warning, Red=error (5 detectors visualization)
- **Confidence bars**: Purple fill, subtle background

## Key Interaction Patterns

### Command Palette (Power Users)
```
Cmd+K or / opens unified search:
→ "Run SMA_Cross on BTC/USDT (24h)" → instant execution
→ "Pause detector: stop_hunt" → immediate toggle
→ "Show agency strategies" → filtered view
```

### Microsecond Feedback Loop
- All actions: `<100ms perceived response`
- Skeleton screens while loading
- Optimistic UI: Show trade as "PENDING" immediately

### Risk Control Overlay
When `max_drawdown_limit` (15%) hits:
```
┌─────────────────────────────────────────┐
│ ⚠️  MAX DRAWDOWN LIMIT (15%) REACHED    │
│ Current DD: 15.3% across 3 strategies   │
│ [Pause All] [Reduce Position] [Analyze]  │
└─────────────────────────────────────────┘
```

### Progressive Disclosure
- **Default**: Signal Matrix with confidence + detector status
- **Expand**: Strategy parameters, indicator values
- **Deep dive**: Evolution fitness history, detector raw output

## Accessibility Requirements

- Tab order: Header → Signal Matrix → Controls → Live Feed
- ARIA labels: "Signal: BTC-USDT LONG, confidence 87 percentage"
- Contrast ratio > 15:1 for #f7f8f8 on #08090a
- Keyboard shortcuts:
  - `Space` - pause/resume selected strategy
  - `E` - execute signal
  - `R` - refresh feed
  - `/` - open command palette

## Implementation Notes

### Frontend Stack
- React + TypeScript (strong typing for financial data)
- WebSocket connection to `/ws` endpoint
- TailwindCSS with custom theme (Linear dark + Kraken purple)
- Recharts for equity curves

### Backend Bridge
- FastAPI WebSocket at `/ws`
- Connects to HotSpine reader lib
- Proxies to CCXTBroker for trades
- Serves QuantStats reports at `/reports`

### Validation Checklist (from flawless-ui-ux)
- [ ] All interactive elements have clear hover/focus/active states
- [ ] Color contrast meets WCAG AA (4.5:1)
- [ ] Touch targets minimum 44×44 pixels
- [ ] Keyboard navigation works logically and complete
- [ ] Screen reader announces all signals
- [ ] Loading states shown immediately (skeleton screens)
- [ ] Error states provide actionable recovery
- [ ] 100ms target met for all user actions
- [ ] Offline queue syncs trades when connection restored

---

*Generated: Session combining flawless-ui-ux-backend-design-principles with BTQuant architecture audit.*